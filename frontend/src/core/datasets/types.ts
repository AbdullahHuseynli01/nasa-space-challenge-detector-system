import type { LucideIcon } from "lucide-react";

import type { RegionDefinition } from "@/core/regions/define";
import type { TrendDirection } from "@/types/api";

/**
 * Strategy object for one scientific variable. Everything that differs between
 * variables (formatting, units, chart scale, wording) lives here, so charts,
 * cards and API adapters stay variable-agnostic.
 */
export interface VariableStrategy<TId extends string = string, TUnit extends string = string> {
  /** Must match the backend `Variable` enum value. */
  readonly id: TId;
  /** Must match the backend `Unit` enum value. */
  readonly unit: TUnit;
  /** Unit as shown to people, e.g. "fraction", "ppm", "°C". */
  readonly unitLabel: string;
  readonly label: string;
  readonly shortLabel: string;
  readonly description: string;
  /** Title of the plotted series, e.g. "Annual mean sea-ice fraction". */
  readonly seriesLabel: string;
  /** Format one observation for display (tooltips, stats). */
  formatValue(value: number): string;
  /** Format an axis tick; may be terser than `formatValue`. */
  formatTick(value: number): string;
  /** Format a trend slope (units per year) as a human-readable rate. */
  formatRate(slopePerYear: number): string;
  /** Fixed y-axis domain, or "auto" to fit the data with padding. */
  readonly domain: "auto" | readonly [min: number, max: number];
  /** Headline wording for each trend direction, e.g. "Ice loss trend". */
  readonly trendLabels: Readonly<Record<TrendDirection, string>>;
}

/** How the backend computes the trend; shown beside the statistics. */
export interface TrendMethodology {
  /** Label of the slope statistic, e.g. "Sen's slope". */
  readonly slopeLabel: string;
  /** Label of the significance test, shown under the p-value. */
  readonly testLabel: string;
  /** One-sentence description of the whole method. */
  readonly summary: string;
}

/** Where a dataset's endpoints live. */
export interface DatasetApiAdapter {
  readonly analysisPath: string;
  readonly explainPath: string;
}

export interface DatasetDefinition<
  TId extends string = string,
  TVariables extends readonly VariableStrategy[] = readonly VariableStrategy[],
  TRegions extends readonly RegionDefinition[] = readonly RegionDefinition[],
> {
  readonly id: TId;
  readonly label: string;
  readonly description: string;
  readonly icon: LucideIcon;
  /** "planned" datasets appear in the selector but cannot be selected. */
  readonly status: "available" | "planned";
  /** Data provenance shown in the UI. */
  readonly source: string;
  readonly regions: TRegions;
  readonly variables: TVariables;
  readonly methodology: TrendMethodology;
  readonly api: DatasetApiAdapter;
}
