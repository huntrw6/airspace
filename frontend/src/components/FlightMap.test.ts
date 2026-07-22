// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import {
  AIRPLANE_SYMBOL,
  circleCrossingSeconds,
  isHelicopter,
  mapProjectionSeconds,
  markerRotation,
  projectedPosition,
} from "./FlightMap";

describe("live aircraft projection", () => {
  it("moves an eastbound aircraft between provider observations", () => {
    const observed = "2026-01-01T00:00:00Z";
    const result = projectedPosition(
      { latitude: 33, longitude: -118, heading: 90, ground_speed_knots: 450, observed_at: observed },
      Date.parse(observed) + 1000,
      60,
    );
    expect(result).not.toBeNull();
    expect(result![0]).toBeCloseTo(33, 3);
    expect(result![1]).toBeGreaterThan(-118);
  });

  it("does not invent motion when speed data is unavailable", () => {
    expect(projectedPosition({ latitude: 0, longitude: 0, heading: 90 })).toEqual([0, 0]);
  });

  it("uses the east-facing plane emoji as the rotation baseline", () => {
    expect([...AIRPLANE_SYMBOL].map((character) => character.codePointAt(0))).toEqual([
      0x2708,
      0xfe0e,
    ]);
    expect(markerRotation(90, false)).toBe(0);
    expect(markerRotation(0, false)).toBe(-90);
  });

  it("recognizes helicopter codes and descriptions", () => {
    expect(isHelicopter("R44")).toBe(true);
    expect(isHelicopter("Airbus Helicopters H145")).toBe(true);
    expect(isHelicopter("B738")).toBe(false);
    expect(markerRotation(270, true)).toBe(0);
  });

  it("stops projecting after the aircraft could cross the buffered map area", () => {
    const observed = "2026-01-01T00:00:00Z";
    const flight = { latitude: 33, longitude: -118, heading: 90, ground_speed_knots: 450, observed_at: observed };
    const crossingSeconds = mapProjectionSeconds(8, flight.ground_speed_knots);
    const atCrossing = projectedPosition(
      flight,
      Date.parse(observed) + crossingSeconds * 1000,
      crossingSeconds,
    );
    const longAfterCrossing = projectedPosition(
      flight,
      Date.parse(observed) + 300_000,
      crossingSeconds,
    );
    expect(crossingSeconds).toBeCloseTo(86.4, 1);
    expect(longAfterCrossing![0]).toBeCloseTo(atCrossing![0], 8);
    expect(longAfterCrossing![1]).toBeCloseTo(atCrossing![1], 8);
  });

  it("does not project when circle or speed data is unavailable", () => {
    expect(circleCrossingSeconds(8, undefined)).toBe(0);
    expect(circleCrossingSeconds(0, 450)).toBe(0);
  });
});
