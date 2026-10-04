// @vitest-environment jsdom
import { cleanup, render } from "@testing-library/react";
import L from "leaflet";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Location } from "../api";
import { FlightMap } from "./FlightMap";
import { MapPicker } from "./MapPicker";

const location: Location = {
  id: "test-location",
  label: "Test location",
  latitude: 34,
  longitude: -118,
  radius_km: 8,
  detection_mode: "all",
  facing_direction: 0,
  fov_width: 360,
  enabled: true,
  created_at: "2026-01-01T00:00:00Z",
  overhead_threshold_km: 1,
  notification_cooldown_seconds: 1800,
};

beforeEach(() => {
  vi.stubEnv("VITE_CARTO_BASEMAPS_API_KEY", "test-key&value");
  vi.stubGlobal("ResizeObserver", class {
    observe() {}
    disconnect() {}
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("authenticated CARTO basemaps", () => {
  it.each(["flight map", "location picker"])("adds the configured key and attribution to the %s", (component) => {
    const tiles = vi.spyOn(L, "tileLayer");
    if (component === "flight map") {
      render(<FlightMap locations={[location]} sightings={[]} />);
    } else {
      render(<MapPicker position={null} radiusKm={8} onChange={vi.fn()} />);
    }
    expect(tiles).toHaveBeenCalledWith(
      "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?key=test-key%26value",
      expect.objectContaining({
        attribution: expect.stringContaining("CARTO"),
      }),
    );
    expect(tiles.mock.calls[0][1]?.attribution).toContain("OpenStreetMap");
  });
});
