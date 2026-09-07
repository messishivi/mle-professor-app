import numpy as np

from mle_professor.embeddings.encoder import HashingEncoder, build_encoder
from mle_professor.embeddings.store import VectorStore


def test_hash_encoder_is_deterministic_and_normalized():
    enc = HashingEncoder(dim=64)
    a = enc.encode(["residual connections help deep nets"])
    b = enc.encode(["residual connections help deep nets"])
    assert a.shape == (1, 64)
    np.testing.assert_allclose(a, b)
    assert abs(float(np.linalg.norm(a[0])) - 1.0) < 1e-5


def test_hash_encoder_separates_unrelated_text():
    enc = HashingEncoder(dim=128)
    vecs = enc.encode(["attention is all you need", "pancakes and maple syrup"])
    sim = float(vecs[0] @ vecs[1])
    assert sim < 0.5


def test_build_encoder_honors_hash_backend(settings):
    enc = build_encoder(settings)
    assert enc.name.startswith("hash-")


def test_lancedb_roundtrip(settings):
    enc = HashingEncoder(dim=settings.hash_dim)
    store = VectorStore(settings.lancedb_path, enc)
    texts = ["transformers use self-attention", "sgd with momentum"]
    vectors = enc.encode(texts)
    store.add_chunks(
        chunks=[
            {
                "id": "p1:0",
                "paper_id": 1,
                "note_id": 0,
                "source": "paper",
                "title": "Attention",
                "section": "abstract",
                "chunk_index": 0,
                "text": texts[0],
            },
            {
                "id": "p2:0",
                "paper_id": 2,
                "note_id": 0,
                "source": "paper",
                "title": "Optim",
                "section": "abstract",
                "chunk_index": 0,
                "text": texts[1],
            },
        ],
        vectors=vectors,
    )
    hits = store.search("self attention in transformers", k=2)
    assert hits
    assert hits[0].title == "Attention"
    assert store.backend_name in {"lancedb", "numpy"}
    store.delete_paper(1)
    hits_after = store.search("self attention in transformers", k=2)
    assert all(h.paper_id != 1 for h in hits_after)
