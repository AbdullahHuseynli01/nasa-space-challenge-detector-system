"use client";

import { motion, type Variants } from "framer-motion";

import { EASE_OUT_EXPO } from "@/components/ui/motion";
import { cn } from "@/lib/cn";
import type { InsightToken, ParsedInsight } from "@/lib/insights/parse-insight";
import type { TrendDirection } from "@/types/api";

const TOKEN_CLASS: Readonly<Record<Exclude<InsightToken["kind"], "direction">, string>> = {
  text: "",
  number: "rounded-lg bg-surface px-1.5 py-0.5 font-mono text-[0.9em] font-medium text-ink shadow-clay-sm",
  significant: "font-semibold text-accent",
  not_significant: "font-semibold text-caution",
  entity: "font-semibold text-ink",
};

const DIRECTION_CLASS: Readonly<Record<TrendDirection, string>> = {
  increasing: "font-semibold text-rise",
  decreasing: "font-semibold text-fall",
  no_significant_trend: "font-semibold text-ink",
};

const reveal: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.16 } },
};

const sentence: Variants = {
  hidden: { opacity: 0, y: 10, filter: "blur(4px)" },
  show: { opacity: 1, y: 0, filter: "blur(0px)", transition: { duration: 0.5, ease: EASE_OUT_EXPO } },
};

interface InsightTextProps {
  readonly insight: ParsedInsight;
  readonly direction: TrendDirection;
}

/** Reveals parsed sentences one by one; the first one leads. */
export function InsightText({ insight, direction }: InsightTextProps) {
  return (
    <motion.div variants={reveal} initial="hidden" animate="show" className="space-y-3">
      {insight.sentences.map((tokens, index) => (
        <motion.p
          key={index}
          variants={sentence}
          className={cn(
            "leading-[1.75] text-pretty",
            index === 0 ? "text-[15px] text-ink sm:text-base" : "text-sm text-ink-muted",
          )}
        >
          {tokens.map((token, i) =>
            token.kind === "text" ? (
              token.text
            ) : (
              <span
                key={i}
                className={token.kind === "direction" ? DIRECTION_CLASS[direction] : TOKEN_CLASS[token.kind]}
              >
                {token.text}
              </span>
            ),
          )}
        </motion.p>
      ))}
    </motion.div>
  );
}
