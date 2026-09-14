import { request } from "./api";

/**
 * Live ML Pulse types — mirror the FastAPI /pulse payload exactly
 * (trends.PulseItem + api._pulse_payload: fit + memo per item).
 * snake_case on purpose: no camelCase conversion, 1:1 with the API.
 */

export interface PulseFit {
  /** "Set stack" | "High fit" | "Watch" | "Skip" (trends.score_against_stack) */
  label: string;
  score: number;
  so_what: string;
}

export interface PulseMemo {
  /** "Adopt" | "Prototype" | "Watch" | "Skip" (case varies by origin) */
  verdict: string;
  constraint_note: string;
  so_what: string;
  paper_url: string;
  /** "heuristic" | "groq" */
  origin: string;
}

export interface PulseItem {
  topic: string;
  why: string;
  paper_id: string | null;
  paper_title: string;
  paper_url: string;
  concept: string;
  concept_blurb: string;
  in_library: boolean;
  /** "hf_daily" | "arxiv" */
  source: string;
  abstract: string;
  published_date: string;
  fit: PulseFit;
  memo: PulseMemo;
}

export interface PulsePayload {
  /** ISO-8601, e.g. "2026-09-13T23:53:30+00:00" (null when no snapshot) */
  fetched_at: string | null;
  items: PulseItem[];
  /** Empty on GET /pulse (snapshots don't persist errors); set after refresh */
  errors: string[];
  stack: string[];
}

export interface MemoRefineResult {
  item_key: string;
  stack_key: string;
  memo: PulseMemo;
}

export async function getPulse(): Promise<PulsePayload> {
  return request<PulsePayload>("/pulse");
}

export async function refreshPulse(): Promise<PulsePayload> {
  return request<PulsePayload>("/pulse/refresh", { method: "POST" });
}

export async function refineMemo(
  item: PulseItem,
  stack: string[],
): Promise<MemoRefineResult> {
  return request<MemoRefineResult>("/pulse/memos/refine", {
    method: "POST",
    body: JSON.stringify({ item, stack }),
  });
}

/**
 * memo_item_key parity (trends.py:181-182): (paper_id or topic)[:120].
 */
export function memoItemKey(item: PulseItem): string {
  return (item.paper_id || item.topic).slice(0, 120);
}

/** "2026-09-13T23:53:30+00:00" → "2026-09-13 23:53 UTC". */
export function formatFetchedAt(iso: string | null): string {
  if (!iso) return "never";
  const m = iso.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/);
  if (!m) return iso;
  return `${m[1]} ${m[2]} UTC`;
}

export type PulseView = "stack" | "all";

/**
 * "For my stack" view (app.py:518-525 parity): with a non-empty stack,
 * sort by (-score, original index) and drop Skip items; with an empty
 * stack the list passes through in snapshot order.
 */
export function rankItems(
  items: PulseItem[],
  stack: string[],
  view: PulseView,
): PulseItem[] {
  if (view !== "stack" || stack.length === 0) return items;
  return items
    .map((item, index) => ({ item, index }))
    .filter(({ item }) => item.fit.label !== "Skip")
    .sort((a, b) => b.item.fit.score - a.item.fit.score || a.index - b.index)
    .map(({ item }) => item);
}

/** ApiError.message already carries the server detail; any other Error is
 *  unwrapped to its message (network-level failures in tests/dev). */
export function pulseErrorMessage(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
