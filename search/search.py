"""
search.py — Semantic search engine backed by FAISS.

Query → result flow
───────────────────
1.  User query string arrives at SemanticSearcher.search().
2.  The query is embedded with the *same* Gemini model used at index time,
    but with task_type="RETRIEVAL_QUERY" (optimised for short queries).
3.  The query vector is L2-normalised (matches how corpus vectors were stored).
4.  FAISS searches the IndexFlatIP index for the top-k nearest neighbours.
    Because all vectors are unit-length, the inner product equals cosine
    similarity, so scores are in [0, 1] — higher is more relevant.
5.  FAISS returns (distances, indices).  `indices[i]` is the position of the
    i-th nearest vector in the index, which is identical to `metadata[i]`
    because we added vectors and metadata in the same order.
6.  We look up metadata[index] for each returned index and build a rich
    result dict that the UI can display directly.

Run standalone for quick CLI testing:
    python search/search.py
"""

import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, ".env"))

import faiss

from utils.helpers import get_logger, load_json

logger = get_logger(__name__)


class SemanticSearcher:
    """
    Wraps a FAISS index + metadata store and exposes a single `.search()` method.

    Designed to be instantiated once (e.g. via Streamlit's @st.cache_resource)
    and reused across many queries.
    """

    def __init__(self, index_path: str, metadata_path: str) -> None:
        self.index: faiss.IndexFlatIP | None = None
        self.metadata: list[dict] = []
        self._load_index(index_path)
        self._load_metadata(metadata_path)

        # Import lazily to avoid circular dependency at module load time
        from embedding.embed import get_query_embedding
        self._embed_query = get_query_embedding

    # ── Loaders ───────────────────────────────────────────────────────────────

    def _load_index(self, path: str) -> None:
        if not os.path.exists(path):
            logger.error("FAISS index not found: %s", path)
            return
        self.index = faiss.read_index(path)
        logger.info("FAISS index loaded: %d vectors", self.index.ntotal)

    def _load_metadata(self, path: str) -> None:
        self.metadata = load_json(path)
        logger.info("Metadata loaded: %d chunk records", len(self.metadata))

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def is_ready(self) -> bool:
        """True when both index and metadata are loaded and non-empty."""
        return self.index is not None and bool(self.metadata)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Return up to *top_k* results ranked by cosine similarity.

        Each result dict contains:
            rank, score, chunk_id, page_id, title, content, images, url
        """
        if not self.is_ready:
            logger.error("Searcher not ready — check index and metadata paths.")
            return []

        # Step 1 — embed the query
        query_vec = self._embed_query(query)
        if query_vec is None:
            logger.error("Could not embed query: '%s'", query)
            return []

        # Step 2 — normalise (must match normalisation applied during indexing)
        q_arr = np.array([query_vec], dtype=np.float32)
        faiss.normalize_L2(q_arr)

        # Step 3 — ANN search
        effective_k = min(top_k, self.index.ntotal)
        distances, indices = self.index.search(q_arr, effective_k)

        # Step 4 — map FAISS indices → metadata records
        results: list[dict] = []
        for rank, (dist, idx) in enumerate(zip(distances[0], indices[0]), start=1):
            if idx == -1:               # FAISS sentinel for "no result"
                continue
            if idx >= len(self.metadata):
                logger.warning("FAISS index %d out of metadata bounds", idx)
                continue

            meta = self.metadata[idx]
            results.append(
                {
                    "rank":       rank,
                    "score":      float(dist),
                    "chunk_id":   meta["chunk_id"],
                    "page_id":    meta["page_id"],
                    "title":      meta["title"],
                    "content":    meta["content"],
                    "images":     meta.get("images", []),
                    "url":        meta.get("url", ""),
                    "media_type": meta.get("media_type", "text"),
                    "media_path": meta.get("media_path"),
                }
            )

        logger.info("Query '%s' → %d result(s)", query, len(results))
        return results


# ── Convenience function ──────────────────────────────────────────────────────

def search_documents(
    query: str,
    top_k: int = 5,
    base_dir: str | None = None,
) -> list[dict]:
    """
    One-shot helper: create a searcher, run one query, return results.

    Useful for scripting; the UI uses SemanticSearcher directly so it can
    cache the instance across reruns.
    """
    root = base_dir or _ROOT
    searcher = SemanticSearcher(
        index_path=os.path.join(root, "embeddings", "faiss_index.bin"),
        metadata_path=os.path.join(root, "embeddings", "metadata.json"),
    )
    return searcher.search(query, top_k)


# ── Entry point (CLI demo) ────────────────────────────────────────────────────

if __name__ == "__main__":
    q = input("Enter search query: ").strip()
    if not q:
        print("No query entered.")
        sys.exit(0)

    hits = search_documents(q)
    if not hits:
        print("No results found.")
    else:
        for hit in hits:
            print(f"\n[{hit['rank']}] {hit['title']}  (score: {hit['score']:.4f})")
            print(f"    {hit['content'][:200]}…")
            print(f"    {hit['url']}")
