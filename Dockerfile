# MLE Professor — single container image (VPS and PaaS friendly).
#
# Stage 1 builds the Next.js frontend as a STATIC export (out/).
# Stage 2 runs the FastAPI backend with uvicorn; it serves the API under
# /api and the static frontend from the same origin, so one port is all a
# host needs to expose.
#
# Build:  docker build -t mle-professor .
# Run:    docker run --rm -p 8000:8000 \
#             -e GROQ_API_KEY=gsk_... \
#             -v mle-data:/data \
#             mle-professor
# Demo:   docker run --rm -p 8000:8000 -e MLE_DEMO_MODE=1 mle-professor
#
# Env (all optional):
#   GROQ_API_KEY    Groq key for Consultant (leave empty for keyless demo)
#   GROQ_MODEL      model name (default: openai/gpt-oss-120b)
#   MLE_DEMO_MODE   1 = seed sample papers when the library is empty
#   MLE_DATA_DIR    SQLite location (default: /data — mount a volume here)
#   API_PREFIX      API mount path (default: /api)
#   MLE_WEB_ROOT    static export location (default: /app/web)
#   PORT            listen port (default: 8000)

# ---------- Stage 1: static frontend export ----------
FROM node:24 AS frontend
WORKDIR /web

# Install pinned deps first (layer cache friendly). pnpm version is pinned by
# the packageManager field in package.json (corepack reads it).
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile

# Build the static export. NEXT_EXPORT=1 switches next.config.ts to
# output: "export"; NEXT_PUBLIC_API_BASE is baked into the client bundle.
COPY frontend/ ./
ENV NEXT_EXPORT=1 \
    NEXT_PUBLIC_API_BASE=/api
RUN pnpm build

# ---------- Stage 2: Python API + static hosting ----------
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    API_PREFIX=/api \
    MLE_WEB_ROOT=/app/web \
    MLE_DATA_DIR=/data \
    PORT=8000

WORKDIR /app

# Production-only dependencies (the frontend is static; the heavy
# mle_professor dev/test deps are NOT installed here).
COPY requirements.txt ./
# Generous retries/timeout: deploys from slow VPS/PaaS networks shouldn't
# fail the build on a single flaky wheel download.
RUN pip install --no-cache-dir --retries 10 --timeout 120 -r requirements.txt

# Root API modules only (no tests, docs, or frontend sources).
COPY *.py ./

# Static export from stage 1.
COPY --from=frontend /web/out /app/web

RUN mkdir -p /data

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import sys, urllib.request; r = urllib.request.urlopen('http://127.0.0.1:8000/api/healthz', timeout=4); sys.exit(0 if r.status == 200 else 1)" || exit 1

CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT}"]
