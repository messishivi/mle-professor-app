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
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from dotenv import load_dotenv

import pipeline as ingest_pipeline
from consultant import chat_with_consultant, paper_apply_prompt
from database import Paper, PaperDatabase, get_db
from repo import fetch_readme, parse_repo
from pipeline import DEFAULT_CATEGORIES
from trends import (
    STACK_CHOICES,
    draft_decision_memo,
    load_pulse,
    memo_item_key,
    refine_decision_memo,
    refresh_pulse,
    score_against_stack,
    stack_key,
)

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

MAIN_PULSE = "ML Pulse"
MAIN_HUB = "Research Hub"
MAIN_CONSULTANT = "Consultant Terminal"
MAIN_SECTIONS = (MAIN_PULSE, MAIN_HUB, MAIN_CONSULTANT)

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
            if st.button("Apply to my system", key=f"ex-{paper.id}", use_container_width=True):
                queue_apply(store, paper)
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
    st.markdown("**Your stack**")
    st.caption("Pulse ranks papers as High fit / Watch / Skip against this.")
    current_stack = store.get_stack()
    picked = st.multiselect(
        "I work on",
        options=STACK_CHOICES,
        default=[c for c in current_stack if c in STACK_CHOICES],
        key="stack_select",
    )
    if picked != current_stack:
        store.set_stack(picked)
    if picked:
        st.caption(" · ".join(picked))
    if "application_ctx" not in st.session_state:
        st.session_state.application_ctx = store.get_application()
    if "known_papers_ctx" not in st.session_state:
        st.session_state.known_papers_ctx = store.get_known_papers()
    st.text_area(
        "I'm building",
        placeholder="What you ship — e.g. RL post-training, RAG over a corpus, two-tower rec… train/serve split",
        key="application_ctx",
        height=90,
    )
    st.text_input(
        "Papers I already use",
        placeholder="Methods already in the stack, e.g. PPO, DPO",
        key="known_papers_ctx",
    )
    if "repo_url_ctx" not in st.session_state:
        st.session_state.repo_url_ctx = store.get_repo_url()
    st.text_input(
        "Repo (README)",
        placeholder="https://github.com/you/your-service",
        key="repo_url_ctx",
        help="Public GitHub/GitLab README is used in Apply delta. Sent to Groq. No private/company repos.",
    )
    if st.session_state.application_ctx != store.get_application():
        store.set_application(st.session_state.application_ctx)
    if st.session_state.known_papers_ctx != store.get_known_papers():
        store.set_known_papers(st.session_state.known_papers_ctx)
    repo_url = (st.session_state.repo_url_ctx or "").strip()
    if repo_url != store.get_repo_url():
        store.set_repo_url(repo_url)
        store.set_repo_readme("", source_url="")
        if parse_repo(repo_url):
            try:
                with st.spinner("Fetching README…"):
                    doc = fetch_readme(repo_url)
                store.set_repo_readme(doc.content, source_url=doc.readme_url)
            except Exception as exc:
                st.warning(str(exc))
    if store.get_repo_readme():
        st.caption(
            f"README loaded · {len(store.get_repo_readme())} chars · used in Apply delta"
        )
        with st.expander("README preview"):
            st.markdown(store.get_repo_readme()[:1500])
        reload_label = "Reload README"
    elif parse_repo(repo_url):
        st.caption("Paste a public repo, then load the README for Apply delta.")
        reload_label = "Load README"
    else:
        reload_label = ""
        if repo_url:
            st.caption("Need a GitHub or GitLab repo URL.")
    if reload_label and st.button(reload_label, use_container_width=True):
        try:
            with st.spinner("Fetching README…"):
                doc = fetch_readme(store.get_repo_url() or repo_url)
            store.set_repo_readme(doc.content, source_url=doc.readme_url)
            st.rerun()
        except Exception as exc:
            st.warning(str(exc))

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
            with st.spinner("Pulling Hugging Face trending + newest arXiv (last 60 days)…"):
                snap = refresh_pulse(store)
            st.session_state.last_pulse = snap.fetched_at
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    pulse = load_pulse(store)
    if pulse:
        st.caption(
            f"Pulse · {len(pulse.items)} trending + new (last 60 days) · {pulse.fetched_at[:16]}"
        )
    st.caption("Max results below is for **Refresh papers** (your library), not Pulse.")

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
            with st.spinner("Mapping onto your system…" if layer == "apply" else "Consulting…"):
                reply = chat_with_consultant(
                    prompt, history, layer=layer, store=get_store()
                )
            st.markdown(reply.content)
            if reply.sources:
                with st.expander("Checked sources (click these — do not trust an unsourced paper name)"):
                    for src in reply.sources:
                        kind = src.get("kind") or "source"
                        title = src.get("title") or "untitled"
                        url = src.get("url") or ""
                        if url:
                            st.markdown(f"- **{kind}** · [{title}]({url})")
                        else:
                            st.markdown(f"- **{kind}** · {title}")
            st.session_state[key].append({"role": "assistant", "content": reply.content})
        except Exception as exc:
            st.error(str(exc))
            st.session_state[key].append({"role": "assistant", "content": str(exc)})


def render_consultant_terminal() -> None:
    st.subheader("Consultant Terminal")
    if "consultant_layer" not in st.session_state:
        st.session_state.consultant_layer = "apply"
    for layer in ("apply", "explain", "systems"):
        key = _history_key(layer)
        if key not in st.session_state:
            st.session_state[key] = []

    layer_label = st.radio(
        "Layer",
        options=["apply", "explain", "systems"],
        format_func=lambda value: {
            "apply": "1 · Apply to my system",
            "explain": "2 · Plain English",
            "systems": "3 · Systems critic",
        }[value],
        horizontal=True,
        key="consultant_layer",
    )
    if layer_label == "apply":
        st.markdown(
            "<div class='terminal-hint'>"
            "Default · map the paper onto YOUR application (user / item / data / "
            "train / serve / eval): Use / Adapt / Ignore, delta vs papers + repo README, "
            "then an implementation path."
            "</div>",
            unsafe_allow_html=True,
        )
        placeholder = "How do I apply this paper to my system given the papers I already use?"
    elif layer_label == "explain":
        st.markdown(
            "<div class='terminal-hint'>"
            "Short plain-English briefing · cites retrieved links. "
            "Products (e.g. OpenAI Astra) are not swapped for similarly named papers."
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
        "Morning brief: Hugging Face Daily Papers **trending** plus newest arXiv "
        "cs.LG / cs.CL / cs.AI, limited to the last 60 days. "
        "**For my stack** re-ranks that list. Not the library Max results slider."
    )
    snap = load_pulse(store)
    if not snap or not snap.items:
        st.info("No pulse yet. Click **Refresh ML Pulse** in the sidebar.")
        return
    stack = store.get_stack()
    view = st.radio(
        "Show",
        options=["my_stack", "all"],
        format_func=lambda v: "For my stack" if v == "my_stack" else "Everything",
        horizontal=True,
        key="pulse_view",
    )
    ranked = [(score_against_stack(item, stack), i, item) for i, item in enumerate(snap.items)]
    if view == "my_stack" and stack:
        ranked.sort(key=lambda row: (-row[0].score, row[1]))
        ranked = [row for row in ranked if row[0].label != "Skip"]
        if not ranked:
            st.info("Nothing on your stack in this pulse. Switch to Everything, or refresh.")
            return
    st.caption(f"Updated {snap.fetched_at} · {len(ranked)} items")
    for fit, i, item in ranked:
        with st.container(border=True):
            st.markdown(f"**{item.topic}**")
            kind = [fit.label.lower()]
            if item.published_date:
                kind.append(item.published_date[:10])
            if item.source == "hf_daily":
                kind.append("trending")
            elif item.source == "arxiv":
                kind.append("arxiv new")
            if item.paper_id:
                kind.append("paper")
            if item.concept:
                kind.append("concept")
            if item.in_library:
                kind.append("in library")
            st.markdown(
                " ".join(f'<span class="tag">{k}</span>' for k in kind),
                unsafe_allow_html=True,
            )
            st.caption(fit.so_what)
            if item.why:
                st.write(item.why)
            ikey = memo_item_key(item)
            skey = stack_key(stack)
            saved = store.get_memo(ikey, skey)
            if saved:
                memo_verdict = saved["verdict"]
                memo_constraint = saved["constraint_note"]
                memo_so_what = saved["so_what"]
                memo_url = saved.get("paper_url") or item.paper_url
                memo_origin = saved.get("origin") or "heuristic"
            else:
                draft = draft_decision_memo(item, fit, stack)
                memo_verdict = draft.verdict
                memo_constraint = draft.constraint
                memo_so_what = draft.so_what
                memo_url = draft.paper_url
                memo_origin = draft.origin
            st.markdown(
                f"**Decision · {memo_verdict.upper()}**"
                + (f" · _{memo_origin}_" if memo_origin == "groq" else "")
            )
            st.caption(memo_so_what)
            st.caption(f"Constraint: {memo_constraint}")
            if memo_url:
                st.markdown(f"Link: [{memo_url}]({memo_url})")
            cols = st.columns((3, 2, 1.2, 1.4))
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
                    "Apply", key=f"pulse-ex-{i}-{item.paper_id}", use_container_width=True
                ):
                    paper = SimpleNamespace(
                        id=item.paper_id,
                        title=item.paper_title or item.topic,
                        authors="",
                        published_date="",
                        summary_raw=item.abstract or item.why,
                    )
                    queue_apply(store, paper)
            with cols[3]:
                if st.button(
                    "Refine memo",
                    key=f"pulse-memo-{i}-{ikey}",
                    use_container_width=True,
                    disabled=not _api_ready(),
                ):
                    draft = draft_decision_memo(item, fit, stack)
                    refined = refine_decision_memo(item, fit, stack, draft)
                    store.save_memo(ikey, skey, **refined.as_dict())
                    st.rerun()


def queue_apply(store: PaperDatabase, paper: Any) -> None:
    """Run Apply on the Consultant pane; Streamlit tabs cannot be selected in code."""
    st.session_state.consultant_layer = "apply"
    st.session_state.pending_user_message = paper_apply_prompt(
        paper,
        application=store.get_application(),
        known_papers=store.get_known_papers(),
        repo_url=store.get_repo_url(),
    )
    st.session_state.open_consultant = True
    st.rerun()


def _active_section() -> str:
    # Flag must be applied before the section widget is instantiated.
    if st.session_state.pop("open_consultant", False):
        st.session_state.main_section = MAIN_CONSULTANT
    if "main_section" not in st.session_state:
        st.session_state.main_section = MAIN_PULSE
    return st.radio(
        "Section",
        options=list(MAIN_SECTIONS),
        horizontal=True,
        key="main_section",
        label_visibility="collapsed",
    )


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
  <p class="muted">What moved in ML today, the paper, the concept, and whether it fits your stack — with links you can check.</p>
</div>
""",
        unsafe_allow_html=True,
    )

    section = _active_section()
    if section == MAIN_PULSE:
        render_ml_pulse(store)
    elif section == MAIN_HUB:
        render_research_hub(store)
    else:
        render_consultant_terminal()


main()
