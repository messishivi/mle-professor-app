"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getConsultStatus } from "@/lib/api";
import type { ConsultStatus } from "@/lib/api";
import {
  CONSULT_LAYERS,
  LAYER_HINTS,
  LAYER_LABELS,
  LAYER_PLACEHOLDERS,
  OFFLINE_MESSAGE,
  getDemoKey,
  getHistory,
  setDemoKey,
  setHistory,
  streamConsult,
} from "@/lib/consult";
import type {
  ConsultLayer,
  ConsultSource,
  ConsultTurn,
} from "@/lib/consult";

const LAYER_SET: ReadonlySet<string> = new Set(CONSULT_LAYERS);

interface TurnMeta {
  model: string;
  provider: string;
}

/**
 * Consultant Terminal (Streamlit parity, app.py:387-484):
 * - three layers with separate histories (st.session_state parity, in-memory)
 * - per-layer hint + placeholder (exact Streamlit strings)
 * - "Clear session" per layer
 * - offline: no request is made and the exact OFFLINE_MESSAGE is shown
 *   (app.py:394-398); demo mode adds the session-only BYOK key (demo.py)
 * - SSE streaming: sources -> delta* -> done | error (P2c contract)
 */
export function ConsultantClient() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [status, setStatus] = useState<ConsultStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [layer, setLayer] = useState<ConsultLayer>("apply");
  const [histories, setHistories] = useState<
    Record<ConsultLayer, ConsultTurn[]>
  >({ apply: [], explain: [], systems: [] });
  const [demoKey, setDemoKeyState] = useState("");
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [busyLabel, setBusyLabel] = useState("");
  const [streamText, setStreamText] = useState("");
  const [turnSources, setTurnSources] = useState<ConsultSource[] | null>(null);
  const [lastMeta, setLastMeta] = useState<TurnMeta | null>(null);
  const [turnError, setTurnError] = useState<string | null>(null);
  const [queued, setQueued] = useState<{ prompt: string; layer: ConsultLayer } | null>(null);
  const queuedHandled = useRef(false);
  const initDone = useRef(false);

  // Load provider readiness (failure degrades to offline, not a page failure).
  const loadStatus = useCallback(() => {
    setStatusError(null);
    getConsultStatus()
      .then(setStatus)
      .catch((exc) => {
        setStatus(null);
        setStatusError(exc instanceof Error ? exc.message : "Cannot reach the API.");
      });
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  // Restore in-memory session state + pick up a queued Apply turn (once).
  useEffect(() => {
    if (initDone.current) return;
    initDone.current = true;
    setHistories({
      apply: getHistory("apply"),
      explain: getHistory("explain"),
      systems: getHistory("systems"),
    });
    setDemoKeyState(getDemoKey());
    const q = searchParams.get("q");
    const l = searchParams.get("layer");
    if (q && !queuedHandled.current) {
      queuedHandled.current = true;
      setQueued({
        prompt: q,
        layer: LAYER_SET.has(l ?? "") ? (l as ConsultLayer) : "apply",
      });
    }
  }, [searchParams]);

  // Run the queued turn once readiness is known (or its load failed).
  useEffect(() => {
    if (!queued || status === null) return;
    const { prompt, layer: queuedLayer } = queued;
    setQueued(null);
    setLayer(queuedLayer);
    router.replace("/consultant");
    void runTurn(prompt, queuedLayer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queued, status]);

  const history = histories[layer];

  const runTurn = useCallback(
    async (prompt: string, turnLayer: ConsultLayer) => {
      const text = prompt.trim();
      if (!text || busy) return;
      const past = histories[turnLayer];
      const userTurn: ConsultTurn = { role: "user", content: text };
      const next = [...past, userTurn];
      setHistories((h) => ({ ...h, [turnLayer]: next }));
      setHistory(turnLayer, next);
      setDraft("");
      setTurnError(null);
      setTurnSources(null);
      setLastMeta(null);
      setStreamText("");

      const key = demoKey.trim();
      const ready = !!status?.ready || (!!status?.demo_mode && key.length > 0);

      // app.py parity: when not ready no request goes out; the exact offline
      // message is shown and kept in the layer history.
      if (!ready) {
        const withOffline: ConsultTurn[] = [
          ...next,
          { role: "assistant", content: OFFLINE_MESSAGE },
        ];
        setHistories((h) => ({ ...h, [turnLayer]: withOffline }));
        setHistory(turnLayer, withOffline);
        setTurnError(OFFLINE_MESSAGE);
        return;
      }

      setBusy(true);
      setBusyLabel(turnLayer === "apply" ? "Mapping onto your system…" : "Consulting…");
      let content = "";
      let gotError: string | null = null;
      try {
        await streamConsult(
          {
            message: text,
            history: past,
            layer: turnLayer,
            apiKey: status?.demo_mode ? key : undefined,
          },
          (ev) => {
            if (ev.type === "sources") {
              setTurnSources(ev.sources);
            } else if (ev.type === "delta") {
              content += ev.text;
              setStreamText(content);
            } else if (ev.type === "done") {
              content = ev.content;
              setStreamText(ev.content);
              setLastMeta({ model: ev.model, provider: ev.provider });
            } else if (ev.type === "error") {
              gotError = ev.message;
            }
          },
        );
        if (!gotError && !content.trim()) {
          gotError = "The model returned an empty response.";
        }
      } catch (exc) {
        if (exc instanceof DOMException && exc.name === "AbortError") return;
        gotError = exc instanceof Error ? exc.message : "Consultant request failed.";
      }

      const finalTurn: ConsultTurn = {
        role: "assistant",
        content: gotError ? gotError : content.trim(),
      };
      const final = [...next, finalTurn];
      setHistories((h) => ({ ...h, [turnLayer]: final }));
      setHistory(turnLayer, final);
      if (gotError) setTurnError(gotError);
      setStreamText("");
      setBusy(false);
      setBusyLabel("");
    },
    [busy, demoKey, histories, status],
  );

  const send = useCallback(() => {
    void runTurn(draft, layer);
  }, [draft, layer, runTurn]);

  const clearSession = useCallback(() => {
    setHistories((h) => ({ ...h, [layer]: [] }));
    setHistory(layer, []);
    setTurnError(null);
    setTurnSources(null);
    setLastMeta(null);
  }, [layer]);

  const onDemoKeyChange = useCallback((value: string) => {
    setDemoKeyState(value);
    setDemoKey(value);
  }, []);

  const lastIsAssistant =
    history.length > 0 && history[history.length - 1].role === "assistant";

  return (
    <div className="mx-auto flex w-full max-w-[860px] flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-0">
          Consultant Terminal
        </h1>
        <p className="mt-1 text-sm text-ink-1">
          Grounded in your library, repo README, and the pulse — answers cite
          what they checked.
        </p>
      </div>

      {statusError ? (
        <p role="alert" className="rounded-lg border border-bad/40 bg-bad/10 px-3 py-2 text-sm text-bad">
          {statusError}{" "}
          <button
            type="button"
            onClick={loadStatus}
            className="font-mono text-xs underline hover:text-ink-0"
          >
            Retry
          </button>
        </p>
      ) : status === null ? (
        <p className="font-mono text-xs text-ink-2">checking consultant…</p>
      ) : status.ready ? (
        <p className="rounded-lg border border-ok/40 bg-ok/10 px-3 py-2 text-sm text-ok">
          Consultant ready · {status.provider} · {status.model}
        </p>
      ) : status.demo_mode ? (
        <p className="rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-sm text-warn">
          Paste a Groq key above to unlock the Consultant (this session only).
        </p>
      ) : (
        <p className="rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-sm text-warn">
          Set <code className="font-mono">GROQ_API_KEY</code> in{" "}
          <code className="font-mono">.env</code> for the Consultant Terminal.
        </p>
      )}

      {status?.demo_mode && (
        <div className="rounded-[10px] border border-line-0 bg-bg-1 p-4">
          <p className="text-sm text-ink-1">
            Demo mode — explore freely. Data is ephemeral and nothing is saved.
            Add your own Groq key below to unlock the Consultant Terminal.
          </p>
          <label className="mt-3 block">
            <span className="font-mono text-xs text-ink-2">
              Groq API key (this session only)
            </span>
            <input
              type="password"
              value={demoKey}
              onChange={(e) => onDemoKeyChange(e.target.value)}
              className="mt-1 w-full rounded-lg border border-line-0 bg-bg-0 px-3 py-2 font-mono text-sm text-ink-0 outline-none transition-colors duration-120 focus:border-accent"
              placeholder="gsk_…"
            />
          </label>
          <p className="mt-1 text-xs text-ink-2">
            Kept in memory for this browser session. Never written to disk.
          </p>
        </div>
      )}

      <div role="tablist" aria-label="Consultant layer" className="flex flex-wrap gap-1.5">
        {CONSULT_LAYERS.map((l) => (
          <button
            key={l}
            type="button"
            role="tab"
            aria-selected={layer === l}
            onClick={() => setLayer(l)}
            className={`rounded-lg border px-3 py-1.5 font-mono text-xs transition-colors duration-120 ${
              layer === l
                ? "border-accent bg-accent/10 text-ink-0"
                : "border-line-0 bg-bg-1 text-ink-1 hover:border-line-1"
            }`}
          >
            {LAYER_LABELS[l]}
          </button>
        ))}
      </div>

      <p className="text-[13px] leading-relaxed text-ink-2">{LAYER_HINTS[layer]}</p>

      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={clearSession}
          disabled={history.length === 0}
          className="rounded-lg border border-line-0 bg-bg-1 px-3 py-1.5 font-mono text-xs text-ink-1 transition-colors duration-120 hover:border-line-1 hover:text-ink-0 disabled:opacity-50"
        >
          Clear session
        </button>
        {lastMeta && lastIsAssistant && (
          <span className="font-mono text-[11px] text-ink-2">
            {lastMeta.provider} · {lastMeta.model}
          </span>
        )}
      </div>

      <div className="flex min-h-[120px] flex-col gap-3">
        {history.length === 0 && !busy && (
          <p className="rounded-[10px] border border-dashed border-line-0 px-4 py-6 text-center text-sm text-ink-2">
            No turns yet in this layer.
          </p>
        )}
        {history.map((turn, i) => (
          <div
            key={i}
            className={
              turn.role === "user"
                ? "self-end max-w-[90%] rounded-[10px] rounded-br-sm border border-accent/40 bg-accent/10 px-4 py-2.5 text-sm whitespace-pre-wrap text-ink-0"
                : "self-start w-full rounded-[10px] rounded-bl-sm border border-line-0 bg-bg-1 px-4 py-3 text-sm whitespace-pre-wrap text-ink-1"
            }
          >
            {turn.content}
            {turn.role === "assistant" && i === history.length - 1 && turnSources && turnSources.length > 0 && (
              <details className="mt-3 rounded-lg border border-line-0 bg-bg-0">
                <summary className="cursor-pointer px-3 py-2 font-mono text-xs text-ink-2">
                  Checked sources (click these — do not trust an unsourced paper name)
                </summary>
                <ul className="flex flex-col gap-1.5 px-3 pb-3 text-[13px]">
                  {turnSources.map((src, j) => (
                    <li key={j} className="text-ink-1">
                      <span className="font-semibold text-ink-0">{src.kind}</span>
                      {" · "}
                      {src.url ? (
                        <a
                          href={src.url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-accent hover:underline"
                        >
                          {src.title}
                        </a>
                      ) : (
                        src.title
                      )}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        ))}
        {busy && (
          <div className="self-start w-full rounded-[10px] rounded-bl-sm border border-line-0 bg-bg-1 px-4 py-3">
            <p className="font-mono text-xs text-ink-2">{busyLabel}</p>
            {streamText && (
              <p className="mt-2 text-sm whitespace-pre-wrap text-ink-1">{streamText}</p>
            )}
          </div>
        )}
      </div>

      {turnError && (
        <p role="alert" className="rounded-lg border border-bad/40 bg-bad/10 px-3 py-2 text-sm whitespace-pre-wrap text-bad">
          {turnError}
        </p>
      )}

      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={LAYER_PLACEHOLDERS[layer]}
          disabled={busy}
          aria-label="Consultant message"
          className="min-w-0 flex-1 rounded-lg border border-line-0 bg-bg-0 px-3 py-2 text-sm text-ink-0 outline-none transition-colors duration-120 focus:border-accent disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={busy || draft.trim().length === 0}
          className="shrink-0 rounded-lg bg-accent px-4 py-2 font-mono text-xs font-medium text-bg-0 transition-opacity duration-120 hover:opacity-90 disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  );
}
