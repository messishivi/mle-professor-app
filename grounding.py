"""Retrieve checkable sources so the consultant cannot invent papers."""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from database import PaperDatabase

STOP = {
    "a",
    "an",
    "the",
    "of",
    "and",
    "or",
    "for",
    "to",
    "in",
    "on",
    "is",
    "it",
    "me",
    "my",
    "about",
    "what",
    "whats",
    "explain",
    "paper",
    "model",
    "please",
}

# Product names that are not arXiv papers. Matched on query tokens.
PRODUCTS = [
    {
        "keys": frozenset({"astra", "gpt-6-astra", "gpt6astra"}),
        "title": "GPT-6 Astra (OpenAI model, launched 3 Sep 2026)",
        "url": "https://openai.com/index/gpt-6-astra/",
        "also": "https://openai.com/index/path-to-astra/",
        "snippet": (
            "OpenAI product, not an academic paper. Official name is GPT-6 Astra. "
            "API id gpt-6-astra. Do not substitute an arXiv paper titled ASTAR or A*. "
            "Google's Project Astra is a different product."
        ),
    }
]


class Source(BaseModel):
    model_config = ConfigDict(extra="ignore")

    kind: str
    title: str
    url: str = ""
    snippet: str = ""
    paper_id: Optional[str] = None


def query_tokens(text: str) -> list[str]:
    raw = re.findall(r"[A-Za-z0-9][A-Za-z0-9.+_-]{0,40}", text or "")
    out: list[str] = []
    seen: set[str] = set()
    for tok in raw:
        key = tok.lower()
        if key in STOP or key in seen:
            continue
        seen.add(key)
        out.append(tok)
    return out[:8]


def arxiv_search_query(text: str) -> Optional[str]:
    tokens = query_tokens(text)
    if not tokens:
        return None
    return " AND ".join(f"all:{t}" for t in tokens[:5])


def product_sources(text: str) -> list[Source]:
    blob = (text or "").lower()
    hits: list[Source] = []
    for spec in PRODUCTS:
        if any(k in blob for k in spec["keys"]):
            hits.append(
                Source(
                    kind="product",
                    title=spec["title"],
                    url=spec["url"],
                    snippet=spec["snippet"] + (f" Also: {spec['also']}" if spec.get("also") else ""),
                )
            )
    return hits


def library_sources(text: str, store: PaperDatabase, *, limit: int = 4) -> list[Source]:
    papers = store.list_papers(query=text, limit=limit)
    if not papers:
        tokens = query_tokens(text)
        if tokens:
            papers = store.list_papers(query=tokens[0], limit=limit)
    out: list[Source] = []
    for paper in papers[:limit]:
        out.append(
            Source(
                kind="library",
                title=paper.title,
                url=f"https://arxiv.org/abs/{paper.id}",
                snippet=(
                    getattr(paper, "summary_raw", None)
                    or getattr(paper, "abstract", None)
                    or ""
                )[:280],
                paper_id=paper.id,
            )
        )
    return out


def pulse_sources(text: str, store: PaperDatabase, *, limit: int = 4) -> list[Source]:
    raw = store.latest_pulse()
    if not raw:
        return []
    tokens = [t.lower() for t in query_tokens(text)]
    hits: list[Source] = []
    for row in raw.get("items") or []:
        if not isinstance(row, dict):
            continue
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("topic", "paper_title", "paper_id", "concept", "why")
        ).lower()
        if tokens and not any(t in blob for t in tokens):
            continue
        pid = str(row.get("paper_id") or "") or None
        hits.append(
            Source(
                kind="pulse",
                title=str(row.get("paper_title") or row.get("topic") or "Pulse item"),
                url=str(row.get("paper_url") or (f"https://arxiv.org/abs/{pid}" if pid else "")),
                snippet=str(row.get("why") or row.get("concept_blurb") or "")[:280],
                paper_id=pid,
            )
        )
        if len(hits) >= limit:
            break
    return hits


def arxiv_sources(text: str, *, limit: int = 4) -> list[Source]:
    from pipeline import fetch_atom_xml, parse_atom_feed

    query = arxiv_search_query(text)
    if not query:
        return []
    try:
        xml_bytes = fetch_atom_xml(query, max_results=limit, timeout=20)
        entries, _ = parse_atom_feed(xml_bytes)
    except Exception:
        return []
    out: list[Source] = []
    for entry in entries[:limit]:
        out.append(
            Source(
                kind="arxiv",
                title=entry.title,
                url=entry.abs_url or f"https://arxiv.org/abs/{entry.id}",
                snippet=(entry.summary or "")[:280],
                paper_id=entry.id,
            )
        )
    return out


def gather_sources(
    text: str,
    store: Optional[PaperDatabase] = None,
    *,
    include_arxiv: bool = True,
) -> list[Source]:
    sources: list[Source] = []
    sources.extend(product_sources(text))
    if store is not None:
        sources.extend(library_sources(text, store))
        sources.extend(pulse_sources(text, store))
    if include_arxiv:
        sources.extend(arxiv_sources(text))
    seen: set[str] = set()
    unique: list[Source] = []
    for src in sources:
        key = (src.kind, src.url or src.title)
        if key in seen:
            continue
        seen.add(key)
        unique.append(src)
    return unique


def format_sources_for_model(sources: list[Source]) -> str:
    if not sources:
        return (
            "Retrieved sources: none.\n"
            "Do not invent a paper, arXiv id, or URL. If you cannot verify, say so."
        )
    lines = [
        "Retrieved sources (the only papers/products you may cite):",
        "If the user asked about a named product, answer that product first. "
        "Do not replace it with a similarly named paper.",
    ]
    for i, src in enumerate(sources, start=1):
        url = src.url or "(no url)"
        pid = f" arXiv:{src.paper_id}" if src.paper_id else ""
        lines.append(f"{i}. [{src.kind}] {src.title}{pid}")
        lines.append(f"   {url}")
        if src.snippet:
            lines.append(f"   {src.snippet}")
    return "\n".join(lines)
