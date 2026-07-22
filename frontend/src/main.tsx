import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { api, Profile, type Sighting } from "./api";
import { MapPicker } from "./components/MapPicker";
import { FlightMap } from "./components/FlightMap";
import { LocationSettings } from "./components/LocationSettings";
import { AdminApp } from "./components/AdminApp";
import { AddressSearch } from "./components/AddressSearch";
import { SightingCard } from "./components/SightingCard";
import { isLiveSighting } from "./sightings";
import "./style.css";
const presets = {
  "Directly overhead": 1.5,
  "Very close": 4,
  Nearby: 8,
  "Wider area": 20,
};
function needsIosInstallation(): boolean {
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const legacyStandalone = Boolean(
    (navigator as Navigator & { standalone?: boolean }).standalone,
  );
  return (
    ios &&
    !legacyStandalone &&
    !window.matchMedia("(display-mode: standalone)").matches
  );
}
function App() {
  const [profile, setProfile] = useState<Profile | null>(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [step, setStep] = useState(0),
    [position, setPosition] = useState<{
      latitude: number;
      longitude: number;
    } | null>(null),
    [radius, setRadius] = useState(8),
    [adding, setAdding] = useState(false),
    [status, setStatus] = useState("not_configured"),
    [sightings, setSightings] = useState<Sighting[]>([]);
  useEffect(() => {
    api
      .profile()
      .then(setProfile)
      .catch(() => {})
      .finally(() => setLoading(false));
    api
      .status()
      .then((s) => setStatus(s.provider))
      .catch(() => {});
    if ("serviceWorker" in navigator)
      navigator.serviceWorker.register("/sw.js");
  }, []);
  useEffect(() => {
    if (profile)
      api
        .sightings()
        .then(setSightings)
        .catch(() => {});
  }, [profile]);
  useEffect(() => {
    if (!profile) return;
    let active = true;
    const refreshSightings = () =>
      api
        .sightings()
        .then((next) => {
          if (active) setSightings(next);
        })
        .catch(() => {});
    const events = new EventSource("/api/events");
    events.onopen = () =>
      setError((current) =>
        current === "Live updates are reconnecting…" ? "" : current,
      );
    events.addEventListener("sightings", (event) => {
      try {
        setSightings(JSON.parse((event as MessageEvent).data));
      } catch {
        // Ignore a malformed event; the next server event contains a full snapshot.
      }
    });
    events.onerror = () => {
      setError("Live updates are reconnecting…");
      void refreshSightings();
    };
    const fallbackTimer = window.setInterval(refreshSightings, 15_000);
    return () => {
      active = false;
      window.clearInterval(fallbackTimer);
      events.close();
    };
  }, [profile]);
  useEffect(() => {
    if (step === 5)
      api
        .profile()
        .then(setProfile)
        .catch((e) => setError(String(e)));
  }, [step]);
  useEffect(() => {
    if (profile && profile.locations.length === 0 && step === 0) setStep(1);
  }, [profile, step]);
  async function refreshProfile() {
    setProfile(await api.profile());
  }
  const locate = () => {
    if (!window.isSecureContext) {
      setError("Current location requires HTTPS. Open AirSpace through your secure reverse-proxy address, then try again.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setPosition({
          latitude: p.coords.latitude,
          longitude: p.coords.longitude,
        });
        setStep(2);
      },
      () =>
        setError(
          "We could not use this device’s location. Enter coordinates or choose a point on the map when available.",
        ),
    );
  };
  async function begin() {
    try {
      setError("");
      const p = await api.createProfile(
        Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
      );
      setProfile(p);
      setStep(1);
    } catch (e) {
      setError(String(e));
    }
  }
  async function save() {
    if (!position) return;
    try {
      await api.addLocation({
        label: "your circle",
        ...position,
        radius_km: radius,
        detection_mode: "all",
        facing_direction: 0,
        fov_width: 360,
        overhead_threshold_km: 1,
        notification_cooldown_seconds: 1800,
      });
      setStep(4);
    } catch (e) {
      setError(String(e));
    }
  }
  async function saveAdditional() {
    if (!position) return;
    try {
      await api.addLocation({
        label: "Another viewing spot",
        ...position,
        radius_km: radius,
        detection_mode: "all",
        facing_direction: 0,
        fov_width: 360,
        overhead_threshold_km: 1,
        notification_cooldown_seconds: 1800,
      });
      await refreshProfile();
      setAdding(false);
      setPosition(null);
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : "Location could not be added.",
      );
    }
  }
  async function notify() {
    if (!("Notification" in window) || !("serviceWorker" in navigator)) {
      setError(
        "This browser does not support plane notifications. You can still use the live dashboard.",
      );
      return;
    }
    const result = await Notification.requestPermission();
    if (result !== "granted") {
      setError(
        "Notifications were not enabled. You can change this later in browser settings.",
      );
      return;
    }
    let stage = "service-worker";
    let registration: ServiceWorkerRegistration | undefined;
    let publicKeyLength: number | undefined;
    try {
      registration = await navigator.serviceWorker.ready;
      stage = "public-key";
      const { public_key } = await api.pushKey();
      publicKeyLength = public_key.length;
      const padding = "=".repeat((4 - (public_key.length % 4)) % 4),
        raw = atob(
          (public_key + padding).replace(/-/g, "+").replace(/_/g, "/"),
        ),
        key = Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
      stage = "push-service-subscribe";
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: key,
      });
      stage = "airspace-registration";
      await api.registerPush(subscription);
      setStep(5);
    } catch (e) {
      const errorName = e instanceof DOMException || e instanceof Error ? e.name : "UnknownError";
      const errorMessage = e instanceof Error ? e.message : String(e);
      const diagnostic = {
        stage,
        error_name: errorName,
        error_message: errorMessage,
        permission: Notification.permission,
        secure_context: window.isSecureContext,
        service_worker_state: registration?.active?.state || null,
        push_manager_available: Boolean(registration && "pushManager" in registration),
        public_key_length: publicKeyLength,
        platform: navigator.userAgent,
      };
      console.error("AirSpace push diagnostic", diagnostic, e);
      let diagnosticId = "not recorded";
      try {
        diagnosticId = (await api.reportPushDiagnostic(diagnostic)).diagnostic_id;
      } catch (reportError) {
        console.error("AirSpace could not report push diagnostic", reportError);
      }
      setError(`Push failed at ${stage}: ${errorName}: ${errorMessage} (diagnostic ${diagnosticId})`);
    }
  }
  if (loading)
    return (
      <main>
        <p>Opening AirSpace…</p>
      </main>
    );
  if (!profile || profile.locations.length === 0) {
    return (
      <main>
        <header>
          <span className="brand">AirSpace</span>
          <span className="status">
            ●{" "}
            {status === "healthy"
              ? "Live flights"
              : "Service status: " + status}
          </span>
        </header>
        <section className="hero">
          <p className="eyebrow">PLANES, MADE FRIENDLY</p>
          <h1>
            Know what’s flying
            <br />
            <em>over your home.</em>
          </h1>
          <p>
            Choose a viewing spot and AirSpace will tell you when an interesting
            aircraft is nearby—no aviation knowledge needed.
          </p>
          {step === 0 && (
            <button onClick={begin}>
              Get started <span>→</span>
            </button>
          )}
          {step === 1 && (
            <div className="card">
              <h2>Where do you watch planes?</h2>
              <p>
                Your exact location is private to this browser profile. We do
                not sell it or use advertising trackers.
              </p>
              <button onClick={locate}>Use my current location</button>
              <AddressSearch
                onChoose={(result) => {
                  setPosition(result);
                }}
              />
              <MapPicker
                position={position}
                radiusKm={radius}
                onChange={setPosition}
              />
              {position && (
                <button onClick={() => setStep(2)}>
                  Use this map location
                </button>
              )}
              <p className="fine">
                Clearing browser data or deleting the installed app may remove
                access to this profile.
              </p>
            </div>
          )}
          {step === 2 && (
            <div className="card">
              <h2>How close should planes be?</h2>
              <div className="choices">
                {Object.entries(presets).map(([n, v]) => (
                  <button
                    className={radius === v ? "selected" : ""}
                    onClick={() => setRadius(v)}
                    key={n}
                  >
                    {n}
                    <small>{v} km · {(v * 0.621371).toFixed(1)} mi</small>
                  </button>
                ))}
              </div>
              <button onClick={save}>Save your circle</button>
            </div>
          )}
          {step === 4 && (
            <div className="card">
              <h2>Ready for plane alerts?</h2>
              {needsIosInstallation() && (
                <p>
                  On iPhone or iPad, first tap Safari’s Share button, choose{" "}
                  <strong>Add to Home Screen</strong>, then open AirSpace from
                  its new Home Screen icon to enable alerts.
                </p>
              )}
              <p>
                Tap the button, then allow notifications when your browser asks.
              </p>
              <button onClick={notify} disabled={needsIosInstallation()}>
                Enable Plane Notifications
              </button>
              <button className="quiet" onClick={() => setStep(5)}>
                Not now
              </button>
            </div>
          )}
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
        </section>
      </main>
    );
  }
  const nearby = sightings.filter(isLiveSighting);
  const selectedSighting = new URLSearchParams(location.search).get("sighting");
  const history = sightings.filter((s) => s.state !== "held" && !isLiveSighting(s));
  return (
    <main>
      <header>
        <span className="brand">AirSpace</span>
        <span className="status">
          ● {status === "healthy" ? "Tracking live" : "Data " + status}
        </span>
      </header>
      <section>
        <p className="eyebrow">YOUR AIRSPACE</p>
        <h1>{nearby.length ? "A plane is nearby" : "The sky is quiet"}</h1>
        <p>
          {nearby.length
            ? "Here’s what’s passing your viewing spot right now."
            : "We’re watching your circle and you'll get a notification when something is overhead"}
        </p>
        <FlightMap locations={profile.locations} sightings={nearby} />
        <div className="grid">
          {nearby.map((s) => (
            <SightingCard key={s.id} sighting={s} expanded={selectedSighting === s.id} />
          ))}
        </div>
        <details open={Boolean(selectedSighting)}>
          <summary>Recent sighting history ({history.length})</summary>
          <div className="grid history">
            {history.length ? history.map((s) => <SightingCard key={`history-${s.id}`} sighting={s} expanded={selectedSighting === s.id} />) : <p>No completed sightings yet.</p>}
          </div>
        </details>
        {error && (
          <p role="status" className="error">
            {error}
          </p>
        )}
        <details>
          <summary>Privacy and profile settings</summary>
          <button
            onClick={() => {
              setPosition(null);
              setAdding(!adding);
            }}
          >
            {adding ? "Cancel adding location" : "Add another location"}
          </button>
          {adding && (
            <div className="location-settings">
              <h2>Choose another viewing spot</h2>
              <button onClick={locate}>Use my current location</button>
              <AddressSearch onChoose={setPosition} />
              <MapPicker
                position={position}
                radiusKm={radius}
                onChange={setPosition}
              />
              <label>
                Notification distance
                <select
                  value={radius}
                  onChange={(event) => setRadius(Number(event.target.value))}
                >
                  {Object.entries(presets).map(([name, value]) => (
                    <option value={value} key={name}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
              {position && (
                <button onClick={saveAdditional}>Monitor this location</button>
              )}
            </div>
          )}
          {profile.locations.map((location) => (
            <LocationSettings
              key={location.id}
              location={location}
              onChanged={refreshProfile}
            />
          ))}
          <button
            onClick={async () => {
              try {
                const result = await api.testPush();
                setError(
                  result.delivered
                    ? "Test notification sent."
                    : "The test was queued but could not be delivered yet.",
                );
              } catch (testError) {
                setError(
                  testError instanceof Error
                    ? testError.message
                    : "The test notification could not be sent.",
                );
              }
            }}
          >
            Send a test notification
          </button>
          <button
            className="danger"
            onClick={async () => {
              if (confirm("Delete this profile and all its data?")) {
                await api.deleteProfile();
                location.reload();
              }
            }}
          >
            Delete all my data
          </button>
        </details>
      </section>
    </main>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {location.pathname.startsWith("/admin") ? <AdminApp /> : <App />}
  </React.StrictMode>,
);
