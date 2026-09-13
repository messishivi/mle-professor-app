"""P2a: API skeleton + Papers (list / mark-read / arXiv ingest)."""

from pathlib import Path
from unittest.mock import patch

import pytest
import requests
from fastapi.testclient import TestClient

from api import create_app
from database import PaperDatabase

FIXTURE = Path(__file__).parent / "fixtures" / "arxiv_feed.xml"


@pytest.fixture
def client(tmp_path: Path):
    db = PaperDatabase(tmp_path / "mle_knowledge.db")
    with TestClient(create_app(db)) as test_client:
        yield test_client


def _seed(db: PaperDatabase, **overrides) -> str:
    fields = dict(
        id="1706.03762",
        title="Attention Is All You Need",
        authors="Ashish Vaswani, Noam Shazeer",
        published_date="2017-06-12",
        summary_raw="Transformer abstract.",
    )
    fields.update(overrides)
    return db.create_paper(**fields).id


def test_healthz_reports_ok_and_paper_count(client, tmp_path: Path):
    db = PaperDatabase(tmp_path / "mle_knowledge.db")
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "mle-professor-api"
    assert body["papers"] == 0
    _seed(db)
    assert client.get("/healthz").json()["papers"] == 1


def test_list_papers_empty(client):
    response = client.get("/papers")
    assert response.status_code == 200
    assert response.json() == {"count": 0, "papers": []}


def test_list_papers_filters_match_streamlit_saved_pane(client, tmp_path: Path):
    db = PaperDatabase(tmp_path / "mle_knowledge.db")
    _seed(db)
    _seed(
        db,
        id="1512.03385",
        title="Deep Residual Learning",
        authors="Kaiming He",
        published_date="2015-12-10",
        summary_raw="ResNet abstract.",
    )
    db.set_read_status("1512.03385", 1)

    body = client.get("/papers").json()
    assert body["count"] == 2
    assert {p["id"] for p in body["papers"]} == {"1706.03762", "1512.03385"}

    by_query = client.get("/papers", params={"q": "ResNet"}).json()
    assert [p["id"] for p in by_query["papers"]] == ["1512.03385"]

    unread = client.get("/papers", params={"read": 0}).json()
    assert [p["id"] for p in unread["papers"]] == ["1706.03762"]

    read = client.get("/papers", params={"read": 1}).json()
    assert [p["id"] for p in read["papers"]] == ["1512.03385"]

    limited = client.get("/papers", params={"limit": 1}).json()
    assert limited["count"] == 1


def test_list_papers_rejects_bad_read_flag(client):
    assert client.get("/papers", params={"read": 2}).status_code == 400


def test_get_paper_returns_full_record_or_404(client, tmp_path: Path):
    db = PaperDatabase(tmp_path / "mle_knowledge.db")
    _seed(db)

    # Canonical id, prefix and version variants all resolve to the same row.
    # (URL form is intentionally not a path parameter: '/' cannot appear in
    # a path segment; the frontend sends paper.id, which is canonical.)
    for ref in ("1706.03762", "arxiv:1706.03762v7", "ARXIV:1706.03762"):
        response = client.get(f"/papers/{ref}")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == "1706.03762"
        assert body["title"] == "Attention Is All You Need"
        assert body["read_status"] == 0

    assert client.get("/papers/2106.12345").status_code == 404
    assert client.get("/papers/not-an-id").status_code == 400


def test_patch_read_status_marks_and_unmarks(client, tmp_path: Path):
    db = PaperDatabase(tmp_path / "mle_knowledge.db")
    _seed(db)

    marked = client.patch("/papers/1706.03762", json={"read_status": 1})
    assert marked.status_code == 200
    assert marked.json()["read_status"] == 1
    assert db.get_paper("1706.03762").read_status == 1

    unmarked = client.patch("/papers/1706.03762", json={"read_status": 0})
    assert unmarked.status_code == 200
    assert unmarked.json()["read_status"] == 0

    # Version-suffixed ids work too (normalization parity with Streamlit).
    assert client.patch("/papers/arxiv:1706.03762v7", json={"read_status": 1}).status_code == 200

    assert client.patch("/papers/2106.12345", json={"read_status": 1}).status_code == 404
    assert client.patch("/papers/not-an-id", json={"read_status": 1}).status_code == 400
    assert client.patch("/papers/1706.03762", json={"read_status": 2}).status_code == 422
    assert client.patch("/papers/1706.03762", json={}).status_code == 422


def test_ingest_upserts_arxiv_feed_and_is_idempotent(client, tmp_path: Path):
    db = PaperDatabase(tmp_path / "mle_knowledge.db")
    xml = FIXTURE.read_bytes()

    with patch("pipeline.fetch_atom_xml", return_value=xml):
        response = client.post("/papers/ingest", json={"categories": ["cs.CL", "cs.LG"]})
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "cat:cs.CL OR cat:cs.LG"
    assert body["fetched"] == 2
    assert body["upserted"] == 2
    assert body["skipped"] == 1
    assert db.count() == 2

    with patch("pipeline.fetch_atom_xml", return_value=xml):
        again = client.post("/papers/ingest").json()
    assert db.count() == 2
    assert again["upserted"] == 2


def test_ingest_rejects_bad_parameters(client):
    assert client.post("/papers/ingest", json={"categories": ["bad;cat"]}).status_code == 400
    assert client.post("/papers/ingest", json={"max_results": 0}).status_code == 422
    assert client.post("/papers/ingest", json={"max_results": 500}).status_code == 422


def test_ingest_maps_arxiv_network_failure_to_502(client, tmp_path: Path):
    with patch("pipeline.fetch_atom_xml", side_effect=requests.ConnectionError("blocked")):
        response = client.post("/papers/ingest")
    assert response.status_code == 502
    assert "ArXiv API request failed" in response.json()["detail"]
