from grounding import (
    arxiv_search_query,
    format_sources_for_model,
    product_sources,
    query_tokens,
)


def test_astra_is_tagged_as_openai_product():
    hits = product_sources("explain the openai astra model")
    assert hits
    assert hits[0].kind == "product"
    assert "openai.com/index/gpt-6-astra" in hits[0].url
    assert "not an academic paper" in hits[0].snippet.lower()
    assert "ASTAR" in hits[0].snippet or "A*" in hits[0].snippet


def test_arxiv_query_is_sanitized():
    q = arxiv_search_query("explain the OpenAI Astra model; DROP TABLE papers")
    assert q is not None
    assert ";" not in q
    assert "'" not in q
    assert "all:OpenAI" in q or "all:Astra" in q
    assert q.startswith("all:")


def test_stopwords_stripped():
    assert "explain" not in [t.lower() for t in query_tokens("explain the astra model")]
    assert "astra" in [t.lower() for t in query_tokens("explain the astra model")]


def test_format_sources_forbids_invention_when_empty():
    text = format_sources_for_model([])
    assert "Do not invent" in text
