import type { Sighting } from "./api";

export const LIVE_SIGHTING_STATES = new Set([
  "detected",
  "approaching",
  "in_view",
  "overhead",
  "departing",
]);

export function isLiveSighting(sighting: Sighting): boolean {
  return LIVE_SIGHTING_STATES.has(sighting.state);
}
