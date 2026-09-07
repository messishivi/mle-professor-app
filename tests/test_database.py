from pathlib import Path

import pytest

from database import PaperDatabase, normalize_arxiv_id


@pytest.fixture
def db(tmp_path: Path) -> PaperDatabase:
    return PaperDatabase(tmp_path / "mle_knowledge.db")


def test_normalize_arxiv_variants():
    assert normalize_arxiv_id("1706.03762") == "1706.03762"
    assert normalize_arxiv_id("arxiv:1706.03762v7") == "1706.03762"
    assert normalize_arxiv_id("https://arxiv.org/abs/1706.03762") == "1706.03762"
    assert normalize_arxiv_id("https://arxiv.org/pdf/1706.03762.pdf") == "1706.03762"


def test_create_and_get(db: PaperDatabase):
    paper = db.create_paper(
        id="1706.03762",
        title="Attention Is All You Need",
        authors=["Vaswani", "Shazeer"],
        published_date="2017-06-12",
        summary_raw="Transformers.",
        summary_structured={"methods": ["attention"]},
    )
    assert paper.id == "1706.03762"
    assert paper.authors == "Vaswani, Shazeer"
    assert paper.summary_structured == {"methods": ["attention"]}
    assert paper.read_status == 0
    fetched = db.get_paper("https://arxiv.org/abs/1706.03762v1")
    assert fetched is not None
    assert fetched.title == paper.title


def test_create_duplicate_raises(db: PaperDatabase):
    db.create_paper(id="1706.03762", title="A")
    with pytest.raises(ValueError, match="already exists"):
        db.create_paper(id="arxiv:1706.03762v2", title="B")


def test_upsert_does_not_duplicate_or_reset_state(db: PaperDatabase):
    first = db.upsert_paper(
        id="1706.03762",
        title="Attention Is All You Need",
        authors="Vaswani et al.",
        summary_raw="v1 abstract",
    )
    db.set_read_status(first.id, 1)
    marked = db.get_paper(first.id)
    assert marked is not None and marked.read_status == 1
    added_at = marked.added_at

    second = db.upsert_paper(
        id="https://arxiv.org/abs/1706.03762v7",
        title="Attention Is All You Need",
        authors="Vaswani, Shazeer, Parmar",
        summary_raw="updated abstract",
        summary_structured={"tokens": 512},
    )
    assert second.id == "1706.03762"
    assert db.count() == 1
    assert second.summary_raw == "updated abstract"
    assert second.authors.startswith("Vaswani")
    assert second.read_status == 1
    assert second.added_at == added_at
    assert second.summary_structured == {"tokens": 512}


def test_update_delete_and_list(db: PaperDatabase):
    db.upsert_paper(id="1512.03385", title="ResNet", authors="He et al.")
    db.upsert_paper(id="1412.6980", title="Adam", authors="Kingma, Ba")
    db.update_paper("1412.6980", summary_raw="Adaptive moments.")
    adam = db.get_paper("1412.6980")
    assert adam is not None
    assert adam.summary_raw == "Adaptive moments."
    unread = db.list_papers(read_status=0)
    assert len(unread) == 2
    with pytest.raises(ValueError):
        db.delete_paper("not-an-arxiv-id")
    assert db.delete_paper("1512.03385") is True
    assert db.count() == 1


def test_parameterized_queries_reject_sql_in_title(db: PaperDatabase):
    db.upsert_paper(
        id="2106.09685",
        title='LoRA"); DROP TABLE papers; --',
        summary_raw="low rank",
    )
    assert db.count() == 1
    paper = db.get_paper("2106.09685")
    assert paper is not None
    assert "DROP TABLE" in paper.title
