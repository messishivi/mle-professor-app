"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { ApiPaper } from "@/lib/api";
import { listPapers, patchPaper } from "@/lib/api";
import { buildApplyPrompt, getSettings } from "@/lib/consult";
import type { ApplyContext } from "@/lib/consult";
import { LibraryRow } from "@/components/library-row";
import { IngestForm } from "@/components/ingest-form";

type ReadFilter = "all" | "unread" | "read";

const FILTERS: { id: ReadFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "unread", label: "Unread" },
  { id: "read", label: "Read" },
];

interface PapersClientProps {
  /**
   * "all" (Papers page): full library, search, filters, ingest.
   * "saved" (Saved page): read papers only — Streamlit "Saved" pane parity.
   */
  mode?: "all" | "saved";
}

export function PapersClient({ mode = "all" }: PapersClientProps) {
  const savedOnly = mode === "saved";

  const [papers, setPapers] = useState<ApiPaper[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<ReadFilter>("all");

  const [busyId, setBusyId] = useState<string | null>(null);

  const seq = useRef(0);
  const router = useRouter();

  const load = useCallback(async () => {
    const id = ++seq.current;
    setLoading(true);
    setError(null);
    try {
      const res = await listPapers({
        q: query.trim() || undefined,
        read: savedOnly ? 1 : filter === "all" ? undefined : filter === "unread" ? 0 : 1,
      });
      if (id !== seq.current) return;
      setPapers(res.papers);
      setCount(res.count);
    } catch (exc) {
      if (id !== seq.current) return;
      setPapers([]);
      setCount(0);
      setError(exc instanceof Error ? exc.message : "Failed to load papers.");
    } finally {
      if (id === seq.current) setLoading(false);
    }
  }, [query, filter, savedOnly]);

  // Initial load + refetch on search/filter changes (250 ms debounce so
  // typing doesn't fire a request per keystroke).
  useEffect(() => {
    const timer = setTimeout(load, savedOnly ? 0 : 250);
    return () => clearTimeout(timer);
  }, [load, savedOnly]);

  async function toggleRead(paper: ApiPaper) {
    if (busyId) return;
    const next = paper.read_status === 1 ? 0 : 1;
    setBusyId(paper.id);
    // optimistic update, rolled back on failure
    setPapers((prev) =>
      prev.map((p) =>
        p.id === paper.id ? { ...p, read_status: next as 0 | 1 } : p,
      ),
    );
    try {
      await patchPaper(paper.id, next);
      setCount((c) => c); // count unchanged by a read toggle
      if (savedOnly && next === 0) {
        // the row leaves the saved view
        setPapers((prev) => prev.filter((p) => p.id !== paper.id));
      }
    } catch (exc) {
      setPapers((prev) =>
        prev.map((p) =>
          p.id === paper.id ? { ...p, read_status: paper.read_status } : p,
        ),
      );
      setError(exc instanceof Error ? exc.message : "Failed to update paper.");
    } finally {
      setBusyId(null);
    }
  }

  // Streamlit parity (app.py:193-195): "Apply to my system" on every row.
  // The full paper (title/authors/date/abstract) is passed to
  // buildApplyPrompt with the user's saved settings as context.
  const apply = useCallback(async (paper: ApiPaper) => {
    let ctx: ApplyContext = { application: "", known_papers: "", repo_url: "" };
    try {
      const s = await getSettings();
      ctx = {
        application: s.application,
        known_papers: s.known_papers,
        repo_url: s.repo_url,
      };
    } catch {
      // dead settings endpoint -> empty context; the paper fields remain
    }
    const prompt = buildApplyPrompt(
      {
        id: paper.id,
        title: paper.title,
        authors: paper.authors,
        published_date: paper.published_date ?? "",
        summary_raw: paper.summary_raw,
      },
      ctx,
    );
    router.push(`/consultant?layer=apply&q=${encodeURIComponent(prompt)}`);
  }, [router]);

  const heading = savedOnly ? "Saved" : "Papers";
  const caption = savedOnly
    ? "Papers you marked read."
    : `Your library · ${count} paper${count === 1 ? "" : "s"}`;

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{heading}</h1>
          <p className="mt-0.5 text-[13px] text-ink-2">{caption}</p>
        </div>
        <div className="flex flex-col items-end gap-2">
          {!savedOnly && (
            <label htmlFor="paper-search" className="sr-only">
              Search papers
            </label>
          )}
          {!savedOnly && (
            <input
              id="paper-search"
              type="search"
              placeholder="Search title, authors, id…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-64 rounded-lg border border-line-0 bg-bg-1 px-3 py-1.5 text-sm text-ink-0 placeholder:text-ink-2 focus:border-line-1 focus:outline-none"
            />
          )}
          {!savedOnly && (
            <div
              role="tablist"
              aria-label="Read status filter"
              className="flex gap-1 rounded-lg border border-line-0 bg-bg-1 p-0.5"
            >
              {FILTERS.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  role="tab"
                  aria-selected={filter === f.id}
                  onClick={() => setFilter(f.id)}
                  className={`rounded-md px-3 py-1 font-mono text-xs transition-colors duration-120 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
                    filter === f.id
                      ? "bg-bg-3 text-ink-0"
                      : "text-ink-2 hover:text-ink-1"
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </header>

      {error && (
        <p role="alert" className="text-[13px] text-bad">
          {error}
        </p>
      )}

      {loading && (
        <p role="status" className="font-mono text-xs text-ink-2">
          loading…
        </p>
      )}

      {!loading && !error && papers.length === 0 && (
        <div className="rounded-[10px] border border-dashed border-line-1 bg-bg-1 px-6 py-10 text-center">
          <p className="text-sm text-ink-1">
            {savedOnly
              ? "No saved papers yet — mark a paper read and it lands here."
              : query
                ? `No papers match “${query}”.`
                : "No papers yet — ingest from ArXiv."}
          </p>
          {!savedOnly && papers.length === 0 && count === 0 && (
            <p className="mt-1 font-mono text-xs text-ink-2">
              Use the ArXiv ingest below to pull the latest papers.
            </p>
          )}
        </div>
      )}

      {!loading && papers.length > 0 && (
        <div className="flex flex-col gap-3">
          {papers.map((paper) => (
            <LibraryRow
              key={paper.id}
              paper={paper}
              busy={busyId === paper.id}
              onToggleRead={toggleRead}
              onApply={(p) => void apply(p)}
            />
          ))}
        </div>
      )}

      {!savedOnly && (
        <div className="w-full max-w-md">
          <IngestForm
            onIngested={() => {
              void load();
            }}
          />
        </div>
      )}
    </div>
  );
}
