from pathlib import Path
from unittest.mock import patch

from database import PaperDatabase
from trends import (
    PulseItem,
    RawSignal,
    StackFit,
    _dedupe,
    _items_from_signals,
    draft_decision_memo,
    fetch_hf_daily,
    match_concept,
    score_against_stack,
)


def test_stack_fit_high_for_matching_concept():
    item = PulseItem(
        topic="FreeToken MoE serving",
        paper_title="FreeToken",
        concept="Mixture of Experts",
        abstract="sparse experts routing",
        paper_id="2608.16157",
    )
    fit = score_against_stack(item, ["Mixture of Experts", "Quantization"])
    assert fit.label == "High fit"
    assert fit.score >= 80


def test_decision_memo_prototype_on_high_fit():
    item = PulseItem(
        topic="FreeToken MoE serving",
        paper_title="FreeToken",
        paper_id="2608.16157",
        paper_url="https://arxiv.org/abs/2608.16157",
        concept="Mixture of Experts",
        in_library=False,
    )
    fit = StackFit("High fit", 90, "On your stack (Mixture of Experts).")
    memo = draft_decision_memo(item, fit, ["Mixture of Experts"])
    assert memo.verdict == "prototype"
    assert "arxiv.org/abs/2608.16157" in memo.paper_url
    assert "routing" in memo.constraint.lower() or "serving" in memo.constraint.lower()


def test_decision_memo_skip():
    item = PulseItem(topic="Unrelated ethics sim", concept="Safety / alignment", paper_id="1")
    fit = StackFit("Skip", 10, "Skip unless curious.")
    memo = draft_decision_memo(item, fit, ["Quantization"])
    assert memo.verdict == "skip"


def test_stack_fit_skip_when_no_overlap():
    item = PulseItem(
        topic="A farm simulation for LLM ethics",
        concept="Safety / alignment",
        abstract="animals in a gridworld",
        paper_id="2609.04444",
    )
    fit = score_against_stack(item, ["Quantization"])
    assert fit.label == "Skip"


def test_match_concept_picks_moe():
    name, blurb = match_concept("DeepSeekMoE: routing at scale", "We train a mixture of experts.")
    assert name == "Mixture of Experts"
    assert "experts" in blurb.lower()


def test_dedupe_by_arxiv_id():
    a = RawSignal(paper_id="1706.03762", title="A", source="hf_daily")
    b = RawSignal(paper_id="1706.03762", title="A v2", source="arxiv")
    c = RawSignal(paper_id="1512.03385", title="B", source="arxiv")
    out = _dedupe([a, b, c])
    assert [x.paper_id for x in out] == ["1706.03762", "1512.03385"]


def test_items_flag_library(tmp_path: Path):
    db = PaperDatabase(tmp_path / "mle_knowledge.db")
    db.upsert_paper(id="1706.03762", title="Attention Is All You Need", summary_raw="attn")
    signals = [
        RawSignal(
            paper_id="1706.03762",
            title="Attention Is All You Need",
            abstract="self-attention transformer",
            source="hf_daily",
            url="https://arxiv.org/abs/1706.03762",
        )
    ]
    items = _items_from_signals(signals, db)
    assert items[0].in_library is True
    assert items[0].concept == "Transformers"


def test_fetch_hf_daily_parses_nested_paper():
    payload = [
        {
            "paper": {
                "id": "2609.04444",
                "title": "HarvestBench",
                "summary": "A farm simulation for LLM agents.",
                "authors": [{"name": "Ada"}],
            }
        }
    ]
    with patch("trends.requests.get") as mocked:
        mocked.return_value.status_code = 200
        mocked.return_value.json.return_value = payload
        mocked.return_value.raise_for_status.return_value = None
        rows = fetch_hf_daily(5)
    assert len(rows) == 1
    assert rows[0].paper_id == "2609.04444"
    assert rows[0].title == "HarvestBench"
