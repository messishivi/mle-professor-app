"""SQLite store for paper metadata, notes, and interview sessions."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator, Optional

SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS papers (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    external_id TEXT,
    title TEXT NOT NULL,
    authors TEXT NOT NULL DEFAULT '',
    abstract TEXT NOT NULL DEFAULT '',
    year INTEGER,
    venue TEXT,
    pdf_path TEXT,
    topics TEXT NOT NULL DEFAULT '[]',
    chunk_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE(source, external_id)
);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY,
    paper_id INTEGER REFERENCES papers(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    topics TEXT NOT NULL DEFAULT '[]',
    chunk_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS interview_sessions (
    id INTEGER PRIMARY KEY,
    mode TEXT NOT NULL,
    topic TEXT NOT NULL DEFAULT '',
    paper_id INTEGER REFERENCES papers(id) ON DELETE SET NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    score REAL,
    max_score REAL,
    item_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS interview_items (
    id INTEGER PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
    question_id TEXT,
    question TEXT NOT NULL,
    model_answer TEXT NOT NULL DEFAULT '',
    user_answer TEXT,
    evaluation TEXT,
    score REAL,
    difficulty TEXT NOT NULL DEFAULT 'medium',
    topic TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS interview_progress (
    question_id TEXT PRIMARY KEY,
    last_score REAL,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_seen TEXT
);

CREATE INDEX IF NOT EXISTS idx_papers_title ON papers(title);
CREATE INDEX IF NOT EXISTS idx_items_session ON interview_items(session_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _topics_dump(topics: list[str] | None) -> str:
    return json.dumps(topics or [], ensure_ascii=False)


def _topics_load(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(value, list):
        return [str(t) for t in value]
    return []


@dataclass
class Paper:
    id: int
    source: str
    external_id: Optional[str]
    title: str
    authors: str
    abstract: str
    year: Optional[int]
    venue: Optional[str]
    pdf_path: Optional[str]
    topics: list[str]
    chunk_count: int
    created_at: str


@dataclass
class Note:
    id: int
    paper_id: Optional[int]
    title: str
    body: str
    topics: list[str]
    chunk_count: int
    created_at: str


@dataclass
class InterviewSession:
    id: int
    mode: str
    topic: str
    paper_id: Optional[int]
    started_at: str
    completed_at: Optional[str]
    score: Optional[float]
    max_score: Optional[float]
    item_count: int


@dataclass
class InterviewItem:
    id: int
    session_id: int
    question_id: Optional[str]
    question: str
    model_answer: str
    user_answer: Optional[str]
    evaluation: Optional[str]
    score: Optional[float]
    difficulty: str
    topic: str


@dataclass
class Stats:
    papers: int = 0
    notes: int = 0
    chunks: int = 0
    sessions: int = 0
    topics: list[str] = field(default_factory=list)


class PaperStore:
    def __init__(self, path: str | Any) -> None:
        self.path = str(path)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init(self) -> None:
        with self._db() as conn:
            conn.executescript(SCHEMA)

    def get_meta(self, key: str) -> Optional[str]:
        with self._db() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
            return None if row is None else str(row["value"])

    def set_meta(self, key: str, value: str) -> None:
        with self._db() as conn:
            conn.execute(
                "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def add_paper(
        self,
        *,
        source: str,
        title: str,
        authors: str = "",
        abstract: str = "",
        external_id: Optional[str] = None,
        year: Optional[int] = None,
        venue: Optional[str] = None,
        pdf_path: Optional[str] = None,
        topics: Optional[list[str]] = None,
    ) -> int:
        with self._db() as conn:
            if external_id:
                existing = conn.execute(
                    "SELECT id FROM papers WHERE source = ? AND external_id = ?",
                    (source, external_id),
                ).fetchone()
                if existing:
                    conn.execute(
                        """
                        UPDATE papers
                        SET title = ?, authors = ?, abstract = ?, year = ?, venue = ?,
                            pdf_path = COALESCE(?, pdf_path), topics = ?
                        WHERE id = ?
                        """,
                        (
                            title,
                            authors,
                            abstract,
                            year,
                            venue,
                            pdf_path,
                            _topics_dump(topics),
                            existing["id"],
                        ),
                    )
                    return int(existing["id"])
            cur = conn.execute(
                """
                INSERT INTO papers(source, external_id, title, authors, abstract, year, venue, pdf_path, topics, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source,
                    external_id,
                    title,
                    authors,
                    abstract,
                    year,
                    venue,
                    pdf_path,
                    _topics_dump(topics),
                    _now(),
                ),
            )
            return int(cur.lastrowid)

    def set_chunk_count(self, paper_id: int, count: int) -> None:
        with self._db() as conn:
            conn.execute("UPDATE papers SET chunk_count = ? WHERE id = ?", (count, paper_id))

    def set_pdf_path(self, paper_id: int, pdf_path: str) -> None:
        with self._db() as conn:
            conn.execute("UPDATE papers SET pdf_path = ? WHERE id = ?", (pdf_path, paper_id))

    def get_paper(self, paper_id: int) -> Optional[Paper]:
        with self._db() as conn:
            row = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
            return None if row is None else self._paper(row)

    def find_by_external(self, source: str, external_id: str) -> Optional[Paper]:
        with self._db() as conn:
            row = conn.execute(
                "SELECT * FROM papers WHERE source = ? AND external_id = ?",
                (source, external_id),
            ).fetchone()
            return None if row is None else self._paper(row)

    def list_papers(self, query: str = "") -> list[Paper]:
        sql = "SELECT * FROM papers"
        params: tuple[Any, ...] = ()
        if query.strip():
            like = f"%{query.strip()}%"
            sql += " WHERE title LIKE ? OR authors LIKE ? OR abstract LIKE ? OR topics LIKE ?"
            params = (like, like, like, like)
        sql += " ORDER BY created_at DESC, id DESC"
        with self._db() as conn:
            return [self._paper(r) for r in conn.execute(sql, params).fetchall()]

    def delete_paper(self, paper_id: int) -> None:
        with self._db() as conn:
            conn.execute("DELETE FROM papers WHERE id = ?", (paper_id,))

    def add_note(
        self,
        *,
        title: str,
        body: str,
        paper_id: Optional[int] = None,
        topics: Optional[list[str]] = None,
    ) -> int:
        with self._db() as conn:
            cur = conn.execute(
                """
                INSERT INTO notes(paper_id, title, body, topics, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (paper_id, title, body, _topics_dump(topics), _now()),
            )
            return int(cur.lastrowid)

    def set_note_chunk_count(self, note_id: int, count: int) -> None:
        with self._db() as conn:
            conn.execute("UPDATE notes SET chunk_count = ? WHERE id = ?", (count, note_id))

    def get_note(self, note_id: int) -> Optional[Note]:
        with self._db() as conn:
            row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
            return None if row is None else self._note(row)

    def list_notes(self, paper_id: Optional[int] = None) -> list[Note]:
        with self._db() as conn:
            if paper_id is None:
                rows = conn.execute("SELECT * FROM notes ORDER BY created_at DESC").fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM notes WHERE paper_id = ? ORDER BY created_at DESC",
                    (paper_id,),
                ).fetchall()
            return [self._note(r) for r in rows]

    def delete_note(self, note_id: int) -> None:
        with self._db() as conn:
            conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))

    def start_session(
        self,
        *,
        mode: str,
        topic: str = "",
        paper_id: Optional[int] = None,
    ) -> int:
        with self._db() as conn:
            cur = conn.execute(
                """
                INSERT INTO interview_sessions(mode, topic, paper_id, started_at)
                VALUES (?, ?, ?, ?)
                """,
                (mode, topic, paper_id, _now()),
            )
            return int(cur.lastrowid)

    def add_item(
        self,
        session_id: int,
        *,
        question: str,
        model_answer: str = "",
        question_id: Optional[str] = None,
        difficulty: str = "medium",
        topic: str = "",
    ) -> int:
        with self._db() as conn:
            cur = conn.execute(
                """
                INSERT INTO interview_items(session_id, question_id, question, model_answer, difficulty, topic)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, question_id, question, model_answer, difficulty, topic),
            )
            conn.execute(
                "UPDATE interview_sessions SET item_count = item_count + 1 WHERE id = ?",
                (session_id,),
            )
            return int(cur.lastrowid)

    def get_session(self, session_id: int) -> Optional[InterviewSession]:
        with self._db() as conn:
            row = conn.execute(
                "SELECT * FROM interview_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            return None if row is None else self._session(row)

    def list_sessions(self, limit: int = 20) -> list[InterviewSession]:
        with self._db() as conn:
            rows = conn.execute(
                "SELECT * FROM interview_sessions ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [self._session(r) for r in rows]

    def list_items(self, session_id: int) -> list[InterviewItem]:
        with self._db() as conn:
            rows = conn.execute(
                "SELECT * FROM interview_items WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
            return [self._item(r) for r in rows]

    def record_answer(
        self,
        item_id: int,
        *,
        user_answer: str,
        evaluation: str,
        score: float,
    ) -> None:
        with self._db() as conn:
            conn.execute(
                """
                UPDATE interview_items
                SET user_answer = ?, evaluation = ?, score = ?
                WHERE id = ?
                """,
                (user_answer, evaluation, score, item_id),
            )
            row = conn.execute(
                "SELECT question_id FROM interview_items WHERE id = ?", (item_id,)
            ).fetchone()
            qid = row["question_id"] if row else None
            if qid:
                conn.execute(
                    """
                    INSERT INTO interview_progress(question_id, last_score, attempts, last_seen)
                    VALUES (?, ?, 1, ?)
                    ON CONFLICT(question_id) DO UPDATE SET
                        last_score = excluded.last_score,
                        attempts = interview_progress.attempts + 1,
                        last_seen = excluded.last_seen
                    """,
                    (qid, score, _now()),
                )

    def complete_session(self, session_id: int) -> InterviewSession:
        with self._db() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(score), 0) AS s, COUNT(*) AS n FROM interview_items WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            score = float(row["s"] or 0)
            n = int(row["n"] or 0)
            conn.execute(
                """
                UPDATE interview_sessions
                SET completed_at = ?, score = ?, max_score = ?
                WHERE id = ?
                """,
                (_now(), score, float(n * 5), session_id),
            )
        session = self.get_session(session_id)
        assert session is not None
        return session

    def stats(self) -> Stats:
        with self._db() as conn:
            papers = int(conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0])
            notes = int(conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0])
            chunks = int(
                conn.execute(
                    "SELECT COALESCE(SUM(chunk_count), 0) FROM papers"
                ).fetchone()[0]
            ) + int(
                conn.execute(
                    "SELECT COALESCE(SUM(chunk_count), 0) FROM notes"
                ).fetchone()[0]
            )
            sessions = int(
                conn.execute("SELECT COUNT(*) FROM interview_sessions").fetchone()[0]
            )
            topic_rows = conn.execute("SELECT topics FROM papers").fetchall()
        bag: dict[str, int] = {}
        for row in topic_rows:
            for t in _topics_load(row["topics"]):
                bag[t] = bag.get(t, 0) + 1
        topics = [k for k, _ in sorted(bag.items(), key=lambda kv: (-kv[1], kv[0]))]
        return Stats(
            papers=papers, notes=notes, chunks=chunks, sessions=sessions, topics=topics
        )

    @staticmethod
    def _paper(row: sqlite3.Row) -> Paper:
        return Paper(
            id=int(row["id"]),
            source=row["source"],
            external_id=row["external_id"],
            title=row["title"],
            authors=row["authors"] or "",
            abstract=row["abstract"] or "",
            year=row["year"],
            venue=row["venue"],
            pdf_path=row["pdf_path"],
            topics=_topics_load(row["topics"]),
            chunk_count=int(row["chunk_count"] or 0),
            created_at=row["created_at"],
        )

    @staticmethod
    def _note(row: sqlite3.Row) -> Note:
        return Note(
            id=int(row["id"]),
            paper_id=row["paper_id"],
            title=row["title"],
            body=row["body"],
            topics=_topics_load(row["topics"]),
            chunk_count=int(row["chunk_count"] or 0),
            created_at=row["created_at"],
        )

    @staticmethod
    def _session(row: sqlite3.Row) -> InterviewSession:
        return InterviewSession(
            id=int(row["id"]),
            mode=row["mode"],
            topic=row["topic"] or "",
            paper_id=row["paper_id"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            score=row["score"],
            max_score=row["max_score"],
            item_count=int(row["item_count"] or 0),
        )

    @staticmethod
    def _item(row: sqlite3.Row) -> InterviewItem:
        return InterviewItem(
            id=int(row["id"]),
            session_id=int(row["session_id"]),
            question_id=row["question_id"],
            question=row["question"],
            model_answer=row["model_answer"] or "",
            user_answer=row["user_answer"],
            evaluation=row["evaluation"],
            score=row["score"],
            difficulty=row["difficulty"] or "medium",
            topic=row["topic"] or "",
        )
