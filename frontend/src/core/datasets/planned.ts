import { Leaf, Thermometer, Wind } from "lucide-react";

import { defineDataset } from "./define";

/**
 * Roadmap datasets, rendered as disabled "soon" tabs. To ship one, give it its
 * own file with `status: "available"`, its variables and its regions (the
 * backend must expose matching enum values); it is already registered.
 */

export const globalTemperatureDataset = defineDataset({
  id: "global-temperature",
  label: "Global Temperature",
  description: "Surface air temperature anomalies.",
  icon: Thermometer,
  status: "planned",
  source: "NASA GISS",
  regions: [],
  variables: [],
});

export const co2Dataset = defineDataset({
  id: "co2",
  label: "CO₂ Levels",
  description: "Atmospheric carbon dioxide concentration.",
  icon: Wind,
  status: "planned",
  source: "NASA OCO-2",
  regions: [],
  variables: [],
});

export const vegetationDataset = defineDataset({
  id: "vegetation",
  label: "Vegetation Index",
  description: "Normalized Difference Vegetation Index (NDVI).",
  icon: Leaf,
  status: "planned",
  source: "NASA MODIS",
  regions: [],
  variables: [],
});
