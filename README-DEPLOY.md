# Deploy notes

The README "Try it now" section is already in `README.md`. Demo mode and
`MLE_DATA_DIR` are already applied in the tree (`demo.py`, `app.py`,
`database.py`). Do not re-apply `patches/`.

## Maintainer

- **Streamlit Community Cloud:** new app → point at `app.py` → in *Advanced
  settings → Secrets* add `GROQ_API_KEY`, or leave it empty and set the
  `MLE_DEMO_MODE=1` env var for a keyless demo with bring-your-own-key.
- **Hugging Face Spaces (recommended for visibility):** new Space → Streamlit SDK →
  push this repo. Add `GROQ_API_KEY` as a Space secret, or ship demo mode.
  Spaces gives you free hosting *and* discovery on the HF hub.
- **Docker / GHCR:** the `docker-publish` workflow builds on every `v*` tag and
  pushes to `ghcr.io/messishivi/mle-professor-app`. Users run the one-liner above.
- **Daily digest:** the `pulse-digest` workflow runs `scripts/build_pulse_digest.py`
  every morning and commits `docs/pulse/index.html`. Enable GitHub Pages
  (Settings → Pages → Deploy from branch → `main` → `/docs`) to serve it.
  No secrets needed — feed collection and memos are keyless.
- **Demo mode** (`demo.py`, `MLE_DEMO_MODE=1`):
  - Seeds 3 sample papers on first run and shows a banner.
  - Visitors can paste their own Groq key into the sidebar; it lives in
    `st.session_state` only — never on disk, never in the DB.
  - With the flag off, the app behaves exactly as before.

The worked example lives at [`examples/nanogpt-lora-porting-plan.md`](examples/nanogpt-lora-porting-plan.md).
