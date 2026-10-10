/**
 * Runtime validation of untrusted JSON. Each schema is checked against its
 * hand-written contract in `@/types/api` via `satisfies`, so the two can never
 * drift apart silently.
 */

import { z } from "zod";

import {
  isRegionId,
  isUnitId,
  isVariableId,
  type RegionId,
  type UnitId,
  type VariableId,
} from "@/core/datasets/registry";
import {
  TREND_DIRECTIONS,
  type AnalysisResponse,
  type ExplanationResponse,
  type FastApiErrorBody,
  type RateLimitErrorBody,
} from "@/types/api";

const regionSchema = z.custom<RegionId>(isRegionId, { message: "Unknown region" });
const variableSchema = z.custom<VariableId>(isVariableId, { message: "Unknown variable" });
const unitSchema = z.custom<UnitId>(isUnitId, { message: "Unknown unit" });
const yearSchema = z.int().min(1).max(9999);

const periodSchema = z
  .object({ start: yearSchema, end: yearSchema })
  .refine((p) => p.start <= p.end, "period.start must be <= period.end");

const trendSchema = z.object({
  direction: z.enum(TREND_DIRECTIONS),
  sen_slope: z.number().min(-1).max(1),
  p_value: z.number().min(0).max(1),
  significant: z.boolean(),
});

export const analysisResponseSchema = z.object({
  region: regionSchema,
  variable: variableSchema,
  unit: unitSchema,
  period: periodSchema,
  annual_series: z
    .array(z.object({ year: yearSchema, value: z.number() }))
    .min(1),
  trend: trendSchema,
}) satisfies z.ZodType<AnalysisResponse>;

export const explanationResponseSchema = z.object({
  explanation: z.string().min(1),
}) satisfies z.ZodType<ExplanationResponse>;

export const rateLimitErrorSchema = z.object({
  code: z.literal("RATE_LIMIT_EXCEEDED"),
  message: z.string(),
  retry_after_seconds: z.number().positive(),
}) satisfies z.ZodType<RateLimitErrorBody>;

export const fastApiErrorSchema = z.object({
  detail: z.union([
    z.string(),
    z.array(
      z.object({
        loc: z.array(z.union([z.string(), z.number()])),
        msg: z.string(),
        type: z.string(),
      }),
    ),
  ]),
}) satisfies z.ZodType<FastApiErrorBody>;
