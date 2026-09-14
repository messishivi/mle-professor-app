import type { PulseFit } from "@/lib/pulse";

interface Cfg {
  filled: number;
  cls: string;
  text: string;
}

/**
 * Maps a live fit label (trends.score_against_stack) onto the P1 meter:
 * "High fit" → 3 ok · "Watch" → 2 warn · "Skip" → 1 bad ·
 * "Set stack" → 2 neutral (it is a prompt, not a verdict).
 * Unknown labels fall back to a score-based mapping.
 */
function cfgFor(fit: PulseFit): Cfg {
  const l = fit.label.toLowerCase();
  if (l === "high fit") return { filled: 3, cls: "bg-ok", text: "HIGH FIT" };
  if (l === "watch") return { filled: 2, cls: "bg-warn", text: "WATCH" };
  if (l === "skip") return { filled: 1, cls: "bg-bad", text: "SKIP" };
  if (l === "set stack")
    return { filled: 2, cls: "bg-line-1", text: "SET STACK" };
  if (fit.score >= 70)
    return { filled: 3, cls: "bg-ok", text: fit.label.toUpperCase() };
  if (fit.score >= 30)
    return { filled: 2, cls: "bg-warn", text: fit.label.toUpperCase() };
  return { filled: 1, cls: "bg-bad", text: fit.label.toUpperCase() };
}

export function StackFitMeter({ fit }: { fit: PulseFit }) {
  const c = cfgFor(fit);
  return (
    <span
      role="img"
      aria-label={`Stack fit ${c.text.toLowerCase()}`}
      className="inline-flex items-center gap-1.5"
    >
      <span aria-hidden className="flex items-center gap-0.5">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className={`h-2.5 w-1.5 rounded-[1px] ${
              i < c.filled ? c.cls : "bg-line-0"
            }`}
          />
        ))}
      </span>
      <span className="font-mono text-[11px] tracking-[0.04em] text-ink-1">
        {c.text}
      </span>
    </span>
  );
}
