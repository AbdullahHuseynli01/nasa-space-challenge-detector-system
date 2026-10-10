"use client";

import { motion } from "framer-motion";
import { useId, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";

import type { RegisteredVariable } from "@/core/datasets/registry";
import { useElementSize } from "@/hooks/use-element-size";
import { buildSeriesGeometry, CHART_MARGIN, chartHeight, minChartHeight } from "@/lib/charts/series-geometry";
import type { AnnualSeriesPoint } from "@/types/api";

interface SeriesChartProps {
  readonly series: readonly AnnualSeriesPoint[];
  readonly variable: RegisteredVariable;
  /** Changing this replays the draw-in animation (e.g. on region switch). */
  readonly animationKey: string;
}

export function SeriesChart({ series, variable, animationKey }: SeriesChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { width, height: available } = useElementSize(containerRef);
  const gradientId = useId();
  const [active, setActive] = useState<number | null>(null);

  const minHeight = width > 0 ? minChartHeight(width) : 280;
  const height = width > 0 ? chartHeight(width, available) : minHeight;

  const geometry = useMemo(
    () =>
      width > 0 && series.length > 0
        ? buildSeriesGeometry({ series, domain: variable.domain, width, height })
        : null,
    [series, variable.domain, width, height],
  );

  const activePoint = active === null ? undefined : series[active];
  const first = series[0];
  const latest = series.at(-1);

  const onPointerMove = (event: PointerEvent<SVGSVGElement>) => {
    if (!geometry) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    setActive(geometry.nearestIndex(event.clientX - bounds.left));
  };

  const onKeyDown = (event: KeyboardEvent<SVGSVGElement>) => {
    const last = series.length - 1;
    const moves: Record<string, number> = {
      ArrowLeft: Math.max(0, (active ?? last + 1) - 1),
      ArrowRight: Math.min(last, (active ?? -1) + 1),
      Home: 0,
      End: last,
    };
    if (event.key === "Escape") setActive(null);
    else if (event.key in moves) {
      event.preventDefault();
      setActive(moves[event.key] ?? null);
    }
  };

  return (
    // flex-1 lets the chart grow into a stretched card; the SVG is absolutely
    // positioned so it never props the container open (which would block shrinking).
    <div ref={containerRef} className="relative w-full flex-1" style={{ minHeight }}>
      {geometry && first && latest && (
        <>
          <svg
            width={width}
            height={height}
            role="img"
            tabIndex={0}
            aria-label={`${variable.seriesLabel}, ${first.year}–${latest.year}. Latest ${variable.formatValue(latest.value)} in ${latest.year}. Use arrow keys to inspect years.`}
            className="absolute left-0 top-0 cursor-crosshair touch-none rounded-2xl outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
            onPointerMove={onPointerMove}
            onPointerLeave={() => setActive(null)}
            onKeyDown={onKeyDown}
            onBlur={() => setActive(null)}
          >
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--series)" stopOpacity={0.22} />
                <stop offset="100%" stopColor="var(--series)" stopOpacity={0} />
              </linearGradient>
            </defs>

            {geometry.yTicks.map((tick) => (
              <g key={tick.value}>
                <line
                  x1={CHART_MARGIN.left}
                  x2={width - CHART_MARGIN.right}
                  y1={tick.position}
                  y2={tick.position}
                  stroke="var(--ink-faint)"
                  strokeOpacity={0.18}
                  strokeDasharray="2 6"
                  strokeLinecap="round"
                />
                <text
                  x={CHART_MARGIN.left - 12}
                  y={tick.position}
                  dy="0.32em"
                  textAnchor="end"
                  className="fill-ink-faint font-mono text-[11px] tabular-nums"
                >
                  {variable.formatTick(tick.value)}
                </text>
              </g>
            ))}
            {geometry.xTicks.map((tick) => (
              <text
                key={tick.value}
                x={tick.position}
                y={height - 6}
                textAnchor="middle"
                className="fill-ink-faint font-mono text-[11px] tabular-nums"
              >
                {tick.value}
              </text>
            ))}

            <motion.path
              key={`area-${animationKey}`}
              d={geometry.areaPath}
              fill={`url(#${gradientId})`}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.8, delay: 0.35 }}
            />
            <motion.path
              key={`line-${animationKey}`}
              d={geometry.linePath}
              fill="none"
              stroke="var(--series)"
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1] }}
            />

            {activePoint && (
              <line
                x1={geometry.x(activePoint.year)}
                x2={geometry.x(activePoint.year)}
                y1={CHART_MARGIN.top}
                y2={height - CHART_MARGIN.bottom}
                stroke="var(--ink-faint)"
                strokeOpacity={0.45}
                strokeDasharray="3 4"
                pointerEvents="none"
              />
            )}

            {/* Latest observation, and the hovered one, as raised clay beads. */}
            {[latest, activePoint].map((point, index) =>
              point ? (
                <g key={index} pointerEvents="none">
                  <circle cx={geometry.x(point.year)} cy={geometry.y(point.value)} r={7} fill="var(--surface)" />
                  <circle cx={geometry.x(point.year)} cy={geometry.y(point.value)} r={4.5} fill="var(--series)" />
                </g>
              ) : null,
            )}
          </svg>

          {activePoint && (
            <ChartTooltip
              x={geometry.x(activePoint.year)}
              y={geometry.y(activePoint.value)}
              width={width}
              year={activePoint.year}
              value={variable.formatValue(activePoint.value)}
              label={variable.shortLabel}
            />
          )}
        </>
      )}
    </div>
  );
}

function ChartTooltip({
  x,
  y,
  width,
  year,
  value,
  label,
}: {
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly year: number;
  readonly value: string;
  readonly label: string;
}) {
  const flip = x > width - 170;
  return (
    <div
      role="status"
      className="pointer-events-none absolute z-10 whitespace-nowrap rounded-2xl bg-surface px-3.5 py-2.5 shadow-clay"
      style={{
        left: x,
        top: Math.max(0, y - 70),
        transform: `translateX(${flip ? "calc(-100% - 16px)" : "16px"})`,
      }}
    >
      <p className="text-[11px] font-medium text-ink-faint">{year}</p>
      <p className="mt-0.5 text-sm">
        <span className="font-mono font-semibold tabular-nums text-ink">{value}</span>{" "}
        <span className="text-ink-muted">{label}</span>
      </p>
    </div>
  );
}

export function SeriesTable({
  series,
  variable,
}: {
  readonly series: readonly AnnualSeriesPoint[];
  readonly variable: RegisteredVariable;
}) {
  return (
    <div className="relative min-h-[300px] flex-1 sm:min-h-[340px]">
      <div className="absolute inset-0 overflow-y-auto rounded-[20px] bg-well shadow-well [scrollbar-width:thin]">
        <table className="w-full text-sm">
          <caption className="sr-only">{variable.seriesLabel} by year</caption>
          <thead className="sticky top-0 bg-well/95 text-left text-[11px] uppercase tracking-[0.12em] text-ink-faint backdrop-blur">
            <tr>
              <th scope="col" className="px-5 py-3 font-semibold">Year</th>
              <th scope="col" className="px-5 py-3 text-right font-semibold">{variable.shortLabel}</th>
            </tr>
          </thead>
          <tbody className="font-mono tabular-nums">
            {[...series].reverse().map((point) => (
              <tr key={point.year} className="transition-colors hover:bg-surface/60">
                <td className="px-5 py-2 text-ink-muted">{point.year}</td>
                <td className="px-5 py-2 text-right text-ink">{variable.formatValue(point.value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
