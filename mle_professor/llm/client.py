"""SpaceXAI (xAI) client. Reasoning stays in the cloud; nothing large is loaded locally."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any, Optional

from mle_professor.config import Settings, get_settings


class LLMNotConfigured(RuntimeError):
    pass


class LLMClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = None

    @property
    def configured(self) -> bool:
        return bool(self.settings.xai_api_key)

    @property
    def model(self) -> str:
        return self.settings.xai_model

    def _openai(self):
        if not self.configured:
            raise LLMNotConfigured(
                "Set XAI_API_KEY (preferred) or OPENAI_API_KEY in .env to enable "
                "cloud reasoning, chat, and grading."
            )
        if self._client is None:
            import httpx
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self.settings.xai_api_key,
                base_url=self.settings.xai_base_url,
                timeout=httpx.Timeout(3600.0),
            )
        return self._client

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.4,
        max_tokens: int = 1800,
    ) -> str:
        response = self._openai().chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return (response.choices[0].message.content or "").strip()

    def stream(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.4,
        max_tokens: int = 1800,
    ) -> Iterator[str]:
        stream = self._openai().chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            piece = getattr(delta, "content", None)
            if piece:
                yield piece

    def json_chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 2000,
    ) -> Any:
        try:
            response = self._openai().chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content or "{}"
        except Exception:
            raw = self.chat(messages, temperature=temperature, max_tokens=max_tokens)
        return _parse_json(raw)


def _parse_json(raw: str) -> Any:
    text = (raw or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fenced:
        return json.loads(fenced.group(1).strip())
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    start_l = text.find("[")
    end_l = text.rfind("]")
    if start_l >= 0 and end_l > start_l:
        return json.loads(text[start_l : end_l + 1])
    raise ValueError("Model did not return JSON.")
