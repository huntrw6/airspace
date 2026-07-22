import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";

afterEach(() => vi.restoreAllMocks());

describe("profile API", () => {
  it("keeps valid zero coordinates", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            id: "zero",
            label: "Equator",
            latitude: 0,
            longitude: 0,
            radius_km: 8,
            detection_mode: "all",
            facing_direction: 0,
            fov_width: 360,
            enabled: true,
            created_at: new Date().toISOString(),
            overhead_threshold_km: 1,
            notification_cooldown_seconds: 1800,
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    const result = await api.addLocation({
      label: "Equator",
      latitude: 0,
      longitude: 0,
      radius_km: 8,
      detection_mode: "all",
      facing_direction: 0,
      fov_width: 360,
      overhead_threshold_km: 1,
      notification_cooldown_seconds: 1800,
    });
    expect(result.latitude).toBe(0);
    expect(result.longitude).toBe(0);
  });
  it("renders server errors as text values, not HTML", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            JSON.stringify({ detail: "<img src=x onerror=alert(1)>" }),
            { status: 422, headers: { "Content-Type": "application/json" } },
          ),
        ),
    );
    await expect(api.profile()).rejects.toThrow("<img src=x onerror=alert(1)>");
  });
});
