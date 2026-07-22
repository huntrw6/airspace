import { describe, expect, it } from "vitest";
import type { Sighting } from "./api";
import { isLiveSighting } from "./sightings";

function sighting(state: string): Sighting {
  return {
    id: state,
    location_id: "home",
    state,
    first_detected_at: "2026-01-01T00:00:00Z",
    last_seen_at: "2026-01-01T00:00:00Z",
    minimum_distance_km: 1,
    flight: {},
  };
}

describe("live sighting states", () => {
  it.each(["detected", "approaching", "in_view", "overhead", "departing"])(
    "keeps %s aircraft on the live map",
    (state) => expect(isLiveSighting(sighting(state))).toBe(true),
  );

  it.each(["held", "historic", "expired"])(
    "keeps %s aircraft off the live map",
    (state) => expect(isLiveSighting(sighting(state))).toBe(false),
  );
});
