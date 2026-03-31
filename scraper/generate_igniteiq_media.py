"""
generate_igniteiq_media.py — Synthetic audio + video for IgniteIQ (igniteiq.ai).

Creates 2 audio + 2 video files about IgniteIQ's AI business solutions,
then incrementally embeds them and appends to the existing FAISS index.

Run:
    python scraper/generate_igniteiq_media.py
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

logger = get_logger(__name__)

# ── IgniteIQ content ──────────────────────────────────────────────────────────

IGNITEIQ_AUDIO = [
    {
        "filename": "igniteiq_intro_audio.mp3",
        "title": "IgniteIQ — AI Solutions for Business",
        "text": (
            "Welcome to IgniteIQ. We help businesses unlock the power of artificial intelligence. "
            "At IgniteIQ, our mission is simple: bring practical, scalable AI solutions to organisations "
            "of every size. Whether you are a startup looking to automate your first workflow, or an "
            "enterprise ready to transform your operations end to end, IgniteIQ has the tools and "
            "expertise to get you there. Our platform integrates seamlessly with your existing systems, "
            "so you can start seeing results in days, not months. From intelligent data analysis to "
            "natural language processing and predictive modelling, IgniteIQ covers the full spectrum "
            "of modern AI. Get in touch today and ignite your business with the power of AI."
        ),
    },
    {
        "filename": "igniteiq_usecase_audio.mp3",
        "title": "IgniteIQ — Real Business Use Cases",
        "text": (
            "Let us talk about how IgniteIQ helps real businesses solve real problems. "
            "First, customer support automation. IgniteIQ's conversational AI can handle up to "
            "eighty percent of routine support queries, freeing your team to focus on complex cases. "
            "Second, sales forecasting. Our predictive models analyse historical data and market signals "
            "to give your sales team accurate revenue forecasts every quarter. "
            "Third, document intelligence. Upload contracts, invoices, or reports and IgniteIQ extracts "
            "key information instantly, cutting manual data entry by ninety percent. "
            "Fourth, employee productivity. Our AI assistant integrates with Slack, Teams, and email "
            "to summarise threads, draft replies, and surface relevant information on demand. "
            "IgniteIQ — AI that works as hard as you do."
        ),
    },
]

IGNITEIQ_VIDEO = [
    {
        "filename": "igniteiq_platform_video.mp4",
        "title": "IgniteIQ Platform Overview",
        "slides": [
            ("IgniteIQ", "AI Solutions for Business", "#0a2540"),
            ("What We Do", "We build AI tools that plug into\nyour existing business workflows.", "#1a3a5c"),
            ("Our Platform", "- Natural Language Processing\n- Predictive Analytics\n- Document AI\n- Conversational Agents", "#0a2540"),
            ("Integrations", "Works with Salesforce, HubSpot,\nSlack, Teams, and 50+ more tools.", "#1a3a5c"),
            ("Get Started", "igniteiq.ai  |  Contact us today", "#0a2540"),
        ],
    },
    {
        "filename": "igniteiq_results_video.mp4",
        "title": "IgniteIQ — Measurable Business Results",
        "slides": [
            ("IgniteIQ Results", "AI-Driven Business Outcomes", "#1a0a40"),
            ("80% Less Support Load", "Automate routine queries with\nIgniteIQ Conversational AI.", "#2d1b69"),
            ("90% Faster Data Entry", "Document Intelligence extracts\ndata from any file instantly.", "#1a0a40"),
            ("3x Forecast Accuracy", "Predictive models trained on\nyour own business data.", "#2d1b69"),
            ("Start Today", "igniteiq.ai  —  Ignite Your Business", "#1a0a40"),
        ],
    },
]


# ── Audio generator ───────────────────────────────────────────────────────────

def _generate_audio(items: list[dict], audio_dir: str) -> list[dict]:
    from gtts import gTTS
    chunks = []
    for i, item in enumerate(items):
        out_path = os.path.join(audio_dir, item["filename"])
        tts = gTTS(text=item["text"], lang="en", slow=False)
        tts.save(out_path)
        logger.info("  Audio [%d/%d] generated: %s", i + 1, len(items), item["filename"])
        chunks.append({
            "chunk_id":   f"igniteiq_audio_{i}",
            "page_id":    f"igniteiq_a{i}",
            "title":      item["title"],
            "content":    item["text"],
            "images":     [],
            "url":        "https://igniteiq.ai/",
            "media_type": "audio",
            "media_path": out_path,
        })
    return chunks


# ── Video generator ───────────────────────────────────────────────────────────

def _generate_video(items: list[dict], video_dir: str) -> list[dict]:
    import imageio
    from PIL import Image, ImageDraw, ImageFont
    import textwrap

    W, H = 640, 368
    FPS = 1
    SECONDS_PER_SLIDE = 3
    chunks = []

    for i, item in enumerate(items):
        out_path = os.path.join(video_dir, item["filename"])
        frames = []

        for title, body, bg_hex in item["slides"]:
            # Parse hex color
            bg_hex = bg_hex.lstrip("#")
            bg = tuple(int(bg_hex[j:j+2], 16) for j in (0, 2, 4))

            img = Image.new("RGB", (W, H), color=bg)
            draw = ImageDraw.Draw(img)

            try:
                font_title = ImageFont.truetype("arial.ttf", 42)
                font_body  = ImageFont.truetype("arial.ttf", 24)
            except Exception:
                font_title = ImageFont.load_default()
                font_body  = ImageFont.load_default()

            # Title
            draw.text((W // 2, H // 3), title, font=font_title, fill="#ffffff", anchor="mm")

            # Body (wrapped)
            for li, line in enumerate(body.split("\n")):
                y = H // 2 + li * 32
                draw.text((W // 2, y), line, font=font_body, fill="#ccddff", anchor="mm")

            frame = np.array(img)
            for _ in range(FPS * SECONDS_PER_SLIDE):
                frames.append(frame)

        writer = imageio.get_writer(
            out_path, fps=FPS, codec="libx264",
            output_params=["-pix_fmt", "yuv420p"],
        )
        for frame in frames:
            writer.append_data(frame)
        writer.close()

        content = item["slides"][1][1].replace("\n", " ") + " " + item["slides"][2][1].replace("\n", " ")
        logger.info("  Video [%d/%d] generated (H.264): %s", i + 1, len(items), item["filename"])
        chunks.append({
            "chunk_id":   f"igniteiq_video_{i}",
            "page_id":    f"igniteiq_v{i}",
            "title":      item["title"],
            "content":    content,
            "images":     [],
            "url":        "https://igniteiq.ai/",
            "media_type": "video",
            "media_path": out_path,
        })
    return chunks


# ── Incremental embed + append to FAISS ──────────────────────────────────────

def _incremental_embed(new_chunks: list[dict]) -> None:
    import faiss
    from embedding.embed import get_embedding

    index_path    = os.path.join(_ROOT, "embeddings", "faiss_index.bin")
    metadata_path = os.path.join(_ROOT, "embeddings", "metadata.json")

    # Load existing
    index    = faiss.read_index(index_path)
    metadata = load_json(metadata_path)
    logger.info("Existing index: %d vectors", index.ntotal)

    new_vectors  = []
    new_metadata = []

    for i, chunk in enumerate(new_chunks):
        media_type = chunk["media_type"]
        audio_path = chunk["media_path"] if media_type == "audio" else None
        video_path = chunk["media_path"] if media_type == "video" else None

        logger.info("[%d/%d] (%s) %s", i + 1, len(new_chunks), media_type, chunk["chunk_id"])

        text = f"{chunk['title']} — {chunk['content']}"
        vec  = get_embedding(text, audio_path=audio_path, video_path=video_path)

        if vec is None:
            logger.warning("  Skipped (embedding failed).")
            continue

        rel_path = os.path.relpath(chunk["media_path"], _ROOT).replace(os.sep, "/")

        new_metadata.append({
            "chunk_id":    chunk["chunk_id"],
            "page_id":     chunk["page_id"],
            "title":       chunk["title"],
            "content":     chunk["content"],
            "images":      chunk.get("images", []),
            "url":         chunk.get("url", ""),
            "media_type":  media_type,
            "media_path":  rel_path,
            "faiss_index": index.ntotal + len(new_vectors),
        })
        new_vectors.append(vec)

        if i < len(new_chunks) - 1:
            time.sleep(0.5)

    if not new_vectors:
        logger.error("No new embeddings generated.")
        return

    # Append to FAISS
    arr = np.array(new_vectors, dtype=np.float32)
    faiss.normalize_L2(arr)
    index.add(arr)
    faiss.write_index(index, index_path)
    logger.info("FAISS index updated: %d vectors total", index.ntotal)

    # Append to metadata
    metadata.extend(new_metadata)
    save_json(metadata, metadata_path)
    logger.info("Metadata updated: %d total entries", len(metadata))


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    audio_dir = os.path.join(_ROOT, "assets", "audio")
    video_dir = os.path.join(_ROOT, "assets", "video")
    ensure_dir(audio_dir)
    ensure_dir(video_dir)

    logger.info("Generating IgniteIQ audio files…")
    audio_chunks = _generate_audio(IGNITEIQ_AUDIO, audio_dir)

    logger.info("Generating IgniteIQ video files…")
    video_chunks = _generate_video(IGNITEIQ_VIDEO, video_dir)

    all_new = audio_chunks + video_chunks
    logger.info("Embedding and appending %d new chunks to FAISS…", len(all_new))
    _incremental_embed(all_new)

    logger.info("Done — %d IgniteIQ chunks added (2 audio + 2 video)", len(all_new))
