import type { StackFit } from "@/lib/pulse-types";

const CFG: Record<StackFit, { label: string; filled: number; cls: string }> = {
  high: { label: "HIGH", filled: 3, cls: "bg-ok" },
  watch: { label: "WATCH", filled: 2, cls: "bg-warn" },
  low: { label: "LOW", filled: 1, cls: "bg-bad" },
};

export function StackFitMeter({ fit }: { fit: StackFit }) {
  const c = CFG[fit];
  return (
    <span
      role="img"
      aria-label={`Stack fit ${c.label.toLowerCase()}`}
      className="inline-flex items-center gap-1.5"
    >
      <span aria-hidden className="flex items-center gap-0.5">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className={`h-2.5 w-1.5 rounded-[1px] ${i < c.filled ? c.cls : "bg-line-0"}`}
          />
        ))}
      </span>
      <span className="font-mono text-[11px] tracking-[0.04em] text-ink-1">
        {c.label}
      </span>
    </span>
  );
}
