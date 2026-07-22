// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import {
  AIRPLANE_SYMBOL,
  bufferedViewingBounds,
  circleCrossingSeconds,
  flightMarkerLabel,
  isHelicopter,
  mapProjectionSeconds,
  markerRotation,
  projectedPosition,
} from "./FlightMap";

describe("live aircraft projection", () => {
  it("labels aircraft markers with the airline and callsign", () => {
    expect(flightMarkerLabel({
      airline: "Hawaiian Airlines",
      callsign: "ASA836",
    })).toBe("Hawaiian Airlines ASA836");
    expect(flightMarkerLabel({ callsign: "N123AB" })).toBe("N123AB");
    expect(flightMarkerLabel({})).toBe("Unidentified aircraft");
  });

  it("calculates buffered map bounds without requiring a mounted Leaflet layer", () => {
    const bounds = bufferedViewingBounds({
      latitude: 34,
      longitude: -118,
      radius_km: 8,
    });

    expect(bounds.isValid()).toBe(true);
    expect(bounds.contains([34, -118])).toBe(true);
    expect(bounds.getNorth() - bounds.getSouth()).toBeGreaterThan(0.17);
  });

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
    expect(markerRotation(45, true)).toBe(0);
    expect(markerRotation(undefined, true)).toBe(0);
  });

  it("stops projection at the buffered map boundary from the observed position", () => {
    const observed = "2026-01-01T00:00:00Z";
    const flight = { latitude: 33, longitude: -118, heading: 90, ground_speed_knots: 450, observed_at: observed };
    const location = { latitude: 33, longitude: -118, radius_km: 8 };
    const crossingSeconds = mapProjectionSeconds(location, flight);
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
    expect(crossingSeconds).toBeCloseTo(43.2, 1);
    expect(longAfterCrossing![0]).toBeCloseTo(atCrossing![0], 8);
    expect(longAfterCrossing![1]).toBeCloseTo(atCrossing![1], 8);
  });

  it("allows a full buffered diameter only when observed at the entry edge", () => {
    const latitude = 33;
    const radiusKm = 10;
    const longitudeDegrees = radiusKm /
      (111.32 * Math.cos((latitude * Math.PI) / 180));
    const seconds = mapProjectionSeconds(
      { latitude, longitude: -118, radius_km: 8 },
      {
        latitude,
        longitude: -118 - longitudeDegrees,
        heading: 90,
        ground_speed_knots: 450,
      },
    );
    expect(seconds).toBeCloseTo(86.4, 1);
  });

  it("does not project when circle or speed data is unavailable", () => {
    expect(circleCrossingSeconds(8, undefined)).toBe(0);
    expect(circleCrossingSeconds(0, 450)).toBe(0);
  });
});
