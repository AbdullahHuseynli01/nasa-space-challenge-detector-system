import { Snowflake } from "lucide-react";

import { antarctic, arctic } from "@/core/regions/catalog";
import { formatPercent, formatSigned } from "@/lib/format";

import { defineDataset, defineVariable } from "./define";

const seaIceFraction = defineVariable({
  id: "sea_ice_fraction",
  unit: "fraction",
  unitLabel: "fraction",
  label: "Sea-Ice Covered Fraction",
  shortLabel: "Ice fraction",
  description: "Fraction of the selected polar region covered by sea ice.",
  seriesLabel: "Annual mean sea-ice fraction",
  formatValue: (value) => formatPercent(value, 2),
  formatTick: (value) => formatPercent(value, 0),
  // Fraction/year → percentage points per decade, the conventional framing.
  formatRate: (slope) => `${formatSigned(slope * 100 * 10, 2)} pp / decade`,
  domain: "auto",
  trendLabels: {
    increasing: "Ice growth trend",
    decreasing: "Ice loss trend",
    no_significant_trend: "No significant trend",
  },
});

export const seaIceDataset = defineDataset({
  id: "sea-ice",
  label: "Sea Ice",
  description: "Time-series observations and deterministic trend analysis of polar sea-ice fraction.",
  icon: Snowflake,
  status: "available",
  source: "NASA GES DISC · MERRA-2 FRSEAICE (M2TMNXFLX)",
  regions: [arctic, antarctic],
  variables: [seaIceFraction],
});
