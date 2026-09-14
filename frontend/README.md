# MLE Professor — frontend

Next.js (App Router) + Tailwind CSS v4 frontend for the MLE Professor app.
Design spec: [`design.md`](../design.md) ("Terminal Ink" — dark-first, system
fonts, no UI kit).

## Commands

| Command | Purpose |
|---|---|
| `pnpm dev` | Dev server on http://127.0.0.1:3000 |
| `pnpm build` / `pnpm start` | Production build / serve |
| `pnpm lint` | ESLint |
| `pnpm test` | Unit + component tests (Vitest + Testing Library) |
| `pnpm test:e2e` | Playwright smoke tests (starts the dev server itself) |

## Status — P5 (multi-provider wiring, complete)

- Shell: sticky top nav + dark/light theming (dark default, persisted in
  `localStorage`, applied before first paint)
- **Pulse** (`app/page.tsx`): live ML Pulse from the API (`lib/pulse.ts`) —
  snapshot + refresh, "For my stack" / "Everything" re-rank, per-item memos
  with verdict badges + stack-fit meters, "Refine memo" (needs an online
  Consultant), per-item **Apply** (papers with a `paper_id`) — builds the
  byte-parity Apply prompt and queues it into the Consultant's Apply layer
- **Papers / Saved** (`app/papers`, `app/saved`): live library with search,
  read/unread filter + optimistic toggle, category ingest (`lib/api.ts`);
  per-paper **Apply to my system** on the Papers view (same queue path)
- **Consultant** (`app/consultant`): SSE terminal (`lib/consult.ts` +
  `components/consultant-client.tsx`) — three layers (Apply to my system /
  Plain English / Systems critic) with per-layer history, streamed deltas,
  "Checked sources" disclosure on the final turn, and session clear. Provider
  and model ride each request from the Settings selection (session-only store
  in `lib/consult.ts`); in demo mode a session-only key can also be pasted
  here. Offline, the send path is handled locally with the selected
  provider's canonical offline note (`providers.py`) and never POSTs
- **Settings** (`app/settings`): live stack chips ("Your stack"),
  "I'm building" / "Papers I already use" / "Repo (README)" fields with the
  Streamlit sidebar strings, README load/reload against the backend
  (`POST /settings/repo-readme`) with a `{chars}`-only status caption
  (intentional deviations: no `parse_repo` gate, no preview body), and the
  "Consultant LLM provider" section (P5): provider dropdown with live
  readiness labels from `/consult/status`, per-provider model prefill, and a
  session-only BYOK key (in memory only — lost on reload, never persisted)
- The P1 mock prototype (`mock-pulse.ts`, `paper-card.tsx`) has been removed

### Parity notes

- `buildApplyPrompt` is byte-identical to the Streamlit
  `paper_apply_prompt` (preamble, context extras, blank-title fallback,
  trailing-space behavior) — pinned in `tests/lib/consult.test.ts`.
- History sent to the API excludes the current prompt, matching the
  Streamlit request shape.
- Parity probes (read-only, not part of the suite):
  `scripts/parity-probe-pulse.cjs`, `scripts/parity-probe-saved.cjs`,
  `scripts/parity-probe-consultant.cjs`. These compare against the old
  Streamlit reference app, which now lives on the `legacy/streamlit` branch
  (run it there on 127.0.0.1:8501 if you need them).
