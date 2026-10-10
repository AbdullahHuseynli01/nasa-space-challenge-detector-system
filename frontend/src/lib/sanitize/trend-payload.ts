import {
  SIGNIFICANCE_ALPHA,
  type AnalysisResponse,
  type ExplanationRequest,
  type TrendResult,
} from "@/types/api";

import { sanitizeFloat, type SignConstraint } from "./sanitize-float";

export class TrendPayloadError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "TrendPayloadError";
  }
}

const SLOPE_SIGN: Partial<Record<TrendResult["direction"], SignConstraint>> = {
  increasing: "positive",
  decreasing: "negative",
};

/**
 * Normalise a trend so it serialises without exponent notation while keeping
 * every invariant the backend's `TrendResult.validate_consistency` enforces.
 */
function sanitizeTrend(trend: TrendResult): TrendResult {
  const sanitized: TrendResult = {
    direction: trend.direction,
    significant: trend.significant,
    // Truncation keeps `p_value < 0.05` exactly as it was.
    p_value: sanitizeFloat(trend.p_value, { mode: "trunc", min: 0, max: 1 }),
    // A significant decreasing trend must stay strictly negative (and vice versa).
    sen_slope: sanitizeFloat(trend.sen_slope, {
      mode: "round",
      min: -1,
      max: 1,
      sign: trend.significant ? SLOPE_SIGN[trend.direction] : undefined,
    }),
  };

  assertTrendConsistency(sanitized);
  return sanitized;
}

/**
 * Client-side mirror of the Pydantic validator. Failing here costs nothing;
 * failing on the server costs one request of a small rate-limited budget.
 */
function assertTrendConsistency(trend: TrendResult): void {
  const { direction, sen_slope, p_value, significant } = trend;

  if (significant !== p_value < SIGNIFICANCE_ALPHA) {
    throw new TrendPayloadError("significant must equal (p_value < 0.05).");
  }
  if (!significant) {
    if (direction !== "no_significant_trend") {
      throw new TrendPayloadError(
        "Non-significant results must use direction 'no_significant_trend'.",
      );
    }
    return;
  }
  if (direction === "no_significant_trend") {
    throw new TrendPayloadError(
      "Significant results must be classified as increasing or decreasing.",
    );
  }
  if (direction === "increasing" && sen_slope <= 0) {
    throw new TrendPayloadError("Increasing trends must have a positive sen_slope.");
  }
  if (direction === "decreasing" && sen_slope >= 0) {
    throw new TrendPayloadError("Decreasing trends must have a negative sen_slope.");
  }
}

export function buildExplanationRequest(analysis: AnalysisResponse): ExplanationRequest {
  return {
    region: analysis.region,
    variable: analysis.variable,
    period: { start: analysis.period.start, end: analysis.period.end },
    trend: sanitizeTrend(analysis.trend),
  };
}
