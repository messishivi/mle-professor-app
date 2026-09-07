from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from mle_professor.llm.prompts import format_context, tutor_messages
from mle_professor.ui.runtime import get_context, llm_banner
from mle_professor.ui.theme import page_setup

page_setup("Tutor", "💬")
ctx = get_context()
llm_banner(ctx)

st.title("Tutor")
st.caption("Retrieves from your library, then asks Grok to teach with citations.")

if "tutor_history" not in st.session_state:
    st.session_state.tutor_history = []
if "tutor_display" not in st.session_state:
    st.session_state.tutor_display = []

papers = ctx.store.list_papers()
scope = st.selectbox(
    "Restrict retrieval",
    ["All papers"] + [f"{p.id} · {p.title}" for p in papers],
)
if st.button("Clear conversation"):
    st.session_state.tutor_history = []
    st.session_state.tutor_display = []
    st.rerun()

for msg in st.session_state.tutor_display:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("Ask about a paper, an algorithm, or an interview angle…")
if prompt:
    st.session_state.tutor_display.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    paper_id = None if scope == "All papers" else int(scope.split(" · ", 1)[0])
    hits = ctx.retriever.context_hits(prompt, paper_id=paper_id)
    with st.expander("Retrieved context", expanded=False):
        st.markdown(format_context(hits))

    with st.chat_message("assistant"):
        if not ctx.llm.configured:
            fallback = (
                "Cloud reasoning is off (no `XAI_API_KEY`). Here is the retrieved context "
                "you can study locally:\n\n" + format_context(hits)
            )
            st.markdown(fallback)
            st.session_state.tutor_display.append(
                {"role": "assistant", "content": fallback}
            )
        else:
            messages = tutor_messages(st.session_state.tutor_history, prompt, hits)
            placeholder = st.empty()
            collected = []
            try:
                for piece in ctx.llm.stream(messages):
                    collected.append(piece)
                    placeholder.markdown("".join(collected))
            except Exception as exc:
                placeholder.error(str(exc))
                collected = [str(exc)]
            answer = "".join(collected)
            st.session_state.tutor_history.extend(
                [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": answer},
                ]
            )
            st.session_state.tutor_history = st.session_state.tutor_history[-12:]
            st.session_state.tutor_display.append(
                {"role": "assistant", "content": answer}
            )
