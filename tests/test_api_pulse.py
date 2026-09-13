"""P2b: ML Pulse + sidebar settings endpoints — parity with app.py.

Parity anchors:
- ``app.render_ml_pulse``: load snapshot, per-item stack fit, saved memo or
  heuristic draft (trends.score_against_stack / draft_decision_memo).
- Sidebar: stack multiselect (STACK_CHOICES), application, known papers,
  repo URL + README (repo.fetch_readme; a repo change clears the README).

Network seams: ``trends.fetch_hf_daily`` and ``trends.fetch_atom_xml`` are
patched (the module-level import in trends.py), and GROQ_API_KEY is removed
so the keyless heuristic path runs (no clustering LLM call).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests
from fastapi.testclient import TestClient

import trends
from api import create_app
from database import PaperDatabase
from repo import RepoReadme
from trends import PULSE_ITEM_LIMIT, RawSignal

FRESH_DAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _recent_atom_xml() -> bytes:
    """Atom feed with <published> dates inside the 60-day pulse window.

    Dates are generated relative to "now" so the fixture does not rot.
    """
    now = datetime.now(timezone.utc)
    d1 = (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    d2 = (now - timedelta(days=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <title>ArXiv Query: pulse test</title>
  <entry>
    <id>http://arxiv.org/abs/2609.10001v1</id>
    <published>{d1}</published>
    <title>Sparse Mixture of Experts routing for edge inference</title>
    <summary>A router that activates a sparse mixture of experts on-device.</summary>
    <author><name>Test Author</name></author>
    <arxiv:primary_category term="cs.LG"/>
    <category term="cs.LG" scheme="http://arxiv.org/schemas/atom"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2609.10002v1</id>
    <published>{d2}</published>
    <title>Quantizing adapters with 4-bit LoRA for production serving</title>
    <summary>Int4 quantization of LoRA adapters with serving-aware eval.</summary>
    <author><name>Other Author</name></author>
    <arxiv:primary_category term="cs.LG"/>
    <category term="cs.LG" scheme="http://arxiv.org/schemas/atom"/>
  </entry>
</feed>
""".encode("utf-8")


def _hf_signals() -> list[RawSignal]:
    """Two HF Daily signals; the second duplicates an arXiv feed entry
    (must be deduped by paper_id in refresh_pulse)."""
    return [
        RawSignal(
            paper_id="2609.20001",
            title="Speculative decoding with a draft model on constrained GPUs",
            abstract="A draft model proposes tokens for speculative decoding.",
            authors="HF Author",
            source="hf_daily",
            url="https://arxiv.org/abs/2609.20001",
            published=FRESH_DAY,
        ),
        RawSignal(
            paper_id="2609.10001",
            title="Sparse Mixture of Experts routing for edge inference",
            abstract="A router that activates a sparse mixture of experts on-device.",
            authors="Test Author",
            source="hf_daily",
            url="https://arxiv.org/abs/2609.10001",
            published=FRESH_DAY,
        ),
    ]


@pytest.fixture
def db(tmp_path) -> PaperDatabase:
    return PaperDatabase(tmp_path / "mle_knowledge.db")


@pytest.fixture
def client(db) -> TestClient:
    with TestClient(create_app(db)) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Hermetic: no LLM key, no demo mode."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("MLE_DEMO_MODE", raising=False)


# ---------------------------------------------------------------- /pulse


def test_pulse_empty_without_snapshot(client):
    res = client.get("/pulse")
    assert res.status_code == 200
    body = res.json()
    assert body["fetched_at"] is None
    assert body["items"] == []
    assert body["errors"] == []
    assert body["stack"] == []


def test_refresh_pulse_keyless_builds_heuristic_items(client, db):
    """Keyless path: heuristic clustering, dedupe, in_library flags,
    Set-stack fit, watch verdicts — all identical to the Streamlit pane."""
    db.upsert_paper(
        id="2609.20001",
        title="Speculative decoding paper",
        authors="A",
        published_date=FRESH_DAY,
        summary_raw="draft model speculative decoding",
    )
    with (
        patch("trends.fetch_hf_daily", lambda limit=20: _hf_signals()),
        patch("trends.fetch_atom_xml", lambda *a, **k: _recent_atom_xml()),
    ):
        res = client.post("/pulse/refresh")
    assert res.status_code == 200
    body = res.json()
    assert body["fetched_at"]
    assert body["errors"] == []
    # 2 HF + 2 arXiv signals, one paper_id duplicate -> 3 unique items
    by_id = {i["paper_id"]: i for i in body["items"]}
    assert sorted(by_id) == ["2609.10001", "2609.10002", "2609.20001"]

    # Concept matching is trends.match_concept, exactly as the pane does it
    assert by_id["2609.10001"]["concept"] == "Mixture of Experts"
    assert by_id["2609.10002"]["concept"] == "Quantization"
    assert by_id["2609.20001"]["concept"] == "Speculative decoding"
    assert by_id["2609.20001"]["in_library"] is True
    assert by_id["2609.10001"]["in_library"] is False

    # No stack set -> every item gets the neutral fit + a heuristic watch memo
    for item in body["items"]:
        assert item["fit"]["label"] == "Set stack"
        assert item["fit"]["score"] == 40
        assert item["memo"]["verdict"] == "watch"
        assert item["memo"]["origin"] == "heuristic"

    # Snapshot is persisted: GET /pulse returns the same items (load_pulse)
    snap = client.get("/pulse").json()
    assert sorted(i["paper_id"] for i in snap["items"]) == sorted(by_id)
    assert snap["fetched_at"] == body["fetched_at"]


def test_refresh_collects_source_errors(client):
    def boom(limit=20):
        raise RuntimeError("HF down")

    with (
        patch("trends.fetch_hf_daily", boom),
        patch("trends.fetch_atom_xml", lambda *a, **k: _recent_atom_xml()),
    ):
        res = client.post("/pulse/refresh")
    assert res.status_code == 200
    body = res.json()
    # Parity: per-source failures are reported, the other source still lands
    assert any("Hugging Face Daily Papers" in e for e in body["errors"])
    assert {i["paper_id"] for i in body["items"]} == {"2609.10001", "2609.10002"}


def test_refresh_caps_items_at_limit(client):
    signals = [
        RawSignal(
            paper_id=f"2609.3000{i}",
            title=f"Paper {i} about transformers and attention",
            abstract="",
            authors="",
            source="hf_daily",
            url="",
            published=FRESH_DAY,
        )
        for i in range(40)
    ]
    with (
        patch("trends.fetch_hf_daily", lambda limit=20: signals),
        patch("trends.fetch_atom_xml", lambda *a, **k: _recent_atom_xml()),
    ):
        res = client.post("/pulse/refresh")
    assert res.status_code == 200
    assert len(res.json()["items"]) == PULSE_ITEM_LIMIT


def test_pulse_get_surfaces_saved_memo_and_fit(client, db):
    """render_ml_pulse parity: saved memo wins over the draft; fit labels
    follow score_against_stack (High fit in-stack / Skip off-stack)."""
    with (
        patch("trends.fetch_hf_daily", lambda limit=20: _hf_signals()),
        patch("trends.fetch_atom_xml", lambda *a, **k: _recent_atom_xml()),
    ):
        client.post("/pulse/refresh")
    db.set_stack(["Mixture of Experts"])
    db.save_memo(
        "2609.10001",
        trends.stack_key(["Mixture of Experts"]),
        verdict="adopt",
        constraint_note="Serving cost is routing + all-to-all bandwidth.",
        so_what="Design input.",
        paper_url="https://arxiv.org/abs/2609.10001",
        origin="groq",
    )
    body = client.get("/pulse").json()
    assert body["stack"] == ["Mixture of Experts"]
    moe = next(i for i in body["items"] if i["paper_id"] == "2609.10001")
    assert moe["fit"]["label"] == "High fit"
    assert moe["memo"]["verdict"] == "adopt"
    assert moe["memo"]["origin"] == "groq"
    spec = next(i for i in body["items"] if i["paper_id"] == "2609.20001")
    assert spec["fit"]["label"] == "Skip"
    assert spec["memo"]["verdict"] == "skip"  # draft heuristic for off-stack


# ------------------------------------------------- /pulse/memos/refine


def _pulse_item() -> dict:
    return {
        "topic": "LoRA adapter serving",
        "why": "Why it matters",
        "paper_id": "2609.40001",
        "paper_title": "Serving LoRA adapters in production",
        "paper_url": "https://arxiv.org/abs/2609.40001",
        "concept": "LoRA / adapters",
        "concept_blurb": "Training a thin low-rank update instead of the full network.",
        "in_library": False,
        "source": "hf_daily",
        "abstract": "LoRA adapters with serving eval.",
        "published_date": FRESH_DAY,
    }


def test_memo_refine_keyless_saves_heuristic_memo(client, db):
    res = client.post(
        "/pulse/memos/refine",
        json={"item": _pulse_item(), "stack": ["LoRA / adapters"]},
    )
    assert res.status_code == 200
    body = res.json()
    # High fit (concept in stack) + not in library -> prototype
    assert body["memo"]["verdict"] == "prototype"
    assert body["memo"]["origin"] == "heuristic"
    assert body["memo"]["paper_url"] == "https://arxiv.org/abs/2609.40001"
    assert body["item_key"] == "2609.40001"
    saved = db.get_memo(body["item_key"], body["stack_key"])
    assert saved is not None
    assert saved["verdict"] == "prototype"
    assert saved["origin"] == "heuristic"


def test_memo_refine_verdicts_follow_fit(client):
    res = client.post(
        "/pulse/memos/refine",
        json={"item": _pulse_item(), "stack": ["Diffusion"]},
    )
    assert res.json()["memo"]["verdict"] == "skip"  # off-stack -> Skip fit

    item = _pulse_item()
    item["in_library"] = True
    res = client.post(
        "/pulse/memos/refine",
        json={"item": item, "stack": ["LoRA / adapters"]},
    )
    assert res.json()["memo"]["verdict"] == "adopt"  # High fit + in library


def test_memo_refine_rejects_missing_topic(client):
    item = _pulse_item()
    del item["topic"]
    res = client.post("/pulse/memos/refine", json={"item": item})
    assert res.status_code == 422


# ------------------------------------------------------------ /settings


def test_get_settings_defaults(client):
    res = client.get("/settings")
    assert res.status_code == 200
    body = res.json()
    assert body["stack"] == []
    assert body["application"] == ""
    assert body["known_papers"] == ""
    assert body["repo_url"] == ""
    assert body["repo_readme_url"] == ""
    assert body["repo_readme_chars"] == 0
    # Same 16 canonical concepts as the Streamlit multiselect
    assert body["stack_choices"] == list(trends.STACK_CHOICES)


def test_put_settings_roundtrip_and_partial_update(client):
    res = client.put(
        "/settings",
        json={
            "stack": ["Transformers", "LoRA / adapters"],
            "application": "Two-tower recommender for a news app",
            "known_papers": "1706.03762",
            "repo_url": "https://github.com/me/rec-svc",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["stack"] == ["Transformers", "LoRA / adapters"]
    assert body["application"] == "Two-tower recommender for a news app"
    assert body["known_papers"] == "1706.03762"
    assert body["repo_url"] == "https://github.com/me/rec-svc"

    # Partial update: only the provided field changes
    body = client.put("/settings", json={"application": "RAG support bot"}).json()
    assert body["application"] == "RAG support bot"
    assert body["stack"] == ["Transformers", "LoRA / adapters"]
    assert body["repo_url"] == "https://github.com/me/rec-svc"


def test_put_settings_repo_url_change_clears_readme(client, db):
    db.set_repo_readme("# Old readme", source_url="https://github.com/me/old/README.md")
    body = client.put("/settings", json={"repo_url": "https://github.com/me/new"}).json()
    assert body["repo_url"] == "https://github.com/me/new"
    assert body["repo_readme_chars"] == 0
    assert body["repo_readme_url"] == ""


def test_put_settings_same_repo_url_keeps_readme(client, db):
    db.set_repo_url("https://github.com/me/same")
    db.set_repo_readme("# readme", source_url="https://github.com/me/same/README.md")
    body = client.put("/settings", json={"repo_url": "https://github.com/me/same"}).json()
    assert body["repo_readme_chars"] == 8


# ------------------------------------------------- /settings/repo-readme


def test_repo_readme_fetch_saves_content(client, db):
    fake = RepoReadme(
        url="https://github.com/me/rec-svc",
        readme_url="https://raw.githubusercontent.com/me/rec-svc/main/README.md",
        content="# Rec service\n",
        name="README.md",
    )
    with patch("api.fetch_readme", lambda raw, **k: fake):
        res = client.post(
            "/settings/repo-readme", json={"url": "https://github.com/me/rec-svc"}
        )
    assert res.status_code == 200
    body = res.json()
    assert body["chars"] == len("# Rec service\n")
    assert body["readme_url"].startswith("https://raw.githubusercontent.com")
    assert db.get_repo_readme() == "# Rec service\n"
    assert db.get_repo_readme_url().startswith("https://raw.githubusercontent.com")


def test_repo_readme_falls_back_to_saved_url(client, db):
    db.set_repo_url("https://gitlab.com/me/svc")
    fake = RepoReadme(url="u", readme_url="r", content="c", name="README.md")
    fetch_mock = patch("api.fetch_readme", MagicMock(return_value=fake)).start()
    try:
        res = client.post("/settings/repo-readme")
    finally:
        patch.stopall()
    assert res.status_code == 200
    fetch_mock.assert_called_once()
    assert fetch_mock.call_args.args[0] == "https://gitlab.com/me/svc"


def test_repo_readme_no_url_is_400(client):
    res = client.post("/settings/repo-readme")
    assert res.status_code == 400
    assert "No repo URL" in res.json()["detail"]


def test_repo_readme_unsupported_host_is_400(client):
    with patch("api.fetch_readme") as m:
        m.side_effect = ValueError("Unsupported repo host: example.com (github/gitlab only)")
        res = client.post(
            "/settings/repo-readme", json={"url": "https://example.com/x/y"}
        )
    assert res.status_code == 400
    assert "example.com" in res.json()["detail"]


def test_repo_readme_network_failure_is_502(client):
    with patch("api.fetch_readme") as m:
        m.side_effect = requests.ConnectionError("boom")
        res = client.post(
            "/settings/repo-readme", json={"url": "https://github.com/me/x"}
        )
    assert res.status_code == 502
