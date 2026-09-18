"""P2c: Consultant Terminal SSE endpoint — parity with app.py.

Parity anchors:
- Grounding is consultant.chat_with_consultant's pipeline: gather_sources
  (library + pulse + products + arXiv), repo README source, application
  context block, build_messages (system prompt per layer).
- Offline behavior: app.py:395 shows
  "Consultant is offline. Set `GROQ_API_KEY` in `.env`." — the SSE
  ``error`` event carries exactly that text when no key is available.
- LLM seam: ``api.providers.stream_chat`` (providers.py), patched here;
  the arXiv grounding seam is ``pipeline.fetch_atom_xml`` (lazy import
  inside grounding.arxiv_sources).
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import demo
from api import create_app
from database import PaperDatabase


def parse_sse(body: str) -> list[tuple[str, dict]]:
    """Parse an SSE body into (event, data) pairs."""
    events: list[tuple[str, dict]] = []
    for block in body.strip().split("\n\n"):
        event, data = "message", ""
        for line in block.strip().splitlines():
            if line.startswith("event: "):
                event = line[len("event: "):]
            elif line.startswith("data: "):
                data += line[len("data: "):]
        if data:
            events.append((event, json.loads(data)))
    return events


@pytest.fixture
def db(tmp_path) -> PaperDatabase:
    return PaperDatabase(tmp_path / "mle_knowledge.db")


@pytest.fixture
def client(db) -> TestClient:
    with TestClient(create_app(db)) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Hermetic: no LLM key, no provider override, no demo mode
    (api.create_app loads .env once; override=False so process env wins)."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("MLE_DEMO_MODE", raising=False)
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    for var in (
        "LLM_PROVIDER",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "OPENAI_BASE_URL",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_MODEL",
        "LOCAL_API_KEY",
        "LOCAL_MODEL",
        "LOCAL_BASE_URL",
    ):
        monkeypatch.delenv(var, raising=False)


def _no_arxiv():
    """Grounding never touches the network in these tests."""
    return patch("pipeline.fetch_atom_xml", lambda *a, **k: b"<feed></feed>")


# -------------------------------------------------------- /consult/status


def test_consult_status_keyless(client):
    res = client.get("/consult/status")
    assert res.status_code == 200
    body = res.json()
    assert body["ready"] is False
    assert body["provider"] == "groq"
    assert body["model"] == "openai/gpt-oss-120b"
    assert body["demo_mode"] is False
    # P5: the active provider's canonical offline text + the per-provider map
    assert body["offline_message"] == (
        "Consultant is offline. Set `GROQ_API_KEY` in `.env`."
    )
    assert set(body["providers"]) == {"groq", "openai", "anthropic", "local"}
    assert body["providers"]["groq"]["ready"] is False
    assert body["providers"]["openai"]["ready"] is False
    assert body["providers"]["anthropic"]["ready"] is False
    assert body["providers"]["local"]["ready"] is True  # keyless by design
    assert body["providers"]["local"]["model"] == "local"
    assert body["providers"]["openai"]["offline_message"] == (
        "Consultant is offline. Set `OPENAI_API_KEY` in `.env`."
    )


def test_consult_status_with_key(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "sk-test")
    monkeypatch.setenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    body = client.get("/consult/status").json()
    assert body["ready"] is True
    assert body["model"] == "llama-3.3-70b-versatile"


def test_consult_status_env_provider_flips_active_entry(client, monkeypatch):
    """LLM_PROVIDER=openai with a key: top-level follows the env provider,
    the map still reports every provider independently."""
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    body = client.get("/consult/status").json()
    assert body["ready"] is True
    assert body["provider"] == "openai"
    assert body["model"] == "gpt-4o-mini"
    assert body["offline_message"] == (
        "Consultant is offline. Set `OPENAI_API_KEY` in `.env`."
    )
    assert body["providers"]["groq"]["ready"] is False
    assert body["providers"]["openai"]["ready"] is True
    assert body["providers"]["local"]["ready"] is True


def test_consult_status_bad_llm_provider_degrades_not_500(client, monkeypatch):
    """A misconfigured LLM_PROVIDER reports ready:false with the raw value."""
    monkeypatch.setenv("LLM_PROVIDER", "together")
    res = client.get("/consult/status")
    assert res.status_code == 200
    body = res.json()
    assert body["ready"] is False
    assert body["provider"] == "together"
    assert "Unknown provider" in body["offline_message"]
    assert set(body["providers"]) == {"groq", "openai", "anthropic", "local"}


def test_create_app_loads_dotenv_once_process_env_wins(db, monkeypatch, tmp_path):
    """Plan 03 fix: .env is loaded once at create_app (not per request, not at
    import) with override=False, so process env always beats .env."""
    import api as api_mod

    calls: list[tuple[str, dict]] = []

    def fake_load(path, **kwargs):
        calls.append((str(path), kwargs))
        return True

    (tmp_path / ".env").write_text("GROQ_API_KEY=from-dotenv\n")
    monkeypatch.setattr(api_mod, "load_dotenv", fake_load)
    monkeypatch.setattr(api_mod, "ROOT", tmp_path)
    with TestClient(create_app(db)):
        pass
    assert len(calls) == 1
    assert calls[0][0] == str(tmp_path / ".env")
    assert calls[0][1].get("override") is False


# ------------------------------------------------------- /consult/chat


def test_consult_chat_streams_sources_deltas_done(client, db):
    """Happy path: sources event, deltas, done with the full content."""
    seen: dict = {}

    def fake_stream(messages, **kwargs):
        seen["messages"] = messages
        seen["api_key"] = kwargs.get("api_key")
        yield "LoRA is "
        yield "a low-rank adapter."

    db.upsert_paper(
        id="2106.09685",
        title="LoRA: Low-Rank Adaptation of Large Language Models",
        authors="Hu et al.",
        published_date="2021-06-17",
        summary_raw="Freezes pretrained weights and injects low-rank matrices.",
    )
    with patch("api.providers.stream_chat", fake_stream), _no_arxiv():
        res = client.post(
            "/consult/chat", json={"message": "Explain LoRA", "layer": "explain"}
        )
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")

    events = parse_sse(res.text)
    assert [k for k, _ in events] == ["sources", "delta", "delta", "done"]

    # Grounding surfaced the library paper (gather_sources -> library_sources)
    sources = events[0][1]["sources"]
    assert any(
        s["kind"] == "library" and s["paper_id"] == "2106.09685" for s in sources
    )

    assert "".join(d["text"] for k, d in events if k == "delta") == (
        "LoRA is a low-rank adapter."
    )
    done = events[-1][1]
    assert done["content"] == "LoRA is a low-rank adapter."
    assert done["provider"] == "groq"
    assert done["layer"] == "explain"
    assert done["model"] == "openai/gpt-oss-120b"

    # Message assembly parity: layer system prompt + retrieved context
    msgs = seen["messages"]
    assert msgs[0]["role"] == "system"
    assert msgs[-1]["role"] == "user"
    assert "Retrieved sources" in msgs[-1]["content"]
    assert "LoRA: Low-Rank Adaptation of Large Language Models" in msgs[-1][
        "content"
    ]
    assert msgs[-1]["content"].rstrip().endswith("Explain LoRA")
    assert seen["api_key"] is None


def test_consult_chat_offline_without_key_emits_exact_ui_message(client):
    """No key, no BYOK: real providers.stream_chat raises before any network
    call; the error event carries app.py:395's exact text."""
    with _no_arxiv():
        res = client.post("/consult/chat", json={"message": "Explain LoRA"})
    assert res.status_code == 200  # SSE opened; the failure is an event
    events = parse_sse(res.text)
    kinds = [k for k, _ in events]
    assert "error" in kinds
    assert "done" not in kinds
    err = next(d for k, d in events if k == "error")
    assert err["message"] == "Consultant is offline. Set `GROQ_API_KEY` in `.env`."


def test_consult_chat_anthropic_offline_error_is_per_provider(client, monkeypatch):
    """LLM_PROVIDER=anthropic without a key: the error event carries
    anthropic's canonical text, not groq's (P5). Real seam, no patch."""
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    with _no_arxiv():
        res = client.post("/consult/chat", json={"message": "Explain LoRA"})
    assert res.status_code == 200
    events = parse_sse(res.text)
    err = next(d for k, d in events if k == "error")
    assert err["message"] == (
        "Consultant is offline. Set `ANTHROPIC_API_KEY` in `.env`."
    )


def test_consult_chat_request_provider_override(client):
    """Per-request provider/model override wins over env (P5b); the seam
    receives the resolved provider and the done event echoes it."""
    seen: dict = {}

    def fake_stream(messages, **kwargs):
        seen["provider"] = kwargs.get("provider")
        seen["model"] = kwargs.get("model")
        yield "ok"

    with patch("api.providers.stream_chat", fake_stream), _no_arxiv():
        res = client.post(
            "/consult/chat",
            json={
                "message": "Explain LoRA",
                "provider": "openai",
                "model": "gpt-4o",
            },
        )
    assert res.status_code == 200
    events = parse_sse(res.text)
    done = events[-1][1]
    assert done["provider"] == "openai"
    assert done["model"] == "gpt-4o"
    assert seen["provider"] == "openai"
    assert seen["model"] == "gpt-4o"


def test_consult_chat_request_provider_override_without_model_env_default(client):
    """provider override + no model: the provider's env/default model applies."""
    seen: dict = {}

    def fake_stream(messages, **kwargs):
        seen["model"] = kwargs.get("model")
        yield "ok"

    with patch("api.providers.stream_chat", fake_stream), _no_arxiv():
        res = client.post(
            "/consult/chat",
            json={"message": "Explain LoRA", "provider": "anthropic"},
        )
    assert res.status_code == 200
    events = parse_sse(res.text)
    done = events[-1][1]
    assert done["provider"] == "anthropic"
    assert done["model"] == "claude-sonnet-4-5"
    assert seen["model"] == "claude-sonnet-4-5"


def test_consult_chat_unknown_request_provider_is_422(client):
    """A bad per-request provider name is a 422 before any stream opens."""
    res = client.post(
        "/consult/chat",
        json={"message": "Explain LoRA", "provider": "together"},
    )
    assert res.status_code == 422
    assert "Unknown provider" in res.json()["detail"]


def test_consult_chat_byok_key_is_used_not_persisted(client, db, monkeypatch):
    captured: dict = {}

    def fake_stream(messages, **kwargs):
        captured["api_key"] = kwargs.get("api_key")
        yield "ok"

    with patch("api.providers.stream_chat", fake_stream), _no_arxiv():
        res = client.post(
            "/consult/chat",
            json={"message": "Explain LoRA", "api_key": "sk-user-byok"},
        )
    assert res.status_code == 200
    assert captured["api_key"] == "sk-user-byok"
    # BYOK is request-scoped: status still reports keyless, nothing in settings
    assert client.get("/consult/status").json()["ready"] is False


def test_consult_chat_includes_application_context_and_repo(client, db):
    """chat_with_consultant parity: application block + repo README source."""
    captured: dict = {}

    def fake_stream(messages, **kwargs):
        captured["messages"] = messages
        yield "ok"

    db.set_application("Two-tower recommender for a news app")
    db.set_stack(["Recommenders"])
    db.set_known_papers("1706.03762")
    db.set_repo_url("https://github.com/me/rec-svc")
    db.set_repo_readme(
        "# rec-svc\nships a two-tower ranker",
        source_url="https://github.com/me/rec-svc/blob/main/README.md",
    )
    with patch("api.providers.stream_chat", fake_stream), _no_arxiv():
        res = client.post(
            "/consult/chat",
            json={
                "message": "Map this paper onto my rec stack",
                "layer": "apply",
                "history": [
                    {"role": "user", "content": "earlier question"},
                    {"role": "assistant", "content": "earlier answer"},
                ],
            },
        )
    events = parse_sse(res.text)
    sources = events[0][1]["sources"]
    assert any(
        s["kind"] == "repo" and s["title"] == "Your repo README" for s in sources
    )

    msgs = captured["messages"]
    # system (apply layer) + 2 history turns + user with context
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"]
    assert "Name the layers" in msgs[0]["content"] or "relevance" in msgs[0]["content"].lower()
    user = msgs[-1]["content"]
    assert "Building: Two-tower recommender for a news app" in user
    assert "Stack: Recommenders" in user
    assert "Papers they already use: 1706.03762" in user
    assert "- Repo: https://github.com/me/rec-svc" in user
    assert "README (what they already ship" in user
    assert "User question:" in user


def test_consult_chat_error_mid_stream_emits_error_event(client):
    def flaky(messages, **kwargs):
        yield "partial "
        raise RuntimeError("groq 500")

    with patch("api.providers.stream_chat", flaky), _no_arxiv():
        res = client.post("/consult/chat", json={"message": "Explain LoRA"})
    events = parse_sse(res.text)
    assert [k for k, _ in events] == ["sources", "delta", "error"]
    assert "groq 500" in events[-1][1]["message"]


def test_consult_chat_empty_response_emits_error(client):
    def empty(messages, **kwargs):
        return iter(())

    with patch("api.providers.stream_chat", empty), _no_arxiv():
        res = client.post("/consult/chat", json={"message": "Explain LoRA"})
    events = parse_sse(res.text)
    assert [k for k, _ in events] == ["sources", "error"]
    assert "empty" in events[-1][1]["message"]


# ----------------------------------------------------- validation (422)


def test_consult_chat_unknown_layer_is_422(client):
    res = client.post("/consult/chat", json={"message": "hi", "layer": "vibes"})
    assert res.status_code == 422


def test_consult_chat_system_history_role_is_422(client):
    res = client.post(
        "/consult/chat",
        json={
            "message": "hi",
            "history": [{"role": "system", "content": "be nice"}],
        },
    )
    assert res.status_code == 422


def test_consult_chat_bad_history_role_is_422(client):
    res = client.post(
        "/consult/chat",
        json={
            "message": "hi",
            "history": [{"role": "narrator", "content": "once upon a time"}],
        },
    )
    assert res.status_code == 422


def test_consult_chat_empty_message_is_422(client):
    res = client.post("/consult/chat", json={"message": "   "})
    assert res.status_code == 422


# ------------------------------------------------------------- demo mode


def test_demo_mode_seeds_papers_on_app_create(db, monkeypatch):
    """create_app parity with the Streamlit demo banner flow."""
    monkeypatch.setenv("MLE_DEMO_MODE", "1")
    with TestClient(create_app(db)) as test_client:
        body = test_client.get("/papers").json()
    assert body["count"] == len(demo.DEMO_PAPERS)
    # Idempotent: a second create does not duplicate
    with TestClient(create_app(db)) as test_client:
        assert test_client.get("/papers").json()["count"] == len(demo.DEMO_PAPERS)


def test_demo_mode_flag_in_consult_status(client, db, monkeypatch):
    # Rebuild the app with the flag set (the fixture built it keyless)
    monkeypatch.setenv("MLE_DEMO_MODE", "1")
    with TestClient(create_app(db)) as test_client:
        body = test_client.get("/consult/status").json()
    assert body["demo_mode"] is True
    assert body["ready"] is False
