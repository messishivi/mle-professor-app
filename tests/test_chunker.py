from mle_professor.ingest.chunker import chunk_text
from mle_professor.ingest.arxiv import normalize_arxiv_id


def test_chunk_empty():
    assert chunk_text("") == []
    assert chunk_text("   \n\n") == []


def test_chunk_respects_max_chars():
    text = " ".join(["word"] * 400)
    chunks = chunk_text(text, max_chars=120, overlap=20)
    assert len(chunks) > 1
    assert chunks[0].index == 0
    assert all(c.text for c in chunks)


def test_chunk_keeps_paragraphs_together_when_small():
    text = "First paragraph.\n\nSecond paragraph."
    chunks = chunk_text(text, max_chars=400, overlap=0)
    assert len(chunks) == 1
    assert "First paragraph." in chunks[0].text
    assert "Second paragraph." in chunks[0].text


def test_normalize_arxiv_id():
    assert normalize_arxiv_id("1706.03762") == "1706.03762"
    assert normalize_arxiv_id("arxiv:1706.03762v2") == "1706.03762v2"
    assert normalize_arxiv_id("https://arxiv.org/abs/1706.03762") == "1706.03762"
    assert normalize_arxiv_id("https://arxiv.org/pdf/1706.03762.pdf") == "1706.03762"


def test_normalize_arxiv_id_rejects_garbage():
    try:
        normalize_arxiv_id("not-a-paper")
    except ValueError:
        return
    raise AssertionError("expected ValueError")
