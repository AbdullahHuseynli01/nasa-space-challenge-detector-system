import type { z } from "zod";

import { ApiError, RateLimitError, type ApiErrorKind } from "./errors";
import { rateLimitGate } from "./rate-limit-gate";
import { fastApiErrorSchema, rateLimitErrorSchema } from "./schemas";

/**
 * Where API requests go. Both values are inlined at build time, and
 * next.config.ts applies the same rule to decide whether to proxy.
 *
 * - Development: "" — same-origin `/api/*`, proxied to the backend by the
 *   rewrite in next.config.ts, so CORS never applies locally.
 * - Production: NEXT_PUBLIC_API_URL when set — the browser calls the backend
 *   directly (its CORS_ORIGINS must include this site). Otherwise "" — the
 *   proxy, e.g. for preview deployments.
 */
const API_BASE_URL: string =
  process.env.NODE_ENV === "production" ? (process.env.NEXT_PUBLIC_API_URL ?? "").trim().replace(/\/+$/, "") : "";

const DEFAULT_RETRY_AFTER_SECONDS = 60;

type QueryValue = string | number | boolean;

export interface RequestOptions<TSchema extends z.ZodType> {
  readonly schema: TSchema;
  readonly method?: "GET" | "POST";
  readonly query?: Readonly<Record<string, QueryValue | undefined>>;
  readonly body?: unknown;
}

export async function requestJson<TSchema extends z.ZodType>(
  path: string,
  { schema, method = "GET", query, body }: RequestOptions<TSchema>,
): Promise<z.output<TSchema>> {
  const blockedUntil = rateLimitGate.activeBlock();
  if (blockedUntil !== null) {
    throw new RateLimitError(
      "Request budget exhausted. Waiting for the rate-limit window to reset.",
      Math.ceil((blockedUntil - Date.now()) / 1000),
    );
  }

  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers: {
        Accept: "application/json",
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("network", "Unable to reach the analysis service.");
  }

  rateLimitGate.recordResponse(response.headers);
  const payload = await readJson(response);

  if (!response.ok) throw toApiError(response, payload);

  const parsed = schema.safeParse(payload);
  if (!parsed.success) {
    throw new ApiError(
      "invalid_response",
      `Unexpected response from ${path}: ${parsed.error.issues[0]?.message ?? "invalid shape"}`,
      response.status,
    );
  }
  return parsed.data;
}

function buildUrl(path: string, query: RequestOptions<z.ZodType>["query"]): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined) params.set(key, String(value));
  }
  const search = params.toString();
  return `${API_BASE_URL}${path}${search ? `?${search}` : ""}`;
}

const NOT_JSON = Symbol("not-json");

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    const parsed: unknown = JSON.parse(text);
    return parsed;
  } catch {
    return NOT_JSON;
  }
}

const STATUS_KIND: Readonly<Record<number, ApiErrorKind>> = {
  400: "bad_request",
  422: "validation",
  502: "upstream",
  503: "unavailable",
};

function toApiError(response: Response, payload: unknown): ApiError {
  const { status } = response;

  if (status === 429) {
    const body = rateLimitErrorSchema.safeParse(payload);
    const headerSeconds = Number.parseInt(response.headers.get("retry-after") ?? "", 10);
    const retryAfter = body.success
      ? body.data.retry_after_seconds
      : Number.isFinite(headerSeconds)
        ? headerSeconds
        : DEFAULT_RETRY_AFTER_SECONDS;
    const error = new RateLimitError(
      body.success ? body.data.message : "Too many requests. Please wait and try again.",
      retryAfter,
    );
    rateLimitGate.block(error.retryAt);
    return error;
  }

  // A non-JSON 5xx means the Next.js proxy could not reach FastAPI at all.
  if (payload === NOT_JSON && status >= 500) {
    return new ApiError(
      "network",
      "The analysis service is unreachable. Is the FastAPI backend running?",
      status,
    );
  }

  const kind = STATUS_KIND[status] ?? (status >= 500 ? "server" : "bad_request");
  const body = fastApiErrorSchema.safeParse(payload);
  if (!body.success) return new ApiError(kind, `Request failed with HTTP ${status}.`, status);

  const { detail } = body.data;
  return typeof detail === "string"
    ? new ApiError(kind, detail, status)
    : new ApiError(kind, detail[0]?.msg ?? "The request was rejected.", status, detail);
}
