from mle_professor.db.sqlite import PaperStore


def test_paper_roundtrip(settings):
    store = PaperStore(settings.sqlite_path)
    pid = store.add_paper(
        source="arxiv",
        external_id="1706.03762",
        title="Attention Is All You Need",
        authors="Vaswani et al.",
        abstract="Transformers.",
        year=2017,
        topics=["Transformers & NLP"],
    )
    paper = store.get_paper(pid)
    assert paper is not None
    assert paper.title.startswith("Attention")
    assert paper.topics == ["Transformers & NLP"]
    same = store.add_paper(
        source="arxiv",
        external_id="1706.03762",
        title="Attention Is All You Need",
        abstract="Updated abstract.",
    )
    assert same == pid
    updated = store.get_paper(pid)
    assert updated.abstract == "Updated abstract."


def test_notes_and_stats(settings):
    store = PaperStore(settings.sqlite_path)
    pid = store.add_paper(source="pdf", title="Notes host", abstract="abs")
    store.set_chunk_count(pid, 3)
    nid = store.add_note(title="Takeaway", body="Residuals help optimization.", paper_id=pid)
    store.set_note_chunk_count(nid, 1)
    stats = store.stats()
    assert stats.papers == 1
    assert stats.notes == 1
    assert stats.chunks == 4


def test_interview_session(settings):
    store = PaperStore(settings.sqlite_path)
    sid = store.start_session(mode="quiz", topic="Deep Learning")
    item_id = store.add_item(
        sid,
        question="What is a residual?",
        model_answer="A skip connection.",
        question_id="d-01",
        topic="Deep Learning",
    )
    store.record_answer(item_id, user_answer="skip connection", evaluation="partial: ok", score=3)
    session = store.complete_session(sid)
    assert session.item_count == 1
    assert session.score == 3
    assert session.max_score == 5
    items = store.list_items(sid)
    assert items[0].user_answer == "skip connection"
