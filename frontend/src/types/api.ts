/**
 * Wire-level contracts mirroring `backend/app/models/schemas.py`.
 *
 * Every interface is generic over the region / variable / unit identifiers so
 * the same shapes serve every dataset in the registry. The defaults resolve to
 * the unions derived from the dataset registry, so most call sites never pass type
 * arguments.
 */

import type { RegionId, UnitId, VariableId } from "@/core/datasets/registry";

export const TREND_DIRECTIONS = [
  "increasing",
  "decreasing",
  "no_significant_trend",
] as const;

export type TrendDirection = (typeof TREND_DIRECTIONS)[number];

/** Significance level used by the backend (`significant == p_value < ALPHA`). */
export const SIGNIFICANCE_ALPHA = 0.05;

/** Inclusive calendar-year period. */
interface Period {
  readonly start: number;
  readonly end: number;
}

export interface TrendResult {
  readonly direction: TrendDirection;
  /** Theil–Sen slope in variable units per year, within [−1, 1]. */
  readonly sen_slope: number;
  /** Hamed–Rao modified Mann–Kendall p-value, within [0, 1]. */
  readonly p_value: number;
  readonly significant: boolean;
}

export interface AnnualSeriesPoint {
  readonly year: number;
  readonly value: number;
}

export interface AnalysisResponse<
  R extends string = RegionId,
  V extends string = VariableId,
  U extends string = UnitId,
> {
  readonly region: R;
  readonly variable: V;
  readonly unit: U;
  readonly period: Period;
  readonly annual_series: readonly AnnualSeriesPoint[];
  readonly trend: TrendResult;
}

export interface ExplanationRequest<
  R extends string = RegionId,
  V extends string = VariableId,
> {
  readonly region: R;
  readonly variable: V;
  readonly period: Period;
  readonly trend: TrendResult;
}

export interface ExplanationResponse {
  readonly explanation: string;
}

/** One entry of FastAPI's 422 `detail` array. */
export interface ValidationIssue {
  readonly loc: readonly (string | number)[];
  readonly msg: string;
  readonly type: string;
}

/** Body returned by FastAPI `HTTPException` and request-validation errors. */
export interface FastApiErrorBody {
  readonly detail: string | readonly ValidationIssue[];
}

/** Body returned by `RateLimitMiddleware` with HTTP 429. */
export interface RateLimitErrorBody {
  readonly code: "RATE_LIMIT_EXCEEDED";
  readonly message: string;
  readonly retry_after_seconds: number;
}
