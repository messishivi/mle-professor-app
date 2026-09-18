from types import SimpleNamespace

import pytest

import providers
from consultant import (
    APPLY_PROMPT,
    EXPLAIN_PROMPT,
    SYSTEMS_PROMPT,
    SYSTEM_PROMPT,
    ConsultantReply,
    assemble_consult_context,
    build_messages,
    chat_with_consultant,
    format_application_context,
    paper_apply_prompt,
    paper_explain_prompt,
)


def test_default_layer_is_apply_to_system():
    messages = build_messages("How do I apply this to my rec stack?", history=[])
    assert messages[0] == {"role": "system", "content": APPLY_PROMPT}
    assert messages[0]["content"] == SYSTEM_PROMPT
    assert "implementation path" in SYSTEM_PROMPT.lower()
    assert "Use / Adapt / Ignore" in SYSTEM_PROMPT
    assert "Never invent an arXiv id" in SYSTEM_PROMPT
    assert "repo README" in SYSTEM_PROMPT
    assert "user / item" in SYSTEM_PROMPT.lower() or "user (who" in SYSTEM_PROMPT.lower()
    assert "Do not invent a persona tower" in SYSTEM_PROMPT
    assert "generic rec-stack map" not in SYSTEM_PROMPT


def test_explain_layer_still_plain_english():
    messages = build_messages("Explain Kimi K3.", history=[], layer="explain")
    assert messages[0]["content"] == EXPLAIN_PROMPT
    assert "plain-English" in EXPLAIN_PROMPT


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
    assert messages[0]["content"] == APPLY_PROMPT
    assert "competing prompt" not in str(messages[1:])


def test_chat_with_consultant_sends_apply_prompt(monkeypatch):
    captured = {}

    def fake_stream(messages, **kwargs):
        captured["messages"] = messages
        captured.update(kwargs)
        yield "  Short briefing.  "

    monkeypatch.setattr(providers, "stream_chat", fake_stream)
    monkeypatch.setattr("grounding.gather_sources", lambda *a, **k: [])
    monkeypatch.setattr("grounding.format_sources_for_model", lambda sources: "")
    reply = chat_with_consultant("Explain Kimi K3.", history=[])
    assert reply.content == "Short briefing."
    assert reply.layer == "apply"
    assert captured["messages"][0]["content"] == APPLY_PROMPT
    assert captured["messages"][-1]["content"].startswith(
        "Explain Kimi K3"
    ) or "Kimi K3" in captured["messages"][-1]["content"]
    # Default provider is groq when no LLM_PROVIDER env is set (hermetic conftest).
    assert captured["provider"] == "groq"
    assert reply.provider == "groq"


def test_systems_layer_is_opt_in(monkeypatch):
    captured = {}

    def fake_stream(messages, **kwargs):
        captured["messages"] = messages
        yield "HBM bound."

    monkeypatch.setattr(providers, "stream_chat", fake_stream)
    monkeypatch.setattr("grounding.gather_sources", lambda *a, **k: [])
    monkeypatch.setattr("grounding.format_sources_for_model", lambda sources: "")
    chat_with_consultant("Cost KV cache.", history=[], layer="systems")
    assert captured["messages"][0]["content"] == SYSTEMS_PROMPT


def test_chat_with_consultant_honors_llm_provider_env(monkeypatch):
    """Plan 03: the one-shot path must honor LLM_PROVIDER, not just Groq."""
    captured = {}

    def fake_stream(messages, **kwargs):
        captured.update(kwargs)
        yield "ok"

    monkeypatch.setattr(providers, "stream_chat", fake_stream)
    monkeypatch.setattr("grounding.gather_sources", lambda *a, **k: [])
    monkeypatch.setattr("grounding.format_sources_for_model", lambda sources: "")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    reply = chat_with_consultant("hello", [])
    assert reply.provider == "openai"
    assert captured["provider"] == "openai"
    assert captured["model"] == "gpt-4o-mini"


def test_paper_apply_prompt_asks_for_implementation_path():
    paper = SimpleNamespace(
        id="2606.12198",
        title="Audio feedback for RL agents",
        authors="et al.",
        published_date="2026-06-10",
        summary_raw="Distilled audio policy as environment feedback.",
    )
    text = paper_apply_prompt(
        paper,
        application="RL post-training for a speech policy",
        known_papers="PPO, DPO",
        repo_url="https://github.com/you/speech-rl",
    )
    assert "RL post-training" in text
    assert "PPO, DPO" in text
    assert "github.com/you/speech-rl" in text
    assert "README" in text
    assert "implement" in text.lower() or "application" in text.lower()
    assert "do not assume a rec stack" in text.lower()
    assert "persona/user model" not in text.lower()
    assert "retrieval, ranking" not in text.lower()


def test_format_application_context_names_known_papers():
    block = format_application_context(
        "RL post-training for a speech policy",
        ["RL post-training"],
        "PPO, DPO",
        repo_url="https://github.com/you/speech-rl",
        repo_readme="# speech-rl\nPolicy in training/, serve via FastAPI.",
    )
    assert "RL post-training" in block
    assert "PPO" in block
    assert "recommender template" in block.lower()
    assert "github.com/you/speech-rl" in block
    assert "Policy in training/" in block
    assert "delta" in block.lower()


def test_chat_with_consultant_injects_repo_readme(monkeypatch):
    captured = {}

    def fake_stream(messages, **kwargs):
        captured["messages"] = messages
        yield "ok"

    monkeypatch.setattr(providers, "stream_chat", fake_stream)
    monkeypatch.setattr("grounding.gather_sources", lambda *a, **k: [])
    monkeypatch.setattr(
        "grounding.format_sources_for_model",
        lambda sources: "Retrieved sources:\n" + "\n".join(s.url for s in sources if s.url),
    )
    store = SimpleNamespace(
        get_application=lambda: "speech policy",
        get_stack=lambda: ["RL post-training"],
        get_known_papers=lambda: "PPO",
        get_repo_url=lambda: "https://github.com/you/speech-rl",
        get_repo_readme=lambda: "# speech-rl\nFastAPI serve",
        get_repo_readme_url=lambda: "https://github.com/you/speech-rl#readme",
    )
    reply = chat_with_consultant("apply this", [], store=store)
    user_msg = captured["messages"][-1]["content"]
    assert "FastAPI serve" in user_msg
    assert "speech-rl" in user_msg
    assert any(s.get("kind") == "repo" for s in reply.sources)


def test_assemble_consult_context_returns_messages_and_packed(monkeypatch):
    monkeypatch.setattr("grounding.gather_sources", lambda *a, **k: [])
    monkeypatch.setattr("grounding.format_sources_for_model", lambda sources: "")
    store = SimpleNamespace(
        get_application=lambda: "speech policy",
        get_stack=lambda: ["RL post-training"],
        get_known_papers=lambda: "PPO",
        get_repo_url=lambda: "https://github.com/you/speech-rl",
        get_repo_readme=lambda: "# speech-rl\nFastAPI serve",
        get_repo_readme_url=lambda: "https://github.com/you/speech-rl#readme",
    )
    messages, packed = assemble_consult_context(store, "apply this")
    assert messages[0]["role"] == "system"
    assert messages[-1]["content"].endswith("apply this")
    assert len(packed) == 1
    assert packed[0].kind == "repo"


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


def test_module_function_routes_through_provider_seam(monkeypatch):
    """The one-shot entry point must go through providers.stream_chat."""
    captured = {}

    def fake_stream(messages, **kwargs):
        captured["messages"] = messages
        captured.update(kwargs)
        yield "ok"

    monkeypatch.setattr(providers, "stream_chat", fake_stream)
    monkeypatch.setattr("grounding.gather_sources", lambda *a, **k: [])
    monkeypatch.setattr("grounding.format_sources_for_model", lambda sources: "")
    chat_with_consultant("hello", [])
    assert captured["messages"][-1]["content"] == "hello"
    assert captured["api_key"] is None


def test_missing_key_raises_provider_unavailable(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setattr("grounding.gather_sources", lambda *a, **k: [])
    monkeypatch.setattr("grounding.format_sources_for_model", lambda sources: "")
    with pytest.raises(providers.ProviderUnavailable, match="GROQ_API_KEY"):
        chat_with_consultant("hello", [])


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


def test_unknown_layer_message_names_apply(monkeypatch):
    """Nit fix: the error must name all three layers, including apply."""
    monkeypatch.setattr("grounding.gather_sources", lambda *a, **k: [])
    monkeypatch.setattr("grounding.format_sources_for_model", lambda sources: "")
    with pytest.raises(ValueError, match="apply, explain, or systems"):
        chat_with_consultant("hello", [], layer="bogus")
