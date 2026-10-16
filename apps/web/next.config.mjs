import path from "node:path";
import { fileURLToPath } from "node:url";

if (process.env.NETLIFY && !process.env.API_PROXY) {
  throw new Error("API_PROXY must point to the public DeepSight API for a Netlify build.");
}
const api = process.env.API_PROXY || "http://127.0.0.1:8000";
if (process.env.NETLIFY && !api.startsWith("https://")) {
  throw new Error("API_PROXY must use HTTPS for a Netlify build.");
}
const root = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  outputFileTracingRoot: root,
  transpilePackages: ["@reown/appkit", "@reown/appkit-adapter-wagmi"],
  experimental: { proxyTimeout: 120000 },
  async rewrites() {
    return [{ source: "/v1/:path*", destination: `${api}/v1/:path*` }];
  },
};

export default nextConfig;
