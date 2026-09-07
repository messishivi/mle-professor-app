"""ML/AI research pulse: what people are circulating, mapped to a paper and a concept.

X does not expose a public trends API we can call from this laptop. The ML
timeline on X is driven by the same papers Hugging Face Daily Papers and
arXiv cs.LG / cs.CL / cs.AI surface, so those are the sources.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional
import requests
from pydantic import BaseModel, ConfigDict, Field

from database import PaperDatabase, get_db, normalize_arxiv_id, utcnow
from pipeline import parse_atom_feed, fetch_atom_xml, build_category_query

HF_DAILY = "https://huggingface.co/api/daily_papers"
USER_AGENT = "mle-professor/0.1 (personal ML knowledge base)"
ML_CATEGORIES = ("cs.LG", "cs.CL", "cs.AI")

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
]


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


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


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


def fetch_hf_daily(limit: int = 15) -> list[RawSignal]:
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
        out.append(
            RawSignal(
                paper_id=pid,
                title=title,
                abstract=_clean(str(paper.get("summary") or paper.get("abstract") or "")),
                authors=authors,
                source="hf_daily",
                url=f"https://arxiv.org/abs/{pid}",
            )
        )
    return out


def fetch_arxiv_ml(max_results: int = 12) -> list[RawSignal]:
    query = build_category_query(ML_CATEGORIES)
    xml_bytes = fetch_atom_xml(query, max_results=max_results, timeout=30)
    entries, _errors = parse_atom_feed(xml_bytes)
    out: list[RawSignal] = []
    for entry in entries:
        out.append(
            RawSignal(
                paper_id=entry.id,
                title=entry.title,
                abstract=entry.summary,
                authors=", ".join(entry.authors),
                source="arxiv",
                url=entry.abs_url or f"https://arxiv.org/abs/{entry.id}",
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
    for sig in signals[:18]:
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
        "Give 6 to 8 topics. Merge papers that are about the same idea. "
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
    try:
        signals.extend(fetch_hf_daily(15))
    except Exception as exc:
        errors.append(f"Hugging Face Daily Papers: {exc}")
    try:
        signals.extend(fetch_arxiv_ml(10))
    except Exception as exc:
        errors.append(f"arXiv ML feed: {exc}")
    signals = _dedupe(signals)
    items = _cluster_with_groq(signals, db)
    if items is None:
        items = _items_from_signals(signals[:12], db)
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
