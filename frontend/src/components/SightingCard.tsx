import type { Sighting } from "../api";

export function compassHeading(heading?: number): string {
  if (heading === undefined) return "Heading unavailable";
  const names = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  return `${Math.round(heading)}° ${names[Math.round(heading / 45) % 8]}`;
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
  return <article className={`flight ${expanded ? "highlighted" : ""}`} id={`sighting-${sighting.id}`}>
    <h2>{flight.callsign || "Unidentified aircraft"}</h2>
    <p>{flight.airline || flight.aircraft_type || "Aircraft details unavailable"}</p>
    <strong>{flight.origin_city || "Unknown origin"} → {flight.destination_city || "Unknown destination"}</strong>
    <p>{sighting.minimum_distance_km.toFixed(1)} km closest · {flight.altitude_ft?.toLocaleString() || "Altitude unavailable"} ft</p>
    <p>{compassHeading(flight.heading)} · {sighting.state.replace("_", " ")}</p>
    <small>First detected {new Date(sighting.first_detected_at).toLocaleString()} · last seen {new Date(sighting.last_seen_at).toLocaleString()}</small>
    {trackerUrl && <p><a href={trackerUrl} target="_blank" rel="noreferrer">Follow on Flightradar24 ↗</a></p>}
  </article>;
}
