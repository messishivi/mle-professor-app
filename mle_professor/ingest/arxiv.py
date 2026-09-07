"""Fetch arXiv metadata and optional PDF."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ARXIV_ID_RE = re.compile(
    r"(?:arxiv:)?(?:https?://arxiv.org/(?:abs|pdf)/)?(\d{4}\.\d{4,5}(?:v\d+)?|[a-z\-]+/\d{7})(?:\.pdf)?",
    re.IGNORECASE,
)


@dataclass
class ArxivPaper:
    arxiv_id: str
    title: str
    authors: str
    abstract: str
    year: int | None
    venue: str
    pdf_url: str


def normalize_arxiv_id(raw: str) -> str:
    text = (raw or "").strip()
    match = ARXIV_ID_RE.search(text)
    if not match:
        raise ValueError(f"Could not parse an arXiv id from: {raw!r}")
    return match.group(1)


def fetch_arxiv(arxiv_id: str) -> ArxivPaper:
    import arxiv

    clean = normalize_arxiv_id(arxiv_id)
    client = arxiv.Client()
    results = list(client.results(arxiv.Search(id_list=[clean])))
    if not results:
        raise ValueError(f"No arXiv result for {clean}")
    paper = results[0]
    year = paper.published.year if paper.published else None
    authors = ", ".join(a.name for a in paper.authors)
    return ArxivPaper(
        arxiv_id=clean,
        title=_clean_ws(paper.title),
        authors=authors,
        abstract=_clean_ws(paper.summary),
        year=year,
        venue="arXiv",
        pdf_url=paper.pdf_url,
    )


def download_pdf(arxiv_id: str, dest_dir: str | Path) -> Path:
    import arxiv

    clean = normalize_arxiv_id(arxiv_id)
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    client = arxiv.Client()
    results = list(client.results(arxiv.Search(id_list=[clean])))
    if not results:
        raise ValueError(f"No arXiv result for {clean}")
    path = results[0].download_pdf(dirpath=str(dest), filename=f"{clean.replace('/', '_')}.pdf")
    return Path(path)


def _clean_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())
