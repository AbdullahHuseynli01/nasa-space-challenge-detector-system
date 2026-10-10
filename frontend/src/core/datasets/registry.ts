import type { RegionDefinition } from "@/core/regions/define";

import { co2Dataset, globalTemperatureDataset, vegetationDataset } from "./planned";
import { seaIceDataset } from "./sea-ice";
import type { DatasetDefinition, VariableStrategy } from "./types";

/**
 * The dataset registry: the one place a dataset is registered. Every id union
 * (dataset, variable, unit, region) and every lookup below derives from it, so
 * adding a dataset means defining it with `defineDataset(...)` and listing it here.
 */
export const DATASET_REGISTRY = [seaIceDataset, globalTemperatureDataset, co2Dataset, vegetationDataset] as const;

type RegistryEntry = (typeof DATASET_REGISTRY)[number];

export type DatasetId = RegistryEntry["id"];
export type VariableId = RegistryEntry["variables"][number]["id"];
export type UnitId = RegistryEntry["variables"][number]["unit"];
export type RegionId = RegistryEntry["regions"][number]["id"];

export type RegisteredVariable = VariableStrategy<VariableId, UnitId>;
export type RegisteredRegion = RegionDefinition<RegionId>;
export type RegisteredDataset = DatasetDefinition<
  DatasetId,
  readonly RegisteredVariable[],
  readonly RegisteredRegion[]
>;

/** The registry with element types widened, for uniform iteration. */
const datasets: readonly RegisteredDataset[] = DATASET_REGISTRY;

/** Index config objects by id. Two different objects sharing an id is a config error. */
function indexById<T extends { readonly id: string }>(items: readonly T[], kind: string): ReadonlyMap<string, T> {
  const index = new Map<string, T>();
  for (const item of items) {
    const existing = index.get(item.id);
    if (existing !== undefined && existing !== item) {
      throw new Error(`Duplicate ${kind} id "${item.id}" in the dataset registry; define it once and share it.`);
    }
    index.set(item.id, item);
  }
  return index;
}

const datasetsById = indexById(datasets, "dataset");
const variablesById = indexById(
  datasets.flatMap((dataset) => dataset.variables),
  "variable",
);
const regionsById = indexById(
  datasets.flatMap((dataset) => dataset.regions),
  "region",
);
const unitIds = new Set<string>([...variablesById.values()].map((variable) => variable.unit));

export function isVariableId(value: unknown): value is VariableId {
  return typeof value === "string" && variablesById.has(value);
}

export function isUnitId(value: unknown): value is UnitId {
  return typeof value === "string" && unitIds.has(value);
}

export function isRegionId(value: unknown): value is RegionId {
  return typeof value === "string" && regionsById.has(value);
}

/** A fully resolved, always-valid dashboard selection. */
export interface DatasetSelection {
  readonly dataset: RegisteredDataset;
  readonly variable: RegisteredVariable;
  readonly region: RegisteredRegion;
}

export interface RawSelection {
  readonly dataset?: string | null;
  readonly variable?: string | null;
  readonly region?: string | null;
}

/**
 * Turn untrusted input (URL params, storage) into a valid selection, falling
 * back field by field to the first supported option.
 */
export function resolveSelection(raw: RawSelection): DatasetSelection {
  const requested = raw.dataset ? datasetsById.get(raw.dataset) : undefined;
  const dataset =
    requested?.status === "available" ? requested : datasets.find((entry) => entry.status === "available");
  if (!dataset) throw new Error("The dataset registry has no available datasets.");

  const variable = dataset.variables.find((entry) => entry.id === raw.variable) ?? dataset.variables[0];
  const region = dataset.regions.find((entry) => entry.id === raw.region) ?? dataset.regions[0];
  if (!variable || !region) {
    throw new Error(`Dataset "${dataset.id}" needs at least one variable and region.`);
  }

  return { dataset, variable, region };
}
