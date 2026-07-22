import { useEffect, useRef } from "react";
import L from "leaflet";
import type { Location, Sighting } from "../api";

const EARTH_RADIUS_KM = 6371;
const KNOTS_TO_KM_PER_SECOND = 0.000514444;
const MAP_BUFFER_KM = 2;
export const AIRPLANE_SYMBOL = "✈︎";

export function bufferedViewingBounds(
  location: Pick<Location, "latitude" | "longitude" | "radius_km">,
): L.LatLngBounds {
  const diameterMeters = (location.radius_km + MAP_BUFFER_KM) * 2000;
  return L.latLng(location.latitude, location.longitude).toBounds(diameterMeters);
}

export function circleCrossingSeconds(
  radiusKm: number,
  groundSpeedKnots: number | undefined,
): number {
  if (
    !Number.isFinite(radiusKm) ||
    radiusKm <= 0 ||
    !Number.isFinite(groundSpeedKnots) ||
    Number(groundSpeedKnots) <= 0
  )
    return 0;
  return (radiusKm * 2) / (Number(groundSpeedKnots) * KNOTS_TO_KM_PER_SECOND);
}

export function mapProjectionSeconds(
  location: Pick<Location, "latitude" | "longitude" | "radius_km">,
  flight: Sighting["flight"],
): number {
  const { latitude, longitude, heading, ground_speed_knots } = flight;
  if (
    typeof latitude !== "number" ||
    typeof longitude !== "number" ||
    typeof heading !== "number" ||
    typeof ground_speed_knots !== "number" ||
    ground_speed_knots <= 0
  )
    return 0;
  const radiusKm = location.radius_km + MAP_BUFFER_KM;
  const latitudeKm = (latitude - location.latitude) * 111.32;
  const longitudeKm =
    (longitude - location.longitude) *
    111.32 *
    Math.max(0.1, Math.cos((location.latitude * Math.PI) / 180));
  const distanceSquared = latitudeKm ** 2 + longitudeKm ** 2;
  if (distanceSquared > radiusKm ** 2 * (1 + 1e-9)) return 0;
  const headingRadians = (heading * Math.PI) / 180;
  const directionEast = Math.sin(headingRadians);
  const directionNorth = Math.cos(headingRadians);
  const positionAlongHeading =
    longitudeKm * directionEast + latitudeKm * directionNorth;
  const distanceToBoundary =
    -positionAlongHeading +
    Math.sqrt(
      Math.max(
        0,
        positionAlongHeading ** 2 + radiusKm ** 2 - distanceSquared,
      ),
    );
  return Math.max(0, distanceToBoundary) /
    (ground_speed_knots * KNOTS_TO_KM_PER_SECOND);
}

export function projectedPosition(
  flight: Sighting["flight"],
  nowMilliseconds = Date.now(),
  maximumProjectionSeconds = 0,
): [number, number] | null {
  const { latitude, longitude, heading, ground_speed_knots, observed_at } = flight;
  if (typeof latitude !== "number" || typeof longitude !== "number") return null;
  if (
    typeof heading !== "number" ||
    typeof ground_speed_knots !== "number" ||
    !observed_at ||
    maximumProjectionSeconds <= 0
  ) return [latitude, longitude];
  const observed = Date.parse(observed_at);
  if (!Number.isFinite(observed)) return [latitude, longitude];
  const elapsedSeconds = Math.min(
    maximumProjectionSeconds,
    Math.max(0, (nowMilliseconds - observed) / 1000),
  );
  const angularDistance =
    (ground_speed_knots * KNOTS_TO_KM_PER_SECOND * elapsedSeconds) / EARTH_RADIUS_KM;
  const bearing = (heading * Math.PI) / 180;
  const lat1 = (latitude * Math.PI) / 180;
  const lon1 = (longitude * Math.PI) / 180;
  const lat2 = Math.asin(
    Math.sin(lat1) * Math.cos(angularDistance) +
      Math.cos(lat1) * Math.sin(angularDistance) * Math.cos(bearing),
  );
  const lon2 = lon1 + Math.atan2(
    Math.sin(bearing) * Math.sin(angularDistance) * Math.cos(lat1),
    Math.cos(angularDistance) - Math.sin(lat1) * Math.sin(lat2),
  );
  return [(lat2 * 180) / Math.PI, ((((lon2 * 180) / Math.PI) + 540) % 360) - 180];
}

const HELICOPTER_CODES = new Set([
  "R22", "R44", "R66", "B06", "B212", "B412", "B427", "B429", "EC20", "EC25",
  "EC30", "EC35", "EC45", "EC55", "H125", "H130", "H135", "H145", "H160", "H175",
  "H225", "AS32", "AS50", "AS55", "AS65", "S61", "S64", "S65", "S70", "S76", "S92",
  "A109", "A119", "A139", "A149", "A169", "A189", "MI2", "MI6", "MI8", "MI24", "MI26",
  "KA27", "KA29", "KA31", "KA32", "UH1", "H60", "CH47", "AH64", "V22",
]);

export function isHelicopter(aircraftType?: string): boolean {
  if (!aircraftType) return false;
  const normalized = aircraftType.trim().toUpperCase();
  return (
    HELICOPTER_CODES.has(normalized) ||
    /HELICOPTER|ROTORCRAFT|ROTOR CRAFT/.test(normalized)
  );
}

export function markerRotation(heading: number | undefined, helicopter: boolean): number {
  const baseline = helicopter ? 270 : 90;
  return Number.isFinite(heading) ? Number(heading) - baseline : -baseline;
}

export function flightMarkerLabel(flight: Sighting["flight"]): string {
  const airline = flight.airline?.trim();
  const callsign = flight.callsign?.trim();
  return [airline, callsign].filter(Boolean).join(" ") || "Unidentified aircraft";
}

function aircraftIcon(heading?: number, aircraftType?: string): L.DivIcon {
  const helicopter = isHelicopter(aircraftType);
  const rotation = markerRotation(heading, helicopter);
  return L.divIcon({
    className: "aircraft-marker",
    html: `<span class="${helicopter ? "helicopter-symbol" : "airplane-symbol"}" style="transform:rotate(${rotation}deg)">${helicopter ? "🚁" : AIRPLANE_SYMBOL}</span>`,
    iconSize: [34, 34],
    iconAnchor: [17, 17],
  });
}

function radarSweepElement(): SVGSVGElement {
  const trailSegments = Array.from({ length: 24 }, (_, index) => {
    const startAngle = -60 + index * 2.5;
    const endAngle = startAngle + 2.5;
    const point = (angle: number) => {
      const radians = (angle * Math.PI) / 180;
      return [50 + 50 * Math.sin(radians), 50 - 50 * Math.cos(radians)];
    };
    const [startX, startY] = point(startAngle);
    const [endX, endY] = point(endAngle);
    const progress = (index + 1) / 24;
    const opacity = 0.012 + Math.pow(progress, 1.7) * 0.34;

    return `<path class="radar-trail" style="opacity:${opacity.toFixed(3)}" d="M50 50 L${startX.toFixed(2)} ${startY.toFixed(2)} A50 50 0 0 1 ${endX.toFixed(2)} ${endY.toFixed(2)} Z" />`;
  }).join("");

  const element = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  element.setAttribute("viewBox", "0 0 100 100");
  element.setAttribute("preserveAspectRatio", "none");
  element.setAttribute("aria-hidden", "true");
  element.classList.add("radar-sweep-overlay");
  element.innerHTML = `
    <circle class="radar-range-ring" cx="50" cy="50" r="16.67" />
    <circle class="radar-range-ring" cx="50" cy="50" r="33.33" />
    <circle class="radar-center-dot" cx="50" cy="50" r="1.25" />
    <g class="radar-sweep-vector">
      ${trailSegments}
      <line class="radar-beam" x1="50" y1="50" x2="50" y2="0" />
    </g>`;
  return element;
}

export function FlightMap({ locations, sightings }: { locations: Location[]; sightings: Sighting[] }) {
  const element = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const markers = useRef(new Map<string, L.Marker>());
  const currentSightings = useRef(sightings);
  currentSightings.current = sightings;

  function renderAircraft() {
    if (!map.current) return;
    const activeIds = new Set(currentSightings.current.map((sighting) => sighting.id));
    markers.current.forEach((marker, id) => {
      if (!activeIds.has(id)) {
        marker.remove();
        markers.current.delete(id);
      }
    });
    currentSightings.current.forEach((sighting) => {
      const location = locations.find((item) => item.id === sighting.location_id);
      const projectionSeconds = location
        ? mapProjectionSeconds(location, sighting.flight)
        : 0;
      const position = projectedPosition(sighting.flight, Date.now(), projectionSeconds);
      if (!position) return;
      const label = flightMarkerLabel(sighting.flight);
      let marker = markers.current.get(sighting.id);
      if (!marker) {
        marker = L.marker(position, {
          icon: aircraftIcon(sighting.flight.heading, sighting.flight.aircraft_type),
        })
          .bindTooltip(label, { direction: "right", offset: [12, 0] })
          .addTo(map.current!);
        markers.current.set(sighting.id, marker);
      } else {
        marker.setLatLng(position);
        marker.setIcon(aircraftIcon(sighting.flight.heading, sighting.flight.aircraft_type));
        marker.setTooltipContent(label);
      }
    });
  }

  useEffect(() => {
    if (!element.current || locations.length === 0) return;
    const first = locations[0];
    map.current = L.map(element.current, {
      zoomControl: false,
      zoomSnap: 0,
      dragging: false,
      scrollWheelZoom: false,
      doubleClickZoom: false,
      boxZoom: false,
      keyboard: false,
      touchZoom: false,
    }).setView([first.latitude, first.longitude], 11);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
    }).addTo(map.current);
    const radarPane = map.current.createPane("radarPane");
    radarPane.style.zIndex = "450";
    radarPane.style.pointerEvents = "none";
    const viewingBounds = L.latLngBounds([]);
    locations.forEach((location) => {
      const circle = L.circle([location.latitude, location.longitude], {
        radius: location.radius_km * 1000,
        color: "#5ed2e8",
        fillColor: "#168ba4",
        fillOpacity: 0.1,
      }).addTo(map.current!);
      L.svgOverlay(radarSweepElement(), circle.getBounds(), {
        pane: "radarPane",
        interactive: false,
      }).addTo(map.current!);
      viewingBounds.extend(circle.getBounds());
    });
    map.current.fitBounds(viewingBounds, { padding: [0, 0], animate: false });
    renderAircraft();
    const timer = window.setInterval(renderAircraft, 1000);
    return () => {
      window.clearInterval(timer);
      markers.current.clear();
      map.current?.remove();
      map.current = null;
    };
  }, [locations]);

  useEffect(renderAircraft, [sightings]);

  return <div ref={element} className="map dashboard-map" aria-label="Nearby aircraft map" />;
}
