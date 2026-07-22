import asyncio
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx


@dataclass(frozen=True)
class Region:
    north: float
    south: float
    west: float
    east: float
    key: str


@dataclass(frozen=True)
class NormalizedFlight:
    flight_id: str
    provider_flight_id: str | None
    latitude: float
    longitude: float
    observed_at: datetime
    altitude_ft: int | None = None
    heading: float | None = None
    ground_speed_knots: float | None = None
    callsign: str | None = None
    airline: str | None = None
    origin_city: str | None = None
    destination_city: str | None = None
    aircraft_type: str | None = None
    registration: str | None = None


class FlightProvider(Protocol):
    provider_name: str

    async def get_flights_in_region(self, region: Region) -> list[NormalizedFlight]: ...
    async def get_flight_details(self, flight_id: str) -> NormalizedFlight | None: ...
    async def health_check(self) -> bool: ...
    def supports_feature(self, feature: str) -> bool: ...


class ProviderError(RuntimeError):
    pass


class ProviderRateLimited(ProviderError):
    def __init__(self, message: str, retry_after_seconds: int = 60) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


async def bounded_retry(operation: Any, attempts: int = 3, base_delay: float = 0.25) -> Any:
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            return await operation()
        except ProviderRateLimited:
            raise
        except (TimeoutError, httpx.TransportError, ProviderError) as error:
            last = error
            if attempt + 1 < attempts:
                await asyncio.sleep(base_delay * (2**attempt) + random.uniform(0, base_delay))
    raise ProviderError("Provider request failed after bounded retries") from last


def parse_flight_record(record: dict[str, Any], now: datetime | None = None) -> NormalizedFlight:
    try:
        latitude, longitude = float(record["latitude"]), float(record["longitude"])
        identity = str(record.get("id") or record.get("icao24") or "").strip()
    except (KeyError, TypeError, ValueError) as error:
        raise ProviderError("Malformed flight position") from error
    if not identity or not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ProviderError("Malformed flight identity or coordinates")
    altitude = record.get("altitude")
    return NormalizedFlight(
        flight_id=identity,
        provider_flight_id=str(record.get("id")) if record.get("id") else None,
        latitude=latitude,
        longitude=longitude,
        observed_at=now or datetime.now(timezone.utc),
        altitude_ft=int(altitude) if altitude is not None else None,
        heading=float(record["heading"]) if record.get("heading") is not None else None,
        ground_speed_knots=float(record["ground_speed"])
        if record.get("ground_speed") is not None
        else None,
        callsign=str(record["callsign"]).strip() or None
        if record.get("callsign") is not None
        else None,
    )


def parse_fr24_feed_item(
    provider_id: str, values: Any, now: datetime | None = None
) -> NormalizedFlight:
    """Normalize one undocumented FR24 feed array without leaking positional fields."""
    if not isinstance(values, list) or len(values) < 11:
        raise ProviderError("Malformed FlightRadar24 feed record")
    try:
        latitude = float(values[1])
        longitude = float(values[2])
        identity = str(values[0] or provider_id).strip()
        observed = datetime.fromtimestamp(float(values[10]), timezone.utc)
    except (TypeError, ValueError, OverflowError) as error:
        raise ProviderError("Malformed FlightRadar24 flight position") from error
    if not identity or not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ProviderError("Malformed FlightRadar24 identity or coordinates")

    def number(index: int, cast: Any = float) -> Any | None:
        try:
            value = values[index]
            return None if value in (None, "") else cast(value)
        except (IndexError, TypeError, ValueError):
            return None

    def string(index: int) -> str | None:
        try:
            value = str(values[index]).strip()
            return value or None
        except (IndexError, TypeError):
            return None

    return NormalizedFlight(
        flight_id=identity,
        provider_flight_id=provider_id,
        latitude=latitude,
        longitude=longitude,
        observed_at=observed if now is None else now,
        altitude_ft=number(4, int),
        heading=number(3),
        ground_speed_knots=number(5),
        callsign=string(16) or string(13),
        aircraft_type=string(8),
        origin_city=string(11),
        destination_city=string(12),
        airline=string(18),
        registration=string(9),
    )


def _deep_get(value: Any, *path: str) -> Any:
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def merge_fr24_details(flight: NormalizedFlight, payload: Any) -> NormalizedFlight:
    if not isinstance(payload, dict):
        raise ProviderError("Malformed FlightRadar24 detail response")
    callsign = _deep_get(payload, "identification", "callsign") or flight.callsign
    airline = _deep_get(payload, "airline", "name") or flight.airline
    aircraft_type = _deep_get(payload, "aircraft", "model", "text") or flight.aircraft_type
    registration = _deep_get(payload, "aircraft", "registration") or flight.registration
    origin = _deep_get(payload, "airport", "origin", "position", "region", "city")
    destination = _deep_get(payload, "airport", "destination", "position", "region", "city")
    return NormalizedFlight(
        **{
            **flight.__dict__,
            "callsign": str(callsign).strip() or None if callsign is not None else None,
            "airline": str(airline).strip() or None if airline is not None else None,
            "aircraft_type": str(aircraft_type).strip() or None
            if aircraft_type is not None
            else None,
            "registration": str(registration).strip() or None
            if registration is not None
            else None,
            "origin_city": str(origin).strip() or None
            if origin is not None
            else flight.origin_city,
            "destination_city": str(destination).strip() or None
            if destination is not None
            else flight.destination_city,
        }
    )


class FlightRadar24Provider:
    """Cautious adapter for unofficial public FR24 endpoints; no access-control bypasses."""

    provider_name = "flightradar24"

    # FlightRadarAPI enables these position sources for its tracker requests.
    # Ground targets and airport vehicles are intentionally excluded here.
    _feed_params = {
        "faa": "1",
        "satellite": "1",
        "mlat": "1",
        "flarm": "1",
        "adsb": "1",
        "gnd": "0",
        "air": "1",
        "vehicles": "0",
        "estimated": "1",
        "gliders": "1",
        "maxage": "14400",
        "stats": "1",
        "limit": "5000",
    }

    def __init__(
        self,
        base_url: str,
        details_url: str,
        timeout_seconds: float = 10,
        detail_ttl_seconds: int = 900,
        detail_requests_per_cycle: int = 3,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._details_url = details_url.rstrip("/")
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            headers={"User-Agent": "AirSpace/0.1 (+self-hosted aircraft notifications)"},
            follow_redirects=False,
        )
        self._owns_client = client is None
        self._detail_ttl = timedelta(seconds=detail_ttl_seconds)
        self._details: dict[str, tuple[datetime, NormalizedFlight]] = {}
        self._detail_budget_default = detail_requests_per_cycle
        self._detail_budget = detail_requests_per_cycle
        self._blocked_until: dict[str, float] = {}

    def begin_poll_cycle(self) -> None:
        self._detail_budget = self._detail_budget_default

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def supports_feature(self, feature: str) -> bool:
        return feature in {"regional_positions", "flight_details"}

    async def _json(self, url: str, params: dict[str, str]) -> Any:
        host = urlsplit(url).netloc
        remaining = self._blocked_until.get(host, 0) - time.monotonic()
        if remaining > 0:
            raise ProviderRateLimited(
                f"FlightRadar24 host is cooling down for {remaining:.0f} seconds",
                max(1, round(remaining)),
            )
        response = await self._client.get(url, params=params)
        if response.status_code == 429:
            try:
                retry_after = int(response.headers.get("Retry-After", "60"))
            except ValueError:
                retry_after = 60
            retry_after = min(900, max(30, retry_after))
            self._blocked_until[host] = time.monotonic() + retry_after
            raise ProviderRateLimited(
                f"FlightRadar24 rate limited the request; cooling down {retry_after} seconds",
                retry_after,
            )
        if response.status_code >= 500:
            raise ProviderError(f"FlightRadar24 upstream error ({response.status_code})")
        if response.status_code != 200:
            raise ProviderError(f"FlightRadar24 request rejected ({response.status_code})")
        try:
            return response.json()
        except ValueError as error:
            raise ProviderError("FlightRadar24 returned malformed JSON") from error

    async def get_flights_in_region(self, region: Region) -> list[NormalizedFlight]:
        url = f"{self._base_url}/zones/fcgi/feed.js"
        bounds = f"{region.north},{region.south},{region.west},{region.east}"
        payload = await bounded_retry(
            lambda: self._json(url, {**self._feed_params, "bounds": bounds})
        )
        if not isinstance(payload, dict):
            raise ProviderError("FlightRadar24 feed was not an object")
        metadata_keys = {"full_count", "version", "stats", "copyright"}
        visible = payload.get("stats", {}).get("visible", {})
        metadata_only = not (payload.keys() - metadata_keys) and (
            isinstance(visible, dict) and visible and not any(visible.values())
        )
        if metadata_only:
            payload = await bounded_retry(lambda: self._json(url, {"bounds": bounds}))
            if not isinstance(payload, dict):
                raise ProviderError("FlightRadar24 fallback feed was not an object")
        flights: list[NormalizedFlight] = []
        for provider_id, values in payload.items():
            if provider_id in {"full_count", "version", "stats"}:
                continue
            try:
                flights.append(parse_fr24_feed_item(str(provider_id), values))
            except ProviderError:
                continue
        return flights

    async def enrich(self, flight: NormalizedFlight) -> NormalizedFlight:
        provider_id = flight.provider_flight_id
        if not provider_id:
            return flight
        cached = self._details.get(provider_id)
        now = datetime.now(timezone.utc)
        if cached and now - cached[0] < self._detail_ttl:
            detail = cached[1]
            return NormalizedFlight(
                **{
                    **flight.__dict__,
                    "callsign": detail.callsign or flight.callsign,
                    "airline": detail.airline or flight.airline,
                    "origin_city": detail.origin_city or flight.origin_city,
                    "destination_city": detail.destination_city or flight.destination_city,
                    "aircraft_type": detail.aircraft_type or flight.aircraft_type,
                }
            )
        if self._detail_budget <= 0:
            return flight
        self._detail_budget -= 1
        payload = await bounded_retry(
            lambda: self._json(f"{self._details_url}/clickhandler/", {"flight": provider_id})
        )
        detailed = merge_fr24_details(flight, payload)
        self._details[provider_id] = (now, detailed)
        return detailed

    async def get_flight_details(self, flight_id: str) -> NormalizedFlight | None:
        cached = self._details.get(flight_id)
        if cached and datetime.now(timezone.utc) - cached[0] < self._detail_ttl:
            return cached[1]
        return None

    async def health_check(self) -> bool:
        response = await self._client.get(
            f"{self._base_url}/zones/fcgi/feed.js", params={"bounds": "1,0,0,1"}
        )
        return response.status_code == 200
