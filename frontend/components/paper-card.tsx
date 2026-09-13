import type { Paper } from "@/lib/pulse-types";
import { StackFitMeter } from "./stack-fit-meter";
import { VerdictBadge } from "./verdict-badge";

export function PaperCard({ paper }: { paper: Paper }) {
  return (
    <article className="rounded-[10px] border border-line-0 bg-bg-1 p-4 transition-colors duration-120 hover:border-line-1">
      <div className="flex gap-4">
        <div className="hidden w-[72px] shrink-0 flex-col items-start gap-1 font-mono text-xs text-ink-2 sm:flex">
          <span>{paper.source}</span>
          <span>{paper.date}</span>
          <a
            href={paper.url}
            target="_blank"
            rel="noreferrer"
            className="hover:text-accent"
          >
            {paper.arxivId ?? "—"}
          </a>
        </div>

        <div className="min-w-0 flex-1">
          <h3 className="text-[15px] font-medium leading-snug">
            <a
              href={paper.url}
              target="_blank"
              rel="noreferrer"
              className={`hover:underline ${
                paper.read ? "text-ink-2" : "text-ink-0"
              }`}
            >
              {paper.title}
            </a>
            {paper.read && (
              <span className="ml-2 font-mono text-[11px] text-ok">
                ✓ read
              </span>
            )}
          </h3>

          <p className="mt-1 text-[13px] leading-relaxed text-ink-1">
            {paper.abstract}
          </p>

          {paper.concepts.length > 0 && (
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {paper.concepts.map((c) => (
                <li
                  key={c}
                  className="rounded-md bg-bg-2 px-2 py-0.5 font-mono text-xs text-ink-1"
                >
                  {c}
                </li>
              ))}
            </ul>
          )}

          <div className="mt-3 flex flex-wrap items-center gap-3">
            <VerdictBadge verdict={paper.verdict} />
            <StackFitMeter fit={paper.fit} />
          </div>
        </div>
      </div>
    </article>
  );
}
