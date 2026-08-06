import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output: self-contained server build with no node_modules
  // dependency — required for the Render/container deployment (Sprint 14)
  // and trims the image size dramatically.
  output: "standalone",
};

export default nextConfig;
