import { useEffect, useRef } from "react";
import L from "leaflet";
import type { Location, Sighting } from "../api";

const EARTH_RADIUS_KM = 6371;

export function projectedPosition(
  flight: Sighting["flight"],
  nowMilliseconds = Date.now(),
): [number, number] | null {
  const { latitude, longitude, heading, ground_speed_knots, observed_at } = flight;
  if (typeof latitude !== "number" || typeof longitude !== "number") return null;
  if (
    typeof heading !== "number" ||
    typeof ground_speed_knots !== "number" ||
    !observed_at
  ) return [latitude, longitude];
  const observed = Date.parse(observed_at);
  if (!Number.isFinite(observed)) return [latitude, longitude];
  const elapsedSeconds = Math.min(60, Math.max(0, (nowMilliseconds - observed) / 1000));
  const angularDistance = (ground_speed_knots * 0.000514444 * elapsedSeconds) / EARTH_RADIUS_KM;
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

function planeIcon(heading?: number): L.DivIcon {
  const rotation = Number.isFinite(heading) ? Number(heading) - 45 : -45;
  return L.divIcon({
    className: "aircraft-marker",
    html: `<span style="transform:rotate(${rotation}deg)">✈</span>`,
    iconSize: [34, 34],
    iconAnchor: [17, 17],
  });
}

export function FlightMap({ locations, sightings }: { locations: Location[]; sightings: Sighting[] }) {
  const element = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const markers = useRef(new Map<string, L.Marker>());
  const currentSightings = useRef(sightings);
  const fittedAircraft = useRef(false);
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
    const newBounds: L.LatLngExpression[] = [];
    currentSightings.current.forEach((sighting) => {
      const position = projectedPosition(sighting.flight);
      if (!position) return;
      let marker = markers.current.get(sighting.id);
      if (!marker) {
        marker = L.marker(position, { icon: planeIcon(sighting.flight.heading) })
          .bindTooltip(sighting.flight.callsign || "Unidentified aircraft")
          .addTo(map.current!);
        markers.current.set(sighting.id, marker);
        newBounds.push(position);
      } else {
        marker.setLatLng(position);
        marker.setIcon(planeIcon(sighting.flight.heading));
      }
    });
    if (!fittedAircraft.current && newBounds.length) {
      const locationBounds = locations.map((item) => [item.latitude, item.longitude] as L.LatLngTuple);
      map.current.fitBounds(L.latLngBounds([...locationBounds, ...newBounds]), { padding: [30, 30] });
      fittedAircraft.current = true;
    }
  }

  useEffect(() => {
    if (!element.current || locations.length === 0) return;
    const first = locations[0];
    map.current = L.map(element.current).setView([first.latitude, first.longitude], 11);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
    }).addTo(map.current);
    locations.forEach((location) => {
      L.circle([location.latitude, location.longitude], {
        radius: location.radius_km * 1000,
        color: "#5ed2e8",
        fillColor: "#168ba4",
        fillOpacity: 0.1,
      }).bindTooltip(location.label).addTo(map.current!);
    });
    renderAircraft();
    const timer = window.setInterval(renderAircraft, 1000);
    return () => {
      window.clearInterval(timer);
      markers.current.clear();
      map.current?.remove();
      map.current = null;
      fittedAircraft.current = false;
    };
  }, [locations]);

  useEffect(renderAircraft, [sightings]);

  return <div ref={element} className="map dashboard-map" aria-label="Nearby aircraft map" />;
}
