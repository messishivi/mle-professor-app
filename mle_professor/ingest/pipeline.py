"""Ingest papers and notes into SQLite + LanceDB without keeping large models hot."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from mle_professor.config import Settings, get_settings
from mle_professor.db.sqlite import PaperStore
from mle_professor.embeddings.encoder import Encoder
from mle_professor.embeddings.store import VectorStore
from mle_professor.ingest.arxiv import download_pdf, fetch_arxiv
from mle_professor.ingest.chunker import Chunk, chunk_text
from mle_professor.ingest.pdf import extract_pdf_text


Progress = Callable[[str], None]


class IngestPipeline:
    def __init__(
        self,
        store: PaperStore,
        vectors: VectorStore,
        encoder: Encoder,
        settings: Settings | None = None,
    ) -> None:
        self.store = store
        self.vectors = vectors
        self.encoder = encoder
        self.settings = settings or get_settings()

    def ingest_arxiv(
        self,
        arxiv_id: str,
        *,
        topics: Optional[list[str]] = None,
        download_full_pdf: bool = False,
        progress: Optional[Progress] = None,
    ) -> int:
        log = progress or (lambda _msg: None)
        log("Fetching arXiv metadata…")
        paper = fetch_arxiv(arxiv_id)
        pdf_path = None
        body = f"Title: {paper.title}\nAuthors: {paper.authors}\n\nAbstract\n{paper.abstract}"
        if download_full_pdf:
            log("Downloading PDF (capped extraction)…")
            pdf_path = download_pdf(paper.arxiv_id, self.settings.pdf_dir)
            extracted = extract_pdf_text(pdf_path, max_pages=40)
            if extracted:
                body = f"{body}\n\nFull text\n{extracted}"
        paper_id = self.store.add_paper(
            source="arxiv",
            external_id=paper.arxiv_id,
            title=paper.title,
            authors=paper.authors,
            abstract=paper.abstract,
            year=paper.year,
            venue=paper.venue,
            pdf_path=str(pdf_path) if pdf_path else None,
            topics=topics,
        )
        log("Chunking and embedding…")
        self._index_paper(paper_id, paper.title, body, default_section="abstract")
        return paper_id

    def ingest_pdf(
        self,
        path: str | Path,
        *,
        title: str = "",
        authors: str = "",
        topics: Optional[list[str]] = None,
        progress: Optional[Progress] = None,
    ) -> int:
        log = progress or (lambda _msg: None)
        src = Path(path)
        log("Extracting PDF text…")
        text = extract_pdf_text(src, max_pages=40)
        if not text:
            raise ValueError("No extractable text in this PDF.")
        dest = self.settings.pdf_dir / src.name
        if src.resolve() != dest.resolve():
            dest.write_bytes(src.read_bytes())
        paper_title = title.strip() or src.stem.replace("_", " ")
        paper_id = self.store.add_paper(
            source="pdf",
            external_id=src.name,
            title=paper_title,
            authors=authors,
            abstract=text[:1200],
            pdf_path=str(dest),
            topics=topics,
        )
        log("Chunking and embedding…")
        self._index_paper(paper_id, paper_title, text, default_section="pdf")
        return paper_id

    def ingest_note(
        self,
        *,
        title: str,
        body: str,
        paper_id: Optional[int] = None,
        topics: Optional[list[str]] = None,
        progress: Optional[Progress] = None,
    ) -> int:
        log = progress or (lambda _msg: None)
        note_id = self.store.add_note(
            title=title, body=body, paper_id=paper_id, topics=topics
        )
        log("Embedding note…")
        chunks = chunk_text(
            f"{title}\n\n{body}",
            max_chars=self.settings.chunk_chars,
            overlap=self.settings.chunk_overlap,
            section="note",
        )
        self._write_chunks(
            chunks,
            title=title,
            source="note",
            paper_id=paper_id or 0,
            note_id=note_id,
        )
        self.store.set_note_chunk_count(note_id, len(chunks))
        return note_id

    def ingest_seed_paper(
        self,
        *,
        external_id: str,
        title: str,
        authors: str,
        abstract: str,
        year: Optional[int],
        topics: list[str],
        venue: str = "arXiv",
    ) -> int:
        paper_id = self.store.add_paper(
            source="seed",
            external_id=external_id,
            title=title,
            authors=authors,
            abstract=abstract,
            year=year,
            venue=venue,
            topics=topics,
        )
        body = f"Title: {title}\nAuthors: {authors}\n\nAbstract\n{abstract}"
        self._index_paper(paper_id, title, body, default_section="abstract")
        return paper_id

    def delete_paper(self, paper_id: int) -> None:
        self.vectors.delete_paper(paper_id)
        self.store.delete_paper(paper_id)

    def _index_paper(
        self, paper_id: int, title: str, body: str, *, default_section: str
    ) -> None:
        self.vectors.delete_paper(paper_id)
        chunks = chunk_text(
            body,
            max_chars=self.settings.chunk_chars,
            overlap=self.settings.chunk_overlap,
            section=default_section,
        )
        self._write_chunks(
            chunks, title=title, source="paper", paper_id=paper_id, note_id=0
        )
        self.store.set_chunk_count(paper_id, len(chunks))

    def _write_chunks(
        self,
        chunks: list[Chunk],
        *,
        title: str,
        source: str,
        paper_id: int,
        note_id: int,
    ) -> None:
        if not chunks:
            return
        records = []
        texts = []
        for chunk in chunks:
            prefix = "p" if source != "note" else "n"
            parent = paper_id if source != "note" else note_id
            records.append(
                {
                    "id": f"{prefix}{parent}:{chunk.index}",
                    "paper_id": paper_id,
                    "note_id": note_id,
                    "source": source,
                    "title": title,
                    "section": chunk.section,
                    "chunk_index": chunk.index,
                    "text": chunk.text,
                }
            )
            texts.append(chunk.text)
        vectors = self.encoder.encode(texts, is_query=False)
        self.vectors.add_chunks(chunks=records, vectors=vectors)
