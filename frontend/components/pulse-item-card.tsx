import type { PulseItem } from "@/lib/pulse";
import { StackFitMeter } from "./stack-fit-meter";
import { VerdictBadge } from "./verdict-badge";

interface PulseItemCardProps {
  item: PulseItem;
  /** /consult/status ready — "Refine memo" is disabled when offline (app.py parity). */
  apiReady: boolean;
  refining: boolean;
  onRefine: (item: PulseItem) => void;
  /** Queues the paper into the Consultant's Apply layer (app.py:583-593 parity). */
  onApply?: (item: PulseItem) => void;
  /** True while the Apply prompt is being prepared. */
  applying?: boolean;
}

/** Tag row parity (app.py:526-535): fit label, date, trending/arxiv new, paper, concept, in library. */
function tags(item: PulseItem): string[] {
  const t = [item.fit.label];
  if (item.published_date) t.push(item.published_date.slice(0, 10));
  if (item.source === "hf_daily") t.push("trending");
  else if (item.source === "arxiv") t.push("arxiv new");
  if (item.paper_id) t.push("paper");
  if (item.concept) t.push("concept");
  if (item.in_library) t.push("in library");
  return t;
}

export function PulseItemCard({
  item,
  apiReady,
  refining,
  onRefine,
  onApply,
  applying,
}: PulseItemCardProps) {
  const memoUrl = item.memo.paper_url || item.paper_url;
  return (
    <article className="rounded-[10px] border border-line-0 bg-bg-1 p-4 transition-colors duration-120 hover:border-line-1">
      <div className="flex gap-4">
        <div className="hidden w-[72px] shrink-0 flex-col items-start gap-1 font-mono text-xs text-ink-2 sm:flex">
          <span>{item.published_date || "—"}</span>
          {item.paper_id ? (
            <a
              href={item.paper_url || `https://arxiv.org/abs/${item.paper_id}`}
              target="_blank"
              rel="noreferrer"
              className="hover:text-accent"
            >
              arXiv:{item.paper_id}
            </a>
          ) : (
            <span aria-hidden>—</span>
          )}
          <span className={item.source === "hf_daily" ? "text-accent" : ""}>
            {item.source === "hf_daily" ? "trending" : "arxiv new"}
          </span>
        </div>

        <div className="min-w-0 flex-1">
          <h3 className="text-[15px] font-medium leading-snug">
            {item.paper_url ? (
              <a
                href={item.paper_url}
                target="_blank"
                rel="noreferrer"
                className="text-ink-0 hover:underline"
              >
                {item.topic}
              </a>
            ) : (
              <span className="text-ink-0">{item.topic}</span>
            )}
          </h3>

          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {tags(item).map((t) => (
              <span
                key={t}
                className="rounded-md bg-bg-2 px-2 py-0.5 font-mono text-[11px] text-ink-2"
              >
                {t}
              </span>
            ))}
          </div>

          <p className="mt-2 text-[13px] leading-relaxed text-ink-2">
            {item.fit.so_what}
          </p>
          {item.why && (
            <p className="mt-1.5 text-[13px] leading-relaxed text-ink-1">
              {item.why}
            </p>
          )}

          <div className="mt-3 rounded-lg bg-bg-2 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs uppercase tracking-[0.04em] text-ink-2">
                Decision
              </span>
              <VerdictBadge verdict={item.memo.verdict} />
              {item.memo.origin === "groq" && (
                <span className="font-mono text-[11px] italic text-ink-2">
                  groq
                </span>
              )}
            </div>
            {item.memo.so_what && (
              <p className="mt-1.5 text-[13px] leading-relaxed text-ink-1">
                {item.memo.so_what}
              </p>
            )}
            {item.memo.constraint_note && (
              <p className="mt-1 text-[13px] leading-relaxed text-ink-2">
                Constraint: {item.memo.constraint_note}
              </p>
            )}
            {memoUrl && (
              <a
                href={memoUrl}
                target="_blank"
                rel="noreferrer"
                className="mt-1.5 inline-block break-all font-mono text-xs text-accent hover:underline"
              >
                {memoUrl}
              </a>
            )}
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
            <StackFitMeter fit={item.fit} />
            {item.paper_id ? (
              <span className="text-[13px] text-ink-1">
                Paper ·{" "}
                <a
                  href={item.paper_url || `https://arxiv.org/abs/${item.paper_id}`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-ink-0 hover:underline"
                >
                  {item.paper_title || item.paper_id}
                </a>{" "}
                <span className="font-mono text-xs text-ink-2">
                  arXiv:{item.paper_id}
                </span>
              </span>
            ) : (
              <span className="text-[13px] text-ink-2">
                No single paper pinned to this topic.
              </span>
            )}
            {item.concept && (
              <span className="text-[13px] text-ink-1">
                Concept · <strong>{item.concept}</strong>
                {item.concept_blurb && (
                  <span className="text-ink-2"> — {item.concept_blurb}</span>
                )}
              </span>
            )}
            <span className="ml-auto flex items-center gap-2">
              {onApply && item.paper_id && (
                <button
                  type="button"
                  onClick={() => onApply(item)}
                  disabled={applying}
                  className="rounded-lg border border-line-0 bg-bg-2 px-3 py-1 text-xs text-ink-1 transition-colors duration-120 hover:border-line-1 hover:text-ink-0 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                >
                  {applying ? "Queuing…" : "Apply"}
                </button>
              )}
              <button
                type="button"
                onClick={() => onRefine(item)}
                disabled={!apiReady || refining}
                title={
                  apiReady
                    ? undefined
                    : "Consultant is offline — set GROQ_API_KEY in the API .env"
                }
                className="rounded-lg border border-line-0 bg-bg-2 px-3 py-1 text-xs text-ink-1 transition-colors duration-120 hover:border-line-1 hover:text-ink-0 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              >
                {refining ? "Refining…" : "Refine memo"}
              </button>
            </span>
          </div>
        </div>
      </div>
    </article>
  );
}
