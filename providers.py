"""Provider seam for the API's chat path (P2c; multi-provider since P5 / Plan 03).

Registered providers:

- ``groq``      (default) — ``groq`` SDK; key ``GROQ_API_KEY``, model
  ``GROQ_MODEL`` (default ``openai/gpt-oss-120b``).
- ``openai``    — ``openai`` SDK; key ``OPENAI_API_KEY``, model
  ``OPENAI_MODEL`` (default ``gpt-4o-mini``), base URL ``OPENAI_BASE_URL``
  (default ``https://api.openai.com/v1``).
- ``anthropic`` — ``anthropic`` SDK; key ``ANTHROPIC_API_KEY``, model
  ``ANTHROPIC_MODEL`` (default ``claude-sonnet-4-5``).
- ``local``     — ``openai`` SDK pointed at a local OpenAI-compatible server
  (llama.cpp ``llama-server``; the original "Plan 03" target); base URL
  ``LOCAL_BASE_URL`` (default ``http://127.0.0.1:8080/v1``), model
  ``LOCAL_MODEL`` (default ``local``); no key required — an optional
  ``LOCAL_API_KEY`` is honored when set.

The active default is the ``LLM_PROVIDER`` environment variable (default
``groq``); individual requests may override the provider, model, and key
(BYOK). The API routes and the frontend depend only on this module, never on
a concrete provider client. No keys are hardcoded.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterator, Optional

from consultant import DEFAULT_MODEL

#: Active provider when ``LLM_PROVIDER`` is unset.
DEFAULT_PROVIDER = "groq"
#: Back-compat alias for P2c callers/tests; prefer :func:`resolve_provider`.
PROVIDER = DEFAULT_PROVIDER
LOCAL_BASE_URL_DEFAULT = "http://127.0.0.1:8080/v1"

# Same text the Streamlit Terminal shows when _api_ready() is false (app.py:395).
OFFLINE_MESSAGE = "Consultant is offline. Set `GROQ_API_KEY` in `.env`."

OFFLINE_MESSAGES: dict[str, str] = {
    "groq": OFFLINE_MESSAGE,
    "openai": "Consultant is offline. Set `OPENAI_API_KEY` in `.env`.",
    "anthropic": "Consultant is offline. Set `ANTHROPIC_API_KEY` in `.env`.",
    "local": (
        "Consultant is offline. Start a local OpenAI-compatible server "
        "(e.g. llama.cpp) and set `LOCAL_BASE_URL` in `.env`."
    ),
}


class ProviderUnavailable(RuntimeError):
    """No usable API key (and no BYOK override for this request)."""


class UnknownProvider(ValueError):
    """A provider name that is not in :data:`PROVIDERS`."""


@dataclass(frozen=True)
class ProviderSpec:
    """Static configuration for one registered provider."""

    name: str
    key_env: str
    model_env: str
    default_model: str
    base_url: Optional[str]  # None -> the provider SDK's own default
    requires_key: bool


PROVIDERS: dict[str, ProviderSpec] = {
    "groq": ProviderSpec(
        name="groq",
        key_env="GROQ_API_KEY",
        model_env="GROQ_MODEL",
        default_model=DEFAULT_MODEL,
        base_url="https://api.groq.com/openai/v1",
        requires_key=True,
    ),
    "openai": ProviderSpec(
        name="openai",
        key_env="OPENAI_API_KEY",
        model_env="OPENAI_MODEL",
        default_model="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
        requires_key=True,
    ),
    "anthropic": ProviderSpec(
        name="anthropic",
        key_env="ANTHROPIC_API_KEY",
        model_env="ANTHROPIC_MODEL",
        default_model="claude-sonnet-4-5",
        base_url=None,
        requires_key=True,
    ),
    "local": ProviderSpec(
        name="local",
        key_env="LOCAL_API_KEY",
        model_env="LOCAL_MODEL",
        default_model="local",
        base_url=LOCAL_BASE_URL_DEFAULT,
        requires_key=False,
    ),
}


def offline_message(provider: str) -> str:
    """The exact UI text shown when ``provider`` cannot be configured."""
    return OFFLINE_MESSAGES.get(
        provider, f"Consultant is offline. Unknown provider `{provider}`."
    )


def resolve_provider(requested: Optional[str] = None) -> str:
    """Request override > ``LLM_PROVIDER`` env > :data:`DEFAULT_PROVIDER`."""
    name = (requested or os.getenv("LLM_PROVIDER", "")).strip().lower() or DEFAULT_PROVIDER
    if name not in PROVIDERS:
        raise UnknownProvider(
            f"Unknown provider '{name}'. Valid providers: {', '.join(PROVIDERS)}."
        )
    return name


def resolve_key(provider: str, api_key: Optional[str] = None) -> str:
    """BYOK override wins; otherwise the provider's key env.

    Raises :class:`ProviderUnavailable` when a key is required and neither
    exists. ``local`` never raises (auth-less server); any ``LOCAL_API_KEY``
    is honored when present.
    """
    spec = PROVIDERS[provider]
    key = (api_key or os.getenv(spec.key_env, "")).strip()
    if not key and spec.requires_key:
        raise ProviderUnavailable(offline_message(provider))
    return key


def resolve_model(provider: str, model: Optional[str] = None) -> str:
    """Request override > provider model env > provider default."""
    spec = PROVIDERS[provider]
    return (model or os.getenv(spec.model_env, "")).strip() or spec.default_model


def resolve_base_url(provider: str) -> Optional[str]:
    """Base URL for the OpenAI-compatible paths; None -> provider SDK default."""
    if provider == "local":
        return os.getenv("LOCAL_BASE_URL", "").strip() or LOCAL_BASE_URL_DEFAULT
    if provider == "openai":
        return os.getenv("OPENAI_BASE_URL", "").strip() or PROVIDERS["openai"].base_url
    spec = PROVIDERS.get(provider)
    return spec.base_url if spec else None


def _iter_openai_chunks(stream) -> Iterator[str]:
    """Shared delta iterator for the OpenAI-compatible streaming shape
    (groq SDK, openai SDK, and local OpenAI-compatible servers)."""
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta is not None and delta.content:
            yield delta.content


def stream_chat(
    messages: list[dict[str, str]],
    *,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 1800,
) -> Iterator[str]:
    """Yield text deltas for a chat completion on the resolved provider.

    ``groq`` uses the ``groq`` SDK; ``openai`` and ``local`` share the
    ``openai`` SDK (llama.cpp server mode is OpenAI-compatible); ``anthropic``
    uses the ``anthropic`` SDK's streaming messages API.

    Raises :class:`ProviderUnavailable` before any network call when no key
    is available; provider/network errors propagate to the caller.
    """
    name = resolve_provider(provider)
    key = resolve_key(name, api_key)
    model_name = resolve_model(name, model)

    if name == "groq":
        from groq import Groq  # lazy: keeps import light, seam stays patchable

        client = Groq(api_key=key)
        stream = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        yield from _iter_openai_chunks(stream)
    elif name in ("openai", "local"):
        from openai import OpenAI  # lazy: same seam rules as the groq path

        client = OpenAI(api_key=key or "no-key", base_url=resolve_base_url(name))
        stream = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        yield from _iter_openai_chunks(stream)
    else:  # anthropic
        from anthropic import Anthropic  # lazy: same seam rules as the groq path

        system = next(
            (m["content"] for m in messages if m["role"] == "system"), None
        )
        turns = [
            {"role": m["role"], "content": m["content"]}
            for m in messages
            if m["role"] in ("user", "assistant")
        ]
        client = Anthropic(api_key=key)
        with client.messages.stream(
            model=model_name,
            messages=turns,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
        ) as stream:
            for text in stream.text_stream:
                yield text
