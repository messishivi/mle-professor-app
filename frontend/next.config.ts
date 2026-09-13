import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Dev server is canonically bound to localhost; allow loopback access via
  // 127.0.0.1 too (e2e tests and local tooling connect through 127.0.0.1).
  allowedDevOrigins: ["127.0.0.1", "localhost"],
};

export default nextConfig;
