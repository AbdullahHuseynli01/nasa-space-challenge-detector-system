"use client";

import { Segmented, type SegmentOption } from "@/components/ui/segmented";
import {
  DATASET_REGISTRY,
  type DatasetId,
  type DatasetSelection,
  type RegionId,
  type VariableId,
} from "@/core/datasets/registry";
import type { SelectionPatch } from "@/hooks/use-dashboard-selection";

interface SelectorProps {
  readonly selection: DatasetSelection;
  readonly onSelect: (patch: SelectionPatch) => void;
}

/** Every registry entry becomes a tab; planned datasets render disabled. */
export function DatasetSelector({ selection, onSelect }: SelectorProps) {
  const options: SegmentOption<DatasetId>[] = DATASET_REGISTRY.map((dataset) => {
    const Icon = dataset.icon;
    const planned = dataset.status === "planned";
    return {
      value: dataset.id,
      label: dataset.label,
      icon: <Icon className="size-4" aria-hidden />,
      disabled: planned,
      title: planned ? `${dataset.label}: coming soon` : dataset.description,
      hint: planned ? <span className="text-[10px] font-medium text-ink-faint">soon</span> : undefined,
    };
  });

  return (
    // Scrolls sideways on narrow screens (fading at the edge to hint at more);
    // the padding keeps the clay shadow from being clipped.
    <div className="-m-2 min-w-0 overflow-x-auto p-2 [mask-image:linear-gradient(to_right,black_82%,transparent)] [scrollbar-width:none] lg:[mask-image:none]">
      <Segmented
        label="Dataset"
        options={options}
        value={selection.dataset.id}
        onChange={(dataset) => onSelect({ dataset })}
      />
    </div>
  );
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
