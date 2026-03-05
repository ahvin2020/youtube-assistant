import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow server-side file reading from parent workspace directory
  serverExternalPackages: [],
  // Suppress hydration warnings from emoji rendering differences
  reactStrictMode: true,
};

export default nextConfig;
