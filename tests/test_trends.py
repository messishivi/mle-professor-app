from pathlib import Path
from unittest.mock import patch

from database import PaperDatabase
from trends import RawSignal, _dedupe, _items_from_signals, fetch_hf_daily, match_concept


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
