"""ML/AI research pulse: what people are circulating, mapped to a paper and a concept.

X does not expose a public trends API we can call from this laptop. The ML
timeline on X is driven by the same papers Hugging Face Daily Papers and
arXiv cs.LG / cs.CL / cs.AI surface, so those are the sources.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import requests
from pydantic import BaseModel, ConfigDict, Field

from database import PaperDatabase, get_db, normalize_arxiv_id, utcnow
from pipeline import parse_atom_feed, fetch_atom_xml, build_category_query

HF_DAILY = "https://huggingface.co/api/daily_papers"
USER_AGENT = "mle-professor/0.1 (personal ML knowledge base)"
ML_CATEGORIES = ("cs.LG", "cs.CL", "cs.AI")
# Trending + newest, but drop papers older than this (HF trending includes 2023 hits).
PULSE_WINDOW_DAYS = 60
PULSE_ITEM_LIMIT = 20

CONCEPTS: list[tuple[str, str, tuple[str, ...]]] = [
    ("Transformers", "The backbone architecture behind modern language and vision models.", ("transformer", "attention", "self-attention")),
    ("Mixture of Experts", "Sparse routing so only some model experts fire per token.", ("mixture of experts", "moe", "router", "expert")),
    ("RL post-training", "Aligning a pretrained model with preference or reward data (RLHF, DPO, GRPO).", ("rlhf", "dpo", "grpo", "ppo", "preference", "reward model")),
    ("Long context", "Letting a model read far more tokens without blowing memory or quality.", ("long context", "needle", "context window", "rope", "yarn")),
    ("Retrieval-augmented generation", "Fetching documents at query time instead of stuffing everything into weights.", ("rag", "retrieval", "retriever", "dense retrieval")),
    ("Speculative decoding", "A small draft model proposes tokens a large model verifies, to speed generation.", ("speculative decoding", "draft model", "medusa")),
    ("Quantization", "Storing weights in fewer bits so models fit and run cheaper.", ("quantization", "int8", "int4", "awq", "gptq", "gguf")),
    ("LoRA / adapters", "Training a thin low-rank update instead of the full network.", ("lora", "qlora", "adapter", "peft")),
    ("Diffusion", "Generative models that denoise step by step, now used beyond images.", ("diffusion", "flow matching", "score matching", "unet")),
    ("World models", "Learning a simulator of the environment instead of only a policy.", ("world model", "latent dynamics")),
    ("Agents", "Models that use tools, memory, and loops to complete tasks.", ("agent", "tool use", "function calling", "mcp")),
    ("Evaluation / benchmarks", "Measuring what models can actually do, and where they fail.", ("benchmark", "eval", "leaderboard", "harness")),
    ("Safety / alignment", "Stopping models from causing harm while they pursue a goal.", ("safety", "alignment", "jailbreak", "refusal")),
    ("Multimodal", "One model that takes text plus image, audio, or video.", ("multimodal", "vision-language", "vlm", "audio language")),
    ("Distributed training", "Splitting a big training job across GPUs (data, tensor, pipeline parallel).", ("fsdp", "tensor parallel", "pipeline parallel", "deepspeed")),
    ("Recommenders", "Ranking, retrieval, and personalization systems.", ("recommend", "two-tower", "ranking", "ctr", "recsys")),
]

STACK_CHOICES = [name for name, _blurb, _keys in CONCEPTS]


@dataclass(frozen=True)
class StackFit:
    label: str
    score: int
    so_what: str


CONSTRAINTS = {
    "Transformers": "Watch sequence length and attention memory before you copy the architecture.",
    "Mixture of Experts": "Serving cost is routing and all-to-all bandwidth, not just train FLOPs.",
    "RL post-training": "You need preference data and a held-out harm/quality eval, not a vibes demo.",
    "Long context": "Price the KV cache at your real context; quality often dies before the window does.",
    "Retrieval-augmented generation": "Measure retrieval recall on YOUR corpus; the generator cannot fix a dead index.",
    "Speculative decoding": "Gains depend on draft acceptance rate under your latency SLO, not blog speedups.",
    "Quantization": "Eval the drop on your task and match train/serve dtypes; WikiText is not the test.",
    "LoRA / adapters": "Decide what stays frozen in prod and how you version adapters per tenant/task.",
    "Diffusion": "Sample steps vs quality is the product constraint; batch the reverse process if you serve it.",
    "World models": "Sim-to-real gap and reset cost dominate; do not plan a policy on an uncalibrated latent.",
    "Agents": "Tool permissions, loop caps, and eval of multi-step tasks — not a single chat score.",
    "Evaluation / benchmarks": "If it does not match your user task, it is a leaderboard, not a ship gate.",
    "Safety / alignment": "Define the misuse surface and who owns the refusal policy before a prototype.",
    "Multimodal": "Modality lag and labeling cost usually beat model choice in the first quarter.",
    "Distributed training": "Topology (DP/TP/PP) has to match your GPU count and interconnect, or you buy idle time.",
    "Recommenders": "Offline AUC is not the product; watch position bias, leakage, and training-serving skew.",
}


@dataclass(frozen=True)
class DecisionMemo:
    verdict: str
    constraint: str
    so_what: str
    paper_url: str = ""
    origin: str = "heuristic"

    def as_dict(self) -> dict[str, str]:
        return {
            "verdict": self.verdict,
            "constraint_note": self.constraint,
            "so_what": self.so_what,
            "paper_url": self.paper_url,
            "origin": self.origin,
        }


class PulseItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    topic: str
    why: str = ""
    paper_id: Optional[str] = None
    paper_title: str = ""
    paper_url: str = ""
    concept: str = ""
    concept_blurb: str = ""
    in_library: bool = False
    source: str = "hf_daily"
    abstract: str = ""
    published_date: str = ""


class PulseSnapshot(BaseModel):
    fetched_at: str
    items: list[PulseItem] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class RawSignal(BaseModel):
    paper_id: str
    title: str
    abstract: str = ""
    authors: str = ""
    source: str
    url: str = ""
    published: str = ""


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def score_against_stack(item: PulseItem, stack: list[str]) -> StackFit:
    """Rank a pulse item for a working MLE's chosen stack. No extra model call."""
    if not stack:
        return StackFit(
            "Set stack",
            40,
            "Pick your stack in the sidebar to rank this as High / Watch / Skip.",
        )
    blob = " ".join(
        [
            item.topic,
            item.paper_title,
            item.concept,
            item.concept_blurb,
            item.why,
            item.abstract,
        ]
    ).lower()
    stacked = {name: keys for name, _blurb, keys in CONCEPTS if name in stack}
    hits: list[tuple[int, str]] = []
    for name, keys in stacked.items():
        n = 0
        if item.concept == name:
            n += 4
        n += sum(1 for k in keys if k in blob)
        if n:
            hits.append((n, name))
    hits.sort(reverse=True)
    if not hits:
        focus = ", ".join(stack[:3])
        return StackFit(
            "Skip",
            10,
            f"Skip unless curious — it does not overlap {focus}.",
        )
    best_n, best_name = hits[0]
    if item.concept in stack or best_n >= 3:
        return StackFit(
            "High fit",
            80 + min(20, best_n),
            f"On your stack ({best_name}). Worth a 10-minute read if you own this surface.",
        )
    return StackFit(
        "Watch",
        45 + min(20, best_n),
        f"Adjacent to {best_name}. Skim the abstract; deep-read only if it names your failure mode.",
    )


def memo_item_key(item: PulseItem) -> str:
    return (item.paper_id or item.topic)[:120]


def stack_key(stack: list[str]) -> str:
    return json.dumps(sorted({s for s in stack if s}), ensure_ascii=False)


def draft_decision_memo(item: PulseItem, fit: StackFit, stack: list[str]) -> DecisionMemo:
    """Instant Adopt/Prototype/Watch/Skip memo. No model call."""
    if fit.label == "Skip":
        verdict = "skip"
    elif fit.label == "High fit" and item.in_library:
        verdict = "adopt"
    elif fit.label == "High fit":
        verdict = "prototype"
    else:
        verdict = "watch"
    constraint = CONSTRAINTS.get(
        item.concept,
        "Name the eval, the latency budget, and the data you would need before a prototype.",
    )
    url = item.paper_url or (f"https://arxiv.org/abs/{item.paper_id}" if item.paper_id else "")
    so_what = fit.so_what
    if stack and verdict == "prototype":
        so_what = f"Prototype on {item.concept or 'this idea'} against your stack — one eval, one constraint, then kill or keep."
    elif verdict == "adopt":
        so_what = "Already in your library and on-stack. Treat it as a design input, not a new science project."
    return DecisionMemo(
        verdict=verdict,
        constraint=constraint,
        so_what=so_what,
        paper_url=url,
        origin="heuristic",
    )


def refine_decision_memo(
    item: PulseItem,
    fit: StackFit,
    stack: list[str],
    draft: DecisionMemo,
) -> DecisionMemo:
    """Optional Groq pass. Falls back to the heuristic draft on any failure."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return draft
    try:
        from groq import Groq
    except ImportError:
        return draft
    url = draft.paper_url
    payload = {
        "stack": stack,
        "fit": fit.label,
        "concept": item.concept,
        "title": item.paper_title or item.topic,
        "paper_id": item.paper_id,
        "paper_url": url,
        "abstract": (item.abstract or item.why)[:800],
        "allowed_verdicts": ["adopt", "prototype", "watch", "skip"],
    }
    try:
        client = Groq(api_key=api_key)
        model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip() or "openai/gpt-oss-120b"
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You write a 3-line decision memo for a staff MLE. JSON only: "
                        '{"verdict":"adopt|prototype|watch|skip","constraint":str,"so_what":str}. '
                        "Adopt = already investing and should use this as design input. "
                        "Prototype = worth a time-boxed experiment. Watch = skim only. Skip = ignore. "
                        "constraint = one production constraint (eval, latency, data, serving). "
                        "Use only the given paper_url; never invent an arXiv id."
                    ),
                },
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.2,
            max_tokens=400,
        )
        raw = (response.choices[0].message.content or "").strip()
        body = _parse_json(raw)
    except Exception:
        return draft
    if not isinstance(body, dict):
        return draft
    verdict = str(body.get("verdict") or draft.verdict).strip().lower()
    if verdict not in {"adopt", "prototype", "watch", "skip"}:
        verdict = draft.verdict
    constraint = str(body.get("constraint") or draft.constraint).strip() or draft.constraint
    so_what = str(body.get("so_what") or draft.so_what).strip() or draft.so_what
    return DecisionMemo(
        verdict=verdict,
        constraint=constraint,
        so_what=so_what,
        paper_url=url,
        origin="groq",
    )


def _parse_published(raw: str) -> Optional[datetime]:
    text = (raw or "").strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        try:
            dt = datetime.strptime(text[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def published_from_arxiv_id(paper_id: str) -> str:
    """Best-effort YYYY-MM-01 from a modern arXiv id (YYMM.NNNNN)."""
    match = re.match(r"^(\d{2})(\d{2})\.", paper_id or "")
    if not match:
        return ""
    year, month = int(match.group(1)), int(match.group(2))
    if not 1 <= month <= 12:
        return ""
    return f"{2000 + year:04d}-{month:02d}-01"


def is_recent(published: str = "", paper_id: str = "", *, days: int = PULSE_WINDOW_DAYS) -> bool:
    """True if the paper is inside the pulse window (default 60 days)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    for raw in (published, published_from_arxiv_id(paper_id)):
        dt = _parse_published(raw)
        if dt is not None:
            return dt >= cutoff
    return False


def match_concept(title: str, abstract: str) -> tuple[str, str]:
    blob = f"{title} {abstract}".lower()
    best: Optional[tuple[int, str, str]] = None
    for name, blurb, keys in CONCEPTS:
        hits = sum(1 for k in keys if k in blob)
        if hits and (best is None or hits > best[0]):
            best = (hits, name, blurb)
    if best is None:
        return "Deep learning methods", "A current technique in neural network training or inference."
    return best[1], best[2]


def fetch_hf_daily(limit: int = 20) -> list[RawSignal]:
    # Hugging Face Daily Papers trending. Recency is enforced after fetch.
    response = requests.get(
        HF_DAILY,
        params={"limit": max(1, min(limit, 50)), "sort": "trending"},
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        return []
    out: list[RawSignal] = []
    for row in payload:
        paper = row.get("paper") if isinstance(row, dict) else None
        if not isinstance(paper, dict):
            continue
        raw_id = str(paper.get("id") or "").strip()
        title = _clean(str(paper.get("title") or ""))
        if not raw_id or not title:
            continue
        try:
            pid = normalize_arxiv_id(raw_id)
        except ValueError:
            continue
        authors = ", ".join(
            str(a.get("name") or "")
            for a in (paper.get("authors") or [])
            if isinstance(a, dict)
        )
        published = str(
            paper.get("publishedAt") or row.get("publishedAt") or row.get("date") or ""
        )
        out.append(
            RawSignal(
                paper_id=pid,
                title=title,
                abstract=_clean(str(paper.get("summary") or paper.get("abstract") or "")),
                authors=authors,
                source="hf_daily",
                url=f"https://arxiv.org/abs/{pid}",
                published=published[:10] if published else published_from_arxiv_id(pid),
            )
        )
    return out


def fetch_arxiv_ml(max_results: int = 20) -> list[RawSignal]:
    query = build_category_query(ML_CATEGORIES)
    xml_bytes = fetch_atom_xml(query, max_results=max_results, timeout=30)
    entries, _errors = parse_atom_feed(xml_bytes)
    out: list[RawSignal] = []
    for entry in entries:
        published = (entry.published or "")[:10] or published_from_arxiv_id(entry.id)
        out.append(
            RawSignal(
                paper_id=entry.id,
                title=entry.title,
                abstract=entry.summary,
                authors=", ".join(entry.authors),
                source="arxiv",
                url=entry.abs_url or f"https://arxiv.org/abs/{entry.id}",
                published=published,
            )
        )
    return out


def _dedupe(signals: list[RawSignal]) -> list[RawSignal]:
    seen: set[str] = set()
    out: list[RawSignal] = []
    for item in signals:
        if item.paper_id in seen:
            continue
        seen.add(item.paper_id)
        out.append(item)
    return out


def _items_from_signals(signals: list[RawSignal], store: PaperDatabase) -> list[PulseItem]:
    items: list[PulseItem] = []
    for sig in signals:
        concept, blurb = match_concept(sig.title, sig.abstract)
        in_lib = store.get_paper(sig.paper_id) is not None
        items.append(
            PulseItem(
                topic=sig.title,
                why=_clean(sig.abstract)[:420],
                paper_id=sig.paper_id,
                paper_title=sig.title,
                paper_url=sig.url or f"https://arxiv.org/abs/{sig.paper_id}",
                concept=concept,
                concept_blurb=blurb,
                in_library=in_lib,
                source=sig.source,
                abstract=sig.abstract,
                published_date=(sig.published or "")[:10],
            )
        )
    return items


def _cluster_with_groq(signals: list[RawSignal], store: PaperDatabase) -> Optional[list[PulseItem]]:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key or not signals:
        return None
    try:
        from groq import Groq
    except ImportError:
        return None
    digest = []
    for sig in signals[:PULSE_ITEM_LIMIT]:
        digest.append(
            {
                "id": sig.paper_id,
                "title": sig.title,
                "abstract": sig.abstract[:500],
                "source": sig.source,
            }
        )
    client = Groq(api_key=api_key)
    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip() or "openai/gpt-oss-120b"
    prompt = (
        "You map today's ML/AI research chatter to topics a working ML engineer should track.\n"
        "Input is papers circulating on Hugging Face Daily Papers and arXiv cs.LG/CL/AI "
        "(this is what ML Twitter actually discusses; skip sports, celebrity, crypto).\n"
        "Return JSON: {\"topics\":[{\"topic\":str,\"why\":str,\"paper_id\":str,"
        "\"paper_title\":str,\"concept\":str,\"concept_blurb\":str}]}\n"
        "Give up to 20 topics, one paper each, only from this list. "
        "Do not add older or extra papers. "
        "why = 2 short plain-English sentences. concept = a canonical ML idea "
        "(e.g. Mixture of Experts, RAG, speculative decoding).\n"
        f"Papers:\n{json.dumps(digest, ensure_ascii=False)}"
    )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Return JSON only. ML/AI topics only.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=1800,
        )
        raw = (response.choices[0].message.content or "").strip()
        payload = _parse_json(raw)
    except Exception:
        return None
    rows = payload.get("topics") if isinstance(payload, dict) else payload
    if not isinstance(rows, list) or not rows:
        return None
    by_id = {s.paper_id: s for s in signals}
    items: list[PulseItem] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        topic = _clean(str(row.get("topic") or ""))
        if not topic:
            continue
        pid = str(row.get("paper_id") or "").strip()
        try:
            pid = normalize_arxiv_id(pid) if pid else None
        except ValueError:
            pid = None
        sig = by_id.get(pid) if pid else None
        if pid and sig is None:
            continue
        if sig and not is_recent(sig.published, sig.paper_id):
            continue
        title = _clean(str(row.get("paper_title") or (sig.title if sig else "")))
        concept = _clean(str(row.get("concept") or ""))
        blurb = _clean(str(row.get("concept_blurb") or ""))
        if not concept:
            concept, blurb = match_concept(title or topic, sig.abstract if sig else "")
        items.append(
            PulseItem(
                topic=topic,
                why=_clean(str(row.get("why") or "")),
                paper_id=pid,
                paper_title=title,
                paper_url=f"https://arxiv.org/abs/{pid}" if pid else "",
                concept=concept,
                concept_blurb=blurb,
                in_library=bool(pid and store.get_paper(pid)),
                source=sig.source if sig else "cluster",
                abstract=sig.abstract if sig else "",
                published_date=(sig.published if sig else "")[:10],
            )
        )
    return items or None


def _parse_json(raw: str) -> Any:
    text = (raw or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fenced:
        return json.loads(fenced.group(1).strip())
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("not json")


def refresh_pulse(store: Optional[PaperDatabase] = None) -> PulseSnapshot:
    db = store or get_db()
    errors: list[str] = []
    signals: list[RawSignal] = []
    hf: list[RawSignal] = []
    arxiv: list[RawSignal] = []
    try:
        hf = fetch_hf_daily(30)
    except Exception as exc:
        errors.append(f"Hugging Face Daily Papers: {exc}")
    try:
        arxiv = fetch_arxiv_ml(20)
    except Exception as exc:
        errors.append(f"arXiv ML feed: {exc}")
    # Keep HF trending order, then fill with newest arXiv. Do not re-sort by date.
    hf = [s for s in hf if is_recent(s.published, s.paper_id)]
    arxiv = [s for s in arxiv if is_recent(s.published, s.paper_id)]
    signals = _dedupe(hf + arxiv)[:PULSE_ITEM_LIMIT]
    items = _cluster_with_groq(signals, db)
    if items is None:
        items = _items_from_signals(signals, db)
    snapshot = PulseSnapshot(fetched_at=utcnow(), items=items, errors=errors)
    db.save_pulse([item.model_dump() for item in items])
    return snapshot


def load_pulse(store: Optional[PaperDatabase] = None) -> Optional[PulseSnapshot]:
    db = store or get_db()
    raw = db.latest_pulse()
    if not raw:
        return None
    items = []
    for row in raw["items"]:
        try:
            items.append(PulseItem.model_validate(row))
        except Exception:
            continue
    return PulseSnapshot(fetched_at=raw["fetched_at"], items=items)
