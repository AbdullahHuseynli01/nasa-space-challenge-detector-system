import type { AnnualSeriesPoint } from "@/types/api";

/** Plot margins in px; the left one leaves room for y-axis labels. */
export const CHART_MARGIN = { top: 18, right: 18, bottom: 30, left: 48 } as const;

const MIN_HEIGHT = 230;
const MAX_MIN_HEIGHT = 400;
const MAX_FILL_HEIGHT = 600;

/** Smallest comfortable height for a width: compact on phones, taller on wide screens. */
export function minChartHeight(width: number): number {
  return Math.round(Math.min(MAX_MIN_HEIGHT, Math.max(MIN_HEIGHT, width * 0.4)));
}

/**
 * Height that fills the `available` space of a stretched card, but never
 * taller than about 4:3 so the line stays readable.
 */
export function chartHeight(width: number, available: number): number {
  const min = minChartHeight(width);
  const max = Math.max(min, Math.min(MAX_FILL_HEIGHT, width * 0.75));
  return Math.min(max, Math.max(min, available));
}

interface AxisTick {
  readonly value: number;
  /** Pixel position along the axis. */
  readonly position: number;
}

export interface SeriesGeometry {
  readonly x: (year: number) => number;
  readonly y: (value: number) => number;
  readonly linePath: string;
  readonly areaPath: string;
  readonly yTicks: readonly AxisTick[];
  /** Year ticks; `value` is the year. */
  readonly xTicks: readonly AxisTick[];
  /** Index of the point closest to a horizontal pixel offset. */
  readonly nearestIndex: (px: number) => number;
}

interface SeriesGeometryInput {
  /** Non-empty series, sorted by year. */
  readonly series: readonly AnnualSeriesPoint[];
  /** Fixed y-axis domain, or "auto" to fit the data with padding. */
  readonly domain: "auto" | readonly [min: number, max: number];
  readonly width: number;
  readonly height: number;
}

/** Scales, SVG paths and "nice" ticks for an annual line/area chart. */
export function buildSeriesGeometry({ series, domain, width, height }: SeriesGeometryInput): SeriesGeometry {
  const years = series.map((point) => point.year);
  const values = series.map((point) => point.value);
  const minYear = Math.min(...years);
  const maxYear = Math.max(...years);

  const [lo, hi] = domain === "auto" ? paddedExtent(Math.min(...values), Math.max(...values)) : domain;
  const step = niceStep((hi - lo) / 5);
  const domainMin = Math.floor(lo / step) * step;
  const domainMax = Math.ceil(hi / step) * step;

  const innerW = width - CHART_MARGIN.left - CHART_MARGIN.right;
  const innerH = height - CHART_MARGIN.top - CHART_MARGIN.bottom;
  const x = (year: number): number =>
    CHART_MARGIN.left + ((year - minYear) / Math.max(1, maxYear - minYear)) * innerW;
  const y = (value: number): number =>
    CHART_MARGIN.top + (1 - (value - domainMin) / (domainMax - domainMin || 1)) * innerH;

  const linePath = series
    .map((point, i) => `${i === 0 ? "M" : "L"}${x(point.year).toFixed(2)},${y(point.value).toFixed(2)}`)
    .join("");
  const baseline = (height - CHART_MARGIN.bottom).toFixed(2);
  const areaPath = `${linePath}L${x(maxYear).toFixed(2)},${baseline}L${x(minYear).toFixed(2)},${baseline}Z`;

  const yTicks: AxisTick[] = [];
  for (let tick = domainMin; tick <= domainMax + step / 2; tick += step) {
    const value = Number(tick.toFixed(10));
    yTicks.push({ value, position: y(value) });
  }

  const maxLabels = Math.max(2, Math.floor(innerW / 56));
  const yearStep = [1, 2, 5, 10, 20, 50].find((candidate) => (maxYear - minYear) / candidate <= maxLabels) ?? 50;
  const xTicks: AxisTick[] = [];
  for (let year = Math.ceil(minYear / yearStep) * yearStep; year <= maxYear; year += yearStep) {
    xTicks.push({ value: year, position: x(year) });
  }

  const nearestIndex = (px: number): number => {
    const year = minYear + ((px - CHART_MARGIN.left) / innerW) * (maxYear - minYear);
    let best = 0;
    series.forEach((point, i) => {
      if (Math.abs(point.year - year) < Math.abs((series[best]?.year ?? 0) - year)) best = i;
    });
    return best;
  };

  return { x, y, linePath, areaPath, yTicks, xTicks, nearestIndex };
}

function paddedExtent(min: number, max: number): readonly [number, number] {
  const pad = (max - min || Math.abs(max) || 1) * 0.12;
  return [min - pad, max + pad];
}

/** Round a raw step up to 1, 2 or 5 × 10ⁿ. */
function niceStep(raw: number): number {
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const normalized = raw / magnitude;
  const nice = [1, 2, 5, 10].find((candidate) => normalized <= candidate) ?? 10;
  return nice * magnitude;
}
