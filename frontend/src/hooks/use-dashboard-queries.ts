"use client";

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { useCallback, useEffect, useRef } from "react";

import type { DatasetSelection } from "@/core/datasets/registry";
import { analysisQueryOptions, insightQueryOptions } from "@/core/query/options";
import { isRateLimitError } from "@/lib/api/errors";
import type { AnalysisResponse, ExplanationResponse } from "@/types/api";

import { useCountdown } from "./use-rate-limit";

export function useAnalysis(selection: DatasetSelection): UseQueryResult<AnalysisResponse, Error> {
  return useQuery(analysisQueryOptions(selection));
}

export function useAiInsight(
  selection: DatasetSelection,
  analysis: AnalysisResponse | undefined,
): UseQueryResult<ExplanationResponse, Error> {
  return useQuery(insightQueryOptions(selection, analysis));
}

export interface RateLimitRecovery {
  /** Epoch ms when a retry is allowed, or null if not rate-limited. */
  readonly retryAt: number | null;
  readonly secondsLeft: number;
  /** Total length of the current wait, for progress indicators. */
  readonly totalSeconds: number;
}

/**
 * Watches a query error; when it is a 429, counts down and retries exactly
 * once when the window reopens.
 */
export function useRateLimitRecovery(error: unknown, retry: () => unknown): RateLimitRecovery {
  const rateLimit = isRateLimitError(error) ? error : null;
  const retryAt = rateLimit?.retryAt ?? null;
  const secondsLeft = useCountdown(retryAt);
  const retriedFor = useRef<number | null>(null);
  const stableRetry = useStableCallback(retry);

  useEffect(() => {
    if (retryAt === null || secondsLeft > 0) return;
    if (retriedFor.current === retryAt) return;
    retriedFor.current = retryAt;
    stableRetry();
  }, [retryAt, secondsLeft, stableRetry]);

  return {
    retryAt,
    secondsLeft,
    totalSeconds: rateLimit?.retryAfterSeconds ?? 0,
  };
}

function useStableCallback(callback: () => unknown): () => void {
  const ref = useRef(callback);
  useEffect(() => {
    ref.current = callback;
  });
  return useCallback(() => {
    ref.current();
  }, []);
}
