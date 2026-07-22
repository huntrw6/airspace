import { useState } from "react";
import { api, type Location } from "../api";

export function LocationSettings({
  location,
  onChanged,
}: {
  location: Location;
  onChanged: () => Promise<void>;
}) {
  const [label, setLabel] = useState(location.label);
  const [radius, setRadius] = useState(location.radius_km);
  const [direction, setDirection] = useState(
    location.detection_mode === "all"
      ? "all"
      : String(location.facing_direction),
  );
  const [quietEnabled, setQuietEnabled] = useState(
    Boolean(location.quiet_hours?.enabled),
  );
  const [quietStart, setQuietStart] = useState(
    location.quiet_hours?.start || "22:00",
  );
  const [quietEnd, setQuietEnd] = useState(
    location.quiet_hours?.end || "07:00",
  );
  const [message, setMessage] = useState("");
  const [minimumAltitude, setMinimumAltitude] = useState(location.minimum_altitude_ft?.toString() || "");
  const [maximumAltitude, setMaximumAltitude] = useState(location.maximum_altitude_ft?.toString() || "");
  const [cooldown, setCooldown] = useState(location.notification_cooldown_seconds);

  async function save() {
    setMessage("");
    try {
      await api.updateLocation(location.id, {
        label,
        latitude: location.latitude,
        longitude: location.longitude,
        normalized_address: location.normalized_address,
        radius_km: radius,
        detection_mode: direction === "all" ? "all" : "directional",
        facing_direction: direction === "all" ? 0 : Number(direction),
        fov_width: direction === "all" ? 360 : 120,
        minimum_altitude_ft: minimumAltitude ? Number(minimumAltitude) : undefined,
        maximum_altitude_ft: maximumAltitude ? Number(maximumAltitude) : undefined,
        overhead_threshold_km: location.overhead_threshold_km,
        notification_cooldown_seconds: cooldown,
        quiet_hours: quietEnabled
          ? { enabled: true, start: quietStart, end: quietEnd }
          : null,
      });
      await onChanged();
      setMessage("Settings saved.");
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Settings could not be saved.",
      );
    }
  }

  return (
    <fieldset className="location-settings">
      <legend>{location.label}</legend>
      <label>
        Friendly name
        <input
          value={label}
          maxLength={80}
          onChange={(event) => setLabel(event.target.value)}
        />
      </label>
      <label>
        Notification distance
        <select
          value={radius}
          onChange={(event) => setRadius(Number(event.target.value))}
        >
          <option value={1.5}>Directly overhead</option>
          <option value={4}>Very close</option>
          <option value={8}>Nearby</option>
          <option value={20}>Wider area</option>
        </select>
      </label>
      <label>
        Side to watch
        <select
          value={direction}
          onChange={(event) => setDirection(event.target.value)}
        >
          <option value="all">All directions</option>
          <option value="0">North side</option>
          <option value="90">East side</option>
          <option value="180">South side</option>
          <option value="270">West side</option>
        </select>
      </label>
      <label className="checkbox">
        <input
          type="checkbox"
          checked={quietEnabled}
          onChange={(event) => setQuietEnabled(event.target.checked)}
        />
        Use quiet hours
      </label>
      <details>
        <summary>Advanced aircraft filters</summary>
        <div className="time-fields">
          <label>Minimum altitude (ft)<input type="number" min="0" max="100000" value={minimumAltitude} onChange={(event) => setMinimumAltitude(event.target.value)} placeholder="Any" /></label>
          <label>Maximum altitude (ft)<input type="number" min="0" max="100000" value={maximumAltitude} onChange={(event) => setMaximumAltitude(event.target.value)} placeholder="Any" /></label>
        </div>
        <label>Repeat notification cooldown<select value={cooldown} onChange={(event) => setCooldown(Number(event.target.value))}><option value={300}>5 minutes</option><option value={900}>15 minutes</option><option value={1800}>30 minutes</option><option value={3600}>1 hour</option><option value={10800}>3 hours</option></select></label>
      </details>
      {quietEnabled && (
        <div className="time-fields">
          <label>
            Start
            <input
              type="time"
              value={quietStart}
              onChange={(event) => setQuietStart(event.target.value)}
            />
          </label>
          <label>
            End
            <input
              type="time"
              value={quietEnd}
              onChange={(event) => setQuietEnd(event.target.value)}
            />
          </label>
        </div>
      )}
      <button onClick={save}>Save changes</button>
      <button
        className="danger"
        onClick={async () => {
          if (confirm(`Stop monitoring ${location.label}?`)) {
            await api.deleteLocation(location.id);
            await onChanged();
          }
        }}
      >
        Remove location
      </button>
      {message && <p role="status">{message}</p>}
    </fieldset>
  );
}
