import type { ValidationIssue } from "@/types/api";

export type ApiErrorKind =
  /** HTTP 429 from the backend, or blocked locally by the rate-limit gate. */
  | "rate_limited"
  /** HTTP 400: e.g. unsupported region. */
  | "bad_request"
  /** HTTP 422: payload rejected by Pydantic or not enough observations. */
  | "validation"
  /** HTTP 502: the AI provider produced an unusable explanation. */
  | "upstream"
  /** HTTP 503: AI explanations are not configured on the server. */
  | "unavailable"
  /** Other 5xx responses. */
  | "server"
  /** The backend could not be reached (proxy failure, offline). */
  | "network"
  /** The response did not match the expected schema. */
  | "invalid_response"
  /** The request was not sent because the payload failed local validation. */
  | "invalid_payload";

export class ApiError extends Error {
  constructor(
    readonly kind: ApiErrorKind,
    message: string,
    readonly status: number | null = null,
    readonly issues: readonly ValidationIssue[] = [],
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export class RateLimitError extends ApiError {
  /** Epoch milliseconds after which a retry is allowed. */
  readonly retryAt: number;

  constructor(message: string, readonly retryAfterSeconds: number) {
    super("rate_limited", message, 429);
    this.name = "RateLimitError";
    this.retryAt = Date.now() + retryAfterSeconds * 1000;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export function isRateLimitError(error: unknown): error is RateLimitError {
  return error instanceof RateLimitError;
}
