"use client";

import { motion } from "framer-motion";
import { ArrowDownRight, ArrowUpRight, Minus, Sigma, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { ClayBlob, ClayCard, ClayWell, Eyebrow } from "@/components/ui/clay";
import { rise, stagger } from "@/components/ui/motion";
import { Skeleton } from "@/components/ui/skeleton";
import type { RegisteredVariable } from "@/core/datasets/registry";
import type { TrendMethodology } from "@/core/datasets/types";
import { cn } from "@/lib/cn";
import { formatFixed, formatPValue } from "@/lib/format";
import { SIGNIFICANCE_ALPHA, type TrendDirection, type TrendResult } from "@/types/api";

const DIRECTION: Readonly<Record<TrendDirection, { icon: LucideIcon; tone: "rise" | "fall" | "neutral" }>> = {
  increasing: { icon: ArrowUpRight, tone: "rise" },
  decreasing: { icon: ArrowDownRight, tone: "fall" },
  no_significant_trend: { icon: Minus, tone: "neutral" },
};

interface TrendCardProps {
  readonly trend: TrendResult;
  readonly variable: RegisteredVariable;
  readonly methodology: TrendMethodology;
}

export function TrendCard({ trend, variable, methodology }: TrendCardProps) {
  const { icon: Icon, tone } = DIRECTION[trend.direction];

  return (
    // Container queries: metrics sit in a row when the card is wide (tablet)
    // and stack in the narrow side column (desktop) or on phones.
    <ClayCard className="@container p-5 sm:p-7">
      <Eyebrow>Trend analysis</Eyebrow>

      <div className="mt-4 flex items-center gap-4">
        <motion.span
          initial={{ scale: 0.6, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: "spring", stiffness: 320, damping: 18, delay: 0.1 }}
          className="inline-flex"
        >
          <ClayBlob tone={tone} size="lg">
            <Icon className="size-6" strokeWidth={2.4} aria-hidden />
          </ClayBlob>
        </motion.span>
        <div className="min-w-0">
          <p className="text-lg font-semibold tracking-tight text-ink">{variable.trendLabels[trend.direction]}</p>
          <p className="font-mono text-sm tabular-nums text-ink-muted">{variable.formatRate(trend.sen_slope)}</p>
        </div>
      </div>

      <ClayWell className="mt-6 overflow-hidden">
        <motion.dl
          variants={stagger}
          initial="hidden"
          animate="show"
          className="grid grid-cols-1 divide-y divide-ink-faint/15 @xl:grid-cols-3 @xl:divide-x @xl:divide-y-0"
        >
          <Metric
            label={methodology.slopeLabel}
            value={formatFixed(trend.sen_slope, 6)}
            note={`${variable.unitLabel} / year`}
          />
          <Metric label="p-value" value={formatPValue(trend.p_value)} note={methodology.testLabel} />
          <Metric
            label="Significance"
            value={trend.significant ? "Significant" : "Not significant"}
            note={`α = ${SIGNIFICANCE_ALPHA}`}
            valueClassName={trend.significant ? "text-ink" : "text-ink-muted"}
          />
        </motion.dl>
      </ClayWell>

      <p className="mt-4 flex items-start gap-1.5 text-xs text-ink-faint">
        <Sigma className="mt-px size-3.5 shrink-0" aria-hidden />
        {methodology.summary}
      </p>
    </ClayCard>
  );
}

function Metric({
  label,
  value,
  note,
  valueClassName,
}: {
  readonly label: string;
  readonly value: string;
  readonly note: ReactNode;
  readonly valueClassName?: string;
}) {
  return (
    <motion.div variants={rise} className="px-5 py-4">
      <dt className="text-xs text-ink-faint">{label}</dt>
      <dd>
        <span className={cn("mt-1 block font-mono text-lg font-semibold tabular-nums text-ink", valueClassName)}>
          {value}
        </span>
        <span className="mt-0.5 block text-xs text-ink-faint">{note}</span>
      </dd>
    </motion.div>
  );
}

export function TrendCardSkeleton() {
  return (
    <ClayCard className="space-y-5 p-5 sm:p-7" aria-busy>
      <Skeleton className="h-3 w-28" />
      <div className="flex items-center gap-4">
        <Skeleton className="size-14 rounded-[20px]" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-4 w-28" />
        </div>
      </div>
      <Skeleton className="h-40 rounded-[20px]" />
    </ClayCard>
  );
}
