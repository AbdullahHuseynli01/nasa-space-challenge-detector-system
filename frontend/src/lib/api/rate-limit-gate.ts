/**
 * Client-side mirror of the backend's sliding-window limiter (3 requests per
 * 5 minutes by default). Once the server answers 429, every further request is
 * short-circuited locally until `retry_after_seconds` has elapsed, so the UI
 * never burns requests that are guaranteed to fail.
 */

export interface RateLimitSnapshot {
  /** Epoch ms until which requests are blocked; 0 when not blocked. */
  readonly blockedUntil: number;
  /** From `X-RateLimit-Limit`, once a response has been seen. */
  readonly limit: number | null;
  /** From `X-RateLimit-Remaining`, once a response has been seen. */
  readonly remaining: number | null;
}

type Listener = () => void;

let snapshot: RateLimitSnapshot = { blockedUntil: 0, limit: null, remaining: null };
const listeners = new Set<Listener>();

function update(next: Partial<RateLimitSnapshot>): void {
  snapshot = { ...snapshot, ...next };
  listeners.forEach((listener) => listener());
}

function parseHeaderInt(headers: Headers, name: string): number | null {
  const raw = headers.get(name);
  if (raw === null) return null;
  const value = Number.parseInt(raw, 10);
  return Number.isFinite(value) ? value : null;
}

export const rateLimitGate = {
  getSnapshot: (): RateLimitSnapshot => snapshot,

  subscribe(listener: Listener): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },

  /** Epoch ms of the active block, or null when requests may be sent. */
  activeBlock(now = Date.now()): number | null {
    return snapshot.blockedUntil > now ? snapshot.blockedUntil : null;
  },

  block(retryAt: number): void {
    update({ blockedUntil: Math.max(snapshot.blockedUntil, retryAt), remaining: 0 });
  },

  recordResponse(headers: Headers): void {
    const limit = parseHeaderInt(headers, "x-ratelimit-limit");
    const remaining = parseHeaderInt(headers, "x-ratelimit-remaining");
    if (limit !== null || remaining !== null) {
      update({ limit: limit ?? snapshot.limit, remaining: remaining ?? snapshot.remaining });
    }
  },
};
