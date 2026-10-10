import type { RegionId, VariableId } from "@/core/datasets/registry";

/** Root scope; everything under it is eligible for local persistence. */
export const QUERY_SCOPE = "nasa";

export type AnalysisQueryKey = readonly [typeof QUERY_SCOPE, "analysis", RegionId, VariableId];
export type InsightQueryKey = readonly [typeof QUERY_SCOPE, "insight", RegionId, VariableId, number, number];

export const queryKeys = {
  analysis: (region: RegionId, variable: VariableId): AnalysisQueryKey => [QUERY_SCOPE, "analysis", region, variable],

  /**
   * AI insights are indexed by `[region, variable, startYear, endYear]`, so
   * switching tabs restores a previously generated explanation instantly.
   */
  insight: (region: RegionId, variable: VariableId, startYear: number, endYear: number): InsightQueryKey => [
    QUERY_SCOPE,
    "insight",
    region,
    variable,
    startYear,
    endYear,
  ],
};
