"""Runtime settings. Values are read from the environment on first access."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    sqlite_path: Path
    lancedb_path: Path
    pdf_dir: Path
    xai_api_key: str
    xai_base_url: str
    xai_model: str
    xai_embed_model: str
    llm_provider: str
    embedding_backend: str
    local_embed_model: str
    hash_dim: int
    embed_batch_size: int
    chunk_chars: int
    chunk_overlap: int
    search_k: int
    max_context_chunks: int

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.lancedb_path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(ROOT / ".env", override=False)
    data_dir = Path(os.getenv("MLE_DATA_DIR", str(ROOT / "data"))).expanduser()
    backend = os.getenv("EMBEDDING_BACKEND", "local").strip().lower()
    if backend not in {"local", "xai", "hash"}:
        backend = "local"
    xai_key = os.getenv("XAI_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if xai_key:
        provider = "xai"
        api_key = xai_key
        base_url = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1").rstrip("/")
        model = os.getenv("XAI_MODEL", "grok-4.6").strip() or "grok-4.6"
    elif openai_key:
        provider = "openai"
        api_key = openai_key
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    else:
        provider = "xai"
        api_key = ""
        base_url = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1").rstrip("/")
        model = os.getenv("XAI_MODEL", "grok-4.6").strip() or "grok-4.6"
    return Settings(
        data_dir=data_dir,
        sqlite_path=data_dir / "mle_professor.sqlite",
        lancedb_path=data_dir / "lancedb",
        pdf_dir=data_dir / "pdfs",
        xai_api_key=api_key,
        xai_base_url=base_url,
        xai_model=model,
        xai_embed_model=os.getenv("XAI_EMBED_MODEL", "v1").strip() or "v1",
        llm_provider=provider,
        embedding_backend=backend,
        local_embed_model=os.getenv("LOCAL_EMBED_MODEL", "all-MiniLM-L6-v2"),
        hash_dim=int(os.getenv("HASH_EMBED_DIM", "384")),
        embed_batch_size=int(os.getenv("EMBED_BATCH_SIZE", "16")),
        chunk_chars=int(os.getenv("CHUNK_CHARS", "1800")),
        chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "200")),
        search_k=int(os.getenv("SEARCH_K", "8")),
        max_context_chunks=int(os.getenv("MAX_CONTEXT_CHUNKS", "6")),
    )


def reset_settings() -> None:
    get_settings.cache_clear()
