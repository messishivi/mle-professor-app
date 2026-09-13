import type { Verdict } from "@/lib/pulse-types";

const STYLES: Record<Verdict, { label: string; cls: string }> = {
  adopt: { label: "ADOPT", cls: "border-ok/40 bg-ok/10 text-ok" },
  prototype: { label: "PROTOTYPE", cls: "border-accent/40 bg-accent/10 text-accent" },
  watch: { label: "WATCH", cls: "border-warn/40 bg-warn/10 text-warn" },
  skip: { label: "SKIP", cls: "border-bad/40 bg-bad/10 text-bad" },
};

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  const s = STYLES[verdict];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 font-mono text-[11px] uppercase tracking-[0.04em] ${s.cls}`}
    >
      <span aria-hidden className="size-1 rounded-full bg-current" />
      {s.label}
    </span>
  );
}
