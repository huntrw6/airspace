import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

type Position = { latitude: number; longitude: number };

export function MapPicker({
  position,
  radiusKm,
  onChange,
}: {
  position: Position | null;
  radiusKm: number;
  onChange: (position: Position) => void;
}) {
  const element = useRef<HTMLDivElement>(null);
  const callback = useRef(onChange);
  callback.current = onChange;

  useEffect(() => {
    if (!element.current) return;
    const center: L.LatLngExpression = position
      ? [position.latitude, position.longitude]
      : [39, -98];
    const map = L.map(element.current, { scrollWheelZoom: false }).setView(
      center,
      position ? 13 : 3,
    );
    L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
      {
        maxZoom: 19,
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
      },
    ).addTo(map);
    let marker: L.CircleMarker | undefined;
    let radius: L.Circle | undefined;
    const draw = (point: Position) => {
      marker?.remove();
      radius?.remove();
      marker = L.circleMarker([point.latitude, point.longitude], {
        radius: 9,
        color: "#071a2b",
        fillColor: "#f1bb72",
        fillOpacity: 1,
      }).addTo(map);
      radius = L.circle([point.latitude, point.longitude], {
        radius: radiusKm * 1000,
        color: "#168ba4",
        fillOpacity: 0.12,
      }).addTo(map);
    };
    if (position) draw(position);
    map.on("click", (event: L.LeafletMouseEvent) => {
      const point = { latitude: event.latlng.lat, longitude: event.latlng.lng };
      draw(point);
      callback.current(point);
    });
    return () => {
      map.remove();
    };
  }, [position?.latitude, position?.longitude, radiusKm]);

  return (
    <div>
      <div
        ref={element}
        className="map"
        role="application"
        aria-label="Choose a viewing location on the map"
      />
      <div className="coordinate-fields" aria-label="Location coordinates">
        <label>
          Latitude
          <input
            inputMode="decimal"
            value={position?.latitude ?? ""}
            onChange={(event) => {
              const value = Number(event.target.value);
              if (Number.isFinite(value) && value >= -90 && value <= 90)
                onChange({
                  latitude: value,
                  longitude: position?.longitude ?? 0,
                });
            }}
          />
        </label>
        <label>
          Longitude
          <input
            inputMode="decimal"
            value={position?.longitude ?? ""}
            onChange={(event) => {
              const value = Number(event.target.value);
              if (Number.isFinite(value) && value >= -180 && value <= 180)
                onChange({
                  latitude: position?.latitude ?? 0,
                  longitude: value,
                });
            }}
          />
        </label>
      </div>
      <p className="fine">
        Tap the map or enter coordinates. Zero is a valid coordinate.
      </p>
    </div>
  );
}
