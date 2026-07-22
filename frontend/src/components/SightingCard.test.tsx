// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { compassHeading, flightradar24Url, SightingCard } from "./SightingCard";

describe("sighting details", () => {
  it("links an FR24 sighting to its exact live flight", () => {
    expect(flightradar24Url({
      id: "one", location_id: "home", provider_flight_id: "3ABC123", state: "visible",
      first_detected_at: "2026-01-01T00:00:00Z", last_seen_at: "2026-01-01T00:01:00Z",
      minimum_distance_km: 2.25, flight: { callsign: "ASA836" },
    })).toBe("https://www.flightradar24.com/asa836/3abc123");
  });

  it("falls back to FR24 flight history when the live flight id is unavailable", () => {
    expect(flightradar24Url({
      id: "one", location_id: "home", state: "historic",
      first_detected_at: "2026-01-01T00:00:00Z", last_seen_at: "2026-01-01T00:01:00Z",
      minimum_distance_km: 2.25, flight: { callsign: "ASA836" },
    })).toBe("https://www.flightradar24.com/data/flights/asa836");
  });

  it("formats compass headings at the wraparound", () => {
    expect(compassHeading(359)).toBe("359° N");
    expect(compassHeading(90)).toBe("90° E");
  });

  it("renders partial provider data without inventing values", () => {
    render(<SightingCard sighting={{
      id: "one", location_id: "home", state: "historic",
      first_detected_at: "2026-01-01T00:00:00Z", last_seen_at: "2026-01-01T00:01:00Z",
      minimum_distance_km: 2.25, flight: {},
    }} />);
    expect(screen.getByText("Unidentified aircraft")).toBeTruthy();
    expect(screen.getByText(/Altitude unavailable/)).toBeTruthy();
  });
});
