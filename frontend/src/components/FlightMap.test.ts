// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { projectedPosition } from "./FlightMap";

describe("live aircraft projection", () => {
  it("moves an eastbound aircraft between provider observations", () => {
    const observed = "2026-01-01T00:00:00Z";
    const result = projectedPosition(
      { latitude: 33, longitude: -118, heading: 90, ground_speed_knots: 450, observed_at: observed },
      Date.parse(observed) + 1000,
    );
    expect(result).not.toBeNull();
    expect(result![0]).toBeCloseTo(33, 3);
    expect(result![1]).toBeGreaterThan(-118);
  });

  it("does not invent motion when speed data is unavailable", () => {
    expect(projectedPosition({ latitude: 0, longitude: 0, heading: 90 })).toEqual([0, 0]);
  });
});
