import types
from pathlib import Path
from unittest.mock import patch

import pytest
import requests

from database import PaperDatabase
from pipeline import (
    ARXIV_BACKOFF_CAP,
    ARXIV_BACKOFF_BASE,
    arxiv_backoff_delay,
    build_category_query,
    fetch_atom_xml,
    fetch_latest_papers,
    parse_atom_feed,
)

FIXTURE = Path(__file__).parent / "fixtures" / "arxiv_feed.xml"


def _fake_response(status_code, headers=None):
    """Minimal stand-in for ``requests.Response`` (status/content/headers)."""
    resp = types.SimpleNamespace(
        status_code=status_code,
        content=b"<feed>ok</feed>",
        headers=dict(headers or {}),
    )

    def raise_for_status():
        if status_code >= 400:
            raise requests.HTTPError(f"HTTP {status_code}")

    resp.raise_for_status = raise_for_status
    return resp


def _scripted_get(script):
    """Return (get, calls): ``script`` is an ordered list of Response or Exception."""
    calls = []

    def get(*args, **kwargs):
        idx = len(calls)
        calls.append(kwargs)
        item = script[idx] if idx < len(script) else script[-1]
        if isinstance(item, Exception):
            raise item
        return item

    return get, calls


def test_build_category_query_rejects_junk():
    assert build_category_query(["cs.CL", "cs.LG"]) == "cat:cs.CL OR cat:cs.LG"
    with pytest.raises(ValueError, match="Invalid ArXiv category"):
        build_category_query(["cs.LG; DROP TABLE papers"])
    with pytest.raises(ValueError, match="at least one"):
        build_category_query(["", "  "])


def test_parse_atom_feed_skips_broken_entries():
    xml = FIXTURE.read_bytes()
    entries, errors = parse_atom_feed(xml)
    assert [e.id for e in entries] == ["1706.03762", "1512.03385"]
    assert entries[0].title == "Attention Is All You Need"
    assert entries[0].authors[0] == "Ashish Vaswani"
    assert entries[0].primary_category == "cs.CL"
    assert entries[0].pdf_url.endswith("1706.03762v1")
    assert entries[0].doi == "10.5555/3295222.3295349"
    assert len(errors) == 1
    assert "Skipped entry" in errors[0]


def test_parse_atom_feed_rejects_non_xml():
    with pytest.raises(ValueError, match="not valid XML"):
        parse_atom_feed(b"<not><closed>")


def test_fetch_latest_papers_upserts_via_database(tmp_path: Path):
    xml = FIXTURE.read_bytes()
    db = PaperDatabase(tmp_path / "mle_knowledge.db")
    with patch("pipeline.fetch_atom_xml", return_value=xml) as mocked:
        result = fetch_latest_papers(
            query_categories=["cs.CL", "cs.LG"],
            max_results=20,
            db=db,
        )
        mocked.assert_called_once()
    assert result.query == "cat:cs.CL OR cat:cs.LG"
    assert result.fetched == 2
    assert result.upserted == 2
    assert result.skipped == 1
    assert db.count() == 2
    paper = db.get_paper("arxiv:1706.03762v7")
    assert paper is not None
    assert paper.published_date == "2017-06-12"
    assert paper.summary_structured["source"] == "arxiv"
    assert paper.summary_structured["categories"] == ["cs.CL", "cs.LG"]

    with patch("pipeline.fetch_atom_xml", return_value=xml):
        again = fetch_latest_papers(["cs.CL", "cs.LG"], db=db)
    assert db.count() == 2
    assert again.upserted == 2


def test_fetch_latest_papers_caps_max_results(tmp_path: Path):
    db = PaperDatabase(tmp_path / "mle_knowledge.db")
    with pytest.raises(ValueError, match="max_results"):
        fetch_latest_papers(max_results=0, db=db)
    with pytest.raises(ValueError, match="max_results"):
        fetch_latest_papers(max_results=500, db=db)


def test_fetch_atom_xml_returns_content_on_success():
    sleeps = []
    get, calls = _scripted_get([_fake_response(200)])
    out = fetch_atom_xml("cat:cs.CL", get=get, sleep=sleeps.append)
    assert out == b"<feed>ok</feed>"
    assert len(calls) == 1
    assert sleeps == []
    assert calls[0]["params"]["search_query"] == "cat:cs.CL"


def test_fetch_atom_xml_retries_429_then_succeeds_honoring_retry_after():
    sleeps = []
    get, calls = _scripted_get(
        [_fake_response(429, {"Retry-After": "1"}), _fake_response(200)]
    )
    out = fetch_atom_xml("cat:cs.CL", get=get, sleep=sleeps.append)
    assert out == b"<feed>ok</feed>"
    assert len(calls) == 2
    # Retry-After is honored verbatim (capped) — no exponential jitter added.
    assert sleeps == [1.0]


def test_fetch_atom_xml_retries_5xx_and_network_errors():
    sleeps = []
    get, calls = _scripted_get(
        [requests.ConnectionError("boom"), _fake_response(503), _fake_response(200)]
    )
    out = fetch_atom_xml("cat:cs.CL", get=get, sleep=sleeps.append)
    assert out == b"<feed>ok</feed>"
    assert len(calls) == 3
    assert len(sleeps) == 2
    assert all(s >= ARXIV_BACKOFF_BASE for s in sleeps)


def test_fetch_atom_xml_exhausts_retries_on_persistent_429():
    sleeps = []
    get, calls = _scripted_get([_fake_response(429)])
    with pytest.raises(requests.HTTPError, match="429"):
        fetch_atom_xml("cat:cs.CL", max_attempts=3, get=get, sleep=sleeps.append)
    assert len(calls) == 3  # attempts 1-3
    assert len(sleeps) == 2  # slept only between attempts


def test_fetch_atom_xml_non_retryable_4xx_fails_immediately():
    sleeps = []
    get, calls = _scripted_get([_fake_response(400)])
    with pytest.raises(requests.HTTPError):
        fetch_atom_xml("cat:cs.CL", get=get, sleep=sleeps.append)
    assert len(calls) == 1
    assert sleeps == []


def test_fetch_atom_xml_rejects_bad_max_attempts():
    with pytest.raises(ValueError, match="max_attempts"):
        fetch_atom_xml("cat:cs.CL", max_attempts=0, get=_scripted_get([_fake_response(200)])[0])


def test_arxiv_backoff_delay_shape():
    # Exponential: base * 2**(attempt-1) with <=25% jitter.
    assert ARXIV_BACKOFF_BASE <= arxiv_backoff_delay(1) < ARXIV_BACKOFF_BASE * 1.25 + 1e-9
    assert ARXIV_BACKOFF_BASE * 2 <= arxiv_backoff_delay(2) < ARXIV_BACKOFF_BASE * 2.5 + 1e-9
    assert ARXIV_BACKOFF_BASE * 4 <= arxiv_backoff_delay(3) < ARXIV_BACKOFF_BASE * 5 + 1e-9
    # Numeric Retry-After honored, capped at ARXIV_BACKOFF_CAP.
    assert arxiv_backoff_delay(1, "7") == 7.0
    assert arxiv_backoff_delay(1, "999") == ARXIV_BACKOFF_CAP
    # Unparseable Retry-After falls back to exponential.
    assert arxiv_backoff_delay(1, "garbage") >= ARXIV_BACKOFF_BASE
