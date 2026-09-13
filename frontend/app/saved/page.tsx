export default function SavedPage() {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3 text-center">
      <p className="font-mono text-xs uppercase tracking-[0.04em] text-ink-2">
        saved library
      </p>
      <p className="text-sm text-ink-1">
        Nothing saved yet — papers you mark as read or pin land here.
      </p>
    </div>
  );
}
