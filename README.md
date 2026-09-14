# MLE Professor

Consolidated view of what is going on every day in the ML/AI field, for working MLEs.

Local knowledge base: ingest papers, watch an ML/AI pulse, and brief or critique them in chat. Runs on a laptop or a single container. Reasoning goes to your LLM provider (Groq by default); papers and read-state stay on disk.

## What you get

- **ML Pulse** — Hugging Face Daily Papers trending + newest arXiv (`cs.LG`, `cs.CL`, `cs.AI`), limited to the last 60 days, mapped to a paper, a concept, stack fit, and a decision memo (Adopt / Prototype / Watch / Skip + one production constraint)
- **Saved** — your SQLite library (under Pulse): read/unread, structured abstracts
- **Consultant** — default: map a paper onto *your* system (Use / Adapt / Ignore + implementation path). Optional plain-English briefing and systems critic.

Set **I'm building**, **Papers I already use**, and optionally a public **Repo (README)**. **Apply to my system** maps a paper onto your stack (user / item / data / train / serve / eval) and deltas against those papers and the README.

Each person runs their own copy. There is no shared server and no shared API key.

**What good looks like:** [Applying LoRA to nanoGPT](examples/nanogpt-lora-porting-plan.md) — a full Apply-to-my-system run (relevance map, delta vs the live README, implementation path, skip list).

Released under the [MIT License](LICENSE). This is a personal project, not affiliated with any employer.

## Try it now

**Docker (demo mode — no key needed):**

```bash
docker run --rm -p 8000:8000 -e MLE_DEMO_MODE=1 \
  ghcr.io/messishivi/mle-professor-app:latest
```

Open http://127.0.0.1:8000 — the web UI, API, and static pages all come from
this one port.

**Or with compose** (persistent volume):

```bash
MLE_DEMO_MODE=1 docker compose up -d --build
```

**Daily digest** (GitHub Pages, after the `pulse-digest` workflow has run): https://messishivi.github.io/mle-professor-app/pulse/

Deploy notes (VPS, PaaS, GHCR, secrets, auth-deferred): [README-DEPLOY.md](README-DEPLOY.md).

## Setup

```bash
git clone https://github.com/messishivi/mle-professor-app.git
cd mle-professor-app
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
```

In `.env`, set **your** Groq key (not someone else’s):

```
GROQ_API_KEY=gsk_...
GROQ_MODEL=openai/gpt-oss-120b
```

Create a key at [console.groq.com](https://console.groq.com). The Consultant needs it (or pick another provider — see [Providers](#providers-consultant-llm)). Ingest and the library work without it.

### Run it (two processes for local dev)

Terminal 1 — backend (API + static hosting, port 8000), from the repo root with
the venv active:

```bash
uvicorn api:app --reload --port 8000
```

Terminal 2 — frontend dev server (port 3000, talks to the API at 127.0.0.1:8000):

```bash
cd frontend
corepack enable          # once, per machine (enables pnpm; or `npm i -g pnpm`)
pnpm install
pnpm dev
```

Open http://127.0.0.1:3000. Click **Refresh ML Pulse** (and **Refresh papers**
if you want the library filled from arXiv). Opening the app does not fetch by
itself. A healthy backend answers `curl http://127.0.0.1:8000/api/healthz`.

**No keys yet? That's fine.** Pulse, papers, saved, and settings all work
keyless; only the Consultant needs a model. Until you give it one, the
Consultant banner shows the active provider's offline note (e.g.
``Set `GROQ_API_KEY` in `.env`.``).

### Get the Consultant online (local testing)

Pick one — the Consultant banner flips to `Consultant ready · <provider> ·
<model>` when it works:

1. **Env (persists across restarts).** Put the provider's key in `.env` —
   the backend reads it at startup: `GROQ_API_KEY` / `OPENAI_API_KEY` /
   `ANTHROPIC_API_KEY` (see [Providers](#providers-consultant-llm)). `local`
   needs no key.
2. **Settings page (session only).** Settings → *Consultant LLM provider*:
   pick a provider in the dropdown (each entry carries a live readiness label,
   e.g. `openai · needs key`, and the model field prefills the provider's
   default), then paste a key into **API key (this session only)**. The key
   lives in browser memory — never written to disk — and is gone on reload.
3. **Local model (no cloud, no key).** Run `llama-server -m model.gguf
   --port 8080`, pick `local` in the dropdown, and set `LOCAL_MODEL` in `.env`
   to the model name (`LOCAL_BASE_URL` already defaults to
   `http://127.0.0.1:8080/v1`).

The provider selection itself is session-only (sent per request, never
persisted); with no selection, the server default `LLM_PROVIDER` (default
`groq`) applies.

For production you never run these separately: the Docker image builds the frontend as a static export and serves it from the API process (one port).

Python 3.10+ works (LanceDB, if you use the dev extras, needs 3.10+; on older interpreters the app falls back to a numpy index).

### Providers (Consultant LLM)

The Consultant Terminal streams through `providers.py`, a small registry of four providers:

| Provider | Key env | Model env | Default model | Notes |
| --- | --- | --- | --- | --- |
| `groq` (default) | `GROQ_API_KEY` | `GROQ_MODEL` | `openai/gpt-oss-120b` | Original provider; behavior unchanged. |
| `openai` | `OPENAI_API_KEY` | `OPENAI_MODEL` | `gpt-4o-mini` | `OPENAI_BASE_URL` can point at any OpenAI-compatible endpoint. |
| `anthropic` | `ANTHROPIC_API_KEY` | `ANTHROPIC_MODEL` | `claude-sonnet-4-5` | Native Anthropic Messages API. |
| `local` | *(none)* | `LOCAL_MODEL` | `local` | Any OpenAI-compatible local server — e.g. llama.cpp: `llama-server -m model.gguf --port 8080`, then `LOCAL_BASE_URL=http://127.0.0.1:8080/v1` and `LOCAL_MODEL=<model name>`. No key needed. |

- Active provider: `LLM_PROVIDER` (default `groq`). The Consultant page can also override the provider and model per request (in-memory only, same rule as the BYOK key — never persisted).
- If the active provider has no key, the Consultant reports offline with that provider's own message (e.g. ``Set `OPENAI_API_KEY` in `.env`.``); ingest, the library, and pulse keep working.

## Usage notes

- Never commit `.env`, `data/`, or `*.db`. Those are gitignored on purpose.
- `MLE_DATA_DIR` overrides where SQLite lives (used by Docker at `/data`).
- `MLE_DEMO_MODE=1` seeds sample papers when the library is empty. Bring-your-own-key happens on the Settings page (Consultant LLM provider) and is sent per request — never written to disk or the database, and lost on reload.
- Do not put confidential work documents, customer data, or internal papers into the library or the consultant. Chat text goes to the provider you configure (Groq by default; see [Providers](#providers-consultant-llm)).
- **Auth is deferred by design.** The app ships open (single-user, personal use). If you expose it on a public host, put it behind a reverse proxy with basic auth or a VPN — see [README-DEPLOY.md](README-DEPLOY.md). Sensitive ops (chat/ingest) can go behind a toggle later; the API already has a single mount point (`/api`) for that.
- Rotate a key if it was ever pasted into chat, Slack, or email.

## Architecture

```
Browser
  └── Next.js (static export)          pages: /, /papers, /saved, /consultant, /settings
        └── FastAPI (uvicorn, :8000)
              ├── /api/*                papers, pulse, consultant (SSE), settings, healthz
              ├── /                     static frontend (out/)
              ├── SQLite                papers, read state, pulse snapshots  (data/mle_knowledge.db or /data)
              ├── ArXiv + HF            ingest and ML Pulse (public research only; 429-aware retry)
              └── LLM provider          consultant streaming: groq | openai | anthropic | local
                                         (key from env or per request; LLM_PROVIDER selects)
```

- `frontend/` — Next.js (App Router, React, Tailwind). 100% client-side fetching; builds to a flat static export.
- root `*.py` — FastAPI app (`api.py` is the entry point; `create_app(prefix=..., web_root=...)` is what the container wires up).
- `mle_professor/` — dev/test-only package (chunker, encoders, RAG experiments); not imported by the runtime API and not in the container.

## Tests

Backend (run from the repo root):

```bash
EMBEDDING_BACKEND=hash MLE_DATA_DIR=/tmp/mle-prof-test pytest -q
```

Frontend (run from `frontend/`):

```bash
pnpm test            # vitest + React Testing Library
pnpm test:e2e        # Playwright smoke tests (needs the backend on :8000)
```

## License

[MIT](LICENSE) © 2026 Shivani
