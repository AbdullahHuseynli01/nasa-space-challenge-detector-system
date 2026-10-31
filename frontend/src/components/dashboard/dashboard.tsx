"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Satellite } from "lucide-react";

import { ErrorState } from "@/components/feedback/error-state";
import { AiInsightCard } from "@/components/insights/ai-insight-card";
import { ClayBlob, ClayCard } from "@/components/ui/clay";
import { fadeUp, rise, stagger } from "@/components/ui/motion";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { useAnalysis } from "@/hooks/use-dashboard-queries";
import { useDashboardSelection } from "@/hooks/use-dashboard-selection";
import { useDelayedFlag } from "@/hooks/use-delayed-flag";
import { useHydrated } from "@/hooks/use-hydrated";

import { RequestBudget } from "./request-budget";
import { RegionSwitcher, VariableSelector } from "./selectors";
import { SeriesCard, SeriesCardSkeleton } from "./series-card";
import { TrendCard, TrendCardSkeleton } from "./trend-card";

/** How long the first load may take before we explain that the server is waking up. */
const SLOW_LOAD_NOTICE_MS = 5000;

export function Dashboard() {
  const [selection, select] = useDashboardSelection();
  const analysis = useAnalysis(selection);
  // Cache restored from localStorage must not leak into the hydration render.
  const hydrated = useHydrated();
  const data = hydrated ? analysis.data : undefined;
  const failed = hydrated && analysis.isError;
  // Free hosting (e.g. Render) sleeps when idle, so a first request can take ~50 s.
  const slowLoad = useDelayedFlag(hydrated && analysis.isFetching && !analysis.data, SLOW_LOAD_NOTICE_MS);

  const viewKey = `${selection.dataset.id}:${selection.variable.id}:${selection.region.id}:${
    failed ? "error" : data ? "ready" : "loading"
  }`;

  return (
    <motion.main
      variants={stagger}
      initial="hidden"
      animate="show"
      className="mx-auto flex w-full max-w-[1440px] flex-col gap-6 px-4 py-5 sm:gap-8 sm:px-6 sm:py-8 lg:px-10 min-[2000px]:max-w-[1760px]"
    >
      {/* Top bar */}
      <motion.nav variants={rise} className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <ClayBlob tone="accent" size="md">
            <Satellite className="size-5" aria-hidden />
          </ClayBlob>
          <div className="min-w-0 leading-tight">
            <p className="truncate text-sm font-bold text-ink">NASA Open Data</p>
            <p className="truncate text-xs text-ink-faint">Environmental Analytics</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <RequestBudget />
          <ThemeToggle />
        </div>
      </motion.nav>

      {/* Hero */}
      <motion.header variants={rise} className="max-w-3xl pt-2 sm:pt-6">
        <h1 className="text-[clamp(2rem,4.5vw+0.5rem,3.5rem)] leading-[1.05] font-bold tracking-tight text-balance text-ink">
          {selection.dataset.label}, <span className="text-ink-faint">at a glance.</span>
        </h1>
        <p className="mt-3 max-w-2xl text-base text-ink-muted sm:text-lg">{selection.dataset.description}</p>
      </motion.header>

      {/* Controls: stack on mobile, one row from `sm` */}
      <motion.div variants={rise} className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        {selection.dataset.variables.length > 1 && <VariableSelector selection={selection} onSelect={select} />}
        <RegionSwitcher selection={selection} onSelect={select} />
      </motion.div>

      {/*
        Mobile: chart → trend → AI, stacked.
        lg: chart full width, trend and AI side by side below it.
        xl+: chart on the left (stretches to the row height); trend and AI beside it.
      */}
      <div className="grid grid-cols-1 gap-6 lg:gap-8 xl:grid-cols-12">
        <motion.div variants={rise} className="min-w-0 xl:col-span-7 2xl:col-span-8">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div key={viewKey} {...fadeUp} className="h-full">
              {failed ? (
                <ClayCard className="p-5 sm:p-7">
                  <ErrorState error={analysis.error} onRetry={analysis.refetch} />
                </ClayCard>
              ) : data ? (
                <SeriesCard
                  analysis={data}
                  dataset={selection.dataset}
                  variable={selection.variable}
                  region={selection.region}
                />
              ) : (
                <SeriesCardSkeleton
                  notice={
                    slowLoad
                      ? "Waking up the analysis server. Free hosting sleeps when idle, so the first load can take up to a minute."
                      : undefined
                  }
                />
              )}
            </motion.div>
          </AnimatePresence>
        </motion.div>

        <motion.div
          variants={rise}
          className="grid min-w-0 grid-cols-1 content-start gap-6 lg:grid-cols-2 lg:gap-8 xl:col-span-5 xl:grid-cols-1 2xl:col-span-4"
        >
          <AnimatePresence mode="wait" initial={false}>
            {!failed && (
              <motion.div key={viewKey} {...fadeUp}>
                {data ? (
                  <TrendCard
                    trend={data.trend}
                    variable={selection.variable}
                    methodology={selection.dataset.methodology}
                  />
                ) : (
                  <TrendCardSkeleton />
                )}
              </motion.div>
            )}
          </AnimatePresence>
          <AiInsightCard selection={selection} analysis={data} />
        </motion.div>
      </div>

      <motion.footer variants={rise} className="pb-4 pt-2 text-center text-xs text-ink-faint">
        AI explanations only describe the calculated results; they never compute statistics.
      </motion.footer>
    </motion.main>
  );
}
