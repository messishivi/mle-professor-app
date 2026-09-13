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

## Status — P1 (design prototype)

- Shell: sticky top nav + dark/light theming (dark default, persisted in
  `localStorage`, applied before first paint)
- Pulse screen wired to **mock data** (`lib/mock-pulse.ts`, fictional papers)
  — replaced by real API data in P2a/P3a
- Saved / Consultant pages are empty-state placeholders until their
  increments land
