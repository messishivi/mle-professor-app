"""MLE Professor — Streamlit entry point.

Sidebar: ArXiv ingest + SQLite stats.
Tabs: Research Hub (papers) and Consultant Terminal (Grok/OpenAI).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from dotenv import load_dotenv

import pipeline as ingest_pipeline
from consultant import chat_with_consultant, paper_explain_prompt
from database import Paper, PaperDatabase, get_db
from pipeline import DEFAULT_CATEGORIES
from trends import load_pulse, refresh_pulse

load_dotenv(ROOT / ".env", override=False)

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,560;9..144,700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: "IBM Plex Sans", sans-serif; }
h1, h2, h3 { font-family: "Fraunces", Georgia, serif !important; letter-spacing: -0.02em; }
.block-container { padding-top: 1.2rem; max-width: 1280px; }
[data-testid="stSidebarNav"] { display: none; }
div[data-testid="stMetric"] {
  background: #141a2e;
  border: 1px solid rgba(212,165,116,0.18);
  border-radius: 14px;
  padding: 10px 14px;
}
.hero {
  background: linear-gradient(135deg, #141a2e 0%, #1b2744 55%, #24324f 100%);
  border: 1px solid rgba(212,165,116,0.22);
  border-radius: 20px;
  padding: 22px 26px 18px;
  margin-bottom: 0.9rem;
}
.hero h1 { font-size: 2.05rem; margin: 0 0 0.15rem 0; }
.muted { color: #9aa3b8; }
.gold { color: #d4a574; }
.tag {
  display: inline-block;
  background: rgba(212,165,116,0.12);
  color: #d4a574;
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 0.75rem;
  margin: 0 6px 6px 0;
}
.mono { font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 0.85rem; }
.terminal-hint {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  color: #9aa3b8;
  font-size: 0.82rem;
  margin-bottom: 0.8rem;
}
</style>
"""

CATEGORY_OPTIONS = [
    "cs.CL",
    "cs.LG",
    "cs.AI",
    "cs.CV",
    "cs.NE",
    "stat.ML",
    "cs.DC",
    "cs.SE",
]


def get_store() -> PaperDatabase:
    # Do not cache the instance. Streamlit's resource cache kept an old
    # PaperDatabase from before pulse methods existed.
    return get_db()


def _api_ready() -> bool:
    return bool(os.getenv("GROQ_API_KEY", "").strip())


def _stats(store: PaperDatabase) -> dict[str, int]:
    papers = store.list_papers()
    unread = sum(1 for p in papers if p.read_status == 0)
    return {"papers": len(papers), "unread": unread, "read": len(papers) - unread}


def _tags(values: list[str]) -> str:
    return " ".join(f'<span class="tag">{v}</span>' for v in values if v)


def render_structured(paper: Paper) -> None:
    data = paper.summary_structured
    if not data:
        st.caption("No structured summary stored for this paper.")
        return
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            st.write(data)
            return
    if not isinstance(data, dict):
        st.json(data)
        return

    categories: list[str] = []
    primary = data.get("primary_category")
    if primary:
        categories.append(str(primary))
    for cat in data.get("categories") or []:
        text = str(cat)
        if text not in categories:
            categories.append(text)
    if categories:
        st.markdown(_tags(categories), unsafe_allow_html=True)

    abs_url = data.get("abs_url") or f"https://arxiv.org/abs/{paper.id}"
    pdf_url = data.get("pdf_url") or f"https://arxiv.org/pdf/{paper.id}.pdf"
    c1, c2, c3 = st.columns(3)
    c1.link_button("Abstract", str(abs_url), use_container_width=True)
    c2.link_button("PDF", str(pdf_url), use_container_width=True)
    doi = data.get("doi")
    if doi:
        c3.markdown(f"<div class='mono'>DOI {doi}</div>", unsafe_allow_html=True)
    else:
        c3.markdown(f"<div class='mono'>arXiv:{paper.id}</div>", unsafe_allow_html=True)

    if data.get("comment"):
        st.caption(data["comment"])
    extra = {
        k: v
        for k, v in data.items()
        if k not in {"categories", "primary_category", "abs_url", "pdf_url", "doi", "comment", "source"}
        and v
    }
    if extra:
        with st.expander("Structured fields"):
            st.json(extra)


def render_paper(store: PaperDatabase, paper: Paper) -> None:
    status = "Read" if paper.read_status else "Unread"
    with st.container(border=True):
        head, action = st.columns((5.2, 1.1))
        with head:
            st.markdown(f"**{paper.title}**")
            meta = " · ".join(
                part
                for part in [
                    f"`{paper.id}`",
                    paper.authors[:110] if paper.authors else "",
                    paper.published_date or "",
                    status,
                ]
                if part
            )
            st.caption(meta)
        with action:
            label = "Mark unread" if paper.read_status else "Mark read"
            if st.button(label, key=f"read-{paper.id}", use_container_width=True):
                store.set_read_status(paper.id, 0 if paper.read_status else 1)
                st.rerun()
            if st.button("Explain", key=f"ex-{paper.id}", use_container_width=True):
                st.session_state.consultant_layer = "explain"
                st.session_state.pending_user_message = paper_explain_prompt(paper)
                st.rerun()
        if paper.summary_raw:
            st.write(paper.summary_raw)
        render_structured(paper)


def run_ingest(store: PaperDatabase, categories: list[str], max_results: int) -> None:
    with st.spinner("Requesting the ArXiv Atom feed…"):
        result = ingest_pipeline.fetch_latest_papers(
            query_categories=categories,
            max_results=max_results,
            db=store,
        )
    st.session_state.last_ingest = {
        "query": result.query,
        "fetched": result.fetched,
        "upserted": result.upserted,
        "skipped": result.skipped,
        "errors": result.errors,
    }


def render_sidebar(store: PaperDatabase) -> None:
    stats = _stats(store)
    st.markdown("### MLE Professor")
    st.caption("Research hub + staff-level systems consultant")
    a, b, c = st.columns(3)
    a.metric("Papers", stats["papers"])
    b.metric("Unread", stats["unread"])
    c.metric("Read", stats["read"])
    st.caption(f"SQLite · `{store.path.name}`")

    st.divider()
    st.markdown("**ArXiv ingest**")
    categories = st.multiselect(
        "Categories",
        options=CATEGORY_OPTIONS,
        default=list(DEFAULT_CATEGORIES),
    )
    max_results = st.slider("Max results", min_value=5, max_value=50, value=20, step=5)
    if st.button("Refresh ML Pulse", use_container_width=True):
        try:
            with st.spinner("Pulling Hugging Face Daily Papers + arXiv ML…"):
                snap = refresh_pulse(store)
            st.session_state.last_pulse = snap.fetched_at
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    pulse = load_pulse(store)
    if pulse:
        st.caption(f"Pulse · {len(pulse.items)} topics · {pulse.fetched_at[:16]}")

    if st.button("Refresh papers", type="primary", use_container_width=True):
        if not categories:
            st.error("Pick at least one category.")
        else:
            try:
                run_ingest(store, categories, max_results)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    last = st.session_state.get("last_ingest")
    if last:
        st.success(
            f"{last['upserted']} saved · {last['fetched']} fetched · {last['skipped']} skipped"
        )
        st.caption(last["query"])
        for err in last.get("errors") or []:
            st.warning(err)

    st.divider()
    if _api_ready():
        model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        st.success(f"Consultant ready · Groq · {model}")
    else:
        st.warning("Set `GROQ_API_KEY` in `.env` for the Consultant Terminal.")


def render_research_hub(store: PaperDatabase) -> None:
    st.subheader("Research Hub")
    st.caption("Papers in `mle_knowledge.db`. Structured Atom fields stay attached to each row.")
    controls = st.columns((2, 1.2, 1))
    query = controls[0].text_input("Filter", placeholder="title, author, abstract…")
    status = controls[1].selectbox("Status", ["All", "Unread", "Read"])
    controls[2].caption(" ")

    read_status: Optional[int]
    if status == "Unread":
        read_status = 0
    elif status == "Read":
        read_status = 1
    else:
        read_status = None

    papers = store.list_papers(read_status=read_status, query=query or "")
    if not papers:
        st.info("No papers yet. Use **Refresh papers** in the sidebar to pull the latest ArXiv Atom feed.")
        return
    st.caption(f"{len(papers)} paper{'s' if len(papers) != 1 else ''}")
    for paper in papers:
        render_paper(store, paper)


def _history_key(layer: str) -> str:
    return f"consultant_history_{layer}"


def _run_consultant_turn(prompt: str, layer: str) -> None:
    key = _history_key(layer)
    history = list(st.session_state[key])
    st.session_state[key].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        if not _api_ready():
            text = "Consultant is offline. Set `GROQ_API_KEY` in `.env`."
            st.error(text)
            st.session_state[key].append({"role": "assistant", "content": text})
            return
        try:
            reply = chat_with_consultant(prompt, history, layer=layer)
            st.markdown(reply.content)
            st.session_state[key].append({"role": "assistant", "content": reply.content})
        except Exception as exc:
            st.error(str(exc))
            st.session_state[key].append({"role": "assistant", "content": str(exc)})


def render_consultant_terminal() -> None:
    st.subheader("Consultant Terminal")
    if "consultant_layer" not in st.session_state:
        st.session_state.consultant_layer = "explain"
    for layer in ("explain", "systems"):
        key = _history_key(layer)
        if key not in st.session_state:
            st.session_state[key] = []

    layer_label = st.radio(
        "Layer",
        options=["explain", "systems"],
        format_func=lambda value: (
            "1 · Plain English (default)"
            if value == "explain"
            else "2 · Systems critic"
        ),
        horizontal=True,
        key="consultant_layer",
    )
    if layer_label == "explain":
        st.markdown(
            "<div class='terminal-hint'>"
            "First layer · short plain-English briefing · problem, method, why it matters. "
            "No FLOPs or HBM unless you switch layers."
            "</div>",
            unsafe_allow_html=True,
        )
        placeholder = "Ask for a short plain-English explanation of a paper or idea."
    else:
        st.markdown(
            "<div class='terminal-hint'>"
            "Second layer · KV cache · HBM · FLOPs/token · TP / PP / DP. "
            "No introductory lectures."
            "</div>",
            unsafe_allow_html=True,
        )
        placeholder = "Sketch a training/serving design. The critic will attack it."

    tools = st.columns((1, 5))
    if tools[0].button("Clear session", use_container_width=True):
        st.session_state[_history_key(layer_label)] = []
        st.rerun()

    for turn in st.session_state[_history_key(layer_label)]:
        with st.chat_message(turn["role"]):
            st.markdown(turn["content"])

    pending = st.session_state.pop("pending_user_message", None)
    typed = st.chat_input(placeholder)
    prompt = pending or typed
    if not prompt:
        return
    _run_consultant_turn(prompt, layer_label)


def render_ml_pulse(store: PaperDatabase) -> None:
    st.subheader("ML Pulse")
    st.caption(
        "Not generic X trends (sports, ads). This is the ML/AI feed: Hugging Face Daily Papers "
        "plus fresh arXiv cs.LG / cs.CL / cs.AI — the same papers the research timeline actually shares. "
        "Each topic is paired with a paper and a concept."
    )
    snap = load_pulse(store)
    if not snap or not snap.items:
        st.info("No pulse yet. Click **Refresh ML Pulse** in the sidebar.")
        return
    st.caption(f"Updated {snap.fetched_at}")
    for i, item in enumerate(snap.items):
        with st.container(border=True):
            st.markdown(f"**{item.topic}**")
            kind = []
            if item.paper_id:
                kind.append("paper")
            if item.concept:
                kind.append("concept")
            st.markdown(
                " ".join(f'<span class="tag">{k}</span>' for k in kind)
                + (
                    ' <span class="tag">in library</span>'
                    if item.in_library
                    else ""
                ),
                unsafe_allow_html=True,
            )
            if item.why:
                st.write(item.why)
            cols = st.columns((3, 2, 1.2))
            with cols[0]:
                if item.paper_id:
                    st.markdown(
                        f"Paper · [{item.paper_title or item.paper_id}]({item.paper_url})  \n"
                        f"`arXiv:{item.paper_id}`"
                    )
                else:
                    st.caption("No single paper pinned to this topic.")
            with cols[1]:
                st.markdown(f"Concept · **{item.concept or '—'}**")
                if item.concept_blurb:
                    st.caption(item.concept_blurb)
            with cols[2]:
                if item.paper_id and st.button(
                    "Explain", key=f"pulse-ex-{i}-{item.paper_id}", use_container_width=True
                ):
                    paper = SimpleNamespace(
                        id=item.paper_id,
                        title=item.paper_title or item.topic,
                        authors="",
                        published_date="",
                        summary_raw=item.abstract or item.why,
                    )
                    st.session_state.consultant_layer = "explain"
                    st.session_state.pending_user_message = paper_explain_prompt(paper)
                    st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="MLE Professor",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(CSS, unsafe_allow_html=True)
    store = get_store()

    with st.sidebar:
        render_sidebar(store)

    st.markdown(
        """
<div class="hero">
  <div class="gold">Personal ML knowledge base</div>
  <h1>MLE Professor</h1>
  <p class="muted">See what ML/AI is moving. Map it to a paper and a concept. Then brief it in plain English.</p>
</div>
""",
        unsafe_allow_html=True,
    )

    pulse_tab, hub, terminal = st.tabs(["ML Pulse", "Research Hub", "Consultant Terminal"])
    with pulse_tab:
        render_ml_pulse(store)
    with hub:
        render_research_hub(store)
    with terminal:
        render_consultant_terminal()


main()
