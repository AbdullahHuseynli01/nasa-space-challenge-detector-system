"use client";

import { motion } from "framer-motion";

import { useRateLimitBudget } from "@/hooks/use-rate-limit";
import { cn } from "@/lib/cn";

const MAX_DOTS = 10;

/** Remaining backend requests (X-RateLimit-* headers), shown as clay beads. */
export function RequestBudget() {
  const { limit, remaining } = useRateLimitBudget();
  if (limit === null || remaining === null) return null;

  const label = `${remaining} of ${limit} requests left in this window`;
  return (
    <div
      className="flex h-11 items-center gap-2.5 rounded-2xl bg-surface px-3.5 shadow-clay-sm"
      title={label}
      aria-label={label}
      role="status"
    >
      {limit <= MAX_DOTS ? (
        <span className="flex items-center gap-1" aria-hidden>
          {Array.from({ length: limit }, (_, i) => (
            <motion.span
              key={i}
              layout
              className={cn(
                "size-2 rounded-full transition-colors duration-300",
                i < remaining ? "bg-accent shadow-[0_1px_2px_rgb(0_0_0/0.15)]" : "bg-well shadow-well",
              )}
            />
          ))}
        </span>
      ) : null}
      <span className={cn("text-xs font-semibold tabular-nums", remaining === 0 ? "text-caution" : "text-ink-muted")}>
        {remaining}/{limit}
      </span>
    </div>
  );
}
