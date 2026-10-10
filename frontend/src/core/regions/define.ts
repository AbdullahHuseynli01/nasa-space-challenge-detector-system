/**
 * Regions are plain config objects. Datasets list the regions they support and
 * the dataset registry derives the set of known regions from them, so a new
 * dataset can introduce a new region without touching any other file.
 */

export interface GeoBounds {
  /** Southern latitude limit in degrees (−90…90). */
  readonly latMin: number;
  /** Northern latitude limit in degrees (−90…90). */
  readonly latMax: number;
  /** Western longitude limit in degrees (−180…180). */
  readonly lonMin: number;
  /** Eastern longitude limit in degrees (−180…180). */
  readonly lonMax: number;
}

export interface RegionDefinition<TId extends string = string> {
  /** Must match the backend `Region` enum value. */
  readonly id: TId;
  readonly label: string;
  /** Area the backend's time series covers. */
  readonly bounds: GeoBounds;
}

/** Identity helper that keeps the literal id, so registry unions stay exact. */
export function defineRegion<const TId extends string>(region: RegionDefinition<TId>): RegionDefinition<TId> {
  return region;
}

/** "66°N – 90°N", plus the longitude span when the region isn't a full latitude band. */
export function formatBounds({ latMin, latMax, lonMin, lonMax }: GeoBounds): string {
  const lat = (deg: number): string => `${Math.abs(deg)}°${deg >= 0 ? "N" : "S"}`;
  const lon = (deg: number): string => `${Math.abs(deg)}°${deg >= 0 ? "E" : "W"}`;
  const latitudes = `${lat(latMin)} – ${lat(latMax)}`;
  return lonMax - lonMin >= 360 ? latitudes : `${latitudes}, ${lon(lonMin)} – ${lon(lonMax)}`;
}
