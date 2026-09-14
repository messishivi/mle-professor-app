"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ApiError } from "@/lib/api";
import { getConsultStatus } from "@/lib/api";
import type { PulseItem, PulsePayload, PulseView } from "@/lib/pulse";
import {
  formatFetchedAt,
  getPulse,
  memoItemKey,
  pulseErrorMessage,
  rankItems,
  refreshPulse,
  refineMemo,
} from "@/lib/pulse";
import { PulseItemCard } from "./pulse-item-card";

/**
 * Live ML Pulse page (P3b). Replaces the P1 mock prototype:
 * GET /pulse for the snapshot, POST /pulse/refresh for the sidebar's
 * "Refresh ML Pulse", POST /pulse/memos/refine per item, and the
 * "For my stack" / "Everything" re-rank (app.py:518-525 parity,
 * computed client-side from the fit score the API already attached).
 */
export function PulseClient() {
  const [payload, setPayload] = useState<PulsePayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshErrors, setRefreshErrors] = useState<string[]>([]);
  const [actionError, setActionError] = useState<string | null>(null);
  const [view, setView] = useState<PulseView>("stack");
  const [refiningKey, setRefiningKey] = useState<string | null>(null);
  const [apiReady, setApiReady] = useState(false);
  const seq = useRef(0);

  const load = useCallback(async () => {
    const id = ++seq.current;
    setLoading(true);
    setLoadError(null);
    setRefreshErrors([]);
    setActionError(null);
    try {
      const [pulse, status] = await Promise.all([
        getPulse(),
        // A dead /consult/status must not blank the page — refine just
        // stays disabled (it needs the key check, not the feeds).
        getConsultStatus().catch(() => null),
      ]);
      if (id !== seq.current) return;
      setPayload(pulse);
      setApiReady(status?.ready ?? false);
    } catch (e) {
      if (id !== seq.current) return;
      setLoadError(pulseErrorMessage(e as unknown as ApiError));
    } finally {
      if (id === seq.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    setRefreshErrors([]);
    setActionError(null);
    try {
      const p = await refreshPulse();
      setPayload(p);
      setRefreshErrors(p.errors);
    } catch (e) {
      setActionError(pulseErrorMessage(e as unknown as ApiError));
    } finally {
      setRefreshing(false);
    }
  }, []);

  const refine = useCallback(
    async (item: PulseItem) => {
      if (!payload) return;
      const key = memoItemKey(item);
      setRefiningKey(key);
      setActionError(null);
      try {
        const res = await refineMemo(item, payload.stack);
        setPayload((prev) =>
          prev
            ? {
                ...prev,
                items: prev.items.map((i) =>
                  memoItemKey(i) === res.item_key ? { ...i, memo: res.memo } : i,
                ),
              }
            : prev,
        );
      } catch (e) {
        setActionError(pulseErrorMessage(e as unknown as ApiError));
      } finally {
        setRefiningKey(null);
      }
    },
    [payload],
  );

  const stack = payload?.stack ?? [];
  const items = payload
    ? rankItems(payload.items, payload.stack, view)
    : [];
  const showStackEmpty =
    view === "stack" && stack.length > 0 && payload !== null && items.length === 0;

  return (
    <>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-xl font-semibold tracking-tight">Pulse</h1>
        <div className="flex items-center gap-3">
          {payload && (
            <span className="font-mono text-xs text-ink-2">
              updated {formatFetchedAt(payload.fetched_at)} ·{" "}
              {payload.items.length} items
            </span>
          )}
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={refreshing}
            className="rounded-lg border border-line-0 bg-bg-2 px-4 py-1.5 text-sm text-ink-1 transition-colors duration-120 hover:border-line-1 hover:text-ink-0 disabled:cursor-wait disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </div>

      <p className="mt-2 max-w-2xl text-[13px] leading-relaxed text-ink-2">
        Morning brief: Hugging Face Daily Papers <strong>trending</strong> plus
        newest arXiv cs.LG / cs.CL / cs.AI, limited to the last 60 days.{" "}
        <strong>For my stack</strong> re-ranks that list. Saved is your
        library.
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-1.5">
        <span className="mr-1 font-mono text-xs text-ink-2">stack:</span>
        {stack.length > 0 ? (
          stack.map((s) => (
            <span
              key={s}
              className="rounded-md bg-bg-2 px-2 py-0.5 font-mono text-xs text-ink-1"
            >
              {s}
            </span>
          ))
        ) : (
          <span className="font-mono text-xs text-ink-2">
            not set — items rank as “Set stack”
          </span>
        )}
      </div>

      <div
        role="tablist"
        aria-label="Pulse view"
        className="mt-3 flex gap-1 border-b border-line-0 pb-px"
      >
        {(
          [
            ["stack", "For my stack"],
            ["all", "Everything"],
          ] as [PulseView, string][]
        ).map(([v, label]) => (
          <button
            key={v}
            role="tab"
            aria-selected={view === v}
            onClick={() => setView(v)}
            className={`-mb-px rounded-t-md border-b-2 px-3 py-1.5 text-[13px] transition-colors duration-120 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
              view === v
                ? "border-accent text-ink-0"
                : "border-transparent text-ink-2 hover:text-ink-1"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {refreshErrors.length > 0 && (
        <div
          role="alert"
          className="mt-3 rounded-lg border border-bad/40 bg-bad/10 px-3 py-2 text-[13px] text-bad"
        >
          {refreshErrors.map((e) => (
            <p key={e}>{e}</p>
          ))}
        </div>
      )}
      {actionError && (
        <div
          role="alert"
          className="mt-3 rounded-lg border border-bad/40 bg-bad/10 px-3 py-2 text-[13px] text-bad"
        >
          {actionError}
        </div>
      )}

      {loading && (
        <p
          role="status"
          className="mt-8 font-mono text-xs uppercase tracking-[0.04em] text-ink-2"
        >
          Loading pulse…
        </p>
      )}

      {!loading && loadError && (
        <div className="mt-8 flex flex-col items-start gap-2">
          <p role="alert" className="text-sm text-bad">
            {loadError}
          </p>
          <button
            type="button"
            onClick={() => void load()}
            className="rounded-lg border border-line-0 bg-bg-2 px-3 py-1 text-xs text-ink-1 hover:border-line-1 hover:text-ink-0 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            Retry
          </button>
        </div>
      )}

      {!loading && !loadError && payload !== null && payload.items.length === 0 && (
        <div className="mt-8 rounded-lg border border-line-0 bg-bg-1 px-4 py-6 text-center">
          <p className="text-sm text-ink-1">
            No pulse yet. Click <strong>Refresh</strong> to pull the feeds.
          </p>
        </div>
      )}

      {!loading && !loadError && showStackEmpty && (
        <div className="mt-8 rounded-lg border border-line-0 bg-bg-1 px-4 py-6 text-center">
          <p className="text-sm text-ink-1">
            Nothing on your stack in this pulse. Switch to Everything, or
            refresh.
          </p>
        </div>
      )}

      {!loading && !loadError && items.length > 0 && (
        <div className="mt-4 flex flex-col gap-3">
          {items.map((item) => (
            <PulseItemCard
              key={memoItemKey(item)}
              item={item}
              apiReady={apiReady}
              refining={refiningKey === memoItemKey(item)}
              onRefine={(i) => void refine(i)}
            />
          ))}
        </div>
      )}
    </>
  );
}
