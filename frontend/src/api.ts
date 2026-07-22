export type Location = {
  id: string;
  label: string;
  latitude: number;
  longitude: number;
  radius_km: number;
  detection_mode: "all" | "directional";
  facing_direction: number;
  fov_width: number;
  enabled: boolean;
  created_at: string;
  normalized_address?: string;
  minimum_altitude_ft?: number;
  maximum_altitude_ft?: number;
  overhead_threshold_km: number;
  notification_cooldown_seconds: number;
  quiet_hours?: { enabled: boolean; start: string; end: string } | null;
};
export type Sighting = {
  id: string;
  location_id: string;
  state: string;
  first_detected_at: string;
  last_seen_at: string;
  minimum_distance_km: number;
  flight: {
    latitude?: number;
    longitude?: number;
    callsign?: string;
    airline?: string;
    origin_city?: string;
    destination_city?: string;
    aircraft_type?: string;
    altitude_ft?: number;
    heading?: number;
  };
};
export type Profile = {
  timezone: string;
  units: "imperial" | "metric";
  created_at: string;
  locations: Location[];
};
export type AddressResult = {
  label: string;
  latitude: number;
  longitude: number;
};
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    throw new Error(formatApiError(payload, response.status));
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
export function formatApiError(payload: unknown, status: number): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((item) => {
        if (!item || typeof item !== "object") return String(item);
        const issue = item as { msg?: string; loc?: unknown[] };
        const field = issue.loc?.at(-1);
        return `${field ? `${String(field)}: ` : ""}${issue.msg || "Invalid value"}`;
      }).join("; ");
    }
  }
  return `Request failed (${status})`;
}
export function browserPlatform(userAgent: string): string {
  return userAgent.slice(0, 120);
}
export const api = {
  profile: () => request<Profile>("/api/profile"),
  createProfile: (timezone: string) =>
    request<Profile>("/api/profiles", {
      method: "POST",
      body: JSON.stringify({ timezone, units: "imperial" }),
    }),
  addLocation: (value: Omit<Location, "id" | "enabled" | "created_at">) =>
    request<Location>("/api/locations", {
      method: "POST",
      body: JSON.stringify(value),
    }),
  updateLocation: (
    id: string,
    value: Omit<Location, "id" | "enabled" | "created_at">,
  ) =>
    request<Location>(`/api/locations/${id}`, {
      method: "PUT",
      body: JSON.stringify(value),
    }),
  deleteLocation: (id: string) =>
    request<void>(`/api/locations/${id}`, { method: "DELETE" }),
  deleteProfile: () => request<void>("/api/profile", { method: "DELETE" }),
  status: () => request<{ provider: string }>("/api/status"),
  sightings: () => request<Sighting[]>("/api/sightings"),
  searchAddresses: (query: string) =>
    request<AddressResult[]>(
      `/api/geocoding/search?q=${encodeURIComponent(query)}`,
    ),
  pushKey: () => request<{ public_key: string }>("/api/push-key"),
  reportPushDiagnostic: (diagnostic: Record<string, unknown>) =>
    request<{ diagnostic_id: string }>("/api/push-diagnostics", {
      method: "POST",
      body: JSON.stringify(diagnostic),
    }),
  registerPush: (subscription: PushSubscription) =>
    request<{ status: string }>("/api/push-subscriptions", {
      method: "POST",
      body: JSON.stringify({
        ...subscription.toJSON(),
        platform: browserPlatform(navigator.userAgent),
      }),
    }),
  testPush: () =>
    request<{ queued: number; delivered: number }>(
      "/api/push-subscriptions/test",
      {
        method: "POST",
      },
    ),
  adminSummary: (password: string) =>
    request<Record<string, unknown>>("/api/admin/summary", {
      headers: { Authorization: `Bearer ${password}` },
    }),
  adminCleanup: (password: string) =>
    request<Record<string, number>>("/api/admin/cleanup", {
      method: "POST",
      headers: { Authorization: `Bearer ${password}` },
    }),
};
