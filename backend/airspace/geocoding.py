import asyncio
import time
from dataclasses import dataclass

import httpx

from .config import Settings


@dataclass(frozen=True)
class GeocodingResult:
    label: str
    latitude: float
    longitude: float


class Geocoder:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cache: dict[str, tuple[float, list[GeocodingResult]]] = {}
        self._lock = asyncio.Lock()
        self._last_request = 0.0

    async def search(self, query: str) -> list[GeocodingResult]:
        normalized = " ".join(query.casefold().split())
        cached = self._cache.get(normalized)
        now = time.monotonic()
        if cached and cached[0] > now:
            return cached[1]

        async with self._lock:
            cached = self._cache.get(normalized)
            now = time.monotonic()
            if cached and cached[0] > now:
                return cached[1]
            await asyncio.sleep(max(0, 1.0 - (now - self._last_request)))
            async with httpx.AsyncClient(
                base_url=self.settings.geocoding_base_url,
                timeout=self.settings.geocoding_timeout_seconds,
                headers={"User-Agent": self.settings.geocoding_user_agent},
            ) as client:
                response = await client.get(
                    "/search",
                    params={"q": query, "format": "jsonv2", "limit": 5, "addressdetails": 0},
                )
                self._last_request = time.monotonic()
                response.raise_for_status()
                results = [
                    GeocodingResult(
                        label=str(item["display_name"])[:300],
                        latitude=float(item["lat"]),
                        longitude=float(item["lon"]),
                    )
                    for item in response.json()
                    if "display_name" in item and "lat" in item and "lon" in item
                ]
                self._cache[normalized] = (
                    time.monotonic() + self.settings.geocoding_cache_seconds,
                    results,
                )
                return results
