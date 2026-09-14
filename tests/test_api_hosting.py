"""P4: single-image hosting mode — API prefix + static frontend serving."""

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api import create_app
from database import PaperDatabase


def _seed(db: PaperDatabase) -> None:
    db.upsert_paper(
        id="1706.03762",
        title="Attention Is All You Need",
        authors="Ashish Vaswani",
        published_date="2017-06-12",
        summary_raw="Transformer abstract.",
    )


def _make_client(tmp_path: Path, *, prefix: str = "", web_root: Path | None = None):
    db = PaperDatabase(tmp_path / "mle_knowledge.db")
    _seed(db)
    app = create_app(db, prefix=prefix, web_root=str(web_root) if web_root else None)
    return TestClient(app)


def _write_frontend(tmp_path: Path) -> Path:
    """Mirror the Next.js export layout: flat <route>.html + one nested dir."""
    root = tmp_path / "web"
    (root / "nested" / "deep").mkdir(parents=True)
    (root / "index.html").write_text("<html>home</html>")
    (root / "papers.html").write_text("<html>papers</html>")
    (root / "nested" / "deep" / "index.html").write_text("<html>deep</html>")
    (root / "404.html").write_text("<html>not found</html>")
    return root


def test_api_mounted_under_prefix(tmp_path: Path):
    client = _make_client(tmp_path, prefix="/api")
    resp = client.get("/api/papers")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert [p["id"] for p in body["papers"]] == ["1706.03762"]
    resp = client.get("/api/healthz")
    assert resp.status_code == 200
    # Without a web root, the bare path is not a route at all.
    assert client.get("/papers").status_code == 404
    assert client.get("/healthz").status_code == 404


def test_root_mount_unchanged_without_prefix(tmp_path: Path):
    client = _make_client(tmp_path)
    assert client.get("/papers").status_code == 200
    assert client.get("/healthz").status_code == 200


def test_static_files_serve_from_web_root(tmp_path: Path):
    root = _write_frontend(tmp_path)
    client = _make_client(tmp_path, prefix="/api", web_root=root)
    assert client.get("/").text == "<html>home</html>"
    assert client.get("/papers").text == "<html>papers</html>"
    assert client.get("/papers/").text == "<html>papers</html>"
    # Directory-style route resolves to <dir>/index.html.
    assert client.get("/nested/deep").text == "<html>deep</html>"
    assert client.get("/nested/deep/").text == "<html>deep</html>"
    # Static assets keep their extensions.
    assert client.get("/index.html").text == "<html>home</html>"


def test_static_404_falls_back_to_404_html(tmp_path: Path):
    root = _write_frontend(tmp_path)
    client = _make_client(tmp_path, prefix="/api", web_root=root)
    resp = client.get("/no-such-page")
    assert resp.status_code == 404
    assert resp.text == "<html>not found</html>"


def test_path_traversal_is_blocked(tmp_path: Path):
    root = _write_frontend(tmp_path)
    (tmp_path / "secret.txt").write_text("top secret")
    client = _make_client(tmp_path, prefix="/api", web_root=root)
    for path in ("/../secret.txt", "/..%2Fsecret.txt", "/nested/../../secret.txt"):
        resp = client.get(path)
        assert resp.status_code == 404
        assert "top secret" not in resp.text


def test_api_wins_over_static_catchall(tmp_path: Path):
    root = _write_frontend(tmp_path)
    client = _make_client(tmp_path, prefix="/api", web_root=root)
    # Real API routes keep working alongside the catch-all.
    assert client.get("/api/papers").status_code == 200
    # Unknown API paths 404 like the API (JSON), not as the frontend 404 page.
    resp = client.get("/api/no-such-endpoint")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")
    resp = client.get("/api/papers/1706.03762")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Attention Is All You Need"


def test_sse_stream_survives_prefix(tmp_path: Path, monkeypatch):
    """The streaming endpoint stays intact under the /api prefix (P4)."""
    import api as api_module

    client = _make_client(tmp_path, prefix="/api")

    def offline(*args, **kwargs):
        raise api_module.providers.ProviderUnavailable("offline")

    with patch("api.providers.stream_chat", offline), patch(
        "pipeline.fetch_atom_xml", lambda *a, **k: b"<feed></feed>"
    ):
        res = client.post("/api/consult/chat", json={"message": "hi"})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    assert "event: error" in res.text
    assert api_module.providers.OFFLINE_MESSAGE in res.text


def test_no_web_root_means_no_catchall(tmp_path: Path):
    client = _make_client(tmp_path, prefix="/api")
    assert client.get("/papers").status_code == 404
    assert client.get("/anything/else").status_code == 404
