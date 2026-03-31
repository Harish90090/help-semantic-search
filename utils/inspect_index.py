"""
inspect_index.py — Human-readable viewer for the FAISS index + metadata.

Run:
    python utils/inspect_index.py
"""

import json
import os
import sys

import faiss
import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

INDEX_PATH    = os.path.join(_ROOT, "embeddings", "faiss_index.bin")
METADATA_PATH = os.path.join(_ROOT, "embeddings", "metadata.json")

# ── Load ──────────────────────────────────────────────────────────────────────
index = faiss.read_index(INDEX_PATH)
with open(METADATA_PATH, encoding="utf-8") as f:
    metadata = json.load(f)

# ── Summary ───────────────────────────────────────────────────────────────────
print("=" * 65)
print("  FAISS INDEX SUMMARY")
print("=" * 65)
print(f"  File          : {INDEX_PATH}")
print(f"  Index type    : {type(index).__name__}")
print(f"  Total vectors : {index.ntotal}")
print(f"  Dimensions    : {index.d}")
print(f"  File size     : {os.path.getsize(INDEX_PATH) / 1024:.1f} KB")
print(f"  Metadata rows : {len(metadata)}")

# ── Per-vector table ──────────────────────────────────────────────────────────
print()
print("=" * 65)
print("  VECTOR STORE — ALL ENTRIES")
print("=" * 65)
print(f"  {'IDX':<5} {'CHUNK_ID':<10} {'PG':<4} {'NORM':<8} {'FIRST 5 DIMS':<45}  TITLE")
print("  " + "-" * 110)

all_vecs = index.reconstruct_n(0, index.ntotal)
for i, vec in enumerate(all_vecs):
    meta  = metadata[i]
    norm  = round(float(np.linalg.norm(vec)), 4)
    first = [round(float(v), 4) for v in vec[:5]]
    title = meta["title"][:45]
    print(f"  {i:<5} {meta['chunk_id']:<10} {meta['page_id']:<4} {norm:<8} {str(first):<45}  {title}")

# ── Detailed view for first entry ─────────────────────────────────────────────
print()
print("=" * 65)
print("  DETAILED VIEW — VECTOR #0")
print("=" * 65)
m   = metadata[0]
vec = all_vecs[0]
print(f"  chunk_id     : {m['chunk_id']}")
print(f"  page_id      : {m['page_id']}")
print(f"  faiss_index  : {m['faiss_index']}")
print(f"  title        : {m['title']}")
print(f"  url          : {m['url']}")
print(f"  images       : {m['images']}")
print(f"  content      : {m['content'][:120]}...")
print()
print(f"  Vector dims  : {len(vec)}")
print(f"  Dims  0-9    : {[round(float(v),6) for v in vec[:10]]}")
print(f"  Dims 500-504 : {[round(float(v),6) for v in vec[500:505]]}")
print(f"  Dims last 5  : {[round(float(v),6) for v in vec[-5:]]}")
print(f"  Min          : {round(float(np.min(vec)),6)}")
print(f"  Max          : {round(float(np.max(vec)),6)}")
print(f"  Norm         : {round(float(np.linalg.norm(vec)),6)}")
print(f"  Non-zero     : {int(np.count_nonzero(vec))} / {len(vec)}")
