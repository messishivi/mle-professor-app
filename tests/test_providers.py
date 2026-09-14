"""P5a: multi-provider registry + seam (Plan 03).

Covers provider resolution (request override > ``LLM_PROVIDER`` env > groq
default), per-provider key/model/base-URL resolution, per-provider offline
messages, and ``stream_chat`` dispatch to each SDK. All SDK clients are
mocked — no test touches the network.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import providers

ENV_VARS = (
    "LLM_PROVIDER",
    "GROQ_API_KEY",
    "GROQ_MODEL",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_BASE_URL",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL",
    "LOCAL_API_KEY",
    "LOCAL_MODEL",
    "LOCAL_BASE_URL",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Hermetic: no LLM_PROVIDER, no provider keys, no model/base-URL envs."""
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)


# ------------------------------------------------------------- registry


def test_registry_has_the_four_planned_providers():
    assert set(providers.PROVIDERS) == {"groq", "openai", "anthropic", "local"}


def test_registry_defaults_and_key_policy():
    assert providers.DEFAULT_PROVIDER == "groq"
    assert providers.PROVIDER == providers.DEFAULT_PROVIDER  # P2c back-compat
    assert providers.PROVIDERS["groq"].default_model == "openai/gpt-oss-120b"
    assert providers.PROVIDERS["openai"].default_model == "gpt-4o-mini"
    assert providers.PROVIDERS["anthropic"].default_model == "claude-sonnet-4-5"
    assert providers.PROVIDERS["local"].default_model == "local"
    assert providers.PROVIDERS["local"].requires_key is False
    for name in ("groq", "openai", "anthropic"):
        assert providers.PROVIDERS[name].requires_key is True


# ----------------------------------------------------- provider resolution


def test_resolve_provider_defaults_to_groq():
    assert providers.resolve_provider() == "groq"


def test_resolve_provider_env_and_request_override(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    assert providers.resolve_provider() == "anthropic"
    # Request override wins over the env
    assert providers.resolve_provider("openai") == "openai"


def test_resolve_provider_normalizes_case_and_whitespace(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "  LOCAL ")
    assert providers.resolve_provider() == "local"
    assert providers.resolve_provider("Local") == "local"


def test_resolve_provider_unknown_raises():
    with pytest.raises(providers.UnknownProvider):
        providers.resolve_provider("together")


def test_resolve_provider_unknown_env_raises(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mistral")
    with pytest.raises(providers.UnknownProvider):
        providers.resolve_provider()


# --------------------------------------------------------- key/model/base


def test_resolve_key_byok_wins(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "sk-env")
    assert providers.resolve_key("groq", "sk-byok") == "sk-byok"
    assert providers.resolve_key("groq") == "sk-env"


def test_resolve_key_missing_raises_with_provider_message(monkeypatch):
    with pytest.raises(providers.ProviderUnavailable) as exc:
        providers.resolve_key("openai")
    assert (
        str(exc.value)
        == "Consultant is offline. Set `OPENAI_API_KEY` in `.env`."
    )


def test_resolve_key_groq_message_is_streamlit_parity():
    with pytest.raises(providers.ProviderUnavailable) as exc:
        providers.resolve_key("groq")
    assert str(exc.value) == providers.OFFLINE_MESSAGE


def test_resolve_key_local_never_requires_key(monkeypatch):
    assert providers.resolve_key("local") == ""
    monkeypatch.setenv("LOCAL_API_KEY", "sk-local")
    assert providers.resolve_key("local") == "sk-local"


def test_resolve_model_request_env_default(monkeypatch):
    assert providers.resolve_model("openai") == "gpt-4o-mini"
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5")
    assert providers.resolve_model("openai") == "gpt-5"
    # Request override beats the env
    assert providers.resolve_model("openai", "gpt-4o") == "gpt-4o"


def test_resolve_base_url_defaults_and_env(monkeypatch):
    assert (
        providers.resolve_base_url("local") == "http://127.0.0.1:8080/v1"
    )
    assert (
        providers.resolve_base_url("openai") == "https://api.openai.com/v1"
    )
    monkeypatch.setenv("LOCAL_BASE_URL", "http://127.0.0.1:9999/v1")
    assert (
        providers.resolve_base_url("local") == "http://127.0.0.1:9999/v1"
    )
    monkeypatch.setenv("OPENAI_BASE_URL", "https://proxy.example/v1")
    assert (
        providers.resolve_base_url("openai") == "https://proxy.example/v1"
    )
    # groq/anthropic keep their SDK-level defaults
    assert (
        providers.resolve_base_url("groq")
        == "https://api.groq.com/openai/v1"
    )
    assert providers.resolve_base_url("anthropic") is None


def test_offline_message_per_provider():
    assert (
        providers.offline_message("groq")
        == "Consultant is offline. Set `GROQ_API_KEY` in `.env`."
    )
    assert "OPENAI_API_KEY" in providers.offline_message("openai")
    assert "ANTHROPIC_API_KEY" in providers.offline_message("anthropic")
    assert "LOCAL_BASE_URL" in providers.offline_message("local")


# -------------------------------------------------------- stream_chat dispatch


def _delta(content: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=content))]
    )


def _no_delta():
    return SimpleNamespace(choices=[])


def test_stream_chat_groq_uses_groq_sdk(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "sk-groq")
    calls: dict = {}
    fake_client = MagicMock()

    def fake_create(**kwargs):
        calls.update(kwargs)
        return iter([_delta("a"), _no_delta(), _delta(""), _delta("b")])

    fake_client.chat.completions.create.side_effect = fake_create
    with patch("groq.Groq", return_value=fake_client):
        out = list(
            providers.stream_chat(
                [{"role": "user", "content": "hi"}], provider="groq"
            )
        )
    assert out == ["a", "b"]  # empty/None deltas skipped
    assert calls["model"] == "openai/gpt-oss-120b"
    assert calls["messages"] == [{"role": "user", "content": "hi"}]
    assert calls["stream"] is True


def test_stream_chat_openai_uses_openai_sdk(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    calls: dict = {}
    client_args: dict = {}
    fake_client = MagicMock()

    def fake_create(**kwargs):
        calls.update(kwargs)
        return iter([_delta("ok")])

    fake_client.chat.completions.create.side_effect = fake_create

    def fake_openai(api_key=None, base_url=None):
        client_args.update(api_key=api_key, base_url=base_url)
        return fake_client

    with patch("openai.OpenAI", side_effect=fake_openai):
        out = list(
            providers.stream_chat(
                [{"role": "user", "content": "hi"}],
                provider="openai",
                model="gpt-4o",
            )
        )
    assert out == ["ok"]
    assert client_args["api_key"] == "sk-openai"
    assert client_args["base_url"] == "https://api.openai.com/v1"
    assert calls["model"] == "gpt-4o"


def test_stream_chat_local_is_keyless_openai_compatible(monkeypatch):
    """llama.cpp server mode: no key required, base URL from LOCAL_BASE_URL."""
    monkeypatch.setenv("LOCAL_BASE_URL", "http://127.0.0.1:9999/v1")
    calls: dict = {}
    client_args: dict = {}
    fake_client = MagicMock()

    def fake_create(**kwargs):
        calls.update(kwargs)
        return iter([_delta("local says hi")])

    fake_client.chat.completions.create.side_effect = fake_create

    def fake_openai(api_key=None, base_url=None):
        client_args.update(api_key=api_key, base_url=base_url)
        return fake_client

    with patch("openai.OpenAI", side_effect=fake_openai):
        out = list(
            providers.stream_chat(
                [{"role": "user", "content": "hi"}], provider="local"
            )
        )
    assert out == ["local says hi"]
    assert client_args["base_url"] == "http://127.0.0.1:9999/v1"
    assert client_args["api_key"]  # placeholder, never empty
    assert calls["model"] == "local"


def test_stream_chat_anthropic_splits_system_and_streams(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
    calls: dict = {}

    class FakeStream:
        def __enter__(self):
            self.text_stream = iter(["t1", "t2"])
            return self

        def __exit__(self, *exc):
            return False

    fake_client = MagicMock()
    fake_client.messages.stream.side_effect = lambda **kw: (
        calls.update(kw),
        FakeStream(),
    )[1]

    with patch("anthropic.Anthropic", return_value=fake_client):
        messages = [
            {"role": "system", "content": "be brief"},
            {"role": "user", "content": "hi"},
        ]
        out = list(
            providers.stream_chat(messages, provider="anthropic")
        )
    assert out == ["t1", "t2"]
    assert calls["system"] == "be brief"
    assert calls["messages"] == [{"role": "user", "content": "hi"}]
    assert calls["model"] == "claude-sonnet-4-5"
    assert calls["max_tokens"] == 1800


def test_stream_chat_defaults_follow_env_provider(monkeypatch):
    """No provider arg + LLM_PROVIDER=openai routes to the openai SDK."""
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    client_args: dict = {}
    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = lambda **kw: iter(
        [_delta("via env")]
    )

    def fake_openai(api_key=None, base_url=None):
        client_args.update(api_key=api_key, base_url=base_url)
        return fake_client

    with patch("openai.OpenAI", side_effect=fake_openai):
        out = list(providers.stream_chat([{"role": "user", "content": "hi"}]))
    assert out == ["via env"]
    assert client_args["api_key"] == "sk-openai"


def test_stream_chat_no_key_raises_before_any_client(monkeypatch):
    """ProviderUnavailable before construction for every keyed provider."""
    for name in ("groq", "openai", "anthropic"):
        with pytest.raises(providers.ProviderUnavailable):
            list(
                providers.stream_chat(
                    [{"role": "user", "content": "hi"}], provider=name
                )
            )


def test_stream_chat_local_without_env_is_still_available():
    """local never raises from key resolution — the SDK is constructed."""
    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = lambda **kw: iter(
        [_delta("up")]
    )
    with patch("openai.OpenAI", return_value=fake_client):
        out = list(
            providers.stream_chat(
                [{"role": "user", "content": "hi"}], provider="local"
            )
        )
    assert out == ["up"]


# --------------------------------------------------------------- helpers


from unittest.mock import patch  # noqa: E402  (kept with the dispatch tests)


def patch_groq(fake_client):
    return patch("groq.Groq", return_value=fake_client)
