import type { NextConfig } from "next";

// P4 (hosting): the production image ships a *static export* of this app and
// serves it from the FastAPI process (single port, no Node runtime in prod).
// The export is opt-in via NEXT_EXPORT=1 so that `next dev` (used by the e2e
// suite and local dev) keeps its default server-rendered behavior unchanged.
// NEXT_PUBLIC_API_BASE is inlined at build time: the prod build sets it to
// "/api" (same-origin, API mounted under /api); dev leaves it unset and the
// lib falls back to http://127.0.0.1:8000.
const nextConfig: NextConfig = {
  // Dev server is canonically bound to localhost; allow loopback access via
  // 127.0.0.1 too (e2e tests and local tooling connect through 127.0.0.1).
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  output: process.env.NEXT_EXPORT === "1" ? "export" : undefined,
};

export default nextConfig;
