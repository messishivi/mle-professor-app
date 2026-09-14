/**
 * Consultant client (P3c): SSE streaming chat, settings, apply-prompt builder.
 *
 * Mirrors the FastAPI contract in api.py exactly (snake_case, no conversion):
 *   POST /consult/chat  -> SSE: sources -> delta* -> done | error
 *   GET  /consult/status (in lib/api.ts)
 *   GET/PUT /settings, POST /settings/repo-readme
 *
 * Parity anchors: consultant.py (paper_apply_prompt, LAYERS),
 * providers.py (OFFLINE_MESSAGE), demo.py (banner text).
 */

import { ApiError, request } from "@/lib/api";
import type { ConsultStatus } from "@/lib/api";

// ------------------------------------------------------------------ layers

export const CONSULT_LAYERS = ["apply", "explain", "systems"] as const;
export type ConsultLayer = (typeof CONSULT_LAYERS)[number];

/** Streamlit parity: app.py render_consultant_terminal radio labels. */
export const LAYER_LABELS: Record<ConsultLayer, string> = {
  apply: "1 · Apply to my system",
  explain: "2 · Plain English",
  systems: "3 · Systems critic",
};

/** Streamlit parity: per-layer terminal-hint text (app.py:441-468). */
export const LAYER_HINTS: Record<ConsultLayer, string> = {
  apply:
    "Default · map the paper onto YOUR application (user / item / data / " +
    "train / serve / eval): Use / Adapt / Ignore, delta vs papers + repo README, " +
    "then an implementation path.",
  explain:
    "Short plain-English briefing · cites retrieved links. " +
    "Products (e.g. OpenAI Astra) are not swapped for similarly named papers.",
  systems:
    "Second layer · KV cache · HBM · FLOPs/token · TP / PP / DP. " +
    "No introductory lectures.",
};

/** Streamlit parity: per-layer chat_input placeholder (app.py:450-468). */
export const LAYER_PLACEHOLDERS: Record<ConsultLayer, string> = {
  apply: "How do I apply this paper to my system given the papers I already use?",
  explain: "Ask for a short plain-English explanation of a paper or idea.",
  systems: "Sketch a training/serving design. The critic will attack it.",
};

/** providers.py OFFLINE_MESSAGE — byte-identical (Streamlit + API parity). */
export const OFFLINE_MESSAGE =
  "Consultant is offline. Set `GROQ_API_KEY` in `.env`.";

// ------------------------------------------------------------------ chat

export interface ConsultTurn {
  role: "user" | "assistant";
  content: string;
}

export interface ConsultSource {
  kind: string;
  title: string;
  url?: string;
  snippet?: string;
  paper_id?: string;
}

export interface ConsultDone {
  content: string;
  model: string;
  provider: string;
  layer: string;
}

/** One parsed Server-Sent Event from POST /consult/chat. */
export type SseEvent =
  | { type: "sources"; sources: ConsultSource[] }
  | { type: "delta"; text: string }
  | ({ type: "done" } & ConsultDone)
  | { type: "error"; message: string };

/**
 * Decode accumulated SSE text into complete events.
 * The server frames as `event: <name>\ndata: <json>\n\n` (api.py `_sse`).
 * Returns the complete events and the trailing partial to re-buffer.
 */
export function decodeSse(chunk: string): { events: SseEvent[]; rest: string } {
  const parts = chunk.split("\n\n");
  const rest = parts.pop() ?? "";
  const events: SseEvent[] = [];
  for (const part of parts) {
    const ev = parseSseFrame(part);
    if (ev) events.push(ev);
  }
  return { events, rest };
}

function parseSseFrame(frame: string): SseEvent | null {
  let name = "";
  let data = "";
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) name = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!name || !data) return null;
  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(data) as Record<string, unknown>;
  } catch {
    return null;
  }
  switch (name) {
    case "sources":
      return {
        type: "sources",
        sources: (payload.sources as ConsultSource[] | undefined) ?? [],
      };
    case "delta":
      return { type: "delta", text: String(payload.text ?? "") };
    case "done":
      return {
        type: "done",
        content: String(payload.content ?? ""),
        model: String(payload.model ?? ""),
        provider: String(payload.provider ?? ""),
        layer: String(payload.layer ?? ""),
      };
    case "error":
      return { type: "error", message: String(payload.message ?? "Unknown error") };
    default:
      return null;
  }
}

export interface StreamConsultOptions {
  message: string;
  /** Past turns for this layer (the current prompt is NOT included — parity). */
  history: ConsultTurn[];
  layer: ConsultLayer;
  /** Demo-mode BYOK: sent for this request only, never persisted. */
  apiKey?: string;
  /**
   * Per-request provider override (P5): request > LLM_PROVIDER > groq.
   * Undefined = the backend resolves it from env.
   */
  provider?: string;
  /** Per-request model override (P5): request > <PROVIDER>_MODEL > default. */
  model?: string;
  signal?: AbortSignal;
}

/**
 * POST /consult/chat and deliver each SSE event to onEvent.
 * Throws ApiError for transport / HTTP failures; stream-level errors arrive
 * as `{type:"error"}` events (the API always ends the stream with done/error).
 */
export async function streamConsult(
  opts: StreamConsultOptions,
  onEvent: (ev: SseEvent) => void,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000"}/consult/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: opts.message,
        history: opts.history,
        layer: opts.layer,
        api_key: opts.apiKey || null,
        provider: opts.provider || null,
        model: opts.model || null,
      }),
      signal: opts.signal,
    });
  } catch (exc) {
    if (exc instanceof DOMException && exc.name === "AbortError") throw exc;
    throw new ApiError(0, "Cannot reach the API for the consultant.");
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // non-JSON error body
    }
    throw new ApiError(res.status, detail);
  }
  const body = res.body;
  if (!body) throw new ApiError(res.status, "No response body.");
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const { events, rest } = decodeSse(buffer);
    buffer = rest;
    for (const ev of events) onEvent(ev);
  }
  const { events } = decodeSse(buffer + "\n\n");
  for (const ev of events) onEvent(ev);
}

// ---------------------------------------------------------------- settings

/** GET /settings — sidebar state (api.py `_settings_payload`). */
export interface SettingsPayload {
  stack: string[];
  stack_choices: string[];
  application: string;
  known_papers: string;
  repo_url: string;
  repo_readme_url: string;
  repo_readme_chars: number;
}

/** PUT /settings — partial update (api.py `SettingsUpdate`). */
export interface SettingsPatch {
  stack?: string[];
  application?: string;
  known_papers?: string;
  repo_url?: string;
}

export function getSettings(): Promise<SettingsPayload> {
  return request<SettingsPayload>("/settings");
}

export function updateSettings(patch: SettingsPatch): Promise<SettingsPayload> {
  return request<SettingsPayload>("/settings", {
    method: "PUT",
    body: JSON.stringify(patch),
  });
}

/** POST /settings/repo-readme (api.py `load_repo_readme`). */
export interface RepoReadmeResult {
  repo_url: string;
  readme_url: string;
  chars: number;
}

export function loadRepoReadme(url?: string): Promise<RepoReadmeResult> {
  return request<RepoReadmeResult>("/settings/repo-readme", {
    method: "POST",
    body: JSON.stringify(url ? { url } : {}),
  });
}

// -------------------------------------------------------- apply-prompt parity

export interface ApplyPaper {
  id: string;
  title: string;
  authors: string;
  published_date: string;
  summary_raw: string;
}

export interface ApplyContext {
  application: string;
  known_papers: string;
  repo_url: string;
}

/**
 * Byte-parity with consultant.py `paper_apply_prompt`. The FE builds the
 * queued user message the same way Streamlit's `queue_apply` does before
 * handing it to the terminal.
 */
export function buildApplyPrompt(paper: ApplyPaper, ctx: ApplyContext): string {
  const title = paper.title || "Untitled";
  const authors = paper.authors || "";
  const arxivId = paper.id || "";
  const published = paper.published_date || "";
  const abstract = paper.summary_raw || "";
  let extra = "";
  if (ctx.application.trim()) extra += `\nMy system: ${ctx.application.trim()}\n`;
  if (ctx.known_papers.trim()) extra += `I already use: ${ctx.known_papers.trim()}\n`;
  if (ctx.repo_url.trim()) {
    extra +=
      `My repo: ${ctx.repo_url.trim()}\n` +
      "Delta against the repo README in retrieved sources — what is already shipped.\n";
  }
  return (
    "Map this paper onto my current application. What is relevant, what to ignore, " +
    "and how I implement it. Use user / item (or target) / data / training / serving / eval; " +
    "rename those to my modules. Do not assume a rec stack.\n" +
    `${extra}\n` +
    `Title: ${title}\n` +
    `Authors: ${authors}\n` +
    `arXiv: ${arxivId}\n` +
    `Date: ${published}\n\n` +
    `Abstract:\n${abstract}`
  );
}

// ------------------------------------------------- in-memory session storage

/**
 * Consultant session state, held in module scope (client only) — the
 * equivalent of Streamlit's st.session_state for this pane: it survives
 * tab switches within one page session and is lost on reload. Never
 * written to disk.
 */
const historyStore = new Map<ConsultLayer, ConsultTurn[]>();
let demoKeyStore = "";

export function getHistory(layer: ConsultLayer): ConsultTurn[] {
  return historyStore.get(layer) ?? [];
}

export function setHistory(layer: ConsultLayer, turns: ConsultTurn[]): void {
  if (turns.length === 0) historyStore.delete(layer);
  else historyStore.set(layer, turns);
}

export function getDemoKey(): string {
  return demoKeyStore;
}

export function setDemoKey(key: string): void {
  demoKeyStore = key;
}

/**
 * P5: the Consultant's provider selection, same session-only semantics as
 * the demo key (in memory, lost on reload, never persisted — auth DEFERRED).
 * `provider: ""` = the backend resolves the provider from LLM_PROVIDER/groq.
 * `models`/`keys` are keyed per provider so switching keeps each one's
 * overrides; an empty value means "use the provider's env/default".
 */
export interface ProviderSelection {
  provider: string;
  models: Record<string, string>;
  keys: Record<string, string>;
}

const providerSelection: ProviderSelection = {
  provider: "",
  models: {},
  keys: {},
};

export function getProviderSelection(): ProviderSelection {
  return {
    provider: providerSelection.provider,
    models: { ...providerSelection.models },
    keys: { ...providerSelection.keys },
  };
}

export function setProviderSelection(next: ProviderSelection): void {
  providerSelection.provider = next.provider;
  providerSelection.models = { ...next.models };
  providerSelection.keys = { ...next.keys };
}

/**
 * P5: fold the server status + the session selection + the demo key into the
 * single config the terminal acts on — what the banner shows, whether a turn
 * is allowed to fire, and what the request carries.
 */
export interface EffectiveConsultConfig {
  /** Whether the current turn may POST /consult/chat at all. */
  ready: boolean;
  /** Provider name sent with the request ("" = backend resolves from env). */
  provider: string;
  /** Model sent with the request ("" = backend resolves). */
  model: string;
  /** BYOK key sent for this request ("" = the env key applies). */
  key: string;
  /** Exact offline text for the active provider (providers.py parity). */
  offlineMessage: string;
  /** Active provider for the banner ("" if status has not loaded). */
  displayName: string;
}

export function resolveEffectiveConsult(
  status: ConsultStatus | null,
  selection: ProviderSelection,
  demoKey: string,
): EffectiveConsultConfig {
  if (selection.provider) {
    const entry = status?.providers?.[selection.provider];
    const key = (selection.keys[selection.provider] ?? "").trim();
    return {
      ready: !!entry?.ready || key.length > 0,
      provider: selection.provider,
      model: (selection.models[selection.provider] ?? "").trim() ||
        (entry?.model ?? ""),
      key,
      offlineMessage:
        entry?.offline_message ??
        status?.offline_message ??
        OFFLINE_MESSAGE,
      displayName: selection.provider,
    };
  }
  const key = status?.demo_mode ? demoKey.trim() : "";
  return {
    ready: !!status?.ready || (!!status?.demo_mode && key.length > 0),
    provider: "",
    model: status?.model ?? "",
    key,
    offlineMessage: status?.offline_message ?? OFFLINE_MESSAGE,
    displayName: status?.provider ?? "",
  };
}
