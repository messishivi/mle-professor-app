"""MLE Professor API — FastAPI service behind the Next.js frontend.

Increments so far:
- P2a: app skeleton + ``/healthz`` + Papers (list / mark-read / arXiv ingest),
  mirroring the Streamlit app's Saved pane and sidebar ingest.
- P2b: ML Pulse (``/pulse``, ``/pulse/refresh``, ``/pulse/memos/refine``) and
  sidebar settings (``/settings``, ``/settings/repo-readme``), mirroring
  ``app.render_ml_pulse`` and the sidebar stack/application/repo state.

Consultant (P2c) extends this same app.

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
from demo import demo_enabled, seed_demo_data
from repo import fetch_readme
from trends import (
    STACK_CHOICES,
    PulseItem,
    draft_decision_memo,
    load_pulse,
    memo_item_key,
    refresh_pulse,
    refine_decision_memo,
    score_against_stack,
    stack_key,
)

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


class MemoRefineRequest(BaseModel):
    """Body for ``POST /pulse/memos/refine`` (one pulse item + the active stack)."""

    item: PulseItem
    stack: list[str] = Field(default_factory=list)


class SettingsUpdate(BaseModel):
    """Body for ``PUT /settings`` — partial: only the provided fields change."""

    stack: Optional[list[str]] = None
    application: Optional[str] = None
    known_papers: Optional[str] = None
    repo_url: Optional[str] = None


class RepoReadmeRequest(BaseModel):
    """Body for ``POST /settings/repo-readme`` — optional URL override."""

    url: Optional[str] = None


def _pulse_payload(db: PaperDatabase, snap=None) -> dict[str, Any]:
    """Assemble a pulse snapshot the way ``app.render_ml_pulse`` does:
    stack fit per item, then the saved memo (or a fresh heuristic draft).

    ``snap`` defaults to the saved snapshot; the refresh endpoint passes the
    live snapshot it just computed so its ``errors`` reach the response
    (save_pulse does not persist them)."""
    if snap is None:
        snap = load_pulse(db)
    stack = db.get_stack()
    items: list[dict[str, Any]] = []
    if snap is not None:
        for item in snap.items:
            fit = score_against_stack(item, stack)
            saved = db.get_memo(memo_item_key(item), stack_key(stack))
            if saved is not None:
                memo = {
                    "verdict": saved["verdict"],
                    "constraint_note": saved["constraint_note"],
                    "so_what": saved["so_what"],
                    "paper_url": saved.get("paper_url", ""),
                    "origin": saved.get("origin", "heuristic"),
                }
            else:
                memo = draft_decision_memo(item, fit, stack).as_dict()
            items.append(
                {
                    **item.model_dump(),
                    "fit": {
                        "label": fit.label,
                        "score": fit.score,
                        "so_what": fit.so_what,
                    },
                    "memo": memo,
                }
            )
    return {
        "fetched_at": snap.fetched_at if snap is not None else None,
        "items": items,
        "errors": list(snap.errors) if snap is not None else [],
        "stack": stack,
    }


def _settings_payload(db: PaperDatabase) -> dict[str, Any]:
    return {
        "stack": db.get_stack(),
        "stack_choices": list(STACK_CHOICES),
        "application": db.get_application(),
        "known_papers": db.get_known_papers(),
        "repo_url": db.get_repo_url(),
        "repo_readme_url": db.get_repo_readme_url(),
        "repo_readme_chars": len(db.get_repo_readme()),
    }


def create_app(store: Optional[PaperDatabase] = None) -> FastAPI:
    """Build the API. ``store`` is injectable so tests use a temp database."""
    app = FastAPI(title="MLE Professor API", version=API_VERSION)
    db = store or get_db()

    # Demo mode parity: Streamlit seeds the sample library on startup when
    # MLE_DEMO_MODE is set and the library is empty (demo.seed_demo_data).
    if demo_enabled():
        seed_demo_data(db)

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

    @app.get("/pulse")
    def pulse() -> dict[str, Any]:
        """Latest saved ML Pulse snapshot with stack fit + memos (render_ml_pulse parity)."""
        return _pulse_payload(db)

    @app.post("/pulse/refresh")
    def pulse_refresh() -> dict[str, Any]:
        """Refresh HF Daily + arXiv ML feeds and save a new snapshot
        (the 'Refresh ML Pulse' button in app.py)."""
        snap = refresh_pulse(db)
        return _pulse_payload(db, snap=snap)

    @app.post("/pulse/memos/refine")
    def memo_refine(payload: MemoRefineRequest) -> dict[str, Any]:
        """Refine the decision memo for one pulse item (Groq pass with a
        heuristic fallback), then persist it — the 'Refine' button parity."""
        stack = [s.strip() for s in payload.stack if s.strip()]
        item = payload.item
        fit = score_against_stack(item, stack)
        draft = draft_decision_memo(item, fit, stack)
        memo = refine_decision_memo(item, fit, stack, draft)
        item_key = memo_item_key(item)
        skey = stack_key(stack)
        db.save_memo(item_key, skey, **memo.as_dict())
        return {"item_key": item_key, "stack_key": skey, "memo": memo.as_dict()}

    @app.get("/settings")
    def get_settings() -> dict[str, Any]:
        """Sidebar state: stack, application, known papers, repo grounding."""
        return _settings_payload(db)

    @app.put("/settings")
    def put_settings(payload: SettingsUpdate) -> dict[str, Any]:
        """Partial update of sidebar state. Changing the repo URL invalidates
        the cached README (same rule as the Streamlit sidebar)."""
        if payload.stack is not None:
            db.set_stack(payload.stack)
        if payload.application is not None:
            db.set_application(payload.application)
        if payload.known_papers is not None:
            db.set_known_papers(payload.known_papers)
        if payload.repo_url is not None:
            new_url = payload.repo_url.strip()
            if new_url != db.get_repo_url():
                db.set_repo_url(new_url)
                db.set_repo_readme("", source_url="")
        return _settings_payload(db)

    @app.post("/settings/repo-readme")
    def load_repo_readme(
        payload: RepoReadmeRequest = RepoReadmeRequest(),
    ) -> dict[str, Any]:
        """Fetch the GitHub/GitLab README for the repo URL (sidebar 'Load README')."""
        url = (payload.url or db.get_repo_url() or "").strip()
        if not url:
            raise HTTPException(status_code=400, detail="No repo URL set. Set it in settings first.")
        try:
            readme = fetch_readme(url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except requests.RequestException as exc:
            raise HTTPException(status_code=502, detail=f"README fetch failed: {exc}")
        db.set_repo_readme(readme.content, source_url=readme.readme_url)
        return {
            "repo_url": url,
            "readme_url": readme.readme_url,
            "chars": len(readme.content),
        }

    return app


app = create_app()
