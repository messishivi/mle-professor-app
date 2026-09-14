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

## Status — P3 (live wiring, in progress)

- Shell: sticky top nav + dark/light theming (dark default, persisted in
  `localStorage`, applied before first paint)
- **Pulse** (`app/page.tsx`): live ML Pulse from the API (`lib/pulse.ts`) —
  snapshot + refresh, "For my stack" / "Everything" re-rank, per-item memos
  with verdict badges + stack-fit meters, "Refine memo" (needs an online
  Consultant)
- **Papers / Saved** (`app/papers`, `app/saved`): live library with search,
  read/unread filter + optimistic toggle, category ingest (`lib/api.ts`)
- **Consultant** (`app/consultant`): empty-state placeholder until P3c
- The P1 mock prototype (`mock-pulse.ts`, `paper-card.tsx`) has been removed
