"""
scrape.py — Web-scraping module.

Reads a CSV of URLs, fetches each page, extracts title / content / images,
and writes the results to data/raw.json.

Run directly:
    python scraper/scrape.py
"""

import csv
import os
import sys
import time
from urllib.parse import urljoin, urlparse

import warnings

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

# help.drb.com serves XHTML — suppress the harmless parser mismatch warning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Make project root importable from any working directory
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from utils.helpers import clean_text, ensure_dir, get_logger, save_json

logger = get_logger(__name__)

# Mimic a real browser so sites don't block us
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ── CSV reader ────────────────────────────────────────────────────────────────

def read_urls_from_csv(csv_path: str) -> list[str]:
    """
    Read URLs from *csv_path*.

    Looks for a column whose header matches url / urls / link / links / webpage
    (case-insensitive). Falls back to the first column if none match.
    Skips rows with missing or non-HTTP values.
    """
    urls: list[str] = []

    if not os.path.exists(csv_path):
        logger.error("CSV file not found: %s", csv_path)
        return urls

    try:
        with open(csv_path, "r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            fieldnames = reader.fieldnames or []

            # Identify the URL column
            url_col = next(
                (c for c in fieldnames if c.lower() in {"url", "urls", "link", "links", "webpage"}),
                fieldnames[0] if fieldnames else None,
            )

            if url_col is None:
                logger.error("CSV has no columns — is the file empty?")
                return urls

            for row in reader:
                raw = (row.get(url_col) or "").strip()
                if raw.startswith("http"):
                    urls.append(raw)
                elif raw:
                    logger.warning("Skipping non-HTTP value: %s", raw)

    except Exception as exc:
        logger.error("Error reading CSV: %s", exc)

    logger.info("Loaded %d valid URL(s) from %s", len(urls), csv_path)
    return urls


# ── Image extraction ──────────────────────────────────────────────────────────

# Path segments and filename patterns that indicate decorative / icon images
_ICON_PATTERNS = (
    "/icons/", "/icon/", "/arrows/", "/btn/", "/buttons/",
    "/sprites/", "/logo/", "/logos/", "/divider/", "/bg/",
    "arrow", "icon-", "-icon", "logo-", "sprite", "bullet",
    "separator", "placeholder", "blank.png", "spacer",
)

def _is_useful_image(url: str) -> bool:
    """Return True only for images that look like real screenshots or photos."""
    import os as _os
    lower = url.lower()
    # Skip icons, arrows and decorative assets
    if any(pat in lower for pat in _ICON_PATTERNS):
        return False
    # Must be a common image format
    if not any(lower.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif")):
        return False
    # Filename (without extension) must contain a hyphen — all real
    # app screenshots on help.drb.com use hyphenated names like
    # "cshr-lg-in.png". Short single-word filenames are icons/diagrams.
    stem = _os.path.splitext(_os.path.basename(lower))[0]
    if "-" not in stem:
        return False
    return True


def _extract_images(soup: BeautifulSoup, base_url: str, limit: int = 5) -> list[str]:
    """Return up to *limit* useful (non-icon) absolute image URLs from the page."""
    images = []
    for img in soup.find_all("img", src=True):
        src = img.get("src", "").strip()
        if not src:
            continue
        abs_url = urljoin(base_url, src)
        if abs_url.startswith("http") and _is_useful_image(abs_url):
            images.append(abs_url)
        if len(images) >= limit:
            break
    return images


# ── Single-page scraper ───────────────────────────────────────────────────────

def scrape_page(url: str, timeout: int = 15) -> dict | None:
    """
    Fetch *url* and return a dict with keys:
        url, title, content, images

    Returns None when the page cannot be fetched or yields no usable text.
    """
    logger.info("Scraping → %s", url)
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=timeout)
        resp.raise_for_status()
    except requests.Timeout:
        logger.error("Timeout: %s", url)
        return None
    except requests.HTTPError as exc:
        logger.error("HTTP %s: %s", exc.response.status_code, url)
        return None
    except requests.RequestException as exc:
        logger.error("Request error for %s: %s", url, exc)
        return None

    soup = BeautifulSoup(resp.content, "lxml")

    # Strip boilerplate elements that add noise to the text
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe", "noscript"]):
        tag.decompose()
    # Remove contact / address sections common in RoboHelp-based sites
    for tag in soup.find_all(class_=["contact-us", "contact", "address", "footer-links", "cookie-widget-holder"]):
        tag.decompose()

    # Title — prefer <title>, fall back to first <h1>
    title = ""
    if soup.title and soup.title.string:
        title = clean_text(soup.title.string)
    elif soup.find("h1"):
        title = clean_text(soup.find("h1").get_text())
    if not title:
        title = urlparse(url).netloc  # last resort

    # Main content — try semantic containers first, fall back to <body>
    container = (
        soup.find("article")
        or soup.find("main")
        or soup.find(id="content")
        or soup.find(id="mw-content-text")       # Wikipedia
        or soup.find(class_="mw-parser-output")  # Wikipedia
        or soup.find(class_="content")
        or soup.body
    )

    paragraphs: list[str] = []
    if container:
        for tag in container.find_all(["p", "h1", "h2", "h3", "h4", "li"]):
            text = clean_text(tag.get_text())
            # Use a low threshold (15 chars) so short steps like
            # "Enter your password." are not silently dropped
            if len(text) > 15:
                paragraphs.append(text)

    content = " ".join(paragraphs)
    if not content:
        logger.warning("Empty content — skipping: %s", url)
        return None

    return {
        "url": url,
        "title": title,
        "content": content,
        "images": _extract_images(soup, url),
    }


# ── Batch scraper ─────────────────────────────────────────────────────────────

def scrape_all(csv_path: str, output_path: str, delay: float = 1.0) -> list[dict]:
    """
    Scrape every URL in *csv_path* and write results to *output_path*.

    *delay* (seconds) is inserted between requests to be a polite crawler.
    """
    ensure_dir(os.path.dirname(output_path))

    urls = read_urls_from_csv(csv_path)
    if not urls:
        logger.error("No valid URLs — nothing to scrape.")
        return []

    results: list[dict] = []
    for i, url in enumerate(urls):
        page = scrape_page(url)
        if page:
            page["page_id"] = i          # stable integer ID for downstream steps
            results.append(page)
        if i < len(urls) - 1:
            time.sleep(delay)            # rate-limit between requests

    save_json(results, output_path)
    logger.info("Done: %d/%d pages scraped successfully.", len(results), len(urls))
    return results


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    scrape_all(
        csv_path=os.path.join(_ROOT, "urls.csv"),
        output_path=os.path.join(_ROOT, "data", "raw.json"),
    )
