"""
helpers.py — Shared utility functions used across all modules.

Provides: JSON I/O, text cleaning, directory creation, and logging setup.
"""

import json
import os
import re
import logging


def get_logger(name: str) -> logging.Logger:
    """Return a consistently configured logger for any module."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger(name)


logger = get_logger(__name__)


# ── JSON helpers ──────────────────────────────────────────────────────────────

def load_json(filepath: str) -> list | dict:
    """Load and return JSON data from *filepath*. Returns [] on any error."""
    if not os.path.exists(filepath):
        logger.warning("File not found: %s", filepath)
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON in %s: %s", filepath, exc)
        return []


def save_json(data: list | dict, filepath: str) -> None:
    """Serialize *data* to *filepath*, creating parent directories as needed."""
    ensure_dir(os.path.dirname(filepath))
    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    count = len(data) if isinstance(data, (list, dict)) else "?"
    logger.info("Saved %s items → %s", count, filepath)


# ── Text helpers ──────────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """
    Normalize whitespace and strip leading/trailing space.

    Does NOT remove punctuation so sentences stay readable for embeddings.
    """
    if not text:
        return ""
    # Collapse all whitespace sequences (tabs, newlines, multiple spaces) to a single space
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ── Filesystem helpers ────────────────────────────────────────────────────────

def ensure_dir(path: str) -> None:
    """Create *path* and any missing parents. Safe to call on existing dirs."""
    if path:
        os.makedirs(path, exist_ok=True)
