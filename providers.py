"""Provider seam for the API's chat path (P2c).

Today: Groq only — key from the request (BYOK) or the ``GROQ_API_KEY``
environment variable, model from ``GROQ_MODEL``. Plan 03 (local llama.cpp)
plugs in here: the API routes and the frontend depend only on this module,
never on a concrete provider client. No keys are hardcoded.
"""

from __future__ import annotations

import os
from typing import Iterator, Optional

from consultant import DEFAULT_MODEL

PROVIDER = "groq"
# Same text the Streamlit Terminal shows when _api_ready() is false (app.py:395).
OFFLINE_MESSAGE = "Consultant is offline. Set `GROQ_API_KEY` in `.env`."


class ProviderUnavailable(RuntimeError):
    """No usable API key (and no BYOK override for this request)."""


def resolve_key(api_key: Optional[str] = None) -> str:
    """BYOK override wins; otherwise the environment. Raises when neither exists."""
    key = (api_key or os.getenv("GROQ_API_KEY", "")).strip()
    if not key:
        raise ProviderUnavailable(OFFLINE_MESSAGE)
    return key


def resolve_model() -> str:
    """Same rule as consultant._resolve_client: GROQ_MODEL env, else default."""
    return os.getenv("GROQ_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def stream_chat(
    messages: list[dict[str, str]],
    *,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 1800,
) -> Iterator[str]:
    """Yield text deltas for a chat completion (Groq, ``stream=True``).

    Raises :class:`ProviderUnavailable` before any network call when no key
    is available; provider/network errors propagate to the caller.
    """
    from groq import Groq  # lazy: keeps import light, seam stays patchable

    key = resolve_key(api_key)
    client = Groq(api_key=key)
    stream = client.chat.completions.create(
        model=model or resolve_model(),
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta is not None and delta.content:
            yield delta.content
