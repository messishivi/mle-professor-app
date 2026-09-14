import type { ApiPaper } from "@/lib/api";

/**
 * Category chips from summary_structured — render_structured parity
 * (app.py:121-145): primary_category first, then the rest, deduped.
 */
function structuredCategories(s: unknown): string[] {
  if (!s || typeof s !== "object") return [];
  const data = s as Record<string, unknown>;
  const cats: string[] = [];
  const primary = data.primary_category;
  if (typeof primary === "string" && primary) cats.push(primary);
  const arr = data.categories;
  if (Array.isArray(arr)) {
    for (const c of arr) {
      const t = String(c);
      if (t && !cats.includes(t)) cats.push(t);
    }
  }
  return cats;
}

interface LibraryRowProps {
  paper: ApiPaper;
  busy?: boolean;
  onToggleRead?: (paper: ApiPaper) => void;
  /** Queues the paper into the Consultant's Apply layer (app.py:193-195 parity). */
  onApply?: (paper: ApiPaper) => void;
}

/**
 * One row of the library (Streamlit "Saved" pane parity): title, authors,
 * date, arXiv link, abstract, and the read toggle.
 */
export function LibraryRow({ paper, busy, onToggleRead, onApply }: LibraryRowProps) {
  const read = paper.read_status === 1;
  return (
    <article className="rounded-[10px] border border-line-0 bg-bg-1 p-4 transition-colors duration-120 hover:border-line-1">
      <div className="flex gap-4">
        <div className="hidden w-[72px] shrink-0 flex-col items-start gap-1 font-mono text-xs text-ink-2 sm:flex">
          <span>{paper.published_date ?? "—"}</span>
          <a
            href={`https://arxiv.org/abs/${paper.id}`}
            target="_blank"
            rel="noreferrer"
            className="hover:text-accent"
          >
            {paper.id}
          </a>
        </div>

        <div className="min-w-0 flex-1">
          <h3 className="flex items-baseline gap-2 text-[15px] font-medium leading-snug">
            <a
              href={`https://arxiv.org/abs/${paper.id}`}
              target="_blank"
              rel="noreferrer"
              className={`hover:underline ${
                read ? "text-ink-2" : "text-ink-0"
              }`}
            >
              {paper.title || "(untitled)"}
            </a>
          </h3>
          {paper.authors && (
            <p className="mt-0.5 font-mono text-xs text-ink-2">
              {paper.authors}
            </p>
          )}
          {paper.summary_raw && (
            <p className="mt-1 text-[13px] leading-relaxed text-ink-1">
              {paper.summary_raw}
            </p>
          )}
          {(() => {
            const cats = structuredCategories(paper.summary_structured);
            return cats.length > 0 ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {cats.map((c) => (
                  <span
                    key={c}
                    className="rounded-md bg-bg-2 px-2 py-0.5 font-mono text-[11px] text-ink-2"
                  >
                    {c}
                  </span>
                ))}
              </div>
            ) : null;
          })()}
        </div>

        {(onToggleRead || onApply) && (
          <div className="flex shrink-0 flex-col items-end gap-2">
            {onToggleRead && (
              <button
                type="button"
                onClick={() => onToggleRead(paper)}
                disabled={busy}
                aria-pressed={read}
                aria-label={
                  read
                    ? `Mark ${paper.title || paper.id} as unread`
                    : `Mark ${paper.title || paper.id} as read`
                }
                className="rounded-lg border border-line-0 bg-bg-2 px-3 py-1 font-mono text-xs text-ink-1 transition-colors duration-120 hover:border-line-1 hover:text-ink-0 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-50"
              >
                {read ? "✓ read" : "mark read"}
              </button>
            )}
            {onApply && (
              <button
                type="button"
                onClick={() => onApply(paper)}
                aria-label={`Apply ${paper.title || paper.id} to my system`}
                className="rounded-lg border border-line-0 bg-bg-2 px-3 py-1 font-mono text-xs text-ink-1 transition-colors duration-120 hover:border-line-1 hover:text-ink-0 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-50"
              >
                Apply to my system
              </button>
            )}
          </div>
        )}
      </div>
    </article>
  );
}
