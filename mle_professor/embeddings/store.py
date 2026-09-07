"""Vector store: LanceDB when available, otherwise a numpy cosine index.

LanceDB needs Python 3.10+. The numpy backend is the RAM-safe utility path
for a personal corpus (tens of thousands of chunks fit in a few dozen MB).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Protocol

import numpy as np

from mle_professor.embeddings.encoder import Encoder


CHUNKS_TABLE = "chunks"


@dataclass
class Hit:
    id: str
    paper_id: int
    note_id: int
    source: str
    title: str
    section: str
    chunk_index: int
    text: str
    score: float


def _hit(row: dict[str, Any], score: float) -> Hit:
    return Hit(
        id=str(row.get("id") or ""),
        paper_id=int(row.get("paper_id") or 0),
        note_id=int(row.get("note_id") or 0),
        source=str(row.get("source") or ""),
        title=str(row.get("title") or ""),
        section=str(row.get("section") or ""),
        chunk_index=int(row.get("chunk_index") or 0),
        text=str(row.get("text") or ""),
        score=float(score),
    )


def _rows_from_chunks(chunks: list[dict[str, Any]], vectors: np.ndarray) -> list[dict[str, Any]]:
    if vectors.shape[0] != len(chunks):
        raise ValueError("vectors and chunks length mismatch")
    rows = []
    for chunk, vector in zip(chunks, vectors):
        rows.append(
            {
                "id": str(chunk["id"]),
                "paper_id": int(chunk.get("paper_id") or 0),
                "note_id": int(chunk.get("note_id") or 0),
                "source": str(chunk.get("source") or ""),
                "title": str(chunk.get("title") or ""),
                "section": str(chunk.get("section") or ""),
                "chunk_index": int(chunk.get("chunk_index") or 0),
                "text": str(chunk.get("text") or ""),
                "vector": np.asarray(vector, dtype=np.float32).tolist(),
            }
        )
    return rows


class _Backend(Protocol):
    name: str

    def add_chunks(self, chunks: list[dict[str, Any]], vectors: np.ndarray) -> int: ...
    def delete_paper(self, paper_id: int) -> None: ...
    def delete_note(self, note_id: int) -> None: ...
    def search(
        self, vector: list[float], k: int, paper_id: Optional[int]
    ) -> list[Hit]: ...
    def count(self) -> int: ...


class LanceBackend:
    name = "lancedb"

    def __init__(self, path: Path, dim: int) -> None:
        import lancedb
        import pyarrow as pa

        path.mkdir(parents=True, exist_ok=True)
        self.dim = dim
        self._db = lancedb.connect(str(path))
        self._schema = pa.schema(
            [
                pa.field("id", pa.string()),
                pa.field("paper_id", pa.int64()),
                pa.field("note_id", pa.int64()),
                pa.field("source", pa.string()),
                pa.field("title", pa.string()),
                pa.field("section", pa.string()),
                pa.field("chunk_index", pa.int64()),
                pa.field("text", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), dim)),
            ]
        )
        self._table = None

    def table(self):
        if self._table is not None:
            return self._table
        names = set(self._db.table_names())
        if CHUNKS_TABLE in names:
            self._table = self._db.open_table(CHUNKS_TABLE)
        else:
            self._table = self._db.create_table(
                CHUNKS_TABLE, schema=self._schema, mode="create"
            )
        return self._table

    def add_chunks(self, chunks: list[dict[str, Any]], vectors: np.ndarray) -> int:
        rows = _rows_from_chunks(chunks, vectors)
        if not rows:
            return 0
        self.table().add(rows)
        self._table = None
        return len(rows)

    def delete_paper(self, paper_id: int) -> None:
        try:
            self.table().delete(f"paper_id = {int(paper_id)}")
        except Exception:
            pass
        self._table = None

    def delete_note(self, note_id: int) -> None:
        try:
            self.table().delete(f"note_id = {int(note_id)}")
        except Exception:
            pass
        self._table = None

    def search(
        self, vector: list[float], k: int, paper_id: Optional[int]
    ) -> list[Hit]:
        builder = self.table().search(vector).metric("cosine").limit(max(1, k))
        if paper_id is not None:
            builder = builder.where(f"paper_id = {int(paper_id)}", prefilter=True)
        try:
            raw = builder.to_list()
        except Exception:
            return []
        hits = []
        for row in raw:
            distance = float(row.get("_distance", 0.0))
            score = 1.0 / (1.0 + max(distance, 0.0))
            hits.append(_hit(row, score))
        return hits

    def count(self) -> int:
        try:
            return int(self.table().count_rows())
        except Exception:
            return 0


class NumpyBackend:
    """JSONL metadata + memmap-friendly .npy matrix. Cosine search in numpy."""

    name = "numpy"

    def __init__(self, path: Path, dim: int) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self.dir = path / "numpy_index"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.meta_path = self.dir / "chunks.jsonl"
        self.vec_path = self.dir / "vectors.npy"
        self.dim = dim
        self._rows: Optional[list[dict[str, Any]]] = None
        self._mat: Optional[np.ndarray] = None

    def _load(self) -> tuple[list[dict[str, Any]], np.ndarray]:
        if self._rows is not None and self._mat is not None:
            return self._rows, self._mat
        rows: list[dict[str, Any]] = []
        if self.meta_path.exists():
            with self.meta_path.open() as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        rows.append(json.loads(line))
        if self.vec_path.exists() and rows:
            mat = np.load(self.vec_path).astype(np.float32)
            if mat.ndim != 2 or mat.shape[0] != len(rows):
                mat = np.zeros((len(rows), self.dim), dtype=np.float32)
        else:
            mat = np.zeros((len(rows), self.dim), dtype=np.float32)
        self._rows, self._mat = rows, mat
        return rows, mat

    def _save(self, rows: list[dict[str, Any]], mat: np.ndarray) -> None:
        tmp = self.meta_path.with_suffix(".jsonl.tmp")
        with tmp.open("w") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        tmp.replace(self.meta_path)
        np.save(self.vec_path, mat.astype(np.float32))
        self._rows, self._mat = rows, mat.astype(np.float32)

    def add_chunks(self, chunks: list[dict[str, Any]], vectors: np.ndarray) -> int:
        prepared = _rows_from_chunks(chunks, vectors)
        if not prepared:
            return 0
        meta = [{k: v for k, v in row.items() if k != "vector"} for row in prepared]
        new_mat = np.asarray([row["vector"] for row in prepared], dtype=np.float32)
        rows, mat = self._load()
        if mat.size == 0:
            combined = new_mat
        else:
            combined = np.vstack([mat, new_mat])
        self._save(rows + meta, combined)
        return len(meta)

    def delete_paper(self, paper_id: int) -> None:
        rows, mat = self._load()
        keep = [i for i, row in enumerate(rows) if int(row.get("paper_id") or 0) != int(paper_id)]
        self._save([rows[i] for i in keep], mat[keep] if keep else np.zeros((0, self.dim), np.float32))

    def delete_note(self, note_id: int) -> None:
        rows, mat = self._load()
        keep = [i for i, row in enumerate(rows) if int(row.get("note_id") or 0) != int(note_id)]
        self._save([rows[i] for i in keep], mat[keep] if keep else np.zeros((0, self.dim), np.float32))

    def search(
        self, vector: list[float], k: int, paper_id: Optional[int]
    ) -> list[Hit]:
        rows, mat = self._load()
        if mat.size == 0 or not rows:
            return []
        q = np.asarray(vector, dtype=np.float32)
        n = float(np.linalg.norm(q))
        if n > 0:
            q = q / n
        mask = np.ones(len(rows), dtype=bool)
        if paper_id is not None:
            mask = np.array(
                [int(row.get("paper_id") or 0) == int(paper_id) for row in rows],
                dtype=bool,
            )
        if not mask.any():
            return []
        sims = mat[mask] @ q
        idxs = np.nonzero(mask)[0]
        order = np.argsort(-sims)[: max(1, k)]
        hits = []
        for rel in order:
            score = float(sims[rel])
            hits.append(_hit(rows[int(idxs[rel])], score))
        return hits

    def count(self) -> int:
        rows, _ = self._load()
        return len(rows)


class VectorStore:
    def __init__(self, path: str | Path, encoder: Encoder) -> None:
        self.path = Path(path)
        self.encoder = encoder
        self.backend = self._open()

    @property
    def backend_name(self) -> str:
        return self.backend.name

    def _open(self) -> _Backend:
        try:
            return LanceBackend(self.path, self.encoder.dim)
        except Exception:
            return NumpyBackend(self.path, self.encoder.dim)

    def add_chunks(self, *, chunks: list[dict[str, Any]], vectors: np.ndarray) -> int:
        if not chunks:
            return 0
        return self.backend.add_chunks(chunks, vectors)

    def delete_paper(self, paper_id: int) -> None:
        self.backend.delete_paper(paper_id)

    def delete_note(self, note_id: int) -> None:
        self.backend.delete_note(note_id)

    def search(
        self,
        query: str,
        *,
        k: int = 8,
        paper_id: Optional[int] = None,
    ) -> list[Hit]:
        query = (query or "").strip()
        if not query:
            return []
        vector = self.encoder.encode([query], is_query=True)[0].tolist()
        return self.backend.search(vector, k, paper_id)

    def count(self) -> int:
        return self.backend.count()
