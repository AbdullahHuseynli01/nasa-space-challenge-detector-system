import type { RegionDefinition } from "@/core/regions/define";

import type { DatasetApiAdapter, DatasetDefinition, TrendMethodology, VariableStrategy } from "./types";

/** The shared FastAPI endpoints (backend/app/routes). */
const DEFAULT_API: DatasetApiAdapter = {
  analysisPath: "/api/analysis",
  explainPath: "/api/explain",
};

/** The backend's trend method (backend/app/services/trend_analysis.py). */
const DEFAULT_METHODOLOGY: TrendMethodology = {
  slopeLabel: "Sen's slope",
  testLabel: "Mann–Kendall (Hamed–Rao)",
  summary:
    "Trends use the Theil–Sen slope and the Hamed–Rao modified Mann–Kendall test, computed in Python on complete calendar years.",
};

/*
 * Identity helpers with `const` type parameters: they keep literal ids, so the
 * registry can derive exact DatasetId / VariableId / UnitId / RegionId unions.
 */

export function defineVariable<const TId extends string, const TUnit extends string>(
  variable: VariableStrategy<TId, TUnit>,
): VariableStrategy<TId, TUnit> {
  return variable;
}

type DatasetInput<
  TId extends string,
  TVariables extends readonly VariableStrategy[],
  TRegions extends readonly RegionDefinition[],
> = Omit<DatasetDefinition<TId, TVariables, TRegions>, "api" | "methodology"> & {
  /** Defaults to the shared analysis endpoints. */
  readonly api?: Partial<DatasetApiAdapter>;
  /** Defaults to the backend's Theil–Sen / Hamed–Rao method. */
  readonly methodology?: Partial<TrendMethodology>;
};

export function defineDataset<
  const TId extends string,
  const TVariables extends readonly VariableStrategy[],
  const TRegions extends readonly RegionDefinition[],
>(dataset: DatasetInput<TId, TVariables, TRegions>): DatasetDefinition<TId, TVariables, TRegions> {
  if (dataset.status === "available" && (dataset.variables.length === 0 || dataset.regions.length === 0)) {
    throw new Error(`Dataset "${dataset.id}" is available but has no variables or regions.`);
  }
  return {
    ...dataset,
    api: { ...DEFAULT_API, ...dataset.api },
    methodology: { ...DEFAULT_METHODOLOGY, ...dataset.methodology },
  };
}
