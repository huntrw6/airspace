import { useEffect, useState } from "react";
import { api, type AircraftPhoto, type Sighting } from "../api";
import { isHelicopter } from "./FlightMap";

const photoRequests = new Map<string, Promise<AircraftPhoto | null>>();

function loadAircraftPhoto(registration: string): Promise<AircraftPhoto | null> {
  const key = registration.trim().toUpperCase();
  let pending = photoRequests.get(key);
  if (!pending) {
    pending = api.aircraftPhoto(key).then(({ photo }) => photo).catch(() => null);
    photoRequests.set(key, pending);
  }
  return pending;
}

export function compassHeading(heading?: number): string {
  if (heading === undefined) return "Heading unavailable";
  const names = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  return `${Math.round(heading)}° ${names[Math.round(heading / 45) % 8]}`;
}

export function sightingDate(value: string): Date {
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
  return new Date(hasTimezone ? value : `${value}Z`);
}

export function formatSightingTime(
  value: string,
  timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone,
): string {
  return sightingDate(value).toLocaleString(undefined, { timeZone, timeZoneName: "short" });
}

export function flightradar24Url(sighting: Sighting): string | null {
  const callsign = sighting.flight.callsign?.trim().toLowerCase();
  const providerId = sighting.provider_flight_id?.trim().toLowerCase();
  if (callsign && providerId) {
    return `https://www.flightradar24.com/${encodeURIComponent(callsign)}/${encodeURIComponent(providerId)}`;
  }
  if (callsign) {
    return `https://www.flightradar24.com/data/flights/${encodeURIComponent(callsign)}`;
  }
  return null;
}

export function SightingCard({ sighting, expanded = false }: { sighting: Sighting; expanded?: boolean }) {
  const flight = sighting.flight;
  const trackerUrl = flightradar24Url(sighting);
  const aircraftSymbol = isHelicopter(flight.aircraft_type, flight.aircraft_kind) ? "🚁" : "✈️";
  const [photo, setPhoto] = useState<AircraftPhoto | null>(null);
  useEffect(() => {
    let active = true;
    if (!flight.registration) {
      setPhoto(null);
      return () => { active = false; };
    }
    void loadAircraftPhoto(flight.registration).then((value) => {
      if (active) setPhoto(value);
    });
    return () => { active = false; };
  }, [flight.registration]);
  return <article className={`flight ${expanded ? "highlighted" : ""}`} id={`sighting-${sighting.id}`}>
    {photo && <figure className="aircraft-photo">
      <a href={photo.page_url} target="_blank" rel="noreferrer">
        <img src={photo.thumbnail_url} alt={`${flight.registration || "Aircraft"} aircraft`} loading="lazy" />
      </a>
      <figcaption>Photo © {photo.photographer} · Planespotters.net</figcaption>
    </figure>}
    <h2>{flight.callsign || "Unidentified aircraft"} {aircraftSymbol}</h2>
    <p>{flight.airline || flight.aircraft_type || "Aircraft details unavailable"}</p>
    <strong>{flight.origin_city || "Unknown origin"} → {flight.destination_city || "Unknown destination"}</strong>
    <p>{sighting.minimum_distance_km.toFixed(1)} km closest · {flight.altitude_ft?.toLocaleString() || "Altitude unavailable"} ft</p>
    <p>{compassHeading(flight.heading)} · {sighting.state.replace("_", " ")}</p>
    <small>
      First detected {formatSightingTime(sighting.first_detected_at)}
      <br />
      Last seen {formatSightingTime(sighting.last_seen_at)}
    </small>
    {trackerUrl && <p><a href={trackerUrl} target="_blank" rel="noreferrer">Follow on Flightradar24 ↗</a></p>}
  </article>;
}
