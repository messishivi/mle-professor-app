"""Cached process-wide resources. Streamlit reruns must not reload MiniLM."""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from mle_professor.bootstrap import seed_if_needed
from mle_professor.config import Settings, get_settings
from mle_professor.db.sqlite import PaperStore
from mle_professor.embeddings.encoder import Encoder, build_encoder
from mle_professor.embeddings.store import VectorStore
from mle_professor.ingest.pipeline import IngestPipeline
from mle_professor.interview.engine import InterviewEngine
from mle_professor.llm.client import LLMClient
from mle_professor.rag.retriever import Retriever


@dataclass
class AppContext:
    settings: Settings
    store: PaperStore
    encoder: Encoder
    vectors: VectorStore
    pipeline: IngestPipeline
    retriever: Retriever
    llm: LLMClient
    interview: InterviewEngine


@st.cache_resource(show_spinner="Opening local knowledge base…")
def get_context() -> AppContext:
    settings = get_settings()
    settings.ensure_dirs()
    store = PaperStore(settings.sqlite_path)
    encoder = build_encoder(settings)
    vectors = VectorStore(settings.lancedb_path, encoder)
    pipeline = IngestPipeline(store, vectors, encoder, settings)
    previous = store.get_meta("encoder_name")
    if previous and previous != encoder.name:
        store.set_meta("encoder_mismatch", f"{previous} -> {encoder.name}")
    else:
        store.set_meta("encoder_mismatch", "")
    store.set_meta("encoder_name", encoder.name)
    seed_if_needed(pipeline)
    llm = LLMClient(settings)
    return AppContext(
        settings=settings,
        store=store,
        encoder=encoder,
        vectors=vectors,
        pipeline=pipeline,
        retriever=Retriever(store, vectors, settings),
        llm=llm,
        interview=InterviewEngine(store, llm),
    )


def llm_banner(ctx: AppContext) -> None:
    if ctx.llm.configured:
        label = "Grok" if ctx.settings.llm_provider == "xai" else "OpenAI"
        st.sidebar.success(f"{label} ready · {ctx.settings.xai_model}")
    else:
        st.sidebar.warning("No XAI_API_KEY — search and the question bank still work.")
    st.sidebar.caption(
        f"Embeddings: `{ctx.encoder.name}`  ·  dim {ctx.encoder.dim}  ·  index {ctx.vectors.backend_name}"
    )
    mismatch = ctx.store.get_meta("encoder_mismatch")
    if mismatch:
        st.sidebar.error(
            f"Encoder changed ({mismatch}). Delete `data/lancedb` and restart if search looks wrong."
        )
