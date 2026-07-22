// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { isHelicopter, markerRotation, projectedPosition } from "./FlightMap";

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

  it("uses the east-facing plane emoji as the rotation baseline", () => {
    expect(markerRotation(90, false)).toBe(0);
    expect(markerRotation(0, false)).toBe(-90);
  });

  it("recognizes helicopter codes and descriptions", () => {
    expect(isHelicopter("R44")).toBe(true);
    expect(isHelicopter("Airbus Helicopters H145")).toBe(true);
    expect(isHelicopter("B738")).toBe(false);
    expect(markerRotation(270, true)).toBe(0);
  });

  it("continues projecting for five minutes", () => {
    const observed = "2026-01-01T00:00:00Z";
    const flight = { latitude: 33, longitude: -118, heading: 90, ground_speed_knots: 450, observed_at: observed };
    const afterOneMinute = projectedPosition(flight, Date.parse(observed) + 60_000)!;
    const afterFiveMinutes = projectedPosition(flight, Date.parse(observed) + 300_000)!;
    expect(afterFiveMinutes[1]).toBeGreaterThan(afterOneMinute[1]);
  });
});
