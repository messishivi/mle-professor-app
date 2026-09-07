from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from consultant import (
    EXPLAIN_PROMPT,
    SYSTEMS_PROMPT,
    SYSTEM_PROMPT,
    Consultant,
    ConsultantReply,
    build_messages,
    chat_with_consultant,
    paper_explain_prompt,
)


def test_default_layer_is_plain_english():
    messages = build_messages("Explain Kimi K3.", history=[])
    assert messages[0] == {"role": "system", "content": EXPLAIN_PROMPT}
    assert messages[0]["content"] == SYSTEM_PROMPT
    assert "plain-English" in SYSTEM_PROMPT
    assert "three tight sections" in SYSTEM_PROMPT
    assert "Never invent an arXiv id" in SYSTEM_PROMPT
    assert "Do not swap in a similarly named paper" in SYSTEM_PROMPT


def test_systems_layer_keeps_original_persona():
    messages = build_messages("Where does HBM bound decode?", history=[], layer="systems")
    assert messages[0]["content"] == SYSTEMS_PROMPT
    assert SYSTEMS_PROMPT.startswith(
        "You are a Distinguished AI Research Professor and Principal ML Systems Consultant."
    )
    assert "KV cache optimization footprint" in SYSTEMS_PROMPT
    assert "FLOPs/token" in SYSTEMS_PROMPT


def test_history_keeps_user_assistant_and_drops_system():
    history = [
        {"role": "system", "content": "ignore this competing prompt"},
        {"role": "user", "content": "What is Kimi K3?"},
        {"role": "assistant", "content": "A paper about a model family."},
    ]
    messages = build_messages("Go one level deeper on the method.", history)
    roles = [m["role"] for m in messages]
    assert roles == ["system", "user", "assistant", "user"]
    assert messages[0]["content"] == EXPLAIN_PROMPT
    assert "competing prompt" not in str(messages[1:])


def test_chat_with_consultant_sends_explain_prompt():
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            model="openai/gpt-oss-120b",
            choices=[SimpleNamespace(message=SimpleNamespace(content="  Short briefing.  "))],
        )

    client = MagicMock()
    client.chat.completions.create.side_effect = fake_create
    consultant = Consultant(client=client, model="openai/gpt-oss-120b")
    reply = consultant.chat_with_consultant("Explain Kimi K3.", history=[])
    assert reply.content == "Short briefing."
    assert reply.layer == "explain"
    assert captured["messages"][0]["content"] == EXPLAIN_PROMPT
    assert captured["messages"][-1]["content"].startswith("Explain Kimi K3") or "Kimi K3" in captured["messages"][-1]["content"]


def test_systems_layer_is_opt_in():
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            model="openai/gpt-oss-120b",
            choices=[SimpleNamespace(message=SimpleNamespace(content="HBM bound."))],
        )

    client = MagicMock()
    client.chat.completions.create.side_effect = fake_create
    consultant = Consultant(client=client, model="openai/gpt-oss-120b")
    consultant.chat_with_consultant("Cost KV cache.", history=[], layer="systems")
    assert captured["messages"][0]["content"] == SYSTEMS_PROMPT


def test_paper_explain_prompt_includes_abstract():
    paper = SimpleNamespace(
        id="1706.03762",
        title="Attention Is All You Need",
        authors="Vaswani et al.",
        published_date="2017-06-12",
        summary_raw="We propose the Transformer.",
    )
    text = paper_explain_prompt(paper)
    assert "Attention Is All You Need" in text
    assert "We propose the Transformer." in text
    assert "plain English" in text


def test_module_function_uses_injected_client(monkeypatch):
    fake = MagicMock()
    fake.model = "openai/gpt-oss-120b"
    fake.chat_with_consultant.return_value = SimpleNamespace(content="ok")
    monkeypatch.setattr("consultant._default", fake)
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setattr("grounding.gather_sources", lambda *a, **k: [])
    monkeypatch.setattr("grounding.format_sources_for_model", lambda sources: "")
    chat_with_consultant("hello", [])
    fake.chat_with_consultant.assert_called_once()
    args, kwargs = fake.chat_with_consultant.call_args
    assert args[0] == "hello"


def test_consultant_reply_allows_source_without_paper_id():
    reply = ConsultantReply(
        content="GPT-6 Astra is an OpenAI model.",
        model="openai/gpt-oss-120b",
        provider="groq",
        sources=[
            {
                "kind": "product",
                "title": "GPT-6 Astra",
                "url": "https://openai.com/index/gpt-6-astra/",
                "snippet": "OpenAI product",
            }
        ],
    )
    assert reply.sources[0]["kind"] == "product"


def test_build_messages_injects_retrieved_context():
    messages = build_messages(
        "What is Astra?",
        retrieved="Retrieved sources:\n1. [product] GPT-6 Astra\n   https://openai.com/index/gpt-6-astra/",
    )
    assert "User question:" in messages[-1]["content"]
    assert "openai.com/index/gpt-6-astra" in messages[-1]["content"]
    assert messages[-1]["content"].endswith("What is Astra?")


def test_missing_keys_raise(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    import consultant as mod

    monkeypatch.setattr(mod, "_default", None)
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        Consultant()
