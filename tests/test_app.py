import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from database import get_db
from pipeline import IngestResult

CONSULTANT = "Consultant Terminal"


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Hermetic DB with onboarding already completed."""
    monkeypatch.setenv("MLE_DATA_DIR", str(tmp_path))
    s = get_db()
    s.set_setting("onboarding_done", "1")
    return s


@pytest.fixture
def fresh_store(tmp_path, monkeypatch):
    """Hermetic DB that has never seen the onboarding wizard."""
    monkeypatch.setenv("MLE_DATA_DIR", str(tmp_path))
    return get_db()


def _app() -> AppTest:
    at = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "app.py"), default_timeout=30)
    at.run()
    assert not at.exception
    return at


def _switch(at: AppTest, section: str) -> AppTest:
    at.session_state.main_section = section
    at.run()
    assert not at.exception
    return at


def _open_saved(at: AppTest) -> AppTest:
    at.session_state.main_section = "ML Pulse"
    at.session_state.pulse_view = "saved"
    at.run()
    assert not at.exception
    return at


def test_app_sidebar_and_tabs(store):
    at = _app()
    assert [s.value for s in at.subheader] == ["⚡ ML Pulse"]
    assert at.session_state.main_section == "ML Pulse"
    assert [m.label for m in at.metric] == ["Papers", "Unread", "Read"]
    assert any(b.label == "Refresh papers" for b in at.button)
    assert any(b.label == "↻ Refresh" for b in at.button)
    assert any(m.label == "Categories" for m in at.multiselect)
    assert at.slider[0].label == "Max results"
    assert any(b.label == "⚙️ Edit setup" for b in at.button)
    radios = {r.label: r for r in at.radio}
    assert "Section" in radios
    assert "Show" in radios
    assert list(radios["Section"].options) == ["ML Pulse", "Consultant Terminal"]
    assert "saved" in {str(o).lower() for o in radios["Show"].options} or any(
        "saved" in str(o).lower() for o in radios["Show"].options
    )
    _switch(at, CONSULTANT)
    assert [s.value for s in at.subheader] == ["💬 Consultant Terminal"]
    ph = at.chat_input[0].placeholder.lower()
    assert "apply" in ph or "system" in ph
    assert any("sug-apply" in (b.key or "") for b in at.button)
    _open_saved(at)
    assert [s.value for s in at.subheader] == ["⚡ ML Pulse", "📚 Saved"]


def test_onboarding_wizard_first_run(fresh_store):
    at = _app()
    chips = [b for b in at.button if (b.key or "").startswith("ob-chip-")]
    assert len(chips) == 16
    cont = [b for b in at.button if b.label == "Continue →"][0]
    assert cont.disabled
    # Pick a stack chip, then continue.
    chips[0].click()
    at.run()
    assert not at.exception
    assert len(at.session_state.ob_stack) == 1
    [b for b in at.button if b.label == "Continue →"][0].click()
    at.run()
    assert not at.exception
    assert at.session_state.onboarding_step == 2
    assert any(t.label == "I'm building" for t in at.text_area)
    hints = [b for b in at.button if (b.key or "").startswith("ob-ex-")]
    assert hints
    hints[0].click()
    at.run()
    assert not at.exception
    assert at.session_state.ob_application
    # Step 3 via continue.
    [b for b in at.button if b.label == "Continue →"][0].click()
    at.run()
    assert not at.exception
    assert at.session_state.onboarding_step == 3
    assert any("Repo URL" in t.label for t in at.text_input)
    [b for b in at.button if b.label == "✨ Finish setup"][0].click()
    at.run()
    assert not at.exception
    assert fresh_store.get_setting("onboarding_done") == "1"
    # Wizard is gone; main UI renders.
    assert [s.value for s in at.subheader] == ["⚡ ML Pulse"]
    assert not any((b.key or "").startswith("ob-chip-") for b in at.button)


def test_onboarding_skip(fresh_store):
    at = _app()
    [b for b in at.button if b.label == "Skip for now →"][0].click()
    at.run()
    assert not at.exception
    assert at.session_state.onboarding_skipped is True
    assert [s.value for s in at.subheader] == ["⚡ ML Pulse"]
    # Skipping does not persist: a fresh session shows the wizard again.
    assert fresh_store.get_setting("onboarding_done") != "1"


def test_edit_setup_reopens_wizard(store):
    at = _app()
    [b for b in at.button if b.label == "⚙️ Edit setup"][0].click()
    at.run()
    assert not at.exception
    assert any((b.key or "").startswith("ob-chip-") for b in at.button)


def test_library_renders_paper_and_toggles_read(store):
    store.upsert_paper(
        id="1706.03762",
        title="Attention Is All You Need",
        authors="Vaswani et al.",
        published_date="2017-06-12",
        summary_raw="We propose the Transformer.",
        summary_structured={"primary_category": "cs.CL", "categories": ["cs.CL", "cs.LG"]},
        read_status=0,
    )
    at = _open_saved(_app())
    markdown = " ".join(str(m.value) for m in at.markdown)
    assert "Attention Is All You Need" in markdown
    read_buttons = [b for b in at.button if getattr(b, "key", None) == "read-1706.03762"]
    assert read_buttons
    read_buttons[0].click()
    at.run()
    assert not at.exception
    assert get_db().get_paper("1706.03762").read_status == 1
    assert any(b.label == "✓ Mark unread" for b in at.button)
    assert at.toast, "expected a toast on mark-read"


def test_apply_to_my_system_stages_draft_then_sends(store):
    store.upsert_paper(
        id="1706.03762",
        title="Attention Is All You Need",
        authors="Vaswani et al.",
        published_date="2017-06-12",
        summary_raw="We propose the Transformer.",
        summary_structured={"primary_category": "cs.CL", "categories": ["cs.CL", "cs.LG"]},
        read_status=0,
    )
    fake = SimpleNamespace(content="Adapt the attention block in training.", sources=[])
    with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}, clear=False), patch(
        "consultant.chat_with_consultant", return_value=fake
    ) as mock_chat:
        at = _open_saved(_app())
        apply_btns = [b for b in at.button if getattr(b, "key", None) == "ex-1706.03762"]
        assert apply_btns
        apply_btns[0].click()
        at.run()
        assert not at.exception
        # Draft is staged for review — not sent blindly.
        assert at.session_state.main_section == CONSULTANT
        assert [s.value for s in at.subheader] == ["💬 Consultant Terminal"]
        draft = at.session_state["apply_draft"] if "apply_draft" in at.session_state else None
        assert draft and "Attention Is All You Need" in draft["prompt"]
        assert any("Apply draft" in str(m.value) for m in at.markdown)
        mock_chat.assert_not_called()
        # Review and send.
        send = [b for b in at.button if getattr(b, "key", None) == "apply-send"]
        assert send
        send[0].click()
        at.run()
        assert not at.exception
        mock_chat.assert_called_once()
        hist = list(at.session_state["consultant_history_apply"])
        assert hist and hist[0]["role"] == "user"
        assert "Attention Is All You Need" in hist[0]["content"]
        assert "apply_draft" not in at.session_state
        shown = " ".join(str(m.value) for m in at.markdown)
        assert "Adapt the attention block" in shown


def test_apply_draft_can_be_discarded(store):
    store.upsert_paper(id="1706.03762", title="Attention Is All You Need")
    at = _open_saved(_app())
    [b for b in at.button if getattr(b, "key", None) == "ex-1706.03762"][0].click()
    at.run()
    assert not at.exception
    assert "apply_draft" in at.session_state
    [b for b in at.button if getattr(b, "key", None) == "apply-discard"][0].click()
    at.run()
    assert not at.exception
    assert "apply_draft" not in at.session_state
    assert list(at.session_state["consultant_history_apply"]) == []


def test_consultant_suggestion_chip_sends(store):
    fake = SimpleNamespace(content="Here is the plain-English version.", sources=[])
    with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}, clear=False), patch(
        "consultant.chat_with_consultant", return_value=fake
    ) as mock_chat:
        at = _switch(_app(), CONSULTANT)
        chips = [b for b in at.button if (b.key or "").startswith("sug-apply-")]
        assert chips
        chips[0].click()
        at.run()
        assert not at.exception
        mock_chat.assert_called_once()
        hist = list(at.session_state["consultant_history_apply"])
        assert hist and hist[0]["role"] == "user"


def test_consultant_offline_message(store):
    with patch.dict(os.environ, {"GROQ_API_KEY": ""}, clear=False):
        at = _switch(_app(), CONSULTANT)
        at.chat_input[0].set_value("hello?")
        at.run()
        assert not at.exception
        shown = " ".join(str(m.value) for m in at.markdown)
        errors = " ".join(str(e.value) for e in at.error)
        assert "offline" in (shown + errors).lower()


def test_pulse_save_to_library(store):
    store.set_stack(["LoRA / adapters"])
    store.save_pulse(
        [
            {
                "topic": "LoRA adapters",
                "why": "Parameter-efficient fine-tuning.",
                "paper_id": "2106.09685",
                "paper_title": "LoRA: Low-Rank Adaptation of Large Language Models",
                "paper_url": "https://arxiv.org/abs/2106.09685",
                "concept": "LoRA / adapters",
                "concept_blurb": "Low-rank adapters.",
                "in_library": False,
                "source": "arxiv",
                "abstract": "We propose low-rank adaptation.",
                "published_date": "2021-10-16",
            }
        ]
    )
    at = _app()
    assert get_db().get_paper("2106.09685") is None
    save_btns = [b for b in at.button if getattr(b, "key", None) == "pulse-save-0"]
    assert save_btns and save_btns[0].label == "📥 Save"
    save_btns[0].click()
    at.run()
    assert not at.exception
    assert get_db().get_paper("2106.09685") is not None
    saved = [b for b in at.button if getattr(b, "key", None) == "pulse-save-0"]
    assert saved and saved[0].label == "✓ Saved" and saved[0].disabled
    assert at.toast, "expected a toast on save"


def test_refresh_papers_records_ingest_stats(store):
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
        assert at.toast, "expected a toast on ingest"
