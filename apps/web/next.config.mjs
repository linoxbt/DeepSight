import path from "node:path";
import { fileURLToPath } from "node:url";

const api = process.env.API_PROXY || "http://127.0.0.1:8000";
const root = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  outputFileTracingRoot: root,
  transpilePackages: ["@reown/appkit", "@reown/appkit-adapter-wagmi"],
  async rewrites() {
    return [{ source: "/v1/:path*", destination: `${api}/v1/:path*` }];
  },
};

export default nextConfig;
