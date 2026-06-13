import type { NextConfig } from "next";

// Same-origin proxy: the browser calls /api/v1/* and Next forwards to the FastAPI backend.
// Avoids CORS and keeps the X-User-Id dev-auth header flow simple. Override the backend
// origin with BACKEND_ORIGIN (defaults to the documented local uvicorn port).
const BACKEND_ORIGIN = process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/api/v1/:path*", destination: `${BACKEND_ORIGIN}/api/v1/:path*` },
    ];
  },
};

export default nextConfig;
