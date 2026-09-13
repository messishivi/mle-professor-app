"""MLE Professor API — FastAPI service behind the Next.js frontend.

Increment 1 (P2a): app skeleton + ``/healthz`` + Papers
(list / mark-read / arXiv ingest), mirroring the Streamlit app's Saved
pane and sidebar ingest. Pulse (P2b) and Consultant (P2c) extend this
same app.

Run from the repo root:

    uvicorn api:app --port 8000
"""

from __future__ import annotations

import os
from typing import Any, Optional

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

import pipeline as ingest_pipeline
from database import PaperDatabase, get_db, normalize_arxiv_id

API_VERSION = "0.1.0"
DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"


class PaperPatch(BaseModel):
    """Fields accepted by ``PATCH /papers/{id}`` (P2a: mark-read only)."""

    read_status: int

    @field_validator("read_status")
    @classmethod
    def _flag(cls, value: int) -> int:
        if value not in (0, 1):
            raise ValueError("read_status must be 0 (unread) or 1 (read)")
        return value


class IngestRequest(BaseModel):
    """Body for ``POST /papers/ingest`` (same knobs as the Streamlit sidebar)."""

    categories: Optional[list[str]] = None
    max_results: int = Field(default=20, ge=1, le=100)


def create_app(store: Optional[PaperDatabase] = None) -> FastAPI:
    """Build the API. ``store`` is injectable so tests use a temp database."""
    app = FastAPI(title="MLE Professor API", version=API_VERSION)
    db = store or get_db()

    origins = [
        origin.strip()
        for origin in os.getenv("API_CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {"status": "ok", "service": "mle-professor-api", "papers": db.count()}

    @app.get("/papers")
    def list_papers(
        q: str = "",
        read: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict[str, Any]:
        """Same list as the Streamlit Saved pane (app.py: ``list_papers(read_status, query)``)."""
        if read is not None and read not in (0, 1):
            raise HTTPException(status_code=400, detail="read must be 0 (unread) or 1 (read)")
        papers = db.list_papers(read_status=read, query=q, limit=limit)
        return {"count": len(papers), "papers": [p.model_dump() for p in papers]}

    @app.get("/papers/{paper_id}")
    def get_paper(paper_id: str) -> dict[str, Any]:
        try:
            canonical = normalize_arxiv_id(paper_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Could not parse ArXiv id: {paper_id!r}")
        paper = db.get_paper(canonical)
        if paper is None:
            raise HTTPException(status_code=404, detail=f"No paper with id {canonical!r}")
        return paper.model_dump()

    @app.patch("/papers/{paper_id}")
    def patch_paper(paper_id: str, payload: PaperPatch) -> dict[str, Any]:
        try:
            paper = db.update_paper(paper_id, read_status=payload.read_status)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"No paper with id {paper_id!r}")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return paper.model_dump()

    @app.post("/papers/ingest")
    def ingest(payload: IngestRequest = IngestRequest()) -> dict[str, Any]:
        """ArXiv Atom ingest (pipeline.fetch_latest_papers), same as the sidebar button."""
        try:
            result = ingest_pipeline.fetch_latest_papers(
                payload.categories, payload.max_results, db=db
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except requests.RequestException as exc:
            raise HTTPException(status_code=502, detail=f"ArXiv API request failed: {exc}")
        return result.model_dump()

    return app


app = create_app()
