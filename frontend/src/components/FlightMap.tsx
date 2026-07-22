import { useEffect, useRef } from "react";
import L from "leaflet";
import type { Location, Sighting } from "../api";

export function FlightMap({
  locations,
  sightings,
}: {
  locations: Location[];
  sightings: Sighting[];
}) {
  const element = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!element.current || locations.length === 0) return;
    const first = locations[0];
    const map = L.map(element.current).setView(
      [first.latitude, first.longitude],
      11,
    );
    L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
      {
        maxZoom: 19,
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
      },
    ).addTo(map);
    const bounds: L.LatLngExpression[] = [];
    locations.forEach((location) => {
      bounds.push([location.latitude, location.longitude]);
      L.circle([location.latitude, location.longitude], {
        radius: location.radius_km * 1000,
        color: "#168ba4",
        fillOpacity: 0.08,
      })
        .bindTooltip(location.label)
        .addTo(map);
    });
    sightings.forEach((sighting) => {
      const { latitude, longitude, callsign } = sighting.flight;
      if (
        typeof latitude !== "number" ||
        typeof longitude !== "number" ||
        !Number.isFinite(latitude) ||
        !Number.isFinite(longitude)
      )
        return;
      bounds.push([latitude, longitude]);
      L.circleMarker([latitude, longitude], {
        radius: 8,
        color: "#071a2b",
        fillColor: "#f1bb72",
        fillOpacity: 1,
      })
        .bindTooltip(callsign || "Unidentified aircraft")
        .addTo(map);
    });
    if (bounds.length > 1)
      map.fitBounds(L.latLngBounds(bounds), { padding: [30, 30] });
    return () => {
      map.remove();
    };
  }, [locations, sightings]);
  return (
    <div
      ref={element}
      className="map dashboard-map"
      aria-label="Nearby aircraft map"
    />
  );
}
