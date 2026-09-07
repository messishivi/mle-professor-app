from pathlib import Path
from unittest.mock import patch

import pytest

from database import PaperDatabase
from pipeline import (
    build_category_query,
    fetch_latest_papers,
    parse_atom_feed,
)

FIXTURE = Path(__file__).parent / "fixtures" / "arxiv_feed.xml"


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
