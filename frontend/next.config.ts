import { createHash } from "node:crypto";

import type { NextConfig } from "next";

/*
 * Backend connection (see `.env.example`). Read when `next dev` starts and
 * when `next build` runs; src/lib/api/http.ts applies the same rule on the client.
 *
 *   NEXT_PUBLIC_API_URL       Public URL of the FastAPI app (without /api).
 *                             Production: the browser calls it directly (the backend's
 *                             CORS_ORIGINS must include this site).
 *                             Development: the proxy target when BACKEND_URL is unset.
 *   BACKEND_URL               Optional proxy target. The same-origin /api/* proxy is used
 *                             in development, and in production builds without
 *                             NEXT_PUBLIC_API_URL (e.g. Vercel preview deployments).
 *   BACKEND_PROXY_TIMEOUT_MS  Optional proxy timeout; AI explanations can be slow.
 */

const LOCAL_BACKEND_URL = "http://127.0.0.1:8000";
const DEFAULT_PROXY_TIMEOUT_MS = 130_000; // the backend allows Groq up to 120 s

function parseBackendUrl(name: string, raw: string | undefined): string | undefined {
  const value = raw?.trim();
  if (!value) return undefined;

  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error(`${name} must be an absolute URL, e.g. https://api.example.com (received "${value}").`);
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error(`${name} must use http or https (received "${url.protocol}").`);
  }
  if (url.search || url.hash) {
    throw new Error(`${name} must not contain a query string or fragment.`);
  }

  const normalized = `${url.origin}${url.pathname}`.replace(/\/+$/, "");
  if (normalized.endsWith("/api")) {
    throw new Error(`${name} must point to the FastAPI root, without the trailing /api (received "${value}").`);
  }
  return normalized;
}

function parseTimeout(raw: string | undefined): number {
  if (!raw?.trim()) return DEFAULT_PROXY_TIMEOUT_MS;
  const value = Number(raw);
  if (!Number.isInteger(value) || value <= 0) {
    throw new Error(`BACKEND_PROXY_TIMEOUT_MS must be a positive integer (received "${raw}").`);
  }
  return value;
}

const isProduction = process.env.NODE_ENV === "production";
const publicApiUrl = parseBackendUrl("NEXT_PUBLIC_API_URL", process.env.NEXT_PUBLIC_API_URL);
const backendUrl = parseBackendUrl("BACKEND_URL", process.env.BACKEND_URL);

/** Production builds with NEXT_PUBLIC_API_URL call the backend directly; everything else is proxied. */
const directApiUrl = isProduction ? publicApiUrl : undefined;
const proxyTarget = backendUrl ?? publicApiUrl ?? LOCAL_BACKEND_URL;

if (isProduction && !publicApiUrl && !backendUrl) {
  console.warn(
    `\n⚠ Neither NEXT_PUBLIC_API_URL nor BACKEND_URL is set; /api requests will be proxied to ${LOCAL_BACKEND_URL}.\n`,
  );
}

const nextConfig: NextConfig = {
  // Pin the project root to this folder, so the app builds identically on its
  // own or inside a monorepo next to backend/ (otherwise Next infers the root
  // from the nearest lockfile, which a root-level package.json would change).
  outputFileTracingRoot: __dirname,
  turbopack: { root: __dirname },
  env: {
    // Non-secret fingerprint of the active backend, so locally persisted query
    // caches are discarded when the app is pointed at another backend.
    NEXT_PUBLIC_BACKEND_FINGERPRINT: createHash("sha256")
      .update(directApiUrl ?? proxyTarget)
      .digest("hex")
      .slice(0, 12),
  },
  experimental: {
    proxyTimeout: parseTimeout(process.env.BACKEND_PROXY_TIMEOUT_MS),
  },
  async rewrites() {
    if (directApiUrl) return [];
    return [
      {
        // Same-origin `/api/*` calls are proxied server-side to FastAPI,
        // so the browser never makes a cross-origin (CORS) request.
        source: "/api/:path*",
        destination: `${proxyTarget}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
