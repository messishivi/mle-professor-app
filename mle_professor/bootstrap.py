"""First-run seed of the paper catalog into SQLite + LanceDB."""

from __future__ import annotations

from mle_professor.catalog.seed_papers import SEED_PAPERS
from mle_professor.ingest.pipeline import IngestPipeline

SEED_VERSION = "seed-v1"


def seed_if_needed(pipeline: IngestPipeline) -> int:
    store = pipeline.store
    if store.get_meta("seed_version") == SEED_VERSION:
        return 0
    created = 0
    for paper in SEED_PAPERS:
        existing = store.find_by_external("seed", paper.external_id)
        if existing and existing.chunk_count > 0:
            continue
        pipeline.ingest_seed_paper(
            external_id=paper.external_id,
            title=paper.title,
            authors=paper.authors,
            abstract=paper.abstract,
            year=paper.year,
            topics=list(paper.topics),
        )
        created += 1
    store.set_meta("seed_version", SEED_VERSION)
    return created
