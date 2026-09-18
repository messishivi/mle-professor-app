from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from database import PaperDatabase
from trends import (
    PulseItem,
    RawSignal,
    StackFit,
    _cluster_with_llm,
    _dedupe,
    _items_from_signals,
    draft_decision_memo,
    fetch_hf_daily,
    is_recent,
    match_concept,
    refine_decision_memo,
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
    assert out[0].source == "hf_daily"


def test_trending_order_is_kept_ahead_of_arxiv_fill():
    hf = [
        RawSignal(paper_id="2609.00001", title="Hot", source="hf_daily", published="2026-09-08"),
        RawSignal(paper_id="2609.00002", title="Also hot", source="hf_daily", published="2026-09-07"),
    ]
    arxiv = [
        RawSignal(paper_id="2609.00003", title="Newest arxiv", source="arxiv", published="2026-09-10"),
        RawSignal(paper_id="2609.00001", title="Dup", source="arxiv", published="2026-09-10"),
    ]
    out = _dedupe(hf + arxiv)
    assert [x.paper_id for x in out] == ["2609.00001", "2609.00002", "2609.00003"]
    assert [x.source for x in out] == ["hf_daily", "hf_daily", "arxiv"]


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
    params = mocked.call_args.kwargs["params"]
    assert params.get("sort") == "trending"


def test_is_recent_drops_two_year_old_papers():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert is_recent(published=today)
    assert is_recent(published="2023-10-14T17:01:37.000Z") is False
    assert is_recent(paper_id="2310.10688") is False
    assert is_recent(paper_id="2407.16741") is False


def _sample_item():
    return PulseItem(
        topic="FreeToken MoE serving",
        paper_title="FreeToken",
        paper_id="2608.16157",
        paper_url="https://arxiv.org/abs/2608.16157",
        concept="Mixture of Experts",
        in_library=False,
    )


def _sample_draft():
    return draft_decision_memo(
        _sample_item(),
        StackFit("High fit", 90, "On your stack (Mixture of Experts)."),
        ["Mixture of Experts"],
    )


def test_refine_decision_memo_falls_back_without_key():
    """No provider key -> the heuristic draft is returned untouched."""
    draft = _sample_draft()
    assert (
        refine_decision_memo(_sample_item(), StackFit("High fit", 90, ""), ["Mixture of Experts"], draft)
        is draft
    )


def test_refine_decision_memo_honors_provider_seam(monkeypatch):
    """LLM_PROVIDER=openai must be honored, not silently Groq."""
    captured = {}

    def fake_stream(messages, **kwargs):
        captured.update(kwargs)
        yield (
            '{"verdict":"adopt","constraint":"expert parallelism at serve time",'
            '"so_what":"cut KV memory for long contexts"}'
        )

    monkeypatch.setattr("providers.stream_chat", fake_stream)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    memo = refine_decision_memo(
        _sample_item(), StackFit("High fit", 90, ""), ["Mixture of Experts"], _sample_draft()
    )
    assert memo.verdict == "adopt"
    assert "expert parallelism" in memo.constraint
    assert "KV memory" in memo.so_what
    assert memo.origin == "openai"
    assert captured["provider"] == "openai"
    assert "arxiv.org/abs/2608.16157" in memo.paper_url


def test_refine_decision_memo_defaults_to_groq(monkeypatch):
    def fake_stream(messages, **kwargs):
        yield '{"verdict":"watch","constraint":"x","so_what":"y"}'

    monkeypatch.setattr("providers.stream_chat", fake_stream)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    memo = refine_decision_memo(
        _sample_item(), StackFit("High fit", 90, ""), ["Mixture of Experts"], _sample_draft()
    )
    assert memo.verdict == "watch"
    assert memo.origin == "groq"


def test_refine_decision_memo_invalid_verdict_keeps_draft(monkeypatch):
    def fake_stream(messages, **kwargs):
        yield '{"verdict":"banquet","constraint":"x","so_what":"y"}'

    monkeypatch.setattr("providers.stream_chat", fake_stream)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    draft = _sample_draft()
    memo = refine_decision_memo(
        _sample_item(), StackFit("High fit", 90, ""), ["Mixture of Experts"], draft
    )
    assert memo.verdict == draft.verdict


def test_cluster_with_llm_returns_none_without_key():
    # No key for the default provider (hermetic env) -> heuristic fallback.
    signals = [RawSignal(paper_id="2609.00001", title="Hot", source="hf_daily")]
    assert _cluster_with_llm(signals, None) is None


def test_cluster_with_llm_honors_provider(monkeypatch, tmp_path: Path):
    def fake_stream(messages, **kwargs):
        captured.update(kwargs)
        yield (
            '{"topics":[{"topic":"MoE serving","why":"Two sentences here.",'
            '"paper_id":"2609.00001","paper_title":"Hot",'
            '"concept":"Mixture of Experts","concept_blurb":"sparse experts"}]}'
        )

    captured = {}
    monkeypatch.setattr("providers.stream_chat", fake_stream)
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    signals = [
        RawSignal(
            paper_id="2609.00001",
            title="Hot",
            abstract="sparse experts routing",
            source="hf_daily",
            published=today,
        )
    ]
    db = PaperDatabase(tmp_path / "mle_knowledge.db")
    items = _cluster_with_llm(signals, db)
    assert items is not None
    assert len(items) == 1
    assert items[0].topic == "MoE serving"
    assert items[0].concept == "Mixture of Experts"
    assert captured["provider"] == "anthropic"
