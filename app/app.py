"""
app.py — Streamlit UI for the semantic search system.

Run with:
    streamlit run app/app.py
"""

import html as _html
import os
import sys

import streamlit as st

# ── Path setup (must happen before project imports) ───────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

# Load .env so the search engine can reach the Gemini API
from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, ".env"))

from search.search import SemanticSearcher


# ── Metadata enrichment helpers ──────────────────────────────────────────────

def _get_system(doc: dict) -> str:
    """Return which product system a document belongs to.
    Uses explicit 'system' field (set during scraping) when present,
    otherwise falls back to URL-pattern detection for legacy records.
    """
    # Explicit field — set by scrape_new_systems.py for TunnelWatch / SiteWatch
    sys = doc.get("system", "")
    if sys in ("TunnelWatch", "SiteWatch"):
        return sys
    # All Patheon sub-systems (Cashier, Kiosk) → "Patheon"
    url = doc.get("url", "")
    cid = doc.get("chunk_id", "")
    if any(x in cid for x in ("igniteiq", "robot")):
        return "Other"   # kept for domain locking but hidden from form
    if any(p in url for p in ("/cashier/", "/kiosk/", "/tunnel/", "/manage/")):
        return "Patheon" if "/cashier/" in url or "/kiosk/" in url else sys or "Patheon"
    return "Patheon"


def _get_topic(doc: dict) -> str:
    """Return a topic label for grouping.
    Uses explicit 'topic' field (set during scraping) when present,
    otherwise falls back to URL-pattern detection for legacy records.
    """
    # Explicit field — set by scrape_new_systems.py
    if doc.get("topic"):
        return doc["topic"]
    url   = doc.get("url", "")
    cid   = doc.get("chunk_id", "")
    title = doc.get("title", "").lower()
    if "igniteiq" in cid:
        return "IgniteIQ"
    if "robot" in cid:
        return "Robotics"
    # URL-based (text_image chunks have structured URLs)
    _url_topic_map = [
        ("/auth/",            "Authentication"),
        ("/cash-drawer/",     "Cash Drawer"),
        ("/gift-cards/",      "Gift Cards"),
        ("/tender/",          "Tender"),
        ("/customers/",       "Customers"),
        ("/edit-void-refund/","Void & Refund"),
        ("/members-lane/",    "Members"),
        ("/diagnostics/",     "Diagnostics"),
        ("/access/",          "Access"),
        ("/sales/",           "Sales"),
    ]
    for pattern, topic in _url_topic_map:
        if pattern in url:
            return topic
    # Title-based fallback (audio/video DRB chunks have no URL)
    if any(w in title for w in ["log in", "log out", "password", "forgot", "employee id"]):
        return "Authentication"
    if "cash drawer" in title:
        return "Cash Drawer"
    if "gift card" in title:
        return "Gift Cards"
    if any(w in title for w in ["void", "refund"]):
        return "Void & Refund"
    if any(w in title for w in ["tender", "credit card"]):
        return "Tender"
    if "customer" in title:
        return "Customers"
    if any(w in title for w in ["rewash", "sale", "alacarte", "lobby"]):
        return "Sales"
    if any(w in title for w in ["kiosk", "gate", "camera", "receipt", "cart", "rfid"]):
        return "Diagnostics"
    return "General"


# ── Content formatter ─────────────────────────────────────────────────────────

def _format_as_points(text: str) -> str:
    """
    Convert scraped content into structured HTML:
      - Intro / context sentences  → paragraph
      - Short unlabelled phrases   → bold subheading
      - Outcome sentences          → indented italic note
      - Action / imperative steps  → numbered ordered list
    """
    import re

    # Verbs that start an action step (imperative mood)
    IMPERATIVE = {
        "log", "select", "click", "enter", "press", "open", "close", "tap",
        "scan", "insert", "remove", "type", "choose", "navigate", "verify",
        "confirm", "check", "uncheck", "enable", "disable", "turn", "set",
        "add", "save", "submit", "cancel", "return", "print", "test",
        "raise", "lower", "view", "change", "record", "ask", "use", "sell",
        "give", "swipe", "sign", "complete", "wait", "accept", "do", "place",
        "pull", "push", "hold", "release", "ensure", "repeat", "proceed",
    }

    raw = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in raw if len(s.strip()) > 8]

    if not sentences:
        return f"<p>{_html.escape(text)}</p>"

    parts = []
    steps: list[str] = []
    intro_written = False

    def flush_steps():
        if steps:
            items = "".join(f"<li>{_html.escape(s)}</li>" for s in steps)
            parts.append(
                "<ol style='padding-left:1.6rem; margin:0.5rem 0 0.9rem; "
                "line-height:2.0; color:#333;'>" + items + "</ol>"
            )
            steps.clear()

    for sentence in sentences:
        words = sentence.split()
        if not words:
            continue
        first = words[0].lower().rstrip(".,;:")

        # Short phrase with no terminal punctuation → subheading
        if sentence[-1] not in ".!?" and len(words) <= 7:
            flush_steps()
            parts.append(
                f"<p style='font-size:0.97rem; font-weight:700; color:#1A4896; "
                f"margin:1.1rem 0 0.25rem;'>{_html.escape(sentence)}</p>"
            )
            continue

        # Outcome / result observation (starts with article or pronoun)
        if first in ("the", "a", "an", "this", "your", "it"):
            flush_steps()
            parts.append(
                f"<p style='margin:0.1rem 0 0.35rem 1.4rem; color:#666; "
                f"font-style:italic; font-size:0.88rem;'>{_html.escape(sentence)}</p>"
            )
            continue

        # First non-action sentence → introductory paragraph
        if not intro_written and first not in IMPERATIVE:
            flush_steps()
            parts.append(
                f"<p style='margin:0 0 0.75rem; color:#444; font-size:0.94rem; "
                f"line-height:1.75;'>{_html.escape(sentence)}</p>"
            )
            intro_written = True
            continue

        # Action step → numbered list
        steps.append(sentence)

    flush_steps()
    return "".join(parts) if parts else f"<p>{_html.escape(text)}</p>"

# ── Page configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Help.DRB Search",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
/* ── Global ── */
[data-testid="stAppViewContainer"] { background: #f5f7fa; color: #1a1a2e; }
[data-testid="stSidebar"]          { background: #ffffff; border-right: 1px solid #e8ecf0; color: #1a1a2e; }
body, p, div, span, label         { color: #1a1a2e; }

/* ── Search input ── */
.stTextInput > div > div > input {
    font-size: 1.05rem;
    padding: 0.7rem 1rem;
    border-radius: 10px;
    border: 2px solid #dde3ed;
    background: #ffffff !important;
    color: #1a1a2e !important;
    caret-color: #1a1a2e !important;
    transition: border-color 0.2s, box-shadow 0.2s;
}
.stTextInput > div > div > input::placeholder {
    color: #aab0bc !important;
    opacity: 1;
}
.stTextInput > div > div > input:focus {
    border-color: #4f8ef7;
    box-shadow: 0 0 0 3px rgba(79,142,247,0.15);
    outline: none;
}

/* ── Result cards ── */
.result-card {
    background: #ffffff;
    border: 1.5px solid #e4e9f2;
    border-radius: 14px;
    padding: 1.1rem 1.4rem;
    margin-bottom: 0.9rem;
    transition: border-color 0.18s, box-shadow 0.18s;
}
.result-card:hover {
    border-color: #4f8ef7;
    box-shadow: 0 4px 18px rgba(79,142,247,0.13);
}
.result-card.selected {
    border-color: #4f8ef7;
    background: #f0f6ff;
    box-shadow: 0 4px 18px rgba(79,142,247,0.22);
}

/* ── Typography inside cards ── */
.card-rank  { font-size: 0.72rem; font-weight: 700; color: #aaa; letter-spacing: 0.06em; text-transform: uppercase; }
.card-title { font-size: 1.05rem; font-weight: 700; color: #1a1a2e; margin: 0.25rem 0 0.45rem; line-height: 1.4; }
.card-snip  { font-size: 0.88rem; color: #555; line-height: 1.65; }
.card-url   { font-size: 0.78rem; color: #4f8ef7; margin-top: 0.55rem; word-break: break-all; }

/* ── Score badge ── */
.badge {
    display: inline-block;
    background: #e6f4ea;
    color: #2a7d35;
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 0.75rem;
    font-weight: 700;
    margin-bottom: 0.3rem;
}

/* ── Detail panel ── */
.detail-panel {
    background: #ffffff;
    border: 1.5px solid #e4e9f2;
    border-radius: 16px;
    padding: 2rem 2.2rem;
}
.detail-title { font-size: 1.45rem; font-weight: 800; color: #1a1a2e; margin-bottom: 0.6rem; }
.detail-url   { font-size: 0.88rem; color: #4f8ef7; margin-bottom: 1.2rem; word-break: break-all; }
.detail-body  { font-size: 0.93rem; color: #333; line-height: 1.85; white-space: pre-wrap; }

/* ── Section labels ── */
.section-label {
    font-size: 0.75rem; font-weight: 700; color: #9aa5b4;
    text-transform: uppercase; letter-spacing: 0.09em;
    margin-bottom: 0.8rem;
}

/* ── Result count line ── */
.result-count { font-size: 0.88rem; color: #666; margin-bottom: 1.2rem; }

/* ── Divider ── */
.hr { height: 1px; background: #e4e9f2; margin: 2rem 0; border: none; }

/* ── Empty state ── */
.empty-state {
    text-align: center; padding: 4rem 1rem; color: #bbb;
}
.empty-state .icon { font-size: 3.5rem; }
.empty-state p { font-size: 1rem; margin-top: 0.8rem; color: #999; }

/* ── Buttons ── */
.stButton > button {
    background: #ffffff !important;
    color: #1a1a2e !important;
    border: 1.5px solid #dde3ed !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}
.stButton > button:hover {
    background: #f0f6ff !important;
    border-color: #4f8ef7 !important;
    color: #1a4896 !important;
}

/* Hide Streamlit chrome */
#MainMenu { visibility: hidden; }
footer     { visibility: hidden; }
header     { visibility: hidden; }
</style>
""",
    unsafe_allow_html=True,
)


# ── Session state defaults ────────────────────────────────────────────────────
def _init_state() -> None:
    defaults = {
        "results":        [],
        "selected_doc":   None,
        "last_query":     "",
        "search_history": [],   # list of past query strings
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()


# ── Cached search engine loader ───────────────────────────────────────────────
@st.cache_resource(show_spinner="Loading search index…", max_entries=1)
def _load_searcher() -> SemanticSearcher | None:
    """
    Instantiate the SemanticSearcher once and cache it for the lifetime of
    the Streamlit process.  Loading the FAISS index is expensive; caching
    keeps subsequent queries fast.

    Returns None (with a visible Streamlit error) on missing index or bad API key,
    so the app degrades gracefully instead of crashing.
    """
    idx  = os.path.join(_ROOT, "embeddings", "faiss_index.bin")
    meta = os.path.join(_ROOT, "embeddings", "metadata.json")
    if not (os.path.exists(idx) and os.path.exists(meta)):
        return None
    try:
        return SemanticSearcher(idx, meta)
    except EnvironmentError as exc:
        st.error(f"**API key error:** {exc}")
        return None
    except Exception as exc:
        st.error(f"**Failed to load search engine:** {exc}")
        return None


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    # Sidebar logo
    _logo_path = os.path.join(_ROOT, "assets", "drb_logo.svg")
    if os.path.exists(_logo_path):
        with open(_logo_path, "r", encoding="utf-8") as _f:
            _svg = _f.read()
        st.markdown(
            f'<div style="padding:0.6rem 0 1.4rem;">'
            f'<div style="display:inline-block;border-radius:10px;overflow:hidden;'
            f'box-shadow:0 2px 10px rgba(26,72,150,0.12);">'
            f'{_svg}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("## ⚙️ Search Settings")
    top_k = st.slider("Results to return", min_value=1, max_value=20, value=5)

    st.markdown("---")

    # ── Recent Search History ─────────────────────────────────────────────────
    st.markdown("## 🕘 Recent Searches")
    history = st.session_state.search_history

    if not history:
        st.caption("No searches yet.")
    else:
        for past_q in reversed(history[-10:]):   # show last 10, newest first
            if st.button(f"🔎  {past_q}", key=f"hist_{past_q}", use_container_width=True):
                st.session_state["_rerun_query"] = past_q
                st.rerun()

    if history:
        st.markdown("")
        if st.button("🗑️  Clear history", use_container_width=True):
            st.session_state.search_history = []
            st.rerun()

    st.markdown("---")
    st.markdown("## 🔽 Filters")

    _ALL_TYPES   = ["text", "text_image", "audio", "video"]
    # Only 3 systems shown in the form
    _ALL_SYSTEMS = ["Patheon", "TunnelWatch", "SiteWatch"]

    # Topics per system (one system selected = only its topics shown)
    _SYSTEM_TOPICS = {
        "Patheon":     ["Authentication", "Cash Drawer", "Sales", "Gift Cards",
                        "Tender", "Customers", "Void & Refund", "Members",
                        "Access", "Diagnostics"],
        "TunnelWatch": ["Queue Management", "Devices", "Retracts"],
        "SiteWatch":   ["Authentication", "Customers", "Employees", "Reports"],
    }

    _TYPE_LABELS = {
        "text":       "📄 Text",
        "text_image": "🖼 Image + Text",
        "audio":      "🎧 Audio",
        "video":      "🎬 Video",
    }

    st.session_state.pop("_reset_filters", False)

    filter_media_types = st.multiselect(
        "File Type",
        options=_ALL_TYPES,
        default=_ALL_TYPES,
        format_func=lambda x: _TYPE_LABELS.get(x, x),
        key="filter_types",
    )

    filter_systems = st.multiselect(
        "System",
        options=_ALL_SYSTEMS,
        default=_ALL_SYSTEMS,
        key="filter_systems",
    )

    # Topics = union of topics from every selected system
    _active_systems = filter_systems if filter_systems else _ALL_SYSTEMS
    _available_topics: list[str] = []
    _seen: set = set()
    for _sys in _active_systems:
        for _t in _SYSTEM_TOPICS.get(_sys, []):
            if _t not in _seen:
                _available_topics.append(_t)
                _seen.add(_t)

    # Key includes selected systems so topic list resets when systems change
    _topic_key = "filter_topics_" + "_".join(sorted(_active_systems))
    filter_topics = st.multiselect(
        "Topic",
        options=_available_topics,
        default=_available_topics,
        key=_topic_key,
    )

    if st.button("↩ Reset Filters", use_container_width=True):
        for _k in list(st.session_state.keys()):
            if _k.startswith("filter_"):
                st.session_state.pop(_k, None)
        st.rerun()


# ── Page header ───────────────────────────────────────────────────────────────
_logo_svg = ""
if os.path.exists(_logo_path):
    with open(_logo_path, "r", encoding="utf-8") as _f:
        _logo_svg = _f.read()

st.markdown(
    f"""
<div style="
    display:flex; align-items:center; justify-content:center; gap:1.2rem;
    padding: 1.8rem 0 0.6rem;
">
  <!-- DRB logo -->
  <div style="
      display:flex; align-items:center;
      box-shadow: 0 4px 20px rgba(26,72,150,0.15);
      border-radius:10px; overflow:hidden;
  ">
    {_logo_svg}
  </div>

  <!-- Title block -->
  <div>
    <h1 style="
        font-size:2.1rem; font-weight:900; color:#1A4896;
        margin:0; letter-spacing:-0.5px; line-height:1.1;
    ">Help.DRB Search</h1>
    <p style="color:#EF5025; font-size:0.9rem; margin:0.25rem 0 0; font-weight:600;">
        Powered by Gemini Embedding 2 &nbsp;·&nbsp; FAISS Vector Search
    </p>
  </div>
</div>
<div style="height:1px; background:linear-gradient(90deg,transparent,#1A4896,#EF5025,transparent); margin-bottom:1.4rem;"></div>
""",
    unsafe_allow_html=True,
)

# ── Pre-fill from history click ───────────────────────────────────────────────
_prefill = st.session_state.pop("_rerun_query", "")

# ── Search bar row ────────────────────────────────────────────────────────────
col_input, col_btn = st.columns([6, 1])

with col_input:
    query_input = st.text_input(
        label="query",
        value=_prefill,
        placeholder='Search help articles e.g. "how to log in" or "reset password"',
        label_visibility="collapsed",
    )

with col_btn:
    search_btn = st.button("Search", type="primary", use_container_width=True)

# ── Load search engine ────────────────────────────────────────────────────────
searcher = _load_searcher()

if searcher is None:
    st.warning(
        "**Search index not found.**  "
        "Run the pipeline first:\n\n"
        "```\n"
        "python scraper/scrape.py\n"
        "python processor/chunk.py\n"
        "python embedding/embed.py\n"
        "```"
    )
    st.stop()

# ── Trigger search ────────────────────────────────────────────────────────────
query = query_input.strip()

MIN_SCORE = 0.48   # absolute floor — anything below is definitely unrelated

if query and (search_btn or query != st.session_state.last_query):
    with st.spinner("Searching…"):
        raw = searcher.search(query, top_k=top_k)
        # Step 1: drop below absolute floor
        above_floor = [r for r in raw if r["score"] >= MIN_SCORE]
        # Step 2: lock to the domain of the top result so systems never mix
        def _domain(chunk_id):
            if "igniteiq"  in chunk_id: return "igniteiq"
            if "robot"     in chunk_id: return "robot"
            if chunk_id.startswith("tunnel"):     return "tunnelwatch"
            if chunk_id.startswith("sitewatch"):  return "sitewatch"
            return "drb"

        if above_floor:
            top_domain = _domain(above_floor[0].get("chunk_id", ""))
            filtered = [r for r in above_floor if _domain(r.get("chunk_id", "")) == top_domain]
        else:
            filtered = []
        st.session_state.results      = filtered
        st.session_state.last_query   = query
        st.session_state.selected_doc = None
        # Save to history (avoid duplicates, keep latest 20)
        history = st.session_state.search_history
        if query not in history:
            history.append(query)
        if len(history) > 20:
            history.pop(0)

# ── Results section ───────────────────────────────────────────────────────────
_raw_results = st.session_state.results

# Apply sidebar filters (instant — no re-query needed)
results = [
    r for r in _raw_results
    if r.get("media_type") in filter_media_types
    and _get_system(r) in filter_systems
    and _get_topic(r) in filter_topics
]

if not _raw_results and not st.session_state.last_query:
    # Landing / empty state
    st.markdown(
        '<div class="empty-state">'
        "<p>Enter a query above to search through your documents.</p></div>",
        unsafe_allow_html=True,
    )
    st.stop()

if not results and st.session_state.last_query:
    if _raw_results:
        st.warning(
            f"**{len(_raw_results)} result(s) found** but hidden by active filters. "
            "Adjust the File Type / System / Topic filters in the sidebar to show them."
        )
    else:
        st.warning("No results found — try a different query or rebuild the index.")
    st.stop()

# ── Result count ──────────────────────────────────────────────────────────────
_filter_note = (
    f" ({len(_raw_results) - len(results)} hidden by filters)" if len(results) < len(_raw_results) else ""
)
st.markdown(
    f'<p class="result-count">Found <strong>{len(results)}</strong> result(s) for '
    f'"<em>{st.session_state.last_query}</em>"{_filter_note}</p>',
    unsafe_allow_html=True,
)

st.markdown('<p class="section-label">Results</p>', unsafe_allow_html=True)

# ── Result cards with inline detail expansion ─────────────────────────────────
for result in results:
    is_selected = (
        st.session_state.selected_doc is not None
        and st.session_state.selected_doc.get("chunk_id") == result["chunk_id"]
    )
    card_cls   = "result-card selected" if is_selected else "result-card"
    raw_snip   = result["content"][:190] + "…" if len(result["content"]) > 190 else result["content"]
    safe_title = _html.escape(result["title"])
    safe_snip  = _html.escape(raw_snip)
    safe_url   = _html.escape(result["url"])
    score_pct  = round(result["score"] * 100, 1)

    has_image = bool(result.get("images"))
    if has_image:
        col_text, col_thumb = st.columns([5, 1])
    else:
        col_text  = st.container()
        col_thumb = None

    with col_text:
        _mtype = result.get("media_type", "text")
        _media_badge = {
            "audio":      '<span style="background:#fff3e0;color:#e65100;border-radius:20px;padding:2px 9px;font-size:0.72rem;font-weight:700;">🎧 AUDIO</span>',
            "video":      '<span style="background:#f3e5f5;color:#6a1b9a;border-radius:20px;padding:2px 9px;font-size:0.72rem;font-weight:700;">🎬 VIDEO</span>',
            "text_image": '<span style="background:#e3f2fd;color:#1565c0;border-radius:20px;padding:2px 9px;font-size:0.72rem;font-weight:700;">🖼 IMAGE+TEXT</span>',
        }.get(_mtype, "")
        _is_igniteiq_media = _mtype in ("audio", "video") and ("igniteiq" in result.get("chunk_id", "") or "robot" in result.get("chunk_id", ""))
        _sys_tag   = _html.escape(_get_system(result))
        _topic_tag = _html.escape(_get_topic(result))
        st.markdown(
            f"""
<div class="{card_cls}">
  <div style="display:flex; align-items:center; gap:0.6rem; flex-wrap:wrap;">
    <span class="card-rank">#{result['rank']}</span>
    <span class="badge">Match {score_pct}%</span>
    {_media_badge}
    <span style="background:#f0f4ff;color:#3949ab;border-radius:20px;padding:2px 9px;font-size:0.72rem;font-weight:700;">⚙ {_sys_tag}</span>
    <span style="background:#f1f8e9;color:#33691e;border-radius:20px;padding:2px 9px;font-size:0.72rem;font-weight:700;"># {_topic_tag}</span>
  </div>
  <div class="card-title">{safe_title}</div>
  {"" if _is_igniteiq_media else f'<div class="card-snip">{safe_snip}</div>'}
  <div class="card-url">🔗 {safe_url}</div>
</div>
""",
            unsafe_allow_html=True,
        )
        btn_label = "▲ Close" if is_selected else "View Details"
        if st.button(btn_label, key=f"view_{result['chunk_id']}"):
            st.session_state.selected_doc = None if is_selected else result
            st.rerun()

    if col_thumb is not None:
        with col_thumb:
            try:
                st.image(result["images"][0], use_container_width=True)
            except Exception:
                pass

    # ── Inline detail panel — shown directly below this card ──────────────────
    if is_selected:
        doc = st.session_state.selected_doc
        d_title = _html.escape(doc["title"])
        d_url   = _html.escape(doc["url"])

        st.markdown(
            f"""
<div class="detail-panel" style="margin-bottom:1rem;">
  <div class="detail-title">{d_title}</div>
  <div class="detail-url">🔗 <a href="{d_url}" target="_blank">{d_url}</a></div>
</div>
""",
            unsafe_allow_html=True,
        )

        media_type = doc.get("media_type", "text")
        media_path = doc.get("media_path")

        # ── Audio player ──────────────────────────────────────────────────────
        _abs_media = os.path.join(_ROOT, media_path) if media_path else None
        if media_type == "audio" and _abs_media and os.path.exists(_abs_media):
            st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
            st.markdown("**🎧 Audio Guide**")
            with open(_abs_media, "rb") as _af:
                st.audio(_af.read(), format="audio/mp3")

        # ── Video player ──────────────────────────────────────────────────────
        elif media_type == "video" and _abs_media and os.path.exists(_abs_media):
            st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
            st.markdown("**🎬 Video Walkthrough**")
            _vid_col, _ = st.columns([2, 1])
            with _vid_col:
                with open(_abs_media, "rb") as _vf:
                    st.video(_vf.read())

        # ── Images (text+image chunks) ────────────────────────────────────────
        else:
            images = doc.get("images", [])
            if images:
                st.markdown('<div style="margin-top:1.4rem;"></div>', unsafe_allow_html=True)
                img_cols = st.columns(min(len(images), 3))
                for i, img_url in enumerate(images[:3]):
                    with img_cols[i]:
                        try:
                            st.image(img_url, use_container_width=True)
                        except Exception:
                            pass
                st.markdown('<div style="margin-bottom:1.2rem;"></div>', unsafe_allow_html=True)

        _is_igniteiq_media = media_type in ("audio", "video") and ("igniteiq" in doc.get("chunk_id", "") or "robot" in doc.get("chunk_id", ""))
        if not _is_igniteiq_media:
            with st.expander("📄 Full Content", expanded=True):
                st.markdown(
                    f'<div class="detail-body">{_format_as_points(doc["content"])}</div>',
                    unsafe_allow_html=True,
                )

        col_meta1, col_meta2, col_meta3 = st.columns(3)
        col_meta1.metric("Relevance", f"{doc['score']:.4f}")
        col_meta2.metric("Chunk ID", doc["chunk_id"])
        col_meta3.metric("Page ID", doc["page_id"])


