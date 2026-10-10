"use client";

import { useEffect, useState, useSyncExternalStore } from "react";

import { rateLimitGate, type RateLimitSnapshot } from "@/lib/api/rate-limit-gate";

const SERVER_SNAPSHOT: RateLimitSnapshot = { blockedUntil: 0, limit: null, remaining: null };

/** Live view of the request budget reported by the backend. */
export function useRateLimitBudget(): RateLimitSnapshot {
  return useSyncExternalStore(
    rateLimitGate.subscribe,
    rateLimitGate.getSnapshot,
    () => SERVER_SNAPSHOT,
  );
}

/** Seconds remaining until `target` (epoch ms), ticking once per second. */
export function useCountdown(target: number | null): number {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (target === null) return;
    const tick = (): void => setNow(Date.now());
    const id = window.setInterval(tick, 250);
    const first = window.setTimeout(tick, 0);
    return () => {
      window.clearInterval(id);
      window.clearTimeout(first);
    };
  }, [target]);

  return target === null ? 0 : Math.max(0, Math.ceil((target - now) / 1000));
}
