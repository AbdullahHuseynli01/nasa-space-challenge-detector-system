"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

import {
  resolveSelection,
  type DatasetSelection,
  type RegionId,
  type VariableId,
} from "@/core/datasets/registry";

export interface SelectionPatch {
  readonly variable?: VariableId;
  readonly region?: RegionId;
}

/**
 * The dashboard selection lives in the URL (`?dataset=&variable=&region=`) so
 * views are shareable and survive reloads. Untrusted params are resolved
 * through the registry, so invalid values silently fall back to defaults.
 */
export function useDashboardSelection(): readonly [
  DatasetSelection,
  (patch: SelectionPatch) => void,
] {
  const params = useSearchParams();

  const selection = useMemo(
    () =>
      resolveSelection({
        dataset: params.get("dataset"),
        variable: params.get("variable"),
        region: params.get("region"),
      }),
    [params],
  );

  const select = useCallback(
    (patch: SelectionPatch) => {
      const next = resolveSelection({
        dataset: selection.dataset.id,
        variable: patch.variable ?? selection.variable.id,
        region: patch.region ?? selection.region.id,
      });
      const search = new URLSearchParams({
        dataset: next.dataset.id,
        variable: next.variable.id,
        region: next.region.id,
      });
      // Native history updates are synced into useSearchParams by Next.js
      // without a server round-trip.
      window.history.replaceState(null, "", `?${search.toString()}`);
    },
    [selection],
  );

  return [selection, select] as const;
}
