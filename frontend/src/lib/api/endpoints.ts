import type { DatasetSelection } from "@/core/datasets/registry";
import { buildExplanationRequest, TrendPayloadError } from "@/lib/sanitize/trend-payload";
import { SanitizeFloatError } from "@/lib/sanitize/sanitize-float";
import type { AnalysisResponse, ExplanationRequest, ExplanationResponse } from "@/types/api";

import { ApiError } from "./errors";
import { requestJson } from "./http";
import { analysisResponseSchema, explanationResponseSchema } from "./schemas";

/**
 * Dataset-agnostic API adapter. Paths come from the dataset's `api` adapter,
 * so a dataset served by a different endpoint needs no changes here.
 */

export async function fetchAnalysis(selection: DatasetSelection): Promise<AnalysisResponse> {
  const analysis = await requestJson(selection.dataset.api.analysisPath, {
    schema: analysisResponseSchema,
    // `variable` is ignored by today's backend and future-proofs multi-variable datasets.
    query: { region: selection.region.id, variable: selection.variable.id },
  });

  if (analysis.region !== selection.region.id || analysis.variable !== selection.variable.id) {
    throw new ApiError(
      "invalid_response",
      `Expected ${selection.region.id}/${selection.variable.id}, received ${analysis.region}/${analysis.variable}.`,
    );
  }
  return analysis;
}

export async function fetchExplanation(
  selection: DatasetSelection,
  analysis: AnalysisResponse,
): Promise<ExplanationResponse> {
  let payload: ExplanationRequest;
  try {
    payload = buildExplanationRequest(analysis);
  } catch (error) {
    if (error instanceof TrendPayloadError || error instanceof SanitizeFloatError) {
      throw new ApiError("invalid_payload", error.message);
    }
    throw error;
  }

  return requestJson(selection.dataset.api.explainPath, {
    method: "POST",
    schema: explanationResponseSchema,
    body: payload,
  });
}
