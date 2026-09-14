# MLE Professor

Consolidated view of what is going on every day in the ML/AI field, for working MLEs.

Local knowledge base: ingest papers, watch an ML/AI pulse, and brief or critique them in chat. Runs on a laptop or a single container. Reasoning goes to Groq; papers and read-state stay on disk.

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

Create a key at [console.groq.com](https://console.groq.com). Pulse clustering and the consultant need it. Ingest and the library work without it.

### Run it (two processes for local dev)

Terminal 1 — backend (API + static hosting, port 8000):

```bash
uvicorn api:app --reload --port 8000
```

Terminal 2 — frontend dev server (port 3000, talks to the API at 127.0.0.1:8000):

```bash
cd frontend
corepack enable          # once, per machine (enables pnpm)
pnpm install
pnpm dev
```

Open http://127.0.0.1:3000. Click **Refresh ML Pulse** (and **Refresh papers** if you want the library filled from arXiv). Opening the app does not fetch by itself.

For production you never run these separately: the Docker image builds the frontend as a static export and serves it from the API process (one port).

Python 3.10+ works (LanceDB, if you use the dev extras, needs 3.10+; on older interpreters the app falls back to a numpy index).

## Usage notes

- Never commit `.env`, `data/`, or `*.db`. Those are gitignored on purpose.
- `MLE_DATA_DIR` overrides where SQLite lives (used by Docker at `/data`).
- `MLE_DEMO_MODE=1` seeds sample papers when the library is empty. Bring-your-own-key happens on the Consultant page and is sent per request — never written to disk or the database.
- Do not put confidential work documents, customer data, or internal papers into the library or the consultant. Chat text is sent to Groq.
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
              └── Groq                  consultant streaming (key from env or per-request)
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
