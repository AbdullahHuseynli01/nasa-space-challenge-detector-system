"use client";

import { Segmented, type SegmentOption } from "@/components/ui/segmented";
import type { DatasetSelection, RegionId, VariableId } from "@/core/datasets/registry";
import type { SelectionPatch } from "@/hooks/use-dashboard-selection";

interface SelectorProps {
  readonly selection: DatasetSelection;
  readonly onSelect: (patch: SelectionPatch) => void;
}

export function VariableSelector({ selection, onSelect }: SelectorProps) {
  const options: SegmentOption<VariableId>[] = selection.dataset.variables.map((variable) => ({
    value: variable.id,
    label: variable.shortLabel,
    title: variable.description,
  }));

  return (
    <Segmented
      label="Variable"
      size="sm"
      options={options}
      value={selection.variable.id}
      onChange={(variable) => onSelect({ variable })}
    />
  );
}

/** Hidden for single-region datasets; the cards already name the region. */
export function RegionSwitcher({ selection, onSelect }: SelectorProps) {
  if (selection.dataset.regions.length < 2) return null;

  const options: SegmentOption<RegionId>[] = selection.dataset.regions.map((region) => ({
    value: region.id,
    label: region.label,
  }));

  return (
    <Segmented
      label="Region"
      fullWidth
      className="sm:inline-flex sm:w-auto"
      options={options}
      value={selection.region.id}
      onChange={(region) => onSelect({ region })}
    />
  );
}
