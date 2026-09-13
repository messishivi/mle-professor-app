# MLE Professor — Design Language ("Terminal Ink")

Status: v1 (2026-09-13) — approved prototype pending user sign-off.
Applies to: the new web frontend (Next.js + Tailwind). The legacy Streamlit UI does not follow this document.

## 1. Identity

**MLE Professor** is a daily ML paper intelligence app for working MLEs: a **Pulse** of what's worth reading, a **Saved** library, and a grounded **Consultant** terminal.

The design language — internally **"Terminal Ink"** — borrows *genre conventions* of coding/learning platforms (dark editor chrome, dense card lists, monospace for machine-facing text, semantic status badges) and applies them to an **original** look: ink-navy surfaces, a teal accent, and a paper-card list that reads like a terminal feed of research.

> **Research basis:** genre-pattern analysis of public UIs (LeetCode, Codeforces, HackerRank, Exercism, Codewars): top nav + section tabs, problem/paper cards with status badges, dark "editor" themes, monospace accents, green/amber/red status semantics. These are generic conventions, not brand elements.

### Do-not-copy list (hard)

- LeetCode logo, wordmark, or any of its iconography
- LeetCode palette (orange `#FFA116` / `#F56929` family) and its exact hex values
- Any asset files, screenshots, or code copied from LeetCode or any other platform
- Other platforms' distinctive copy/naming (e.g. "Problems", "Contest" tab names, brand mascots)
- Fake OS-window chrome (macOS traffic-light dots) — cliché, not used here

Everything else (top-nav layout, card lists, badges, meters) is generic convention and fine.

## 2. Tokens

### Color — dark theme (default)

| Token | Hex | Use |
|---|---|---|
| `--bg-0` | `#0B0F17` | Page background |
| `--bg-1` | `#111623` | Panels, cards, nav |
| `--bg-2` | `#171E2E` | Raised: hover, inputs, chips |
| `--bg-3` | `#1E2739` | Active/pressed, code block bg |
| `--line-0` | `#232D42` | Default 1px borders |
| `--line-1` | `#2E3A55` | Strong borders, focus outlines |
| `--ink-0` | `#E8EDF6` | Primary text |
| `--ink-1` | `#A5B1C9` | Secondary text |
| `--ink-2` | `#66748E` | Muted text, meta |
| `--accent` | `#4FD8C4` | Interactive: links, active tab, primary buttons |
| `--accent-dim` | `#2A6E63` | Hover-tinted borders, icon accent |
| `--ok` | `#3DD68C` | Adopt verdict, High fit, success |
| `--warn` | `#E8B339` | Watch verdict, mid fit, warning |
| `--bad` | `#E5646E` | Skip verdict, Low fit, error |
| `--code-bg` | `#0D1220` | Code blocks |

### Color — light theme

| Token | Hex | Use |
|---|---|---|
| `--bg-0` | `#F6F8FB` | Page background |
| `--bg-1` | `#FFFFFF` | Panels, cards, nav |
| `--bg-2` | `#EEF2F8` | Hover, inputs, chips |
| `--bg-3` | `#E4EAF3` | Active/pressed, code block bg |
| `--line-0` | `#D9E1EC` | Default borders |
| `--line-1` | `#B9C6DA` | Strong borders, focus outlines |
| `--ink-0` | `#101828` | Primary text |
| `--ink-1` | `#3E4C63` | Secondary text |
| `--ink-2` | `#6B7A94` | Muted text |
| `--accent` | `#0C7A6C` | Interactive (darker for 4.5:1+ on white) |
| `--accent-dim` | `#9CCFC5` | Tints |
| `--ok` | `#15803D` | Adopt / High / success |
| `--warn` | `#A16207` | Watch / mid / warning |
| `--bad` | `#B91C1C` | Skip / Low / error |
| `--code-bg` | `#0D1220` | Code blocks stay dark in both themes |

Tinted badge backgrounds = status color at 10–12% alpha over the panel bg (e.g. `color-mix(in srgb, var(--ok) 12%, transparent)`).

### Type

- **Sans (UI):** system stack — `-apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`. No webfont downloads (weight budget).
- **Mono (machine-facing):** `ui-monospace, "SF Mono", "Cascadia Code", "JetBrains Mono", Menlo, Consolas, monospace`. Always used for: code, arXiv IDs, dates, terminal/prompt text, badge labels, meter labels.
- Scale: 11 (badge/label) · 12 (meta) · 13 (code, secondary) · 14 (body) · 15 (card title) · 18 (section h2) · 20 (page h1) · 24 (nav brand)
- Line-height: 1.5 body, 1.3 headings; paragraph clamp ~90ch in panes.

### Spacing / shape / elevation

- 4px base scale: 4 · 8 · 12 · 16 · 24 · 32 · 48
- Radii: 4 (inputs' inner) · 6 (badges, chips) · 10 (cards, panels, inputs)
- Borders: 1px `--line-0` everywhere by default; 1px `--line-1` on focus/hover-strong
- Elevation: **dark theme = borders, not shadows** (shadow `0 1px 2px rgba(0,0,0,.35)` only for toasts/popovers); light theme may add `0 1px 3px rgba(16,24,40,.08)` on raised cards
- Focus: 2px ring `--accent` (dark) / `--accent` (light), offset 2px — never removed, never outline-only

## 3. Layout system

```
┌────────────────────────────────────────────────────────────┐
│ ▚ MLE Professor │  Pulse  Saved  Consultant │   [◐ theme]  │  ← top nav, 56px, sticky, bg-1, 1px bottom border
├────────────────────────────────────────────────────────────┤
│                                                            │
│   content column: max-width 1200px, px-24, py-24           │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

- **Top nav** (h-56, sticky): brand left (mono, `▚ MLE Professor` — `▚` is our original glyph), section tabs (Pulse / Saved / Consultant; Settings added in P3c), theme toggle right (icon button). Active tab: 2px `--accent` underline + `--ink-0`; inactive: `--ink-1`.
- **Section panes**: full-width within the content column; each pane has a header row (h1 left; actions right, e.g. Refresh + last-updated timestamp in mono 12px muted).
- **Stack context strip** (Pulse only): row of chips (mono 12px, bg-2, radius 6) showing the declared stack that drives fit scoring; "edit" affordance on the right.
- **Lists**: vertical stack of cards, 12px gap. No side-by-side cards (dense single column reads better for paper abstracts).
- **Responsive floor**: 360px. Below 720px: nav tabs scroll horizontally; card meta rail collapses under the title.
- Keyboard: full tab order nav → content → footer; `Esc` closes any expanded memo/panel.

## 4. Component specs

### PaperCard
- Structure: horizontal split — **meta rail** (72px, mono 12px muted: source `HF`/`arXiv`, date, arXiv id link) | **main** (title 15px medium → one-line abstract 13px `--ink-1` → concept chips (≤3, bg-2) → footer row).
- Footer row: `VerdictBadge` + `StackFitMeter` + memo affordance (chevron, expands an inline memo block, bg-3, 12px gap).
- Hover: border → `--line-1`; read papers: title `--ink-2` + a `✓ read` mono marker; no opacity dimming (keeps list scannable).

### VerdictBadge
- Mono, uppercase, 11px, letter-spacing .04em; 1px border in status color, tinted bg (10–12% alpha), 4px dot before label; padding 2×8; radius 6.
- Values: `ADOPT` (ok) · `PROTOTYPE` (accent) · `WATCH` (warn) · `SKIP` (bad).

### StackFitMeter
- 3 segments (6×10px each, 2px gap) + mono 11px label: `HIGH` (all ok) · `WATCH` (first two warn) · `LOW` (first bad). Segments beyond level = `--line-0`.

### ChatPanel (Consultant — built in P3c)
- Terminal-styled pane, **no fake window chrome**: header bar (bg-2, 1px borders, mono 12px `consultant@pulse ~`) · message list (role prefix mono 12px colored: `you` = ink-1, `advisor` = accent; body 14px sans; citations as mono links) · input row (mono 13px, bg-2, 1px border, radius 10; `Enter` sends; streaming shows a blinking block cursor).
- Demo mode: `demo:` prefix in header when `MLE_DEMO_MODE=1`.

### CodeBlock
- `--code-bg` in both themes, 1px `--line-0`, radius 10, padding 12×16, mono 13px, `overflow-x: auto`, 2-space indent, no line numbers in v1.

### Buttons
- **Primary**: `--accent` bg (dark: text `#06231E`; light: white text), radius 8, padding 8×16, 14px; hover: brightness +8%; disabled: `--line-0` bg, `--ink-2` text.
- **Ghost**: transparent, 1px `--line-0`, `--ink-1` text; hover: `--bg-2` bg.
- **Danger**: `--bad` border/text ghost style; used only for destructive actions.

### Forms
- Inputs: `--bg-2`, 1px `--line-0`, radius 10, padding 8×12, 14px; label 12px `--ink-1` above; focus = ring token.
- Selects: same chrome + mono 13px for model/ID-like values.

### EmptyState / Skeleton / Toast
- EmptyState: centered 48px muted icon + 14px `--ink-1` line + one ghost action.
- Skeleton: `--bg-2` blocks, 150ms pulse, exact final layout dimensions.
- Toast: bottom-right, bg-2, 1px `--line-1`, radius 10, 3s, icon + 13px text, slide-up 150ms.

## 5. Accessibility

- WCAG **AA** contrast for all text in both themes (pairs above checked: body ≥ 7:1, secondary ≥ 4.5:1, accent-as-text ≥ 4.5:1 in light theme via the darker accent).
- Status never conveyed by color alone: every badge/meter carries a text label; verdicts repeat in expanded memo text.
- All interactive elements keyboard-reachable, visible focus ring, `aria-current` on active nav tab, `role="log"` + `aria-live="polite"` on the chat stream, `prefers-reduced-motion` disables all motion.

## 6. Motion

- Durations: 150ms `ease-out` for fades/slides (tab underline, memo expand, toast); 120ms for hover color swaps.
- No parallax, no page transitions, no bouncing loaders. Skeleton pulse is the only looping animation.
- All motion off under `prefers-reduced-motion: reduce`.

## 7. Frontend implementation notes

- Tailwind v4: tokens live in `globals.css` as CSS custom properties on `:root` / `.light`; Tailwind theme maps to them (`@theme inline`) so components use `bg-bg-1`, `text-ink-1`, `border-line-0` etc.
- Theming: `data-theme="light"` on `<html>`; default dark; choice persisted in `localStorage`; initial flash avoided by an inline script in `<head>`.
- No UI component library — every component in §4 is hand-built per spec (keeps the bundle light; ~5 components for P1).
- Fonts: system stacks only (see §2) until a reason to self-host one.
