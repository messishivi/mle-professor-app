"""Local SQLite knowledge base for ingested research papers.

The on-disk file is ``mle_knowledge.db``. Paper primary keys are canonical
ArXiv IDs, so ``1706.03762``, ``arxiv:1706.03762v2``, and
``https://arxiv.org/abs/1706.03762`` all map to one row. Re-ingestion uses
``INSERT ... ON CONFLICT(id) DO UPDATE`` rather than ``INSERT OR REPLACE``,
which would delete-and-reinsert and wipe ``read_status`` / ``added_at``.
"""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

ROOT = Path(__file__).resolve().parent
DEFAULT_DB_PATH = ROOT / "data" / "mle_knowledge.db"

# New-style (1706.03762) and old-style (cs/0211011) identifiers, with optional
# version suffix, arxiv: prefix, or abs/pdf URL wrapper.
ARXIV_ID_RE = re.compile(
    r"(?:arxiv:)?(?:https?://(?:www\.)?arxiv\.org/(?:abs|pdf)/)?"
    r"(?P<id>\d{4}\.\d{4,5}|[a-z\-]+(?:\.[A-Z]{2})?/\d{7})"
    r"(?:v\d+)?(?:\.pdf)?",
    re.IGNORECASE,
)

SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    authors TEXT NOT NULL DEFAULT '',
    published_date TEXT,
    summary_raw TEXT NOT NULL DEFAULT '',
    summary_structured TEXT,
    read_status INTEGER NOT NULL DEFAULT 0,
    added_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_papers_published ON papers(published_date);
CREATE INDEX IF NOT EXISTS idx_papers_read ON papers(read_status);
CREATE INDEX IF NOT EXISTS idx_papers_added ON papers(added_at);

CREATE TABLE IF NOT EXISTS pulse_snapshots (
    id INTEGER PRIMARY KEY,
    fetched_at TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decision_memos (
    item_key TEXT NOT NULL,
    stack_key TEXT NOT NULL,
    verdict TEXT NOT NULL,
    constraint_note TEXT NOT NULL,
    so_what TEXT NOT NULL,
    paper_url TEXT NOT NULL DEFAULT '',
    origin TEXT NOT NULL DEFAULT 'heuristic',
    created_at TEXT NOT NULL,
    PRIMARY KEY (item_key, stack_key)
);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_arxiv_id(raw: str) -> str:
    """Collapse URL / prefix / version variants to a stable primary key.

    Version suffixes are stripped (``1706.03762v7`` → ``1706.03762``) so a later
    ingest of the same paper cannot insert a second row.
    """
    text = (raw or "").strip()
    if not text:
        raise ValueError("ArXiv id is empty.")
    match = ARXIV_ID_RE.search(text)
    if not match:
        raise ValueError(f"Could not parse an ArXiv id from: {raw!r}")
    return match.group("id")


def _dump_structured(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        json.loads(text)
        return text
    return json.dumps(value, ensure_ascii=False)


def _load_structured(raw: Optional[str]) -> Optional[Any]:
    if raw is None or raw == "":
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _authors_to_text(authors: Union[str, list[str], tuple[str, ...], None]) -> str:
    if authors is None:
        return ""
    if isinstance(authors, (list, tuple)):
        return ", ".join(str(a).strip() for a in authors if str(a).strip())
    return str(authors).strip()


class Paper(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    title: str = ""
    authors: str = ""
    published_date: Optional[str] = None
    summary_raw: str = ""
    summary_structured: Optional[Any] = None
    read_status: int = 0
    added_at: str = Field(default_factory=utcnow)

    @field_validator("id")
    @classmethod
    def _canonical_id(cls, value: str) -> str:
        return normalize_arxiv_id(value)

    @field_validator("read_status")
    @classmethod
    def _read_flag(cls, value: int) -> int:
        if value not in (0, 1):
            raise ValueError("read_status must be 0 (unread) or 1 (read).")
        return value


class PaperDatabase:
    """CRUD + conflict-safe upsert over ``mle_knowledge.db``."""

    def __init__(self, path: Union[str, Path, None] = None) -> None:
        self.path = Path(path) if path is not None else DEFAULT_DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._db() as conn:
            conn.executescript(SCHEMA)

    def create_paper(
        self,
        *,
        id: str,
        title: str,
        authors: Union[str, list[str]] = "",
        published_date: Optional[str] = None,
        summary_raw: str = "",
        summary_structured: Any = None,
        read_status: int = 0,
    ) -> Paper:
        """Insert a new paper. Raises ``ValueError`` if the ArXiv id exists."""
        paper = Paper(
            id=id,
            title=title,
            authors=_authors_to_text(authors),
            published_date=published_date,
            summary_raw=summary_raw or "",
            summary_structured=summary_structured,
            read_status=read_status,
        )
        try:
            with self._db() as conn:
                conn.execute(
                    """
                    INSERT INTO papers (
                        id, title, authors, published_date,
                        summary_raw, summary_structured, read_status, added_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        paper.id,
                        paper.title,
                        paper.authors,
                        paper.published_date,
                        paper.summary_raw,
                        _dump_structured(paper.summary_structured),
                        paper.read_status,
                        paper.added_at,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                f"Paper {paper.id!r} already exists. Use upsert_paper() for re-ingestion."
            ) from exc
        stored = self.get_paper(paper.id)
        assert stored is not None
        return stored

    def get_paper(self, paper_id: str) -> Optional[Paper]:
        canonical = normalize_arxiv_id(paper_id)
        with self._db() as conn:
            row = conn.execute(
                "SELECT * FROM papers WHERE id = ?", (canonical,)
            ).fetchone()
        return None if row is None else self._from_row(row)

    def list_papers(
        self,
        *,
        read_status: Optional[int] = None,
        query: str = "",
        limit: Optional[int] = None,
    ) -> list[Paper]:
        sql = "SELECT * FROM papers"
        clauses: list[str] = []
        params: list[Any] = []
        if read_status is not None:
            clauses.append("read_status = ?")
            params.append(int(read_status))
        if query.strip():
            like = f"%{query.strip()}%"
            clauses.append("(title LIKE ? OR authors LIKE ? OR summary_raw LIKE ?)")
            params.extend([like, like, like])
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY added_at DESC, published_date DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        with self._db() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._from_row(row) for row in rows]

    def update_paper(self, paper_id: str, **fields: Any) -> Paper:
        """Patch selected columns. ``id`` and ``added_at`` are not writable."""
        allowed = {
            "title",
            "authors",
            "published_date",
            "summary_raw",
            "summary_structured",
            "read_status",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"Cannot update fields: {sorted(unknown)}")
        if not fields:
            paper = self.get_paper(paper_id)
            if paper is None:
                raise KeyError(f"No paper with id {paper_id!r}")
            return paper

        canonical = normalize_arxiv_id(paper_id)
        assignments: list[str] = []
        params: list[Any] = []
        for key, value in fields.items():
            if key == "authors":
                value = _authors_to_text(value)
            elif key == "summary_structured":
                value = _dump_structured(value)
            elif key == "read_status":
                value = Paper(id=canonical, read_status=value).read_status
            assignments.append(f"{key} = ?")
            params.append(value)
        params.append(canonical)
        with self._db() as conn:
            cur = conn.execute(
                f"UPDATE papers SET {', '.join(assignments)} WHERE id = ?",
                params,
            )
            if cur.rowcount == 0:
                raise KeyError(f"No paper with id {paper_id!r}")
        paper = self.get_paper(canonical)
        assert paper is not None
        return paper

    def delete_paper(self, paper_id: str) -> bool:
        canonical = normalize_arxiv_id(paper_id)
        with self._db() as conn:
            cur = conn.execute("DELETE FROM papers WHERE id = ?", (canonical,))
            return cur.rowcount > 0

    def upsert_paper(
        self,
        *,
        id: str,
        title: str,
        authors: Union[str, list[str]] = "",
        published_date: Optional[str] = None,
        summary_raw: str = "",
        summary_structured: Any = None,
        read_status: Optional[int] = None,
    ) -> Paper:
        """Insert or update by canonical ArXiv id without duplicating rows.

        Consecutive ingestions of the same paper (URL vs bare id, ``v1`` vs
        ``v7``, a second crawl) update title/authors/summaries in place.
        ``read_status`` and ``added_at`` are preserved unless ``read_status``
        is passed explicitly.
        """
        canonical = normalize_arxiv_id(id)
        authors_text = _authors_to_text(authors)
        structured = _dump_structured(summary_structured)
        now = utcnow()
        status = 0 if read_status is None else Paper(id=canonical, read_status=read_status).read_status

        with self._db() as conn:
            conn.execute(
                """
                INSERT INTO papers (
                    id, title, authors, published_date,
                    summary_raw, summary_structured, read_status, added_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    authors = excluded.authors,
                    published_date = excluded.published_date,
                    summary_raw = excluded.summary_raw,
                    summary_structured = excluded.summary_structured,
                    read_status = CASE
                        WHEN ? IS NOT NULL THEN excluded.read_status
                        ELSE papers.read_status
                    END
                """,
                (
                    canonical,
                    title,
                    authors_text,
                    published_date,
                    summary_raw or "",
                    structured,
                    status,
                    now,
                    read_status,
                ),
            )
        paper = self.get_paper(canonical)
        assert paper is not None
        return paper

    def set_read_status(self, paper_id: str, read_status: int) -> Paper:
        return self.update_paper(paper_id, read_status=read_status)

    def count(self) -> int:
        with self._db() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0])

    def save_pulse(self, items: list[dict[str, Any]]) -> str:
        stamp = utcnow()
        with self._db() as conn:
            conn.execute(
                "INSERT INTO pulse_snapshots(fetched_at, payload) VALUES (?, ?)",
                (stamp, json.dumps(items, ensure_ascii=False)),
            )
        return stamp

    def latest_pulse(self) -> Optional[dict[str, Any]]:
        with self._db() as conn:
            row = conn.execute(
                "SELECT fetched_at, payload FROM pulse_snapshots ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        try:
            items = json.loads(row["payload"])
        except json.JSONDecodeError:
            items = []
        if not isinstance(items, list):
            items = []
        return {"fetched_at": str(row["fetched_at"]), "items": items}

    def get_setting(self, key: str, default: str = "") -> str:
        with self._db() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return default if row is None else str(row["value"])

    def set_setting(self, key: str, value: str) -> None:
        with self._db() as conn:
            conn.execute(
                """
                INSERT INTO settings(key, value) VALUES(?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def get_stack(self) -> list[str]:
        raw = self.get_setting("stack", "[]")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if isinstance(value, list):
            return [str(v) for v in value if str(v).strip()]
        return []

    def save_memo(
        self,
        item_key: str,
        stack_key: str,
        *,
        verdict: str,
        constraint_note: str,
        so_what: str,
        paper_url: str = "",
        origin: str = "heuristic",
    ) -> None:
        with self._db() as conn:
            conn.execute(
                """
                INSERT INTO decision_memos(
                    item_key, stack_key, verdict, constraint_note, so_what,
                    paper_url, origin, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(item_key, stack_key) DO UPDATE SET
                    verdict = excluded.verdict,
                    constraint_note = excluded.constraint_note,
                    so_what = excluded.so_what,
                    paper_url = excluded.paper_url,
                    origin = excluded.origin,
                    created_at = excluded.created_at
                """,
                (
                    item_key,
                    stack_key,
                    verdict,
                    constraint_note,
                    so_what,
                    paper_url,
                    origin,
                    utcnow(),
                ),
            )

    def get_memo(self, item_key: str, stack_key: str) -> Optional[dict[str, Any]]:
        with self._db() as conn:
            row = conn.execute(
                "SELECT * FROM decision_memos WHERE item_key = ? AND stack_key = ?",
                (item_key, stack_key),
            ).fetchone()
        if row is None:
            return None
        return {k: row[k] for k in row.keys()}

    def set_stack(self, concepts: list[str]) -> None:
        cleaned = []
        seen: set[str] = set()
        for name in concepts:
            text = str(name).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            cleaned.append(text)
        self.set_setting("stack", json.dumps(cleaned, ensure_ascii=False))

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Paper:
        return Paper(
            id=row["id"],
            title=row["title"] or "",
            authors=row["authors"] or "",
            published_date=row["published_date"],
            summary_raw=row["summary_raw"] or "",
            summary_structured=_load_structured(row["summary_structured"]),
            read_status=int(row["read_status"] or 0),
            added_at=str(row["added_at"]),
        )


def get_db(path: Union[str, Path, None] = None) -> PaperDatabase:
    return PaperDatabase(path)
