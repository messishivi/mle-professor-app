"""Lightweight PDF text extraction with pypdf."""

from __future__ import annotations

from pathlib import Path


def extract_pdf_text(path: str | Path, *, max_pages: int = 40) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = reader.pages[: max(1, max_pages)]
    parts: list[str] = []
    for i, page in enumerate(pages, start=1):
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            parts.append(f"[Page {i}]\n{text}")
    return "\n\n".join(parts).strip()
