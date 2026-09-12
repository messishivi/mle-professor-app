# MLE Professor

Consolidated view of what is going on every day in the ML/AI field, for working MLEs.

Local knowledge base: ingest papers, watch an ML/AI pulse, and brief or critique them in chat. Runs on a laptop. Reasoning goes to Groq; papers and read-state stay on disk.

## What you get

- **ML Pulse** — Hugging Face Daily Papers trending + newest arXiv (`cs.LG`, `cs.CL`, `cs.AI`), limited to the last 60 days, mapped to a paper, a concept, stack fit, and a decision memo (Adopt / Prototype / Watch / Skip + one production constraint)
- **Saved** — your SQLite library (under Pulse): read/unread, structured abstracts
- **Consultant** — default: map a paper onto *your* system (Use / Adapt / Ignore + implementation path). Optional plain-English briefing and systems critic.

Set **I'm building**, **Papers I already use**, and optionally a public **Repo (README)**. **Apply to my system** maps a paper onto your stack (user / item / data / train / serve / eval) and deltas against those papers and the README.

Each person runs their own copy. There is no shared server and no shared API key.

**What good looks like:** [Applying LoRA to nanoGPT](examples/nanogpt-lora-porting-plan.md) — a full Apply-to-my-system run (relevance map, delta vs the live README, implementation path, skip list).

Released under the [MIT License](LICENSE). This is a personal project, not affiliated with any employer.

## Try it now

**Docker (demo mode — no `.env`):**

```bash
docker run --rm -p 8501:8501 -e MLE_DEMO_MODE=1 \
  ghcr.io/messishivi/mle-professor-app:latest
```

**Local demo mode** (seeds sample papers; paste a Groq key in the sidebar for this session only):

```bash
MLE_DEMO_MODE=1 streamlit run app.py
```

**Daily digest** (GitHub Pages, after the `pulse-digest` workflow has run): https://messishivi.github.io/mle-professor-app/pulse/

Deploy notes (Streamlit Cloud, HF Spaces, GHCR, Pages): [README-DEPLOY.md](README-DEPLOY.md).

## Setup

```bash
git clone https://github.com/messishivi/mle-professor-app.git
cd mle-professor-app
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

In `.env`, set **your** Groq key (not someone else’s):

```
GROQ_API_KEY=gsk_...
GROQ_MODEL=openai/gpt-oss-120b
```

Create a key at [console.groq.com](https://console.groq.com). Pulse clustering and the consultant need it. Ingest and the library work without it.

```bash
streamlit run app.py
```

Open http://127.0.0.1:8501. Click **Refresh ML Pulse** (and **Refresh papers** if you want the library filled from arXiv). Opening the app does not fetch by itself.

Python 3.9+ works. LanceDB needs 3.10+; on 3.9 the app falls back to a numpy index.

## Usage notes

- Never commit `.env`, `data/`, or `*.db`. Those are gitignored on purpose.
- `MLE_DATA_DIR` overrides where SQLite lives (used by Docker at `/data`).
- `MLE_DEMO_MODE=1` seeds sample papers and accepts a visitor Groq key in session state only.
- Do not put confidential work documents, customer data, or internal papers into the library or the consultant. Chat text is sent to Groq.
- Bind Streamlit to localhost only. Do not `--server.address 0.0.0.0` and do not deploy this as a shared cloud app with one key.
- Rotate a key if it was ever pasted into chat, Slack, or email.

## Architecture

```
Streamlit (localhost)
  ├── SQLite          papers, read state, pulse snapshots   (data/mle_knowledge.db)
  ├── LanceDB/numpy   local semantic index (optional)
  ├── ArXiv + HF      ingest and ML Pulse (public research only)
  └── Groq            explain / systems chat
```

## Tests

```bash
EMBEDDING_BACKEND=hash MLE_DATA_DIR=/tmp/mle-prof-test pytest -q
```

## License

[MIT](LICENSE) © 2026 Shivani
