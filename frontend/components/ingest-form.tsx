"use client";

import { useState } from "react";
import type { IngestResult } from "@/lib/api";
import { ingest } from "@/lib/api";
import { CATEGORY_OPTIONS, DEFAULT_CATEGORIES } from "@/lib/constants";

interface IngestFormProps {
  /** Called after a successful ingest so the list can refetch. */
  onIngested?: (result: IngestResult) => void;
}

/**
 * ArXiv ingest — Streamlit sidebar parity (app.py:304-340): category
 * multiselect (default cs.CL + cs.LG), max-results slider 5..50 step 5,
 * "Pick at least one category." validation, fetched/upserted/skipped summary.
 */
export function IngestForm({ onIngested }: IngestFormProps) {
  const [categories, setCategories] = useState<string[]>([
    ...DEFAULT_CATEGORIES,
  ]);
  const [maxResults, setMaxResults] = useState(20);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<IngestResult | null>(null);

  function toggleCategory(cat: string) {
    setCategories((prev) =>
      prev.includes(cat)
        ? prev.filter((c) => c !== cat)
        : [...prev, cat],
    );
  }

  async function submit() {
    if (running) return;
    if (categories.length === 0) {
      setError("Pick at least one category.");
      return;
    }
    setError(null);
    setRunning(true);
    try {
      const res = await ingest({
        categories,
        max_results: maxResults,
      });
      setResult(res);
      onIngested?.(res);
    } catch (exc) {
      setResult(null);
      setError(
        exc instanceof Error ? exc.message : "Ingest failed.",
      );
    } finally {
      setRunning(false);
    }
  }

  return (
    <section
      aria-label="ArXiv ingest"
      className="rounded-[10px] border border-line-0 bg-bg-1 p-4"
    >
      <h2 className="font-mono text-xs uppercase tracking-[0.04em] text-ink-2">
        ArXiv ingest
      </h2>
      <p className="mt-1 text-[13px] text-ink-1">
        Pull the newest papers into your library.
      </p>

      <fieldset className="mt-3">
        <legend className="mb-1.5 font-mono text-xs text-ink-2">
          Categories
        </legend>
        <div className="flex flex-wrap gap-1.5">
          {CATEGORY_OPTIONS.map((cat) => {
            const active = categories.includes(cat);
            return (
              <button
                key={cat}
                type="button"
                onClick={() => toggleCategory(cat)}
                aria-pressed={active}
                className={`rounded-md px-2 py-0.5 font-mono text-xs transition-colors duration-120 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
                  active
                    ? "bg-accent-dim text-ink-0"
                    : "bg-bg-2 text-ink-1 hover:bg-bg-3"
                }`}
              >
                {cat}
              </button>
            );
          })}
        </div>
      </fieldset>

      <label
        htmlFor="ingest-max"
        className="mt-3 block font-mono text-xs text-ink-2"
      >
        Max results: {maxResults}
      </label>
      <input
        id="ingest-max"
        type="range"
        min={5}
        max={50}
        step={5}
        value={maxResults}
        onChange={(e) => setMaxResults(Number(e.target.value))}
        className="mt-1 w-full accent-[var(--accent)]"
      />

      {error && (
        <p role="alert" className="mt-3 text-[13px] text-bad">
          {error}
        </p>
      )}

      {result && (
        <p
          role="status"
          className="mt-3 font-mono text-xs text-ink-1"
        >
          Fetched {result.fetched} · upserted {result.upserted} · skipped{" "}
          {result.skipped}
          {result.errors.length > 0 && ` · ${result.errors.length} error(s)`}
        </p>
      )}

      <button
        type="button"
        onClick={submit}
        disabled={running}
        className="mt-4 w-full rounded-lg border border-line-0 bg-bg-2 px-4 py-1.5 text-sm text-ink-1 transition-colors duration-120 hover:border-line-1 hover:text-ink-0 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-50"
      >
        {running ? "Requesting the ArXiv Atom feed…" : "Refresh papers"}
      </button>
    </section>
  );
}
