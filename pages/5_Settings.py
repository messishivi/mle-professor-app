from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from mle_professor.config import get_settings
from mle_professor.ui.runtime import get_context, llm_banner
from mle_professor.ui.theme import page_setup

page_setup("Settings", "⚙️")
ctx = get_context()
llm_banner(ctx)
cfg = get_settings()

st.title("Settings")
st.caption("Keys stay on this machine. Restart Streamlit after editing `.env`.")

st.subheader("Reasoning API")
st.write(
    "Chat, grading, and generated interviews call **SpaceXAI / xAI** at "
    f"`{cfg.xai_base_url}` with model `{cfg.xai_model}`."
)
if cfg.xai_api_key:
    st.success("XAI_API_KEY is set.")
else:
    st.warning("XAI_API_KEY is missing. Copy `.env.example` to `.env` and add a key from https://console.x.ai")

st.subheader("Local data")
c1, c2 = st.columns(2)
c1.code(str(cfg.sqlite_path))
c2.code(str(cfg.lancedb_path))
st.write(
    f"Embedding backend: **{cfg.embedding_backend}** · encoder `{ctx.encoder.name}` · dim {ctx.encoder.dim}"
)
st.write(
    f"Vector index: **{ctx.vectors.backend_name}** · rows {ctx.vectors.count()}"
)

st.subheader("RAM budget (16GB MacBook Air)")
st.markdown(
    """
- No local LLM weights. Grok runs in the cloud.
- Default encoder is MiniLM (`all-MiniLM-L6-v2`), ~80MB on CPU, batched.
- PDF extraction is capped at 40 pages.
- SQLite WAL + LanceDB live under `data/` and are gitignored.
- Set `EMBEDDING_BACKEND=hash` for a no-download encoder (tests / ultra-light).
- Set `EMBEDDING_BACKEND=xai` to embed via the xAI embeddings API (`v1`).
"""
)

st.subheader("Environment")
shown = {
    "XAI_MODEL": cfg.xai_model,
    "EMBEDDING_BACKEND": cfg.embedding_backend,
    "LOCAL_EMBED_MODEL": cfg.local_embed_model,
    "MLE_DATA_DIR": str(cfg.data_dir),
}
st.json(shown)
st.caption("Process env has XAI_API_KEY" if os.getenv("XAI_API_KEY") else "Process env has no XAI_API_KEY")
