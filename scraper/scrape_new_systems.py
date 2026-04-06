"""
scrape_new_systems.py — Scrape TunnelWatch and SiteWatch pages from help.drb.com,
chunk them, embed them via Gemini Embedding 2, and append to the existing FAISS index.

Systems added:
  TunnelWatch — /topics/manuals/tunnel/  (14 pages)
  SiteWatch   — /topics/manuals/manage/  (9 pages)

Run:
    python scraper/scrape_new_systems.py
"""

import os
import sys
import time

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, ".env"))

from utils.helpers import ensure_dir, get_logger, load_json, save_json
from scraper.scrape import scrape_page
from processor.chunk import split_into_chunks

logger = get_logger(__name__)

# ── URL lists ─────────────────────────────────────────────────────────────────
# STRICTLY no overlap with existing embedded URLs (Cashier + Kiosk already done)

TUNNELWATCH_URLS = [
    # Queue operations
    "https://help.drb.com/topics/manuals/tunnel/queue/chng-wsh-q-ordr.htm",
    "https://help.drb.com/topics/manuals/tunnel/queue/rmv-vhcl-wsh-q.htm",
    "https://help.drb.com/topics/manuals/tunnel/queue/clr-wash-q.htm",
    "https://help.drb.com/topics/manuals/tunnel/queue/rsnd-vhcl-pstn-1-ovrrd.htm",
    "https://help.drb.com/topics/manuals/tunnel/queue/snd-vhcl.htm",
    "https://help.drb.com/topics/manuals/tunnel/queue/snd-vhcl-any-q-pstn.htm",
    "https://help.drb.com/topics/manuals/tunnel/queue/enbl-dsbl-auto-snd.htm",
    "https://help.drb.com/topics/manuals/tunnel/queue/updt-vhcl-img.htm",
    # Device operations
    "https://help.drb.com/topics/manuals/tunnel/devices/wt-dwn-tnnl.htm",
    "https://help.drb.com/topics/manuals/tunnel/devices/ovrd-dvc.htm",
    # Retract operations
    "https://help.drb.com/topics/manuals/tunnel/retracts/vw-rtrcts-assgnd-vhcl.htm",
    "https://help.drb.com/topics/manuals/tunnel/retracts/add-rtrcts.htm",
    "https://help.drb.com/topics/manuals/tunnel/retracts/remove-rtrcts.htm",
    "https://help.drb.com/topics/manuals/tunnel/retracts/replace-rtrcts.htm",
]

SITEWATCH_URLS = [
    # Authentication
    "https://help.drb.com/topics/manuals/manage/auth/lg-in-pthn-prtl.htm",
    "https://help.drb.com/topics/manuals/manage/auth/lg-out-pthn-prtl.htm",
    # Customer management
    "https://help.drb.com/topics/manuals/manage/customers/add-cstmr.htm",
    "https://help.drb.com/topics/manuals/manage/customers/chng-pln-pymnt-crd-cstmr.htm",
    "https://help.drb.com/topics/manuals/manage/customers/rmv-pymnt-crd-cstmr-prfl.htm",
    # Employee management
    "https://help.drb.com/topics/manuals/manage/employees/look-up-employee-username.htm",
    "https://help.drb.com/topics/manuals/manage/employees/reset-an-employee-password.htm",
    # Reports
    "https://help.drb.com/topics/manuals/manage/reports/vw-bsnss-nsghts.htm",
    "https://help.drb.com/topics/manuals/manage/reports/vw-pgntd-rprts.htm",
]


# ── Topic derivation from URL ─────────────────────────────────────────────────

def _derive_topic(url: str, system: str) -> str:
    if system == "TunnelWatch":
        if "/queue/"    in url: return "Queue Management"
        if "/devices/"  in url: return "Devices"
        if "/retracts/" in url: return "Retracts"
    if system == "SiteWatch":
        if "/auth/"       in url: return "Authentication"
        if "/customers/"  in url: return "Customers"
        if "/employees/"  in url: return "Employees"
        if "/reports/"    in url: return "Reports"
    return "General"


# ── Scrape + chunk one system ─────────────────────────────────────────────────

def _scrape_and_chunk(urls: list[str], system: str, id_prefix: str) -> list[dict]:
    """Scrape each URL, chunk the content, return list of chunk dicts."""
    chunks = []
    page_idx = 0

    for url in urls:
        logger.info("[%s] Scraping %s", system, url)
        page = scrape_page(url)
        if not page:
            logger.warning("  Skipped (scrape failed).")
            time.sleep(1)
            continue

        topic = _derive_topic(url, system)
        raw_chunks = split_into_chunks(page["content"])
        if not raw_chunks:
            # Keep short pages as a single chunk
            raw_chunks = [page["content"]]

        for chunk_idx, chunk_text in enumerate(raw_chunks):
            chunks.append({
                "chunk_id":  f"{id_prefix}_{page_idx}_{chunk_idx}",
                "page_id":   f"{id_prefix}_{page_idx}",
                "title":     page["title"],
                "content":   chunk_text,
                "images":    page.get("images", []),
                "url":       url,
                "media_type": "text_image" if page.get("images") else "text",
                "media_path": None,
                "system":    system,
                "topic":     topic,
            })

        logger.info("  → %d chunk(s) | topic: %s | images: %d",
                    len(raw_chunks), topic, len(page.get("images", [])))
        page_idx += 1
        time.sleep(1.0)   # polite crawl delay

    return chunks


# ── Incremental embed + append to FAISS ──────────────────────────────────────

def _embed_and_append(new_chunks: list[dict]) -> None:
    import faiss
    from embedding.embed import get_embedding

    index_path    = os.path.join(_ROOT, "embeddings", "faiss_index.bin")
    metadata_path = os.path.join(_ROOT, "embeddings", "metadata.json")

    index    = faiss.read_index(index_path)
    metadata = load_json(metadata_path)
    logger.info("Existing index: %d vectors", index.ntotal)

    new_vectors  = []
    new_metadata = []

    for i, chunk in enumerate(new_chunks):
        image_url = chunk["images"][0] if chunk.get("images") else None
        logger.info("[%d/%d] (%s | %s) %s",
                    i + 1, len(new_chunks),
                    chunk["system"], chunk["topic"], chunk["chunk_id"])

        text = f"{chunk['title']} — {chunk['content']}"
        vec  = get_embedding(text, image_url=image_url)

        if vec is None:
            logger.warning("  Skipped (embedding failed).")
            continue

        media_type = "text_image" if image_url else "text"

        new_metadata.append({
            "chunk_id":   chunk["chunk_id"],
            "page_id":    chunk["page_id"],
            "title":      chunk["title"],
            "content":    chunk["content"],
            "images":     chunk.get("images", []),
            "url":        chunk["url"],
            "media_type": media_type,
            "media_path": None,
            "system":     chunk["system"],
            "topic":      chunk["topic"],
            "faiss_index": index.ntotal + len(new_vectors),
        })
        new_vectors.append(vec)

        if i < len(new_chunks) - 1:
            time.sleep(0.5)

    if not new_vectors:
        logger.error("No embeddings generated.")
        return

    arr = np.array(new_vectors, dtype=np.float32)
    faiss.normalize_L2(arr)
    index.add(arr)
    faiss.write_index(index, index_path)
    logger.info("FAISS index updated: %d vectors total", index.ntotal)

    metadata.extend(new_metadata)
    save_json(metadata, metadata_path)
    logger.info("Metadata updated: %d total entries", len(metadata))


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Step 1 — Scraping TunnelWatch pages (%d URLs)", len(TUNNELWATCH_URLS))
    tunnel_chunks = _scrape_and_chunk(TUNNELWATCH_URLS, "TunnelWatch", "tunnel")

    logger.info("=" * 60)
    logger.info("Step 2 — Scraping SiteWatch pages (%d URLs)", len(SITEWATCH_URLS))
    sitewatch_chunks = _scrape_and_chunk(SITEWATCH_URLS, "SiteWatch", "sitewatch")

    all_new = tunnel_chunks + sitewatch_chunks
    logger.info("=" * 60)
    logger.info("Step 3 — Embedding %d new chunks and appending to FAISS…", len(all_new))
    _embed_and_append(all_new)

    logger.info("=" * 60)
    logger.info(
        "Done — %d TunnelWatch + %d SiteWatch chunks added.",
        len(tunnel_chunks), len(sitewatch_chunks),
    )
