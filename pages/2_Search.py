from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from mle_professor.ui.runtime import get_context, llm_banner
from mle_professor.ui.theme import page_setup

page_setup("Search", "🔎")
ctx = get_context()
llm_banner(ctx)

st.title("Semantic search")
st.caption("Runs entirely on-device against LanceDB. No cloud call.")

papers = ctx.store.list_papers()
options = ["All papers"] + [f"{p.id} · {p.title}" for p in papers]
scope = st.selectbox("Scope", options)
k = st.slider("Results", 3, 20, 8)
query = st.text_input("Query", placeholder="why residual connections help optimization")

if query:
    paper_id = None if scope == "All papers" else int(scope.split(" · ", 1)[0])
    hits = ctx.retriever.search(query, k=k, paper_id=paper_id)
    if not hits:
        st.warning("No matches. Try a shorter query or ingest more papers.")
    for hit in hits:
        with st.container(border=True):
            st.markdown(f"**{hit.title}**")
            st.caption(
                f"{hit.section or 'chunk'} · #{hit.chunk_index} · score {hit.score:.3f} · {hit.source}"
            )
            st.write(hit.text)
