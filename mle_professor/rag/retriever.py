from __future__ import annotations

from typing import Optional

from mle_professor.config import Settings, get_settings
from mle_professor.db.sqlite import PaperStore
from mle_professor.embeddings.store import Hit, VectorStore


class Retriever:
    def __init__(
        self,
        store: PaperStore,
        vectors: VectorStore,
        settings: Settings | None = None,
    ) -> None:
        self.store = store
        self.vectors = vectors
        self.settings = settings or get_settings()

    def search(
        self,
        query: str,
        *,
        k: Optional[int] = None,
        paper_id: Optional[int] = None,
    ) -> list[Hit]:
        k = k or self.settings.search_k
        return self.vectors.search(query, k=k, paper_id=paper_id)

    def context_hits(
        self,
        query: str,
        *,
        paper_id: Optional[int] = None,
    ) -> list[Hit]:
        return self.search(
            query, k=self.settings.max_context_chunks, paper_id=paper_id
        )
