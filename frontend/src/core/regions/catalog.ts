import { defineRegion } from "./define";

/**
 * Regions shared by several datasets. Import these instead of redefining them:
 * the registry rejects two different objects with the same id.
 * Bounds match the NASA Giovanni exports the backend serves.
 */

export const arctic = defineRegion({
  id: "arctic",
  label: "Arctic",
  bounds: { latMin: 66, latMax: 90, lonMin: -180, lonMax: 180 },
});

export const antarctic = defineRegion({
  id: "antarctic",
  label: "Antarctic",
  bounds: { latMin: -90, latMax: -66, lonMin: -180, lonMax: 180 },
});
