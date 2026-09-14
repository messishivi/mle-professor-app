import { Suspense } from "react";
import { ConsultantClient } from "@/components/consultant-client";

export const dynamic = "force-dynamic";

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
