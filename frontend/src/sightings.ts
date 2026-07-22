import type { Sighting } from "./api";

export const LIVE_SIGHTING_STATES = new Set([
  "detected",
  "approaching",
  "in_view",
  "overhead",
  "departing",
  "held",
]);

export function isLiveSighting(sighting: Sighting): boolean {
  return LIVE_SIGHTING_STATES.has(sighting.state);
}

function currentDistanceKm(sighting: Sighting): number {
  const current = sighting.flight.distance_km;
  return typeof current === "number" && Number.isFinite(current)
    ? current
    : sighting.minimum_distance_km;
}

export function orderLivePanelsByDistance(sightings: Sighting[]): Sighting[] {
  return [...sightings].sort(
    (left, right) => currentDistanceKm(left) - currentDistanceKm(right),
  );
}
