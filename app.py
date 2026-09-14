"""MLE Professor — Streamlit entry point.

Sidebar: compact setup summary + ArXiv ingest + SQLite stats.
Main: onboarding wizard (first run), ML Pulse (Saved library is a Pulse view), Consultant Terminal.
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

import demo
import pipeline as ingest_pipeline
import consultant
from consultant import paper_apply_prompt
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
/* ---- cards ---- */
[data-testid="stVerticalBlockBorderWrapper"] {
  transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 30px rgba(0,0,0,.38);
  border-color: rgba(212,165,116,.35);
}
/* ---- hero ---- */
.hero {
  background: linear-gradient(135deg, #141a2e 0%, #1b2744 55%, #24324f 100%);
  border: 1px solid rgba(212,165,116,0.22);
  border-radius: 20px;
  padding: 22px 26px 18px;
  margin-bottom: 0.9rem;
  position: relative;
  overflow: hidden;
  animation: heroIn .5s ease both;
}
.hero::after {
  content: "";
  position: absolute;
  top: -60px; right: -60px;
  width: 220px; height: 220px;
  background: radial-gradient(circle, rgba(212,165,116,.22), transparent 70%);
  pointer-events: none;
}
@keyframes heroIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
.hero h1 { font-size: 2.05rem; margin: 0 0 0.15rem 0; }
.muted { color: #9aa3b8; }
.gold { color: #d4a574; }
/* ---- pills & tags ---- */
.tag {
  display: inline-block;
  background: rgba(212,165,116,0.12);
  color: #d4a574;
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 0.75rem;
  margin: 0 6px 6px 0;
}
.pill {
  display: inline-block;
  border-radius: 999px;
  padding: 3px 12px;
  font-size: 0.75rem;
  font-weight: 600;
  margin: 0 6px 6px 0;
  border: 1px solid transparent;
  white-space: nowrap;
}
.pill-high { background: rgba(52,211,153,.14); color: #34d399; border-color: rgba(52,211,153,.4); }
.pill-watch { background: rgba(251,191,36,.13); color: #fbbf24; border-color: rgba(251,191,36,.4); }
.pill-skip { background: rgba(148,163,184,.12); color: #94a3b8; border-color: rgba(148,163,184,.35); }
.pill-adopt { background: rgba(45,212,191,.14); color: #2dd4bf; border-color: rgba(45,212,191,.4); }
.pill-prototype { background: rgba(96,165,250,.15); color: #60a5fa; border-color: rgba(96,165,250,.4); }
.mono { font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 0.85rem; }
.terminal-hint {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  color: #9aa3b8;
  font-size: 0.82rem;
  margin-bottom: 0.8rem;
}
.so-what {
  border-left: 3px solid #d4a574;
  background: rgba(212,165,116,.06);
  border-radius: 0 10px 10px 0;
  padding: 8px 14px;
  margin: 10px 0 6px 0;
  color: #e8ebf4;
}
/* ---- buttons & inputs ---- */
div.stButton > button[kind="primary"] {
  background: linear-gradient(135deg, #b97f3e, #d4a574);
  border: none;
  color: #171208;
  font-weight: 600;
}
div.stButton > button[kind="primary"]:hover { filter: brightness(1.1); color: #171208; }
div.stButton > button { border-radius: 10px; }
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
  border-color: #d4a574 !important;
  box-shadow: 0 0 0 1px #d4a574;
}
[data-testid="stChatMessage"] {
  border-radius: 16px;
  border: 1px solid rgba(212,165,116,.14);
}
.wizard-card {
  background: #141a2e;
  border: 1px solid rgba(212,165,116,.2);
  border-radius: 20px;
  padding: 28px 32px;
  max-width: 760px;
  margin: 0 auto;
  animation: heroIn .45s ease both;
}
.step-label { color: #d4a574; font-weight: 600; font-size: .85rem; letter-spacing: .06em; text-transform: uppercase; }
.empty-cta { text-align: center; padding: 28px 10px; color: #9aa3b8; }
</style>
"""

MAIN_PULSE = "ML Pulse"
MAIN_CONSULTANT = "Consultant Terminal"
MAIN_SECTIONS = (MAIN_PULSE, MAIN_CONSULTANT)

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

ONBOARDING_KEY = "onboarding_done"

SUGGESTIONS: dict[str, list[str]] = {
    "apply": [
        "How do I apply this paper to my system?",
        "What should I prototype first?",
        "What are the risks of adopting this?",
    ],
    "explain": [
        "Explain this like I'm new to the area",
        "What are the 3 key ideas?",
        "How does this compare to what I already use?",
    ],
    "systems": [
        "Critique my training setup",
        "What breaks at 10x scale?",
        "Estimate the serving cost",
    ],
}


def get_store() -> PaperDatabase:
    # Do not cache the instance. Streamlit's resource cache kept an old
    # PaperDatabase from before pulse methods existed.
    return get_db()


def _api_ready() -> bool:
    # Demo mode: a key pasted into the sidebar (session state only) also counts.
    return bool(demo.effective_groq_key())


def _stats(store: PaperDatabase) -> dict[str, int]:
    papers = store.list_papers()
    unread = sum(1 for p in papers if p.read_status == 0)
    return {"papers": len(papers), "unread": unread, "read": len(papers) - unread}


def _tags(values: list[str]) -> str:
    return " ".join(f'<span class="tag">{v}</span>' for v in values if v)


def _fit_pill(label: str) -> str:
    cls = {"High fit": "pill-high", "Watch": "pill-watch", "Skip": "pill-skip"}.get(label, "pill-skip")
    icon = {"High fit": "🎯", "Watch": "👀", "Skip": "⏭️"}.get(label, "•")
    return f'<span class="pill {cls}">{icon} {label}</span>'


def _verdict_pill(verdict: str) -> str:
    cls = {
        "adopt": "pill-adopt",
        "prototype": "pill-prototype",
        "watch": "pill-watch",
        "skip": "pill-skip",
    }.get(verdict, "pill-skip")
    icon = {"adopt": "✅", "prototype": "🧪", "watch": "👀", "skip": "⏭️"}.get(verdict, "•")
    label = {"adopt": "Adopt", "prototype": "Prototype", "watch": "Watch", "skip": "Skip"}.get(
        verdict, verdict
    )
    return f'<span class="pill {cls}">{icon} {label}</span>'


# ---------------------------------------------------------------- onboarding

def _show_wizard(store: PaperDatabase) -> bool:
    if st.session_state.get("show_onboarding"):
        return True
    if st.session_state.get("onboarding_skipped"):
        return False
    return store.get_setting(ONBOARDING_KEY, "") != "1"


def _init_onboarding_state(store: PaperDatabase) -> None:
    if "onboarding_step" not in st.session_state:
        st.session_state.onboarding_step = 1
    if "ob_stack" not in st.session_state:
        st.session_state.ob_stack = [c for c in store.get_stack() if c in STACK_CHOICES]
    if "ob_application" not in st.session_state:
        st.session_state.ob_application = store.get_application()
    if "ob_known" not in st.session_state:
        st.session_state.ob_known = store.get_known_papers()
    if "ob_repo_url" not in st.session_state:
        st.session_state.ob_repo_url = store.get_repo_url()
    if "ob_categories" not in st.session_state:
        st.session_state.ob_categories = list(DEFAULT_CATEGORIES)


def _finish_onboarding(store: PaperDatabase) -> None:
    store.set_stack(list(st.session_state.get("ob_stack", [])))
    store.set_application(st.session_state.get("ob_application", ""))
    store.set_known_papers(st.session_state.get("ob_known", ""))
    repo_url = (st.session_state.get("ob_repo_url", "") or "").strip()
    if repo_url != store.get_repo_url():
        store.set_repo_url(repo_url)
    store.set_setting(ONBOARDING_KEY, "1")
    cats = st.session_state.get("ob_categories") or list(DEFAULT_CATEGORIES)
    store.set_setting("ingest_categories", ",".join(c for c in cats if c in CATEGORY_OPTIONS))
    st.session_state.show_onboarding = False
    st.session_state.onboarding_step = 1
    st.toast("Setup saved — your consultant now knows your stack 🎉")


def render_onboarding(store: PaperDatabase) -> None:
    _init_onboarding_state(store)
    extra = st.session_state.pop("ob_application_append", None)
    if extra:
        cur = (st.session_state.get("ob_application") or "").strip()
        label = str(extra).strip()
        st.session_state.ob_application = f"{cur}; {label}" if cur else label
    step = st.session_state.onboarding_step

    st.markdown("<div style='height:6vh'></div>", unsafe_allow_html=True)
    with st.container():
        st.markdown("<div class='wizard-card'>", unsafe_allow_html=True)
        st.markdown("<div class='gold'>✨ First-time setup</div>", unsafe_allow_html=True)
        st.markdown("## Make the consultant yours")
        st.caption(
            "The magic of MLE Professor is that it maps papers onto *your* system. "
            "Three quick steps and it stops giving generic answers."
        )
        st.progress(step / 3, text=f"Step {step} of 3")

        if step == 1:
            st.markdown("<div class='step-label'>Step 1 · Your stack</div>", unsafe_allow_html=True)
            st.write("**What do you work on?** Tap to select — Pulse ranks papers against this.")
            selected = set(st.session_state.ob_stack)
            cols = st.columns(4)
            for i, choice in enumerate(STACK_CHOICES):
                with cols[i % 4]:
                    active = choice in selected
                    if st.button(
                        ("✓ " if active else "") + choice,
                        key=f"ob-chip-{i}",
                        use_container_width=True,
                        type="primary" if active else "secondary",
                    ):
                        if active:
                            selected.discard(choice)
                        else:
                            selected.add(choice)
                        st.session_state.ob_stack = sorted(selected)
                        st.rerun()
            st.caption(f"{len(selected)} selected" + ("" if selected else " — pick at least one to continue"))
            nav = st.columns((1, 1))
            if nav[1].button("Continue →", type="primary", use_container_width=True, disabled=not selected):
                st.session_state.onboarding_step = 2
                st.rerun()

        elif step == 2:
            st.markdown("<div class='step-label'>Step 2 · What you're building</div>", unsafe_allow_html=True)
            st.write("**What are you shipping?** One or two sentences is plenty.")
            st.text_area(
                "I'm building",
                key="ob_application",
                height=110,
                placeholder="e.g. RL post-training for a 7B chat model; train on 8×H100, serve with vLLM",
                label_visibility="collapsed",
            )
            st.caption("Need inspiration? Tap one:")
            examples = [
                "💬 RL post-training for a chat model",
                "🔎 RAG over our internal docs",
                "🎯 Two-tower recommender",
            ]
            ex_cols = st.columns(len(examples))
            for col, ex in zip(ex_cols, examples):
                if col.button(ex, key=f"ob-ex-{ex[:8]}", use_container_width=True):
                    label = ex.split(" ", 1)[1] if " " in ex else ex
                    st.session_state.ob_application_append = label
                    st.rerun()
            nav = st.columns((1, 1))
            if nav[0].button("← Back", use_container_width=True):
                st.session_state.onboarding_step = 1
                st.rerun()
            if nav[1].button("Continue →", type="primary", use_container_width=True):
                st.session_state.onboarding_step = 3
                st.rerun()

        else:
            st.markdown("<div class='step-label'>Step 3 · Where it lives</div>", unsafe_allow_html=True)
            st.write("**Link your repo** (optional) — the consultant diffs papers against your README.")
            st.text_input(
                "Repo URL",
                key="ob_repo_url",
                placeholder="https://github.com/you/your-service",
                label_visibility="collapsed",
            )
            repo_url = (st.session_state.ob_repo_url or "").strip()
            if repo_url and parse_repo(repo_url):
                if st.button("📥 Load README", use_container_width=True):
                    try:
                        with st.spinner("Fetching README…"):
                            doc = fetch_readme(repo_url)
                        store.set_repo_url(repo_url)
                        store.set_repo_readme(doc.content, source_url=doc.readme_url)
                        st.toast("README loaded ✅")
                        st.rerun()
                    except Exception as exc:
                        st.warning(str(exc))
                if store.get_repo_readme() and store.get_repo_url() == repo_url:
                    st.caption(f"README loaded · {len(store.get_repo_readme())} chars · used in Apply delta")
            elif repo_url:
                st.caption("Need a GitHub or GitLab repo URL.")
            st.text_input(
                "Papers I already use",
                key="ob_known",
                placeholder="Methods already in the stack, e.g. PPO, DPO",
            )
            st.multiselect("ArXiv categories to watch", options=CATEGORY_OPTIONS, key="ob_categories")
            nav = st.columns((1, 1))
            if nav[0].button("← Back", use_container_width=True):
                st.session_state.onboarding_step = 2
                st.rerun()
            if nav[1].button("✨ Finish setup", type="primary", use_container_width=True):
                _finish_onboarding(store)
                st.rerun()

        st.divider()
        if st.button("Skip for now →", key="ob-skip"):
            st.session_state.onboarding_skipped = True
            st.session_state.show_onboarding = False
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------- sidebar

def do_refresh_pulse(store: PaperDatabase) -> None:
    with st.spinner("Pulling Hugging Face trending + newest arXiv (last 60 days)…"):
        snap = refresh_pulse(store)
    st.session_state.last_pulse = snap.fetched_at
    st.toast(f"Pulse refreshed · {len(snap.items)} items ⚡")


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
    st.toast(f"Ingest done · {result.upserted} saved 📥")


def _load_repo_readme(store: PaperDatabase, repo_url: str) -> None:
    doc = fetch_readme(repo_url)
    store.set_repo_url(repo_url)
    store.set_repo_readme(doc.content, source_url=doc.readme_url)


def render_sidebar(store: PaperDatabase) -> None:
    if demo.demo_enabled():
        demo.render_demo_banner()
    st.markdown("### 🎓 MLE Professor")
    st.caption("Research hub + staff-level systems consultant")
    stats = _stats(store)
    a, b, c = st.columns(3)
    a.metric("Papers", stats["papers"])
    b.metric("Unread", stats["unread"])
    c.metric("Read", stats["read"])
    st.caption(f"SQLite · `{store.path.name}`")

    st.divider()
    st.markdown("**🧬 Your setup**")
    stack = store.get_stack()
    if stack:
        shown = stack[:5]
        extra = len(stack) - len(shown)
        st.markdown(_tags(shown + ([f"+{extra} more"] if extra else [])), unsafe_allow_html=True)
    else:
        st.caption("No stack set yet.")
    app_ctx = store.get_application()
    st.caption("🔨 " + ((app_ctx[:90] + "…") if len(app_ctx) > 90 else app_ctx) if app_ctx else "🔨 Nothing described yet.")
    if store.get_repo_readme():
        st.caption("📦 README linked · used in Apply delta")
    elif store.get_repo_url():
        st.caption("📦 Repo set · README not loaded")
    else:
        st.caption("📦 No repo linked")
    if st.button("⚙️ Edit setup", use_container_width=True):
        st.session_state.show_onboarding = True
        st.session_state.onboarding_step = 1
        st.session_state.onboarding_skipped = False
        st.rerun()

    with st.expander("📥 Paper ingest"):
        saved_cats = [
            c for c in store.get_setting("ingest_categories", "").split(",") if c in CATEGORY_OPTIONS
        ]
        categories = st.multiselect(
            "Categories",
            options=CATEGORY_OPTIONS,
            default=saved_cats or list(DEFAULT_CATEGORIES),
            key="ingest_categories",
        )
        max_results = st.slider("Max results", min_value=5, max_value=50, value=20, step=5, key="ingest_max")
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
            st.success(f"{last['upserted']} saved · {last['fetched']} fetched · {last['skipped']} skipped")
            st.caption(last["query"])
            for err in last.get("errors") or []:
                st.warning(err)

    with st.expander("⚡ Pulse"):
        if st.button("Refresh ML Pulse", use_container_width=True):
            try:
                do_refresh_pulse(store)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        pulse = load_pulse(store)
        if pulse:
            st.caption(f"{len(pulse.items)} items · {pulse.fetched_at[:16]}")
        else:
            st.caption("No pulse yet.")

    st.divider()
    if _api_ready():
        model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        st.success(f"Consultant ready · Groq · {model}")
    elif demo.demo_enabled():
        st.warning("Paste a Groq key above to unlock the Consultant (this session only).")
    else:
        st.warning("Set `GROQ_API_KEY` in `.env` for the Consultant Terminal.")


# ---------------------------------------------------------------- library

def render_structured(paper: Paper) -> None:
    data = paper.summary_structured
    if not data:
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
    c1.link_button("📄 Abstract", str(abs_url), use_container_width=True)
    c2.link_button("📕 PDF", str(pdf_url), use_container_width=True)
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


def render_paper_card(store: PaperDatabase, paper: Paper) -> None:
    status = "Read" if paper.read_status else "Unread"
    status_pill = (
        '<span class="pill pill-adopt">✓ Read</span>'
        if paper.read_status
        else '<span class="pill pill-watch">○ Unread</span>'
    )
    with st.container(border=True):
        st.markdown(f"#### {paper.title}")
        meta = " · ".join(
            part
            for part in [
                f"`{paper.id}`",
                paper.authors[:110] if paper.authors else "",
                paper.published_date or "",
            ]
            if part
        )
        st.markdown(status_pill, unsafe_allow_html=True)
        if meta:
            st.caption(meta)
        if paper.summary_raw:
            with st.expander("Summary", expanded=False):
                st.write(paper.summary_raw)
        render_structured(paper)
        act = st.columns((1.4, 1.6))
        label = "✓ Mark unread" if paper.read_status else "○ Mark read"
        if act[0].button(label, key=f"read-{paper.id}", use_container_width=True):
            store.set_read_status(paper.id, 0 if paper.read_status else 1)
            st.toast("Marked as " + ("unread" if paper.read_status else "read"))
            st.rerun()
        if act[1].button("⚡ Apply to my system", key=f"ex-{paper.id}", use_container_width=True, type="primary"):
            queue_apply(store, paper)


def render_library(store: PaperDatabase) -> None:
    st.subheader("📚 Saved")
    st.caption("Your library. Pulse is the morning brief — this is what you kept.")
    controls = st.columns((2.2, 1.4))
    query = controls[0].text_input("🔎 Filter", placeholder="title, author, abstract…", key="lib_query",
                                    label_visibility="collapsed")
    status = controls[1].radio("Status", ["All", "Unread", "Read"], horizontal=True,
                               key="lib_status", label_visibility="collapsed")

    read_status: Optional[int]
    if status == "Unread":
        read_status = 0
    elif status == "Read":
        read_status = 1
    else:
        read_status = None

    papers = store.list_papers(read_status=read_status, query=query or "")
    if not papers:
        st.markdown(
            "<div class='empty-cta'>📭 Nothing here yet.<br>"
            "Open <b>📥 Paper ingest</b> in the sidebar and hit <b>Refresh papers</b> "
            "to pull ArXiv into your library.</div>",
            unsafe_allow_html=True,
        )
        return
    st.caption(f"{len(papers)} paper{'s' if len(papers) != 1 else ''}")
    for paper in papers:
        render_paper_card(store, paper)


# ---------------------------------------------------------------- pulse

def _memo_for(store: PaperDatabase, item: Any, fit: Any, stack: list[str]) -> tuple[str, str, str, str, str]:
    ikey = memo_item_key(item)
    skey = stack_key(stack)
    saved = store.get_memo(ikey, skey)
    if saved:
        return (
            saved["verdict"],
            saved["constraint_note"],
            saved["so_what"],
            saved.get("paper_url") or item.paper_url,
            saved.get("origin") or "heuristic",
        )
    draft = draft_decision_memo(item, fit, stack)
    return draft.verdict, draft.constraint, draft.so_what, draft.paper_url, draft.origin


def save_pulse_item(store: PaperDatabase, item: Any) -> bool:
    """Save a pulse item into the library. Returns True on success."""
    try:
        store.upsert_paper(
            id=item.paper_id,
            title=item.paper_title or item.topic,
            authors="",
            published_date=item.published_date or None,
            summary_raw=item.abstract or item.why,
        )
    except Exception as exc:
        st.error(f"Couldn't save: {exc}")
        return False
    st.toast(f"Saved to your library 📚")
    return True


def render_pulse_card(store: PaperDatabase, item: Any, fit: Any, stack: list[str], index: int) -> None:
    verdict, constraint, so_what, paper_url, origin = _memo_for(store, item, fit, stack)
    in_lib = bool(item.paper_id and store.get_paper(item.paper_id))

    with st.container(border=True):
        top_l, top_r = st.columns((5, 2))
        with top_l:
            st.markdown(_fit_pill(fit.label) + _verdict_pill(verdict), unsafe_allow_html=True)
        with top_r:
            bits = []
            if item.source == "hf_daily":
                bits.append("🔥 trending")
            elif item.source == "arxiv":
                bits.append("🆕 arXiv")
            if item.published_date:
                bits.append(item.published_date[:10])
            if origin == "groq":
                bits.append("✨ refined")
            st.caption(" · ".join(bits))

        st.markdown(f"#### {item.topic}")
        st.markdown(f'<div class="so-what">{so_what}</div>', unsafe_allow_html=True)

        with st.expander("Why this matters"):
            if item.why:
                st.write(item.why)
            st.caption(f"⚠️ Constraint: {constraint}")
            if item.concept:
                st.markdown(f"**Concept · {item.concept}**")
                if item.concept_blurb:
                    st.caption(item.concept_blurb)
            if item.paper_id:
                st.markdown(
                    f"📄 Paper · [{item.paper_title or item.paper_id}]({item.paper_url})  \n"
                    f"`arXiv:{item.paper_id}`"
                )
            elif paper_url:
                st.markdown(f"🔗 [{paper_url}]({paper_url})")
            else:
                st.caption("No single paper pinned to this topic.")

        acts = st.columns((2.0, 1.5, 1.5))
        with acts[0]:
            if st.button("⚡ Apply to my system", key=f"pulse-ex-{index}", use_container_width=True, type="primary"):
                paper = SimpleNamespace(
                    id=item.paper_id or f"pulse-{index}",
                    title=item.paper_title or item.topic,
                    authors="",
                    published_date=item.published_date or "",
                    summary_raw=item.abstract or item.why,
                )
                queue_apply(store, paper)
        with acts[1]:
            if in_lib:
                st.button("✓ Saved", key=f"pulse-save-{index}", use_container_width=True, disabled=True)
            elif item.paper_id:
                if st.button("📥 Save", key=f"pulse-save-{index}", use_container_width=True):
                    if save_pulse_item(store, item):
                        st.rerun()
            else:
                st.button("📥 Save", key=f"pulse-save-{index}", use_container_width=True, disabled=True,
                          help="No paper attached to this topic.")
        with acts[2]:
            if st.button(
                "✨ Refine",
                key=f"pulse-memo-{index}",
                use_container_width=True,
                disabled=not _api_ready(),
                help="Ask Groq for a sharper decision memo." if _api_ready() else "Needs a Groq API key.",
            ):
                draft = draft_decision_memo(item, fit, stack)
                refined = refine_decision_memo(item, fit, stack, draft)
                store.save_memo(memo_item_key(item), stack_key(stack), **refined.as_dict())
                st.toast("Memo refined ✨")
                st.rerun()


def render_ml_pulse(store: PaperDatabase) -> None:
    head, refresh = st.columns((5, 1.4))
    with head:
        st.subheader("⚡ ML Pulse")
    with refresh:
        st.write("")
        if st.button("↻ Refresh", use_container_width=True, key="pulse-refresh-top"):
            try:
                do_refresh_pulse(store)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    st.caption(
        "Morning brief: Hugging Face Daily Papers **trending** plus newest arXiv "
        "cs.LG / cs.CL / cs.AI from the last 60 days — ranked against your stack."
    )
    view = st.radio(
        "Show",
        options=["my_stack", "all", "saved"],
        format_func=lambda v: {
            "my_stack": "🎯 For my stack",
            "all": "🌐 Everything",
            "saved": "📚 Saved",
        }[v],
        horizontal=True,
        key="pulse_view",
        label_visibility="collapsed",
    )
    if view == "saved":
        render_library(store)
        return
    snap = load_pulse(store)
    if not snap or not snap.items:
        st.markdown(
            "<div class='empty-cta'>⚡ No pulse yet.<br>Hit <b>↻ Refresh</b> above to pull today's "
            "trending papers and newest arXiv ML.</div>",
            unsafe_allow_html=True,
        )
        if snap and snap.errors:
            with st.expander("Feed notes"):
                for err in snap.errors:
                    st.caption(err)
        return
    stack = store.get_stack()
    ranked = [(score_against_stack(item, stack), i, item) for i, item in enumerate(snap.items)]
    if view == "my_stack" and stack:
        ranked.sort(key=lambda row: (-row[0].score, row[1]))
        ranked = [row for row in ranked if row[0].label != "Skip"]
        if not ranked:
            st.info("Nothing on your stack in this pulse. Switch to 🌐 Everything, or refresh.")
            return
    st.caption(f"Updated {snap.fetched_at} · {len(ranked)} items")
    for fit, i, item in ranked:
        render_pulse_card(store, item, fit, stack, i)


# ---------------------------------------------------------------- consultant

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
                reply = consultant.chat_with_consultant(
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


def render_apply_sheet() -> bool:
    """Review-and-send sheet for an Apply draft. Returns True if a draft is showing."""
    draft = st.session_state.get("apply_draft")
    if not draft:
        return False
    with st.container(border=True):
        st.markdown("### 📋 Apply draft")
        st.caption(f"Review the brief before sending · **{draft.get('title', '')}**")
        st.text_area(
            "Prompt",
            value=draft.get("prompt", ""),
            height=200,
            key="apply_draft_text",
            label_visibility="collapsed",
        )
        c1, c2 = st.columns(2)
        if c1.button("🚀 Send to consultant", type="primary", use_container_width=True, key="apply-send"):
            prompt = st.session_state.get("apply_draft_text", "") or draft.get("prompt", "")
            st.session_state.pop("apply_draft", None)
            _run_consultant_turn(prompt, "apply")
        if c2.button("Discard", use_container_width=True, key="apply-discard"):
            st.session_state.pop("apply_draft", None)
            st.rerun()
    return True


def _export_chat_markdown(layer: str) -> str:
    turns = st.session_state.get(_history_key(layer), [])
    lines = [f"# Consultant chat · {layer}", ""]
    for t in turns:
        lines.append(f"**{t['role']}**")
        lines.append("")
        lines.append(t["content"])
        lines.append("")
    return "\n".join(lines)


def render_consultant_terminal() -> None:
    st.subheader("💬 Consultant Terminal")
    if "consultant_layer" not in st.session_state:
        st.session_state.consultant_layer = "apply"
    for layer in ("apply", "explain", "systems"):
        key = _history_key(layer)
        if key not in st.session_state:
            st.session_state[key] = []

    render_apply_sheet()

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

    st.caption("Try one:")
    sug_cols = st.columns(len(SUGGESTIONS[layer_label]))
    for col, sug in zip(sug_cols, SUGGESTIONS[layer_label]):
        if col.button(sug, key=f"sug-{layer_label}-{sug[:12]}", use_container_width=True):
            _run_consultant_turn(sug, layer_label)

    tools = st.columns((1, 1, 4))
    if tools[0].button("🧹 Clear session", use_container_width=True):
        st.session_state[_history_key(layer_label)] = []
        st.rerun()
    history = st.session_state[_history_key(layer_label)]
    tools[1].download_button(
        "⬇️ Export",
        data=_export_chat_markdown(layer_label),
        file_name=f"consultant-{layer_label}.md",
        mime="text/markdown",
        use_container_width=True,
        disabled=not history,
    )
    if history:
        tools[2].caption(f"{len(history)} messages in this session")

    for turn in history:
        with st.chat_message(turn["role"]):
            st.markdown(turn["content"])

    typed = st.chat_input(placeholder)
    if not typed:
        return
    _run_consultant_turn(typed, layer_label)


def queue_apply(store: PaperDatabase, paper: Any) -> None:
    """Stage an Apply draft for review on the Consultant pane.

    Streamlit cannot switch tabs in code from the old flow's instant-send, so
    the prompt is staged as an editable draft instead of being sent blindly.
    """
    st.session_state.consultant_layer = "apply"
    st.session_state.apply_draft = {
        "title": getattr(paper, "title", "") or "",
        "paper_id": getattr(paper, "id", "") or "",
        "prompt": paper_apply_prompt(
            paper,
            application=store.get_application(),
            known_papers=store.get_known_papers(),
            repo_url=store.get_repo_url(),
        ),
    }
    st.session_state.open_consultant = True
    st.rerun()


# ---------------------------------------------------------------- navigation

def _active_section() -> str:
    # Flag must be applied before the section widget is instantiated.
    if st.session_state.pop("open_consultant", False):
        st.session_state.main_section = MAIN_CONSULTANT
    if st.session_state.get("main_section") in {"Library", "Research Hub"}:
        st.session_state.main_section = MAIN_PULSE
        st.session_state.pulse_view = "saved"
    if "main_section" not in st.session_state:
        st.session_state.main_section = MAIN_PULSE
    return st.radio(
        "Section",
        options=list(MAIN_SECTIONS),
        horizontal=True,
        key="main_section",
        label_visibility="collapsed",
    )


def render_hero(store: PaperDatabase) -> None:
    stats = _stats(store)
    pulse = load_pulse(store)
    pulse_note = f"Pulse · {len(pulse.items)} items" if pulse else "Pulse · not refreshed yet"
    st.markdown(
        f"""
<div class="hero">
  <div class="gold">Personal ML knowledge base</div>
  <h1>MLE Professor</h1>
  <p class="muted">What moved in ML today, the paper, the concept, and whether it fits your stack — with links you can check.</p>
  <p class="muted mono" style="font-size:.78rem">📚 {stats["papers"]} saved · {stats["unread"]} unread &nbsp;·&nbsp; ⚡ {pulse_note}</p>
</div>
""",
        unsafe_allow_html=True,
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
    if demo.demo_enabled():
        demo.seed_demo_data(store)

    if _show_wizard(store):
        render_onboarding(store)
        return

    with st.sidebar:
        render_sidebar(store)

    render_hero(store)

    section = _active_section()
    if section == MAIN_PULSE:
        render_ml_pulse(store)
    else:
        render_consultant_terminal()


main()
