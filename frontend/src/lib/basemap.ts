const CARTO_DARK_TILES =
  "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png";

export const BASEMAP_ATTRIBUTION =
  '';

export function basemapTileUrl(
  apiKey: string = import.meta.env.VITE_CARTO_BASEMAPS_API_KEY ?? "",
): string {
  const key = apiKey.trim();
  return key ? `${CARTO_DARK_TILES}?key=${encodeURIComponent(key)}` : CARTO_DARK_TILES;
}
