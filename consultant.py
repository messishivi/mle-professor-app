"""Staff-level consultant via the Groq SDK.

Layer 1 (default): short plain-English paper briefing.
Layer 2: production systems critic (original persona).

The API key is read from ``GROQ_API_KEY`` only — never hardcoded.
Default model: ``openai/gpt-oss-120b``. Groq decommissioned ``llama-3.1-70b-versatile``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional, Sequence

from dotenv import load_dotenv
from groq import Groq
from pydantic import BaseModel, ConfigDict, Field, field_validator

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env", override=True)

EXPLAIN_PROMPT = (
    "You are MLE Professor's first-layer explainer. Give a short, plain-English "
    "briefing of a research paper, model, or ML idea.\n\n"
    "The reader is a working ML engineer, not a beginner in a survey course and "
    "not someone asking for a production war-room review.\n\n"
    "Always answer in three tight sections, about 4–6 sentences each:\n"
    "1. What this is (product vs paper — do not mix them up)\n"
    "2. What it actually does / what they did\n"
    "3. Why anyone should care\n"
    "Then a Sources section with markdown links you actually used.\n\n"
    "Rules:\n"
    "- Start with the overall view. Be concrete and short.\n"
    "- If the user names a product (for example OpenAI Astra / GPT-6 Astra), "
    "answer that product. Do not swap in a similarly named paper (ASTAR, A*).\n"
    "- Only cite papers that appear in Retrieved sources, using those exact URLs.\n"
    "- Never invent an arXiv id, paper title, author, or link. If sources are "
    "empty or off-topic, say you cannot verify and do not fabricate a paper.\n"
    "- No formulas unless the user asks.\n"
    "- No KV cache, HBM, FLOPs/token, or tensor/pipeline/data-parallelism layouts "
    "unless the user explicitly asks for systems detail.\n"
    "- If a term is unavoidable, define it in one clause.\n"
    "- Do not pad, lecture, or dump metrics."
)

SYSTEMS_PROMPT = (
    "You are a Distinguished AI Research Professor and Principal ML Systems Consultant. "
    "Your user is a Staff Machine Learning Engineer with 7+ years of experience. "
    "Strictly skip all high-level, elementary, or introductory explanations. "
    "Focus entirely on granular production realities: KV cache optimization footprint, "
    "memory bandwidth bottlenecks, computational cost formulas (FLOPs/token), and "
    "distributed training setups (tensor, pipeline, and data parallelism layouts). "
    "Challenge architectural flaws constructively and aggressively."
)

# First layer is the default public prompt.
SYSTEM_PROMPT = EXPLAIN_PROMPT
DEFAULT_LAYER = "explain"
LAYERS = {
    "explain": EXPLAIN_PROMPT,
    "systems": SYSTEMS_PROMPT,
}

ALLOWED_ROLES = {"user", "assistant"}
MAX_HISTORY = 40
DEFAULT_MODEL = "openai/gpt-oss-120b"


class ChatTurn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: str
    content: str = ""

    @field_validator("role")
    @classmethod
    def _role(cls, value: str) -> str:
        role = (value or "").strip().lower()
        if role == "system":
            raise ValueError("History must not carry a system role; the consultant owns that.")
        if role not in ALLOWED_ROLES:
            raise ValueError(f"Unsupported chat role: {value!r}")
        return role

    @field_validator("content")
    @classmethod
    def _content(cls, value: str) -> str:
        return (value or "").strip()


class ConsultantReply(BaseModel):
    content: str
    model: str
    provider: str
    layer: str = DEFAULT_LAYER
    messages: list[dict[str, str]] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)


def resolve_layer(layer: Optional[str]) -> str:
    name = (layer or DEFAULT_LAYER).strip().lower()
    if name not in LAYERS:
        raise ValueError(f"Unknown consultant layer: {layer!r}. Use explain or systems.")
    return name


def prompt_for(layer: Optional[str] = None) -> str:
    return LAYERS[resolve_layer(layer)]


def _resolve_client() -> tuple[Groq, str]:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Set GROQ_API_KEY in the environment or .env.")
    model = os.getenv("GROQ_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    return Groq(api_key=api_key), model


def _coerce_history(history: Optional[Sequence[Any]]) -> list[ChatTurn]:
    if not history:
        return []
    turns: list[ChatTurn] = []
    for item in history:
        if isinstance(item, ChatTurn):
            turn = item
        elif isinstance(item, dict):
            role = str(item.get("role") or "")
            if role.strip().lower() == "system":
                continue
            turn = ChatTurn(role=role, content=str(item.get("content") or ""))
        elif isinstance(item, (tuple, list)) and len(item) >= 2:
            turn = ChatTurn(role=str(item[0]), content=str(item[1]))
        else:
            raise ValueError(f"Cannot interpret history item: {item!r}")
        if turn.content:
            turns.append(turn)
    return turns[-MAX_HISTORY:]


def build_messages(
    user_message: str,
    history: Optional[Sequence[Any]] = None,
    *,
    layer: Optional[str] = None,
    retrieved: str = "",
) -> list[dict[str, str]]:
    text = (user_message or "").strip()
    if not text:
        raise ValueError("user_message is empty.")
    messages: list[dict[str, str]] = [
        {"role": "system", "content": prompt_for(layer)},
    ]
    for turn in _coerce_history(history):
        messages.append({"role": turn.role, "content": turn.content})
    if retrieved.strip():
        text = f"{retrieved.strip()}\n\nUser question:\n{text}"
    messages.append({"role": "user", "content": text})
    return messages


class Consultant:
    """Thin wrapper around the Groq chat completions API."""

    def __init__(
        self,
        client: Optional[Groq] = None,
        *,
        model: Optional[str] = None,
    ) -> None:
        if client is None:
            client, resolved_model = _resolve_client()
            self.client = client
            self.model = model or resolved_model
        else:
            self.client = client
            self.model = model or os.getenv("GROQ_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
        self.provider = "groq"

    def chat_with_consultant(
        self,
        user_message: str,
        history: Optional[Sequence[Any]] = None,
        *,
        layer: Optional[str] = None,
        retrieved: str = "",
        sources: Optional[list[dict[str, Any]]] = None,
        temperature: float = 0.3,
        max_tokens: int = 1800,
    ) -> ConsultantReply:
        chosen = resolve_layer(layer)
        messages = build_messages(
            user_message, history, layer=chosen, retrieved=retrieved
        )
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = ""
        if response.choices:
            content = (response.choices[0].message.content or "").strip()
        used_model = getattr(response, "model", None) or self.model
        return ConsultantReply(
            content=content,
            model=used_model,
            provider=self.provider,
            layer=chosen,
            messages=messages,
            sources=list(sources or []),
        )


_default: Optional[Consultant] = None


def chat_with_consultant(
    user_message: str,
    history: Optional[Sequence[Any]] = None,
    *,
    layer: Optional[str] = None,
    store: Any = None,
    temperature: float = 0.3,
    max_tokens: int = 1800,
) -> ConsultantReply:
    """Send ``user_message`` to the consultant. Default layer is plain-English explain."""
    global _default
    load_dotenv(ROOT / ".env", override=True)
    model = os.getenv("GROQ_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    if _default is None or _default.model != model:
        _default = Consultant(model=model)
    from grounding import format_sources_for_model, gather_sources

    packed = gather_sources(user_message, store)
    retrieved = format_sources_for_model(packed)
    source_rows = [s.model_dump(exclude_none=True) for s in packed]
    return _default.chat_with_consultant(
        user_message,
        history,
        layer=layer,
        retrieved=retrieved,
        sources=source_rows,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def paper_explain_prompt(paper: Any) -> str:
    """User message that asks layer 1 to brief a stored paper."""
    title = getattr(paper, "title", "") or "Untitled"
    authors = getattr(paper, "authors", "") or ""
    arxiv_id = getattr(paper, "id", "") or ""
    published = getattr(paper, "published_date", "") or ""
    abstract = getattr(paper, "summary_raw", "") or ""
    return (
        "Explain this paper in short plain English.\n\n"
        f"Title: {title}\n"
        f"Authors: {authors}\n"
        f"arXiv: {arxiv_id}\n"
        f"Date: {published}\n\n"
        f"Abstract:\n{abstract}"
    )
