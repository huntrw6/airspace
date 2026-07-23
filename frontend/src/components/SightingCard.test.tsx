// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import {
  compassHeading,
  flightradar24Url,
  formatSightingTime,
  sightingDate,
  SightingCard,
} from "./SightingCard";

describe("sighting details", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("treats legacy offset-less detection times as UTC", () => {
    expect(sightingDate("2026-07-22T22:48:32").toISOString()).toBe(
      "2026-07-22T22:48:32.000Z",
    );
    expect(sightingDate("2026-07-22T15:48:32-07:00").toISOString()).toBe(
      "2026-07-22T22:48:32.000Z",
    );
    expect(formatSightingTime("2026-07-22T22:48:32Z", "America/Los_Angeles")).toMatch(
      /3:48:32 PM PDT/,
    );
  });

  it("shows an attributed aircraft photo when a registration is available", async () => {
    vi.spyOn(api, "aircraftPhoto").mockResolvedValue({ photo: {
      thumbnail_url: "https://t.plnspttrs.net/photo.jpg",
      page_url: "https://www.planespotters.net/photo/123/example",
      photographer: "Example Photographer",
    }});
    render(<SightingCard sighting={{
      id: "photo", location_id: "home", state: "visible",
      first_detected_at: "2026-01-01T00:00:00Z", last_seen_at: "2026-01-01T00:01:00Z",
      minimum_distance_km: 2.25, flight: { registration: "N62889" },
    }} />);
    expect(await screen.findByAltText("N62889 aircraft")).toBeTruthy();
    expect(screen.getByText(/Example Photographer/)).toBeTruthy();
  });

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
    expect(screen.getByText("Unidentified aircraft ✈️")).toBeTruthy();
    expect(screen.getByText(/Altitude unavailable/)).toBeTruthy();
  });

  it("shows the matching aircraft symbol after the flight number", () => {
    const base = {
      location_id: "home", state: "visible", first_detected_at: "2026-01-01T00:00:00Z",
      last_seen_at: "2026-01-01T00:01:00Z", minimum_distance_km: 2.25,
    };
    const { rerender } = render(<SightingCard sighting={{
      ...base, id: "plane", flight: { callsign: "ASA836", aircraft_type: "A330" },
    }} />);
    expect(screen.getByText("ASA836 ✈️")).toBeTruthy();
    rerender(<SightingCard sighting={{
      ...base, id: "helicopter", flight: { callsign: "LIFE1", aircraft_type: "H145" },
    }} />);
    expect(screen.getByText("LIFE1 🚁")).toBeTruthy();
  });
});
