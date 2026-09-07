from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from mle_professor.interview.bank import TOPICS
from mle_professor.ui.runtime import get_context, llm_banner
from mle_professor.ui.theme import page_setup

page_setup("Library", "📚")
ctx = get_context()
llm_banner(ctx)

st.title("Library")
st.caption("Papers live in SQLite. Chunks are embedded into local LanceDB.")

tab_add, tab_browse, tab_notes = st.tabs(["Add", "Browse", "Notes"])

with tab_add:
    mode = st.radio("Source", ["arXiv", "PDF", "Paste note"], horizontal=True)
    topic_opts = st.multiselect("Topics", TOPICS)
    if mode == "arXiv":
        arxiv_id = st.text_input("arXiv id or URL", placeholder="1706.03762 or https://arxiv.org/abs/1706.03762")
        full = st.checkbox("Also download PDF and index up to 40 pages", value=False)
        if st.button("Ingest arXiv", type="primary", disabled=not arxiv_id.strip()):
            status = st.empty()
            try:
                paper_id = ctx.pipeline.ingest_arxiv(
                    arxiv_id.strip(),
                    topics=topic_opts,
                    download_full_pdf=full,
                    progress=lambda msg: status.write(msg),
                )
                paper = ctx.store.get_paper(paper_id)
                st.success(f"Indexed **{paper.title}** ({paper.chunk_count} chunks).")
            except Exception as exc:
                st.error(str(exc))
    elif mode == "PDF":
        title = st.text_input("Title (optional)")
        authors = st.text_input("Authors (optional)")
        uploaded = st.file_uploader("PDF", type=["pdf"])
        if st.button("Ingest PDF", type="primary", disabled=uploaded is None):
            dest = ctx.settings.pdf_dir / uploaded.name
            dest.write_bytes(uploaded.getvalue())
            status = st.empty()
            try:
                paper_id = ctx.pipeline.ingest_pdf(
                    dest,
                    title=title,
                    authors=authors,
                    topics=topic_opts,
                    progress=lambda msg: status.write(msg),
                )
                paper = ctx.store.get_paper(paper_id)
                st.success(f"Indexed **{paper.title}** ({paper.chunk_count} chunks).")
            except Exception as exc:
                st.error(str(exc))
    else:
        note_title = st.text_input("Note title")
        body = st.text_area("Body", height=220)
        papers = ctx.store.list_papers()
        paper_map = {f"{p.id} · {p.title}": p.id for p in papers}
        linked = st.selectbox("Link to paper (optional)", ["None"] + list(paper_map))
        if st.button("Save note", type="primary", disabled=not (note_title.strip() and body.strip())):
            try:
                ctx.pipeline.ingest_note(
                    title=note_title.strip(),
                    body=body.strip(),
                    paper_id=None if linked == "None" else paper_map[linked],
                    topics=topic_opts,
                )
                st.success("Note saved and embedded.")
            except Exception as exc:
                st.error(str(exc))

with tab_browse:
    q = st.text_input("Filter", placeholder="title, author, topic…")
    papers = ctx.store.list_papers(q)
    st.caption(f"{len(papers)} papers")
    for paper in papers:
        with st.container(border=True):
            top, actions = st.columns((4, 1))
            with top:
                st.markdown(f"**{paper.title}**")
                meta = " · ".join(
                    x
                    for x in [
                        paper.authors[:80] if paper.authors else "",
                        str(paper.year or ""),
                        paper.venue or paper.source,
                        paper.external_id or "",
                        f"{paper.chunk_count} chunks",
                    ]
                    if x
                )
                st.caption(meta)
                if paper.topics:
                    st.markdown(
                        " ".join(f'<span class="tag">{t}</span>' for t in paper.topics),
                        unsafe_allow_html=True,
                    )
                if paper.abstract:
                    st.write(paper.abstract[:500] + ("…" if len(paper.abstract) > 500 else ""))
            with actions:
                if st.button("Delete", key=f"del-{paper.id}"):
                    ctx.pipeline.delete_paper(paper.id)
                    st.rerun()

with tab_notes:
    notes = ctx.store.list_notes()
    if not notes:
        st.info("No notes yet.")
    for note in notes:
        with st.container(border=True):
            st.markdown(f"**{note.title}**")
            st.caption(f"{note.created_at} · {note.chunk_count} chunks")
            st.write(note.body[:600] + ("…" if len(note.body) > 600 else ""))
            if st.button("Delete note", key=f"deln-{note.id}"):
                ctx.vectors.delete_note(note.id)
                ctx.store.delete_note(note.id)
                st.rerun()
