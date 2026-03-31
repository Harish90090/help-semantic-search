"""
embed.py — True multimodal embedding pipeline using Gemini Embedding 2.

For every chunk (text, text+image, audio, video) this module:
  1. Calls Gemini Embedding 2 with the appropriate modality mix:
       text-only       → text string
       text + image    → [image bytes, text] (multimodal)
       audio           → [audio bytes, text] (multimodal)
       video           → [video bytes, text] (multimodal)
  2. L2-normalises every vector → inner product == cosine similarity.
  3. Adds vectors to a FAISS IndexFlatIP index.
  4. Saves index  → embeddings/faiss_index.bin
  5. Saves metadata → embeddings/metadata.json

Run:
    python embedding/embed.py
"""

import os
import sys
import time

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, ".env"))

import faiss
import requests as _req
from google import genai
from google.genai import types

from utils.helpers import ensure_dir, get_logger, load_json, save_json

logger = get_logger(__name__)

# ── API configuration ─────────────────────────────────────────────────────────

_API_KEY = os.getenv("GEMINI_API_KEY", "")
if not _API_KEY or _API_KEY == "your_gemini_api_key_here":
    raise EnvironmentError("GEMINI_API_KEY is not set. Add it to your .env file.")

_client = genai.Client(api_key=_API_KEY)

EMBEDDING_MODEL = "models/gemini-embedding-2-preview"
EMBEDDING_DIM   = 3072


# ── Image download helper ─────────────────────────────────────────────────────

def _fetch_image(url: str) -> tuple[bytes, str] | tuple[None, None]:
    """Download image bytes and return (bytes, mime_type) or (None, None)."""
    try:
        resp = _req.get(url, timeout=10)
        resp.raise_for_status()
        ext  = url.lower().rsplit(".", 1)[-1]
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                "png": "image/png",  "webp": "image/webp"}.get(ext, "image/png")
        return resp.content, mime
    except Exception as exc:
        logger.warning("  Could not fetch image %s: %s", url, exc)
        return None, None


# ── Core embedding function ───────────────────────────────────────────────────

def get_embedding(
    text: str,
    image_url:   str | None = None,
    audio_path:  str | None = None,
    video_path:  str | None = None,
    task_type:   str        = "RETRIEVAL_DOCUMENT",
) -> list[float] | None:
    """
    Embed content using Gemini Embedding 2.

    Builds a multimodal Content object when media is provided:
      image_url   → downloads image bytes, prepends as Part
      audio_path  → loads MP3 bytes, prepends as Part
      video_path  → loads MP4 bytes, prepends as Part (short clips only)

    Falls back to text-only if media bytes cannot be loaded.
    Returns None on unrecoverable API error.
    """
    text = text[:8000]
    parts: list = []

    # ── Image ─────────────────────────────────────────────────────────────────
    if image_url:
        img_bytes, mime = _fetch_image(image_url)
        if img_bytes:
            parts.append(
                types.Part(inline_data=types.Blob(mime_type=mime, data=img_bytes))
            )
            logger.debug("  + image (%d bytes)", len(img_bytes))

    # ── Audio ─────────────────────────────────────────────────────────────────
    if audio_path and os.path.exists(audio_path):
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
        parts.append(
            types.Part(inline_data=types.Blob(mime_type="audio/mp3", data=audio_bytes))
        )
        logger.debug("  + audio (%d bytes)", len(audio_bytes))

    # ── Video ─────────────────────────────────────────────────────────────────
    if video_path and os.path.exists(video_path):
        with open(video_path, "rb") as f:
            video_bytes = f.read()
        parts.append(
            types.Part(inline_data=types.Blob(mime_type="video/mp4", data=video_bytes))
        )
        logger.debug("  + video (%d bytes)", len(video_bytes))

    # ── Text (always appended last) ───────────────────────────────────────────
    parts.append(types.Part(text=text))

    try:
        if len(parts) == 1:
            # Text-only — simpler API path
            response = _client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=text,
                config=types.EmbedContentConfig(task_type=task_type),
            )
        else:
            # Multimodal — Content with multiple Parts
            response = _client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=types.Content(parts=parts),
                config=types.EmbedContentConfig(task_type=task_type),
            )
        return response.embeddings[0].values

    except Exception as exc:
        logger.error("  Embedding API error: %s", exc)
        if len(parts) > 1:
            # Fall back to text-only
            logger.warning("  Retrying as text-only…")
            try:
                response = _client.models.embed_content(
                    model=EMBEDDING_MODEL,
                    contents=text,
                    config=types.EmbedContentConfig(task_type=task_type),
                )
                return response.embeddings[0].values
            except Exception as exc2:
                logger.error("  Text-only fallback also failed: %s", exc2)
        return None


def get_query_embedding(query: str) -> list[float] | None:
    """Embed a search query (text-only, RETRIEVAL_QUERY task type)."""
    return get_embedding(query, task_type="RETRIEVAL_QUERY")


# ── FAISS builder ─────────────────────────────────────────────────────────────

def build_faiss_index(vectors: list[list[float]]) -> faiss.IndexFlatIP:
    arr = np.array(vectors, dtype=np.float32)
    faiss.normalize_L2(arr)
    index = faiss.IndexFlatIP(arr.shape[1])
    index.add(arr)
    logger.info("FAISS index built: %d vectors, dim=%d", index.ntotal, arr.shape[1])
    return index


# ── Main pipeline ─────────────────────────────────────────────────────────────

def embed_all(
    chunks_path:       str,
    media_chunks_path: str,
    index_path:        str,
    metadata_path:     str,
    batch_delay:       float = 0.5,
) -> None:
    ensure_dir(os.path.dirname(index_path))

    # Load text chunks
    text_chunks  = load_json(chunks_path)      or []
    # Load media chunks (audio + video)
    media_chunks = load_json(media_chunks_path) if os.path.exists(media_chunks_path) else []

    all_chunks = text_chunks + media_chunks
    if not all_chunks:
        logger.error("No chunks found — run scraper and processor first.")
        return

    logger.info(
        "Embedding %d chunks: %d text/image + %d media (audio/video)",
        len(all_chunks), len(text_chunks), len(media_chunks),
    )

    vectors:  list[list[float]] = []
    metadata: list[dict]        = []

    for i, chunk in enumerate(all_chunks):
        media_type  = chunk.get("media_type", "text")
        audio_path  = chunk.get("media_path") if media_type == "audio" else None
        video_path  = chunk.get("media_path") if media_type == "video" else None

        # For text chunks pick the first image (if any)
        image_url = None
        if media_type in ("text", "text_image", None):
            images = chunk.get("images", [])
            if images:
                image_url   = images[0]
                media_type  = "text_image"
            else:
                media_type  = "text"

        logger.info(
            "[%d/%d] (%s) %s",
            i + 1, len(all_chunks), media_type, chunk["chunk_id"],
        )

        text = f"{chunk['title']} — {chunk['content']}"

        vec = get_embedding(
            text,
            image_url  = image_url,
            audio_path = audio_path,
            video_path = video_path,
        )

        if vec is None:
            logger.warning("  Skipped (embedding failed).")
            continue

        metadata.append({
            "chunk_id":   chunk["chunk_id"],
            "page_id":    chunk["page_id"],
            "title":      chunk["title"],
            "content":    chunk["content"],
            "images":     chunk.get("images", []),
            "url":        chunk.get("url", ""),
            "media_type": media_type,
            "media_path": chunk.get("media_path"),
            "faiss_index": len(vectors),
        })
        vectors.append(vec)

        if i < len(all_chunks) - 1:
            time.sleep(batch_delay)

    if not vectors:
        logger.error("No embeddings generated.")
        return

    index = build_faiss_index(vectors)
    faiss.write_index(index, index_path)
    logger.info("FAISS index saved  → %s", index_path)

    save_json(metadata, metadata_path)
    logger.info("Metadata saved     → %s  (%d entries)", metadata_path, len(metadata))


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    embed_all(
        chunks_path=os.path.join(_ROOT, "data",       "chunks.json"),
        media_chunks_path=os.path.join(_ROOT, "data", "media_chunks.json"),
        index_path=os.path.join(_ROOT,   "embeddings", "faiss_index.bin"),
        metadata_path=os.path.join(_ROOT, "embeddings", "metadata.json"),
    )
