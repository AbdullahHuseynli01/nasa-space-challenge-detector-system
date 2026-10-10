"use client";

import { AnimatePresence, motion } from "framer-motion";
import { ChartSpline, Hourglass, MapPin, Table2 } from "lucide-react";
import { useState } from "react";

import { ClayCard, Eyebrow } from "@/components/ui/clay";
import { fadeUp } from "@/components/ui/motion";
import { Segmented } from "@/components/ui/segmented";
import { Skeleton } from "@/components/ui/skeleton";
import type { RegisteredDataset, RegisteredRegion, RegisteredVariable } from "@/core/datasets/registry";
import { formatBounds } from "@/core/regions/define";
import type { AnalysisResponse } from "@/types/api";

import { SeriesChart, SeriesTable } from "./series-chart";

type ViewMode = "chart" | "table";

interface SeriesCardProps {
  readonly analysis: AnalysisResponse;
  readonly dataset: RegisteredDataset;
  readonly variable: RegisteredVariable;
  readonly region: RegisteredRegion;
}

export function SeriesCard({ analysis, dataset, variable, region }: SeriesCardProps) {
  const [mode, setMode] = useState<ViewMode>("chart");
  const series = analysis.annual_series;
  const first = series[0];
  const latest = series.at(-1);

  return (
    <ClayCard className="flex h-full flex-col p-5 sm:p-7">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <Eyebrow>
            {region.label} · {analysis.period.start}–{analysis.period.end}
          </Eyebrow>
          <h2 className="mt-1 text-lg font-semibold tracking-tight text-ink">{variable.seriesLabel}</h2>
        </div>
        <Segmented
          label="View"
          size="sm"
          iconOnly
          value={mode}
          onChange={setMode}
          options={[
            { value: "chart", label: "Chart", icon: <ChartSpline className="size-4" aria-hidden /> },
            { value: "table", label: "Table", icon: <Table2 className="size-4" aria-hidden /> },
          ]}
        />
      </header>

      {first && latest && (
        <div className="mt-6 flex flex-wrap items-end gap-x-6 gap-y-3">
          <div>
            <p className="text-sm text-ink-muted">Latest · {latest.year}</p>
            <p className="mt-1 font-mono text-4xl font-semibold tracking-tight tabular-nums text-ink sm:text-5xl">
              {variable.formatValue(latest.value)}
            </p>
          </div>
          <dl className="flex flex-wrap gap-2 pb-1.5">
            <Pill label={`${first.year} baseline`} value={variable.formatValue(first.value)} />
            <Pill label="Complete years" value={String(series.length)} />
          </dl>
        </div>
      )}

      <div className="mt-6 flex flex-1 flex-col">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div key={mode} {...fadeUp} className="flex flex-1 flex-col">
            {mode === "chart" ? (
              <SeriesChart series={series} variable={variable} animationKey={`${analysis.region}-${analysis.variable}`} />
            ) : (
              <SeriesTable series={series} variable={variable} />
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      <p className="mt-5 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-xs text-ink-faint">
        <MapPin className="size-3.5 shrink-0" aria-hidden />
        {formatBounds(region.bounds)}
        <span aria-hidden>·</span>
        {dataset.source}
      </p>
    </ClayCard>
  );
}

function Pill({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="flex items-baseline gap-2 rounded-full bg-well px-3.5 py-1.5 shadow-well">
      <dt className="text-xs text-ink-faint">{label}</dt>
      <dd className="font-mono text-sm font-semibold tabular-nums text-ink">{value}</dd>
    </div>
  );
}

/** Loading placeholder; `notice` explains an unusually long wait (e.g. a sleeping server). */
export function SeriesCardSkeleton({ notice }: { readonly notice?: string }) {
  return (
    <ClayCard className="flex h-full flex-col gap-6 p-5 sm:p-7" aria-busy>
      <AnimatePresence>
        {notice && (
          <motion.p
            role="status"
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex items-start gap-3 rounded-[20px] bg-accent-soft px-4 py-3 text-sm text-ink-muted"
          >
            <Hourglass className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
            {notice}
          </motion.p>
        )}
      </AnimatePresence>
      <div className="space-y-2">
        <Skeleton className="h-3 w-36" />
        <Skeleton className="h-5 w-56 max-w-full" />
      </div>
      <Skeleton className="h-12 w-44" />
      <Skeleton className="h-[260px] flex-1 rounded-[20px] sm:h-[320px]" />
    </ClayCard>
  );
}
