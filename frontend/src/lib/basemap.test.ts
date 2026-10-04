import { describe, expect, it } from "vitest";
import { basemapTileUrl } from "./basemap";

describe("basemap tile URL", () => {
  it("keeps Leaflet tile placeholders and safely encodes the key", () => {
    expect(basemapTileUrl(" key&value=1 ")).toBe(
      "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?key=key%26value%3D1",
    );
  });

  it.each(["", "   "])("does not send an empty key parameter for %j", (key) => {
    expect(basemapTileUrl(key)).toBe(
      "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    );
  });
});
