import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlsplit

import httpx

from .config import Settings


@dataclass(frozen=True)
class AircraftPhoto:
    thumbnail_url: str
    page_url: str
    photographer: str


class AircraftPhotoService:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.AsyncClient(
            timeout=settings.aircraft_photos_timeout_seconds,
            headers={"User-Agent": settings.aircraft_photos_user_agent},
        )
        self._owns_client = client is None
        self._cache: dict[str, tuple[float, AircraftPhoto | None]] = {}

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def lookup(self, registration: str) -> AircraftPhoto | None:
        normalized = registration.strip().upper()
        if not normalized or len(normalized) > 20:
            return None
        cached = self._cache.get(normalized)
        now = time.monotonic()
        if cached and cached[0] > now:
            return cached[1]
        response = await self._client.get(
            f"{self._settings.aircraft_photos_base_url.rstrip('/')}/pub/photos/reg/"
            f"{quote(normalized, safe='')}"
        )
        response.raise_for_status()
        photo = self._parse(response.json())
        self._cache[normalized] = (
            now + self._settings.aircraft_photos_cache_seconds,
            photo,
        )
        return photo

    @staticmethod
    def _parse(payload: Any) -> AircraftPhoto | None:
        photos = payload.get("photos") if isinstance(payload, dict) else None
        if not isinstance(photos, list) or not photos or not isinstance(photos[0], dict):
            return None
        value = photos[0]
        thumbnail = value.get("thumbnail_large") or value.get("thumbnail")
        thumbnail_url = thumbnail.get("src") if isinstance(thumbnail, dict) else None
        page_url = value.get("link")
        photographer = value.get("photographer")
        if not isinstance(thumbnail_url, str) or not thumbnail_url.strip():
            return None
        if not isinstance(page_url, str) or not page_url.strip():
            return None
        if not isinstance(photographer, str) or not photographer.strip():
            return None
        thumbnail_host = (urlsplit(thumbnail_url).hostname or "").lower()
        page_host = (urlsplit(page_url).hostname or "").lower()
        if thumbnail_host not in {"t.plnspttrs.net", "img.planespotters.net"}:
            return None
        if page_host not in {"planespotters.net", "www.planespotters.net"}:
            return None
        return AircraftPhoto(thumbnail_url.strip(), page_url.strip(), photographer.strip())
