"""Staff-level consultant via the Groq SDK.

Layer 1 (default): map a paper onto the user's live system.
Layer 2: short plain-English briefing.
Layer 3: production systems critic.

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

APPLY_PROMPT = (
    "You are an MLE implementation guide. The user has a live production system — "
    "whatever they typed (RL post-training, RAG, rec, training stack, agents, …). "
    "A two-tower rec is only one possible example. They already know some papers. "
    "Your job is not a survey. It is: what in THIS paper is relevant to THEIR "
    "application, and the path to put it in production.\n\n"
    "Always use these sections:\n"
    "1. Which paper/product is this? (disambiguate names; use retrieved URLs only)\n"
    "2. Relevance map vs their system — a small table. Rows are generic production "
    "pieces, renamed to match what they actually ship:\n"
    "   user (who/what is requesting or being modeled),\n"
    "   item / target (what is scored, generated, retrieved, or acted on),\n"
    "   data, training, serving, eval.\n"
    "   Add a row only if that module exists in their Application context "
    "(retriever, ranker, reward model, router, …). "
    "Do not invent a persona tower, retrieval stage, or ranker unless they have one. "
    "Do not force rec vocabulary onto an unrelated stack. "
    "For each row: Use / Adapt / Ignore and one clause why.\n"
    "3. Delta vs (a) papers they already use and (b) their repo README if present. "
    "What is new vs modules, data contracts, and train/serve paths that already exist. "
    "Do not recommend rebuilding what the README already describes.\n"
    "4. Implementation path — 4 to 6 numbered steps they can do this quarter "
    "(data contract, where the code would plug in, eval, A/B, kill criteria).\n"
    "5. Skip list — parts of the paper they should not port.\n"
    "6. Sources — markdown links you actually used.\n\n"
    "Rules:\n"
    "- Write for a staff MLE. Short. Concrete. Name modules, not vibes.\n"
    "- If Application context is missing, ask for the system in one line, then still "
    "map onto user / item / data / training / serving / eval.\n"
    "- If the user names a product (OpenAI Astra), answer the product, not a similarly named paper.\n"
    "- Only cite retrieved sources with those exact URLs. Never invent an arXiv id.\n"
    "- Do not dump FLOPs/HBM unless they asked for systems detail."
)

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

# Default layer: map a paper onto the user's live system.
SYSTEM_PROMPT = APPLY_PROMPT
DEFAULT_LAYER = "apply"
LAYERS = {
    "apply": APPLY_PROMPT,
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
    from grounding import Source, format_sources_for_model, gather_sources

    packed = gather_sources(user_message, store)
    if store is not None and hasattr(store, "get_repo_url"):
        repo_url = store.get_repo_url()
        readme = store.get_repo_readme() if hasattr(store, "get_repo_readme") else ""
        readme_url = (
            store.get_repo_readme_url() if hasattr(store, "get_repo_readme_url") else ""
        )
        if repo_url or readme:
            packed = list(packed) + [
                Source(
                    kind="repo",
                    title="Your repo README",
                    url=readme_url or repo_url,
                    snippet=(readme or "")[:280],
                )
            ]
    retrieved = format_sources_for_model(packed)
    if store is not None and hasattr(store, "get_application"):
        app_block = format_application_context(
            store.get_application(),
            store.get_stack(),
            store.get_known_papers(),
            repo_url=store.get_repo_url() if hasattr(store, "get_repo_url") else "",
            repo_readme=store.get_repo_readme() if hasattr(store, "get_repo_readme") else "",
        )
        if app_block:
            retrieved = f"{app_block}\n\n{retrieved}"
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


def format_application_context(
    application: str = "",
    stack: Optional[list[str]] = None,
    known_papers: str = "",
    *,
    repo_url: str = "",
    repo_readme: str = "",
) -> str:
    application = (application or "").strip()
    known_papers = (known_papers or "").strip()
    repo_url = (repo_url or "").strip()
    repo_readme = (repo_readme or "").strip()
    stack = [s for s in (stack or []) if s]
    if not application and not stack and not known_papers and not repo_url and not repo_readme:
        return ""
    lines = [
        "The user's current system (implementation target — map the paper onto this):",
        f"- Building: {application or '(not specified)'}",
        f"- Stack: {', '.join(stack) or '(not specified)'}",
        f"- Papers they already use: {known_papers or '(none listed)'}",
    ]
    if repo_url:
        lines.append(f"- Repo: {repo_url}")
    if repo_readme:
        lines.append("- README (what they already ship — delta against this; do not rebuild it):")
        lines.append(repo_readme)
    lines.append(
        "Do not write a generic survey. Name relevance-map rows after THIS system "
        "(user, item/target, data, training, serving, eval). Do not force a "
        "recommender template unless they described one. Use / Adapt / Ignore, "
        "then the implementation path. Section 3 (delta) must use the README and "
        "known papers when they are present."
    )
    return "\n".join(lines)


def paper_apply_prompt(
    paper: Any,
    *,
    application: str = "",
    known_papers: str = "",
    repo_url: str = "",
) -> str:
    """User message: map this paper onto the MLE's live application."""
    title = getattr(paper, "title", "") or "Untitled"
    authors = getattr(paper, "authors", "") or ""
    arxiv_id = getattr(paper, "id", "") or ""
    published = getattr(paper, "published_date", "") or ""
    abstract = getattr(paper, "summary_raw", None) or getattr(paper, "abstract", None) or ""
    extra = ""
    if application.strip():
        extra += f"\nMy system: {application.strip()}\n"
    if known_papers.strip():
        extra += f"I already use: {known_papers.strip()}\n"
    if repo_url.strip():
        extra += (
            f"My repo: {repo_url.strip()}\n"
            "Delta against the repo README in retrieved sources — what is already shipped.\n"
        )
    return (
        "Map this paper onto my current application. What is relevant, what to ignore, "
        "and how I implement it. Use user / item (or target) / data / training / serving / eval; "
        "rename those to my modules. Do not assume a rec stack.\n"
        f"{extra}\n"
        f"Title: {title}\n"
        f"Authors: {authors}\n"
        f"arXiv: {arxiv_id}\n"
        f"Date: {published}\n\n"
        f"Abstract:\n{abstract}"
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
