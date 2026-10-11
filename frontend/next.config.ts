import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactCompiler: true,
  async rewrites() {
    const apiTarget = (process.env.API_PROXY_TARGET || "http://127.0.0.1:8081").replace(/\/$/, "");
    return [{ source: "/api/:path*", destination: `${apiTarget}/api/:path*` }];
  },
};

export default nextConfig;
