import { PaperCard } from "@/components/paper-card";
import { MOCK_PAPERS, MOCK_STACK, MOCK_UPDATED_AT } from "@/lib/mock-pulse";

export default function PulsePage() {
  return (
    <>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-xl font-semibold tracking-tight">Pulse</h1>
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs text-ink-2">
            updated {MOCK_UPDATED_AT} · mock data
          </span>
          <button
            type="button"
            className="rounded-lg border border-line-0 bg-bg-2 px-4 py-1.5 text-sm text-ink-1 transition-colors duration-120 hover:border-line-1 hover:text-ink-0 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-1.5">
        <span className="mr-1 font-mono text-xs text-ink-2">stack:</span>
        {MOCK_STACK.map((s) => (
          <span
            key={s}
            className="rounded-md bg-bg-2 px-2 py-0.5 font-mono text-xs text-ink-1"
          >
            {s}
          </span>
        ))}
      </div>

      <div className="mt-4 flex flex-col gap-3">
        {MOCK_PAPERS.map((p) => (
          <PaperCard key={p.id} paper={p} />
        ))}
      </div>
    </>
  );
}
