import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  output: "export",
  poweredByHeader: false,
  images: { unoptimized: true },
  turbopack: { root: path.resolve(__dirname) },
  devIndicators: false,
};

export default nextConfig;
