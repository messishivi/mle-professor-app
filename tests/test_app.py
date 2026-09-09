from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from database import get_db
from pipeline import IngestResult


def _app() -> AppTest:
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    assert not at.exception
    return at


def test_app_sidebar_and_tabs():
    at = _app()
    assert [s.value for s in at.subheader] == ["ML Pulse", "Research Hub", "Consultant Terminal"]
    assert [m.label for m in at.metric] == ["Papers", "Unread", "Read"]
    assert any(b.label == "Refresh papers" for b in at.button)
    labels = [m.label for m in at.multiselect]
    assert "Categories" in labels
    assert "I work on" in labels
    assert at.slider[0].label == "Max results"
    assert "plain-English" in at.chat_input[0].placeholder
    tab_labels = [t.label for t in at.tabs]
    assert tab_labels == ["ML Pulse", "Research Hub", "Consultant Terminal"]
    assert any(b.label == "Refresh ML Pulse" for b in at.button)


def test_research_hub_renders_paper_and_toggles_read():
    store = get_db()
    store.upsert_paper(
        id="1706.03762",
        title="Attention Is All You Need",
        authors="Vaswani et al.",
        published_date="2017-06-12",
        summary_raw="We propose the Transformer.",
        summary_structured={"primary_category": "cs.CL", "categories": ["cs.CL", "cs.LG"]},
        read_status=0,
    )
    at = _app()
    markdown = " ".join(str(m.value) for m in at.markdown)
    assert "Attention Is All You Need" in markdown
    read_buttons = [b for b in at.button if getattr(b, "key", None) == "read-1706.03762"]
    assert read_buttons
    read_buttons[0].click()
    at.run()
    assert not at.exception
    assert get_db().get_paper("1706.03762").read_status == 1
    assert any(b.label == "Mark unread" for b in at.button)


def test_refresh_papers_records_ingest_stats():
    fake = IngestResult(
        query="cat:cs.CL OR cat:cs.LG",
        fetched=3,
        upserted=3,
        skipped=0,
        papers=[],
        errors=[],
    )
    with patch("pipeline.fetch_latest_papers", return_value=fake):
        at = _app()
        refresh = [b for b in at.button if b.label == "Refresh papers"][0]
        refresh.click()
        at.run()
        assert not at.exception
        success = " ".join(s.value for s in at.success)
        assert "3 saved" in success
        assert "3 fetched" in success
