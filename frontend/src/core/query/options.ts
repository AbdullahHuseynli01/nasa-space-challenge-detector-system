import { skipToken, type UseQueryOptions } from "@tanstack/react-query";

import type { DatasetSelection } from "@/core/datasets/registry";
import { fetchAnalysis, fetchExplanation } from "@/lib/api/endpoints";
import type { AnalysisResponse, ExplanationResponse } from "@/types/api";

import { queryKeys, type AnalysisQueryKey, type InsightQueryKey } from "./keys";

/*
 * Neither query consumes the AbortSignal on purpose: if the user switches
 * tabs mid-request, the request still completes and lands in the cache
 * instead of being thrown away after it has already used rate-limit budget.
 */

export function analysisQueryOptions(
  selection: DatasetSelection,
): UseQueryOptions<AnalysisResponse, Error, AnalysisResponse, AnalysisQueryKey> {
  return {
    queryKey: queryKeys.analysis(selection.region.id, selection.variable.id),
    queryFn: () => fetchAnalysis(selection),
  };
}

export function insightQueryOptions(
  selection: DatasetSelection,
  analysis: AnalysisResponse | undefined,
): UseQueryOptions<ExplanationResponse, Error, ExplanationResponse, InsightQueryKey> {
  return {
    queryKey: queryKeys.insight(
      selection.region.id,
      selection.variable.id,
      analysis?.period.start ?? 0,
      analysis?.period.end ?? 0,
    ),
    // Disabled until the analysis it explains has loaded.
    queryFn: analysis ? () => fetchExplanation(selection, analysis) : skipToken,
  };
}
