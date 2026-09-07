"""Paragraph-aware character chunking. Avoids tokenizers to keep RAM low."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    index: int
    section: str
    text: str


def chunk_text(
    text: str,
    *,
    max_chars: int = 1800,
    overlap: int = 200,
    section: str = "body",
) -> list[Chunk]:
    cleaned = _normalize(text)
    if not cleaned:
        return []
    max_chars = max(200, max_chars)
    overlap = max(0, min(overlap, max_chars // 3))
    paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [cleaned]

    pieces: list[str] = []
    buf = ""
    for para in paragraphs:
        if len(para) > max_chars:
            if buf:
                pieces.append(buf.strip())
                buf = ""
            pieces.extend(_split_long(para, max_chars, overlap))
            continue
        candidate = f"{buf}\n\n{para}".strip() if buf else para
        if len(candidate) <= max_chars:
            buf = candidate
        else:
            pieces.append(buf.strip())
            buf = para
    if buf.strip():
        pieces.append(buf.strip())

    chunks: list[Chunk] = []
    for i, piece in enumerate(pieces):
        if i > 0 and overlap and len(pieces[i - 1]) > overlap:
            prefix = pieces[i - 1][-overlap:].strip()
            if prefix and not piece.startswith(prefix):
                piece = f"{prefix}\n{piece}"
        chunks.append(Chunk(index=i, section=section, text=piece.strip()))
    return [c for c in chunks if c.text]


def _split_long(text: str, max_chars: int, overlap: int) -> list[str]:
    out: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + max_chars)
        if end < n:
            cut = text.rfind(" ", start + max_chars // 2, end)
            if cut > start:
                end = cut
        piece = text[start:end].strip()
        if piece:
            out.append(piece)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return out


def _normalize(text: str) -> str:
    lines = [line.strip() for line in (text or "").replace("\r\n", "\n").split("\n")]
    collapsed: list[str] = []
    blank = False
    for line in lines:
        if not line:
            if not blank and collapsed:
                collapsed.append("")
            blank = True
            continue
        blank = False
        collapsed.append(line)
    return "\n".join(collapsed).strip()
