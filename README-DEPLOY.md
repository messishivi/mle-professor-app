# Deploy notes

One image, one port, env-driven. The container serves the API under `/api`
and the static Next.js frontend on the same origin, so any host that can run
Docker and set a few environment variables can run the whole app.

## How the image works

- **Stage 1** builds `frontend/` as a static export (`NEXT_EXPORT=1 next build` → `out/`).
- **Stage 2** is `python:3.11-slim` with the production deps
  (`requirements.txt`: fastapi, uvicorn, groq, pydantic, requests,
  python-dotenv) and runs `uvicorn api:app`. The API process also hosts the
  static files (`MLE_WEB_ROOT=/app/web`), so there is no separate web server.
- SQLite lives at `MLE_DATA_DIR` (`/data` by default) — a **volume**, not a
  baked-in file.

### Environment variables

| Var | Default | Meaning |
| --- | --- | --- |
| `GROQ_API_KEY` | *(empty)* | Groq key for the Consultant. Empty = keyless; ingest/pulse still work, Consultant reports offline. |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Model name sent to Groq. |
| `MLE_DEMO_MODE` | *(empty)* | `1` = seed sample papers when the library is empty. |
| `MLE_DATA_DIR` | `/data` | Where `mle_knowledge.db` lives. |
| `API_PREFIX` | `/api` | API mount path. |
| `MLE_WEB_ROOT` | `/app/web` | Static export location. |
| `PORT` | `8000` | Listen port. |

## VPS (your own box)

```bash
git clone https://github.com/messishivi/mle-professor-app.git && cd mle-professor-app
# .env next to docker-compose.yml:
printf 'GROQ_API_KEY=gsk_...\n' > .env
docker compose up -d --build
```

- Expose `8000`. For a public hostname put Caddy/nginx in front with TLS
  (or use a VPN / Tailnet instead of publishing at all — recommended).
- Backups = the `mle-data` volume (or copy `/data/mle_knowledge.db` while the
  container is stopped; it's a single SQLite file, WAL mode).
- The `docker-publish` workflow also pushes to GHCR on `main`/`v*` tags, so
  you can `docker pull ghcr.io/messishivi/mle-professor-app:latest` instead of
  building from source.

## PaaS (any Docker platform)

Push the repo and point the platform at the Dockerfile (or pull the GHCR
image). Then set the environment variables above — no port mapping needed
beyond the platform's default.

- **Hugging Face Spaces** (Docker SDK): push the repo, set `GROQ_API_KEY` as
  a Space secret (or leave it empty for a keyless demo with
  `MLE_DEMO_MODE=1`). Spaces gives you free hosting and discovery.
- **Railway / Render / Fly.io / Fly Machines / Fly.io**: build context = repo
  root, add a persistent volume mounted at `/data` (required for data to
  survive restarts), set `GROQ_API_KEY`.
- **Railway/Render** set their own port — the container honors `PORT`, so no
  change needed.

## Secrets strategy

- **One secret: `GROQ_API_KEY`.** It is read from the environment only. The
  frontend's bring-your-own-key (Consultant page) is sent per request and is
  never persisted — so demo/keyless hosting needs *no* secret at all.
- Never bake the key into the image or a committed `.env`.
- Rotate on any exposure; the key is only ever sent to Groq.

## Auth (deferred — ship open first)

The app ships **open** (no login). That is intentional for single-user,
personal use. If you expose it publicly:

1. **Now:** put a reverse proxy with basic auth (Caddy: `basic_auth user
   $2a$...`) or a VPN/Tailnet in front. Nothing in the app changes.
2. **Later (planned):** a single toggle to require an API token on the
   sensitive ops (chat/ingest). The API already mounts under one prefix
   (`/api`), so the toggle is a middleware on that router — no client changes.

The read-only endpoints (papers list, pulse) are safe to leave open; the
write endpoints (ingest, memo refine, settings) and `/consult/chat` are the
ones to gate.

## Daily digest (unchanged)

The `pulse-digest` workflow runs `scripts/build_pulse_digest.py` every morning
and commits `docs/pulse/index.html`. Enable GitHub Pages
(Settings → Pages → Deploy from branch → `main` → `/docs`) to serve it.
No secrets needed — feed collection and memos are keyless. This workflow is
independent of the app image and is unaffected by the replatform.

## What changed in the replatform (P4)

- Streamlit is gone from `main` (see the `legacy/streamlit` branch for the
  old app). The old Streamlit `Dockerfile` (port 8501) is replaced by the
  multi-stage image above (port 8000).
- `requirements.txt` is now the slim production closure; the heavy dev/test
  deps moved to `requirements-dev.txt`.
- arXiv fetches retry on 429/5xx with backoff (`pipeline.fetch_atom_xml`),
  which matters more on a shared host than on a laptop.

The worked example lives at
[`examples/nanogpt-lora-porting-plan.md`](examples/nanogpt-lora-porting-plan.md).
