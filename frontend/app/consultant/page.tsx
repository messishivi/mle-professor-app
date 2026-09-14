import { Suspense } from "react";
import { ConsultantClient } from "@/components/consultant-client";

// No `dynamic = "force-dynamic"`: this page is fully client-rendered (the
// ConsultantClient does all fetching in the browser), so the P4 static export
// only prerenders this Suspense fallback shell. In Next 16 pages are dynamic
// by default, so the old flag was redundant.

function ConsultantFallback() {
  return (
    <div className="mx-auto flex w-full max-w-[860px] flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight text-ink-0">
        Consultant Terminal
      </h1>
      <p className="font-mono text-xs text-ink-2">loading…</p>
    </div>
  );
}

export default function ConsultantPage() {
  return (
    <Suspense fallback={<ConsultantFallback />}>
      <ConsultantClient />
    </Suspense>
  );
}
