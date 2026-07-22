// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, type Location } from "../api";
import { LocationSettings } from "./LocationSettings";

afterEach(() => vi.restoreAllMocks());

const equator: Location = {
  id: "location-zero",
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
};

describe("location settings", () => {
  it("preserves zero coordinates while updating friendly settings", async () => {
    const update = vi.spyOn(api, "updateLocation").mockResolvedValue(equator);
    const changed = vi.fn().mockResolvedValue(undefined);
    render(<LocationSettings location={equator} onChanged={changed} />);
    fireEvent.change(screen.getByLabelText("Friendly name"), {
      target: { value: "Beach" },
    });
    fireEvent.click(screen.getByText("Save changes"));
    await waitFor(() => expect(update).toHaveBeenCalled());
    expect(update.mock.calls[0][1]).toMatchObject({
      label: "Beach",
      latitude: 0,
      longitude: 0,
    });
    expect(changed).toHaveBeenCalled();
  });
});
