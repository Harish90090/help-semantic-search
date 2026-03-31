"""
chunk.py — Text-chunking / processing module.

Reads data/raw.json, splits every page's content into 300-500 word chunks,
and writes the results to data/chunks.json.

Each chunk record carries:
    chunk_id   — "<page_id>_<chunk_index>"  (unique across the whole corpus)
    page_id    — integer matching the source page
    title      — page title (repeated on every chunk for display convenience)
    content    — the chunk text
    images     — image URLs inherited from the parent page
    url        — source URL

Run directly:
    python processor/chunk.py
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from utils.helpers import clean_text, ensure_dir, get_logger, load_json, save_json

logger = get_logger(__name__)


# ── Chunker ───────────────────────────────────────────────────────────────────

def split_into_chunks(text: str, min_words: int = 300, max_words: int = 500) -> list[str]:
    """
    Split *text* into segments of *min_words*–*max_words* words.

    Strategy:
    1. Walk through the word list in steps of *max_words*.
    2. For mid-document chunks try to end on a sentence boundary (. ! ?)
       so that embeddings capture complete thoughts.
    3. Skip any chunk shorter than 50 words (usually trailing fragments).
    """
    words = text.split()
    chunks: list[str] = []
    i = 0

    while i < len(words):
        slice_words = words[i: i + max_words]
        chunk_text  = " ".join(slice_words)

        # If we're not at the end and the chunk is long enough,
        # try to trim to the last sentence boundary.
        if i + max_words < len(words) and len(slice_words) >= min_words:
            last_boundary = max(
                chunk_text.rfind(". "),
                chunk_text.rfind("! "),
                chunk_text.rfind("? "),
            )
            if last_boundary > 0:
                chunk_text = chunk_text[: last_boundary + 1]

        words_used = len(chunk_text.split())

        if words_used >= 50:
            chunks.append(chunk_text)
        else:
            # Chunk is too small to be useful (e.g. trimmed boundary fragment).
            # Advance by the full original slice so no words are silently lost.
            words_used = len(slice_words)

        i += words_used

    return chunks


# ── Per-page processor ────────────────────────────────────────────────────────

def process_page(page: dict) -> list[dict]:
    """
    Turn a single raw-page dict into a list of chunk dicts.

    Returns an empty list when the page has no usable content.
    """
    content = clean_text(page.get("content", ""))
    if not content:
        logger.warning("No content for page_id=%s (%s)", page.get("page_id"), page.get("url"))
        return []

    raw_chunks = split_into_chunks(content)
    chunks: list[dict] = []

    for idx, chunk_text in enumerate(raw_chunks):
        chunks.append(
            {
                "chunk_id": f"{page['page_id']}_{idx}",
                "page_id": page["page_id"],
                "title": page.get("title", ""),
                "content": chunk_text,
                "images": page.get("images", []),
                "url": page.get("url", ""),
            }
        )

    return chunks


# ── Batch processor ───────────────────────────────────────────────────────────

def chunk_all(input_path: str, output_path: str) -> list[dict]:
    """
    Load all raw pages from *input_path*, chunk them, and write to *output_path*.
    """
    ensure_dir(os.path.dirname(output_path))

    pages = load_json(input_path)
    if not pages:
        logger.error("No pages found in %s — run scraper first.", input_path)
        return []

    all_chunks: list[dict] = []
    for page in pages:
        page_chunks = process_page(page)
        all_chunks.extend(page_chunks)
        logger.info(
            "  Page %-3s  '%s'  →  %d chunk(s)",
            page.get("page_id"),
            page.get("title", "")[:50],
            len(page_chunks),
        )

    save_json(all_chunks, output_path)
    logger.info("Total chunks written: %d", len(all_chunks))
    return all_chunks


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    chunk_all(
        input_path=os.path.join(_ROOT, "data", "raw.json"),
        output_path=os.path.join(_ROOT, "data", "chunks.json"),
    )
