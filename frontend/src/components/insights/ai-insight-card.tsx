"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Clock, RefreshCw, ShieldCheck, Sparkles, TriangleAlert } from "lucide-react";
import { useMemo } from "react";

import { ErrorState } from "@/components/feedback/error-state";
import { ClayBlob, ClayCard, ClayWell } from "@/components/ui/clay";
import { ClayButton } from "@/components/ui/clay-button";
import { fadeUp } from "@/components/ui/motion";
import { Skeleton } from "@/components/ui/skeleton";
import type { DatasetSelection } from "@/core/datasets/registry";
import { useAiInsight } from "@/hooks/use-dashboard-queries";
import { useCountdown, useRateLimitBudget } from "@/hooks/use-rate-limit";
import { isRateLimitError } from "@/lib/api/errors";
import { cn } from "@/lib/cn";
import { formatCountdown, formatRelativeTime } from "@/lib/format";
import { parseInsight } from "@/lib/insights/parse-insight";
import type { AnalysisResponse } from "@/types/api";

import { InsightText } from "./insight-text";

interface AiInsightCardProps {
  readonly selection: DatasetSelection;
  /** Undefined while the analysis is loading or failed. */
  readonly analysis: AnalysisResponse | undefined;
}

type View = "waiting" | "loading" | "ready" | "error";

export function AiInsightCard({ selection, analysis }: AiInsightCardProps) {
  const { data, error, isFetching, dataUpdatedAt, refetch } = useAiInsight(selection, analysis);

  const { blockedUntil } = useRateLimitBudget();
  const blockedFor = useCountdown(blockedUntil > 0 ? blockedUntil : null);

  const view: View = !analysis ? "waiting" : data ? "ready" : isFetching ? "loading" : error ? "error" : "waiting";

  const parsed = useMemo(() => {
    if (!data) return null;
    return parseInsight(data.explanation, {
      // The variable id ("sea_ice_fraction") also matches prose like "sea ice fraction".
      entities: [
        selection.region.label,
        selection.variable.label,
        selection.variable.shortLabel,
        selection.variable.id,
      ],
    });
  }, [data, selection]);

  const mismatch =
    parsed && analysis && parsed.significance !== "unknown"
      ? (parsed.significance === "significant") !== analysis.trend.significant
      : false;

  // dataUpdatedAt makes a regenerated explanation replay its reveal.
  const stateKey = `${view}:${selection.region.id}:${selection.variable.id}:${dataUpdatedAt}`;

  return (
    <ClayCard className="relative p-5 sm:p-7">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex min-w-[min(100%,13rem)] flex-1 items-center gap-3">
          <span className="relative inline-flex">
            {/* Soft breathing halo while a request is in flight. */}
            <AnimatePresence>
              {isFetching && (
                <motion.span
                  aria-hidden
                  className="absolute inset-0 rounded-2xl bg-accent"
                  initial={{ opacity: 0, scale: 1 }}
                  animate={{ opacity: [0.35, 0, 0.35], scale: [1, 1.45, 1] }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
                />
              )}
            </AnimatePresence>
            <ClayBlob tone="accent" className="relative">
              <motion.span
                animate={isFetching ? { rotate: [0, 14, -14, 0] } : { rotate: 0 }}
                transition={isFetching ? { duration: 1.6, repeat: Infinity, ease: "easeInOut" } : { duration: 0.3 }}
                className="inline-flex"
              >
                <Sparkles className="size-5" aria-hidden />
              </motion.span>
            </ClayBlob>
          </span>
          <div className="min-w-0">
            <h2 className="text-lg font-semibold tracking-tight text-ink">AI insight</h2>
            <p className="text-sm text-ink-muted">The calculated trend, in plain words</p>
          </div>
        </div>

        <ClayButton onClick={() => void refetch()} disabled={!analysis || isFetching || blockedFor > 0}>
          {blockedFor > 0 ? (
            <>
              <Clock className="size-4" aria-hidden />
              {formatCountdown(blockedFor)}
            </>
          ) : (
            <>
              <RefreshCw className={cn("size-4", isFetching && "animate-spin")} aria-hidden />
              {data ? "Regenerate" : "Generate"}
            </>
          )}
        </ClayButton>
      </header>

      <div className="mt-6" aria-live="polite" aria-busy={view === "loading"}>
        <AnimatePresence mode="wait" initial={false}>
          <motion.div key={stateKey} {...fadeUp}>
            {view === "waiting" && (
              <ClayWell className="px-5 py-6 text-sm text-ink-faint">
                The explanation appears once the trend analysis is ready.
              </ClayWell>
            )}

            {view === "loading" && <InsightSkeleton />}

            {view === "error" && <ErrorState error={error} onRetry={refetch} />}

            {view === "ready" && parsed && analysis && (
              <div className="space-y-4">
                <ClayWell className={cn("px-5 py-5 transition-opacity duration-300", isFetching && "opacity-60")}>
                  <InsightText insight={parsed} direction={analysis.trend.direction} />
                </ClayWell>

                {/* A failed regenerate keeps the previous explanation visible. */}
                {error && isRateLimitError(error) && <ErrorState error={error} onRetry={refetch} />}

                <footer className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-ink-faint">
                  <span title={new Date(dataUpdatedAt).toLocaleString()}>
                    Saved {formatRelativeTime(dataUpdatedAt)}
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <ShieldCheck className="size-3.5 shrink-0 text-rise" aria-hidden />
                    Explains Python-calculated results only
                  </span>
                  {mismatch && (
                    <span className="inline-flex items-center gap-1.5 text-caution">
                      <TriangleAlert className="size-3.5 shrink-0" aria-hidden />
                      Wording may not match the calculated significance
                    </span>
                  )}
                </footer>
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </ClayCard>
  );
}

function InsightSkeleton() {
  return (
    <ClayWell className="space-y-4 px-5 py-5">
      <div className="flex items-center gap-2 text-sm font-medium text-accent">
        Writing explanation
        <span className="flex gap-1" aria-hidden>
          {[0, 1, 2].map((i) => (
            <motion.span
              key={i}
              className="size-1.5 rounded-full bg-accent"
              animate={{ y: [0, -4, 0], opacity: [0.4, 1, 0.4] }}
              transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.15 }}
            />
          ))}
        </span>
      </div>
      <div className="space-y-2.5">
        <Skeleton className="h-3.5 w-full" />
        <Skeleton className="h-3.5 w-[90%]" />
        <Skeleton className="h-3.5 w-[60%]" />
      </div>
    </ClayWell>
  );
}
