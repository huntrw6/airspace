import { describe, expect, it } from "vitest";
import type { Sighting } from "./api";
import { isLiveSighting, orderLivePanelsByDistance } from "./sightings";

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
  it.each(["detected", "approaching", "in_view", "overhead", "departing", "held"])(
    "keeps %s aircraft on the live map",
    (state) => expect(isLiveSighting(sighting(state))).toBe(true),
  );

  it.each(["historic", "expired"])(
    "keeps %s aircraft off the live map",
    (state) => expect(isLiveSighting(sighting(state))).toBe(false),
  );
});

describe("live notification panel order", () => {
  it("orders a copy by current distance without changing radar input order", () => {
    const far = { ...sighting("in_view"), id: "far", flight: { distance_km: 7 } };
    const close = { ...sighting("in_view"), id: "close", flight: { distance_km: 1.5 } };
    const radarSightings = [far, close];

    expect(orderLivePanelsByDistance(radarSightings).map((item) => item.id)).toEqual([
      "close",
      "far",
    ]);
    expect(radarSightings.map((item) => item.id)).toEqual(["far", "close"]);
  });

  it("uses recorded closest distance for older snapshots without current distance", () => {
    const farther = { ...sighting("in_view"), id: "farther", minimum_distance_km: 5 };
    const nearer = { ...sighting("in_view"), id: "nearer", minimum_distance_km: 2 };

    expect(orderLivePanelsByDistance([farther, nearer]).map((item) => item.id)).toEqual([
      "nearer",
      "farther",
    ]);
  });
});
