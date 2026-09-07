"""Pluggable text encoders.

Backends:
- local: sentence-transformers MiniLM (default, ~80MB, CPU)
- xai:   xAI embeddings API
- hash:  feature-hashing encoder (no download; tests and first-boot fallback)
"""

from __future__ import annotations

import hashlib
from typing import Protocol, runtime_checkable

import numpy as np

from mle_professor.config import Settings, get_settings


@runtime_checkable
class Encoder(Protocol):
    name: str
    dim: int

    def encode(self, texts: list[str], *, is_query: bool = False) -> np.ndarray: ...


class HashingEncoder:
    """Token-hashing encoder. Deterministic, RAM-cheap, no model download."""

    def __init__(self, dim: int = 384) -> None:
        self.name = f"hash-{dim}"
        self.dim = dim

    def encode(self, texts: list[str], *, is_query: bool = False) -> np.ndarray:
        del is_query
        rows = [self._embed(t) for t in texts]
        if not rows:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.vstack(rows)

    def _embed(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        for token in _tokenize(text):
            digest = hashlib.md5(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "little") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[idx] += sign
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec /= norm
        return vec


class MiniLMEncoder:
    """Local MiniLM via sentence-transformers. Loaded lazily, batched, CPU-only."""

    def __init__(self, model_name: str, batch_size: int) -> None:
        self.name = model_name
        self.batch_size = max(1, batch_size)
        self._model = None
        self._dim: int | None = None

    @property
    def dim(self) -> int:
        self._ensure()
        assert self._dim is not None
        return self._dim

    def encode(self, texts: list[str], *, is_query: bool = False) -> np.ndarray:
        del is_query
        self._ensure()
        assert self._model is not None
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        vectors = self._model.encode(
            texts,
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype=np.float32)

    def _ensure(self) -> None:
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(self.name, device="cpu")
        self._dim = int(self._model.get_sentence_embedding_dimension())


class XAIEncoder:
    """Cloud embeddings via the xAI OpenAI-compatible API."""

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        if not api_key:
            raise RuntimeError("XAI_API_KEY is required for the xAI embedding backend.")
        from openai import OpenAI

        self.name = f"xai:{model}"
        self.model = model
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._dim: int | None = None

    @property
    def dim(self) -> int:
        if self._dim is None:
            sample = self.encode(["dimension probe"])
            self._dim = int(sample.shape[1])
        return self._dim

    def encode(self, texts: list[str], *, is_query: bool = False) -> np.ndarray:
        if not texts:
            dim = self._dim or 256
            return np.zeros((0, dim), dtype=np.float32)
        prefix = "query: " if is_query else "passage: "
        payload = [prefix + t for t in texts]
        response = self._client.embeddings.create(
            model=self.model, input=payload, encoding_format="float"
        )
        ordered = sorted(response.data, key=lambda item: item.index)
        matrix = np.asarray([item.embedding for item in ordered], dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms = np.clip(norms, 1e-12, None)
        matrix = matrix / norms
        if self._dim is None:
            self._dim = int(matrix.shape[1])
        return matrix


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    buf: list[str] = []
    for ch in text.lower():
        if ch.isalnum():
            buf.append(ch)
        elif buf:
            tokens.append("".join(buf))
            buf = []
    if buf:
        tokens.append("".join(buf))
    return tokens or ["empty"]


def build_encoder(settings: Settings | None = None) -> Encoder:
    cfg = settings or get_settings()
    if cfg.embedding_backend == "hash":
        return HashingEncoder(dim=cfg.hash_dim)
    if cfg.embedding_backend == "xai":
        return XAIEncoder(cfg.xai_api_key, cfg.xai_base_url, cfg.xai_embed_model)
    encoder = MiniLMEncoder(cfg.local_embed_model, cfg.embed_batch_size)
    try:
        _ = encoder.dim
        return encoder
    except Exception:
        return HashingEncoder(dim=cfg.hash_dim)
