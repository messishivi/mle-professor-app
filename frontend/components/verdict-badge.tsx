const STYLES: Record<string, { label: string; cls: string }> = {
  adopt: { label: "ADOPT", cls: "border-ok/40 bg-ok/10 text-ok" },
  prototype: { label: "PROTOTYPE", cls: "border-accent/40 bg-accent/10 text-accent" },
  watch: { label: "WATCH", cls: "border-warn/40 bg-warn/10 text-warn" },
  skip: { label: "SKIP", cls: "border-bad/40 bg-bad/10 text-bad" },
};

/**
 * Live memo verdicts are free-form strings (case varies by origin, and the
 * groq refine pass can return unexpected text), so normalize by lowercasing
 * and fall back to a neutral style for anything outside the four verdicts.
 */
export function VerdictBadge({ verdict }: { verdict: string }) {
  const key = verdict.trim().toLowerCase();
  const s = STYLES[key] ?? { label: verdict.trim().toUpperCase(), cls: "border-line-1 bg-bg-2 text-ink-1" };
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 font-mono text-[11px] uppercase tracking-[0.04em] ${s.cls}`}
    >
      <span aria-hidden className="size-1 rounded-full bg-current" />
      {s.label}
    </span>
  );
}
