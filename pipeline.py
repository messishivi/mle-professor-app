"""Ingest latest papers from the official ArXiv Atom API into SQLite."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Optional, Sequence, Union
from xml.etree.ElementTree import ParseError

import requests
from pydantic import BaseModel, ConfigDict, Field, field_validator

from database import Paper, PaperDatabase, get_db, normalize_arxiv_id

ARXIV_API = "https://export.arxiv.org/api/query"
ATOM_NS = "http://www.w3.org/2005/Atom"
ARXIV_NS = "http://arxiv.org/schemas/atom"

# cs.LG, math.ST, stat.ML, q-bio.NC, hep-th, …
CATEGORY_RE = re.compile(r"^[a-z][a-z\-]+(\.[A-Za-z0-9\-]+)?$")
MAX_FEED_BYTES = 8 * 1024 * 1024
DEFAULT_CATEGORIES = ("cs.CL", "cs.LG")
USER_AGENT = "mle-professor/0.1 (personal knowledge base; +https://arxiv.org/help/api)"


class ArxivEntry(BaseModel):
    """One Atom <entry> after safe parsing."""

    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    summary: str = ""
    published: str = ""
    updated: Optional[str] = None
    authors: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    primary_category: Optional[str] = None
    pdf_url: Optional[str] = None
    abs_url: Optional[str] = None
    doi: Optional[str] = None
    comment: Optional[str] = None

    @field_validator("id")
    @classmethod
    def _canonical_id(cls, value: str) -> str:
        return normalize_arxiv_id(value)

    @field_validator("title", "summary", mode="before")
    @classmethod
    def _collapse_ws(cls, value: object) -> object:
        if isinstance(value, str):
            return re.sub(r"\s+", " ", value).strip()
        return value

    def to_paper_fields(self) -> dict:
        published_date = self.published[:10] if self.published else None
        return {
            "id": self.id,
            "title": self.title,
            "authors": self.authors,
            "published_date": published_date,
            "summary_raw": self.summary,
            "summary_structured": {
                "source": "arxiv",
                "primary_category": self.primary_category,
                "categories": self.categories,
                "published": self.published,
                "updated": self.updated,
                "pdf_url": self.pdf_url,
                "abs_url": self.abs_url,
                "doi": self.doi,
                "comment": self.comment,
            },
        }


class IngestResult(BaseModel):
    query: str
    fetched: int = 0
    upserted: int = 0
    skipped: int = 0
    papers: list[Paper] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


def _child_text(element: ET.Element, name: str, namespace: str = ATOM_NS) -> str:
    node = element.find(f"{{{namespace}}}{name}")
    if node is None or node.text is None:
        return ""
    return node.text.strip()


def _parse_entry(element: ET.Element) -> ArxivEntry:
    raw_id = _child_text(element, "id")
    title = _child_text(element, "title")
    if not raw_id or not title:
        raise ValueError("Atom entry is missing id or title.")

    authors: list[str] = []
    for author in element.findall(f"{{{ATOM_NS}}}author"):
        name = _child_text(author, "name")
        if name:
            authors.append(name)

    categories: list[str] = []
    for cat in element.findall(f"{{{ATOM_NS}}}category"):
        term = (cat.get("term") or "").strip()
        if term and term not in categories:
            categories.append(term)

    primary_el = element.find(f"{{{ARXIV_NS}}}primary_category")
    primary = (primary_el.get("term") if primary_el is not None else None) or (
        categories[0] if categories else None
    )

    pdf_url = None
    abs_url = None
    for link in element.findall(f"{{{ATOM_NS}}}link"):
        href = (link.get("href") or "").strip()
        rel = (link.get("rel") or "").strip()
        title_attr = (link.get("title") or "").strip().lower()
        mime = (link.get("type") or "").strip()
        if title_attr == "pdf" or mime == "application/pdf":
            pdf_url = href
        elif rel == "alternate" or "/abs/" in href:
            abs_url = href or abs_url

    doi_el = element.find(f"{{{ARXIV_NS}}}doi")
    comment_el = element.find(f"{{{ARXIV_NS}}}comment")

    return ArxivEntry(
        id=raw_id,
        title=title,
        summary=_child_text(element, "summary"),
        published=_child_text(element, "published"),
        updated=_child_text(element, "updated") or None,
        authors=authors,
        categories=categories,
        primary_category=primary,
        pdf_url=pdf_url,
        abs_url=abs_url or raw_id,
        doi=(doi_el.text.strip() if doi_el is not None and doi_el.text else None),
        comment=(comment_el.text.strip() if comment_el is not None and comment_el.text else None),
    )


def parse_atom_feed(xml_bytes: Union[bytes, str]) -> tuple[list[ArxivEntry], list[str]]:
    """Parse an ArXiv Atom document. Malformed entries are skipped, not fatal."""
    if isinstance(xml_bytes, str):
        payload = xml_bytes.encode("utf-8")
    else:
        payload = xml_bytes
    if len(payload) > MAX_FEED_BYTES:
        raise ValueError(f"ArXiv feed exceeds {MAX_FEED_BYTES} bytes.")
    try:
        root = ET.fromstring(payload)
    except ParseError as exc:
        raise ValueError(f"ArXiv feed is not valid XML: {exc}") from exc

    entries: list[ArxivEntry] = []
    errors: list[str] = []
    for element in root.findall(f"{{{ATOM_NS}}}entry"):
        try:
            entries.append(_parse_entry(element))
        except Exception as exc:
            snippet = _child_text(element, "id") or _child_text(element, "title") or "?"
            errors.append(f"Skipped entry {snippet!r}: {exc}")
    return entries, errors


def build_category_query(categories: Sequence[str]) -> str:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in categories:
        cat = (raw or "").strip()
        if not cat:
            continue
        if not CATEGORY_RE.match(cat):
            raise ValueError(f"Invalid ArXiv category: {raw!r}")
        if cat not in seen:
            seen.add(cat)
            cleaned.append(cat)
    if not cleaned:
        raise ValueError("Provide at least one ArXiv category.")
    return " OR ".join(f"cat:{c}" for c in cleaned)


def fetch_atom_xml(
    query: str,
    *,
    max_results: int = 20,
    start: int = 0,
    timeout: float = 30.0,
) -> bytes:
    params = {
        "search_query": query,
        "start": max(0, int(start)),
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    response = requests.get(
        ARXIV_API,
        params=params,
        headers={"User-Agent": USER_AGENT, "Accept": "application/atom+xml, application/xml"},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.content


def fetch_latest_papers(
    query_categories: Optional[Sequence[str]] = None,
    max_results: int = 20,
    *,
    db: Optional[PaperDatabase] = None,
    timeout: float = 30.0,
) -> IngestResult:
    """Pull the newest papers in the given ArXiv categories and upsert them.

    Hits ``export.arxiv.org`` Atom XML, parses each ``<entry>`` into
    ``ArxivEntry``, then writes through ``database.upsert_paper`` so duplicate
    ArXiv IDs from consecutive runs cannot insert a second row.
    """
    categories = list(query_categories) if query_categories is not None else list(DEFAULT_CATEGORIES)
    if max_results < 1 or max_results > 100:
        raise ValueError("max_results must be between 1 and 100.")
    query = build_category_query(categories)
    store = db or get_db()

    xml_bytes = fetch_atom_xml(query, max_results=max_results, timeout=timeout)
    entries, parse_errors = parse_atom_feed(xml_bytes)

    papers: list[Paper] = []
    errors = list(parse_errors)
    skipped = len(parse_errors)
    for entry in entries:
        try:
            papers.append(store.upsert_paper(**entry.to_paper_fields()))
        except Exception as exc:
            skipped += 1
            errors.append(f"Failed to save {entry.id}: {exc}")

    return IngestResult(
        query=query,
        fetched=len(entries),
        upserted=len(papers),
        skipped=skipped,
        papers=papers,
        errors=errors,
    )


if __name__ == "__main__":
    result = fetch_latest_papers()
    print(f"{result.query}: fetched {result.fetched}, saved {result.upserted}, skipped {result.skipped}")
    for paper in result.papers:
        print(f"  {paper.id}  {paper.title[:80]}")
    for err in result.errors:
        print(f"  ! {err}")
