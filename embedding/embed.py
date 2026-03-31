"""
embed.py — Embedding generation and FAISS index construction.

For every chunk in data/chunks.json this module:
  1. Calls the Gemini Embedding 2 API (gemini-embedding-002) to get a 768-dim vector.
  2. L2-normalises every vector so that inner-product == cosine similarity.
  3. Adds vectors to a FAISS IndexFlatIP index.
  4. Saves the index to embeddings/faiss_index.bin.
  5. Saves parallel metadata to embeddings/metadata.json.

The position of a vector inside the FAISS index is its *faiss_index* field
in metadata.json (0, 1, 2 …).  When search returns index i, metadata[i]
gives you the full chunk record.

Run directly:
    python embedding/embed.py
"""

import os
import sys
import time

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

# Load .env before any other import that might need the key
from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, ".env"))

import faiss
from google import genai
from google.genai import types

from utils.helpers import ensure_dir, get_logger, load_json, save_json

logger = get_logger(__name__)

# ── API configuration ─────────────────────────────────────────────────────────

_API_KEY = os.getenv("GEMINI_API_KEY", "")
if not _API_KEY or _API_KEY == "your_gemini_api_key_here":
    raise EnvironmentError(
        "GEMINI_API_KEY is not set. Add it to your .env file."
    )

# Initialise the new google-genai client
_client = genai.Client(api_key=_API_KEY)

EMBEDDING_MODEL = "models/gemini-embedding-2-preview"
EMBEDDING_DIM   = 3072  # gemini-embedding-2-preview outputs 3072-dim vectors


# ── Embedding helpers ─────────────────────────────────────────────────────────

def get_embedding(text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float] | None:
    """
    Call the Gemini Embedding 2 API and return a 768-dim list of floats.

    task_type:
        "RETRIEVAL_DOCUMENT" — for corpus chunks at index time
        "RETRIEVAL_QUERY"    — for user queries at search time

    Returns None on failure so callers can skip bad chunks gracefully.
    """
    try:
        # Truncate to stay within the model's token limit
        text = text[:8000]
        response = _client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config=types.EmbedContentConfig(task_type=task_type),
        )
        return response.embeddings[0].values
    except Exception as exc:
        logger.error("Embedding API error: %s", exc)
        return None


def get_query_embedding(query: str) -> list[float] | None:
    """Convenience wrapper — uses RETRIEVAL_QUERY task type for search queries."""
    return get_embedding(query, task_type="RETRIEVAL_QUERY")


# ── FAISS index builder ───────────────────────────────────────────────────────

def build_faiss_index(vectors: list[list[float]]) -> faiss.IndexFlatIP:
    """
    Build and return a FAISS IndexFlatIP (inner-product) index.

    Vectors are L2-normalised before insertion so that inner product == cosine
    similarity (scores in [0, 1] for well-formed text embeddings).
    """
    arr = np.array(vectors, dtype=np.float32)

    # Normalise to unit vectors — makes IP equal to cosine similarity
    faiss.normalize_L2(arr)

    index = faiss.IndexFlatIP(arr.shape[1])
    index.add(arr)

    logger.info("FAISS index built: %d vectors, dim=%d", index.ntotal, arr.shape[1])
    return index


# ── Main pipeline ─────────────────────────────────────────────────────────────

def embed_all(
    chunks_path: str,
    index_path: str,
    metadata_path: str,
    batch_delay: float = 0.5,
) -> None:
    """
    Generate embeddings for every chunk and persist the FAISS index + metadata.

    batch_delay: seconds between API calls to respect rate limits.
    """
    ensure_dir(os.path.dirname(index_path))

    chunks = load_json(chunks_path)
    if not chunks:
        logger.error("No chunks found in %s — run processor/chunk.py first.", chunks_path)
        return

    vectors:  list[list[float]] = []
    metadata: list[dict]        = []

    for i, chunk in enumerate(chunks):
        logger.info("[%d/%d] Embedding chunk %s", i + 1, len(chunks), chunk["chunk_id"])

        # Prepend the title so the embedding captures both topic and body text
        text = f"{chunk['title']} — {chunk['content']}"
        vec  = get_embedding(text)

        if vec is None:
            logger.warning("  Skipped (embedding failed).")
            continue

        # faiss_index == position in the vectors list (built in the same loop)
        metadata.append({
            "chunk_id":    chunk["chunk_id"],
            "page_id":     chunk["page_id"],
            "title":       chunk["title"],
            "content":     chunk["content"],
            "images":      chunk.get("images", []),
            "url":         chunk["url"],
            "faiss_index": len(vectors),
        })
        vectors.append(vec)

        if i < len(chunks) - 1:
            time.sleep(batch_delay)   # polite rate-limiting

    if not vectors:
        logger.error("No embeddings generated. Check your API key and quota.")
        return

    # Save FAISS index
    index = build_faiss_index(vectors)
    faiss.write_index(index, index_path)
    logger.info("FAISS index saved  -> %s", index_path)

    # Save parallel metadata
    save_json(metadata, metadata_path)
    logger.info("Metadata saved     -> %s  (%d entries)", metadata_path, len(metadata))


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    embed_all(
        chunks_path=os.path.join(_ROOT, "data", "chunks.json"),
        index_path=os.path.join(_ROOT, "embeddings", "faiss_index.bin"),
        metadata_path=os.path.join(_ROOT, "embeddings", "metadata.json"),
    )
