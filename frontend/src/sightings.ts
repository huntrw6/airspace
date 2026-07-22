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

export function sortSightingsByCurrentDistance(sightings: Sighting[]): Sighting[] {
  return [...sightings].sort((left, right) => {
    const leftDistance = Number.isFinite(left.flight.distance_km)
      ? left.flight.distance_km!
      : left.minimum_distance_km;
    const rightDistance = Number.isFinite(right.flight.distance_km)
      ? right.flight.distance_km!
      : right.minimum_distance_km;
    return leftDistance - rightDistance;
  });
}
