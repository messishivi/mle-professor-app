from mle_professor.bootstrap import seed_if_needed
from mle_professor.db.sqlite import PaperStore
from mle_professor.embeddings.encoder import HashingEncoder, build_encoder
from mle_professor.embeddings.store import VectorStore
from mle_professor.ingest.pipeline import IngestPipeline
from mle_professor.interview.bank import QUESTIONS, TOPICS, questions_for
from mle_professor.interview.engine import InterviewEngine
from mle_professor.llm.client import LLMClient


def test_bank_covers_every_topic():
    assert len(QUESTIONS) >= 30
    for topic in TOPICS:
        slice_ = questions_for(topic)
        assert slice_, topic
        assert all(q.answer and q.question for q in slice_)


def test_bank_session_and_empty_grade(settings):
    store = PaperStore(settings.sqlite_path)
    engine = InterviewEngine(store, LLMClient(settings))
    sid = engine.start_bank_session(mode="quiz", topic="Deep Learning", n=3)
    items = store.list_items(sid)
    assert len(items) == 3
    grade = engine.submit(items[0], "")
    assert grade.score == 0
    finished = engine.finish(sid)
    assert finished.completed_at is not None


def test_seed_pipeline_indexes_searchable_chunks(settings):
    store = PaperStore(settings.sqlite_path)
    encoder = build_encoder(settings)
    assert isinstance(encoder, HashingEncoder)
    vectors = VectorStore(settings.lancedb_path, encoder)
    pipeline = IngestPipeline(store, vectors, encoder, settings)
    created = seed_if_needed(pipeline)
    assert created > 0
    assert seed_if_needed(pipeline) == 0
    stats = store.stats()
    assert stats.papers >= 8
    hits = vectors.search("self-attention transformer encoder decoder", k=5)
    assert hits
    titles = " ".join(h.title.lower() for h in hits)
    assert "attention" in titles
