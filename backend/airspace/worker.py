import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from .config import Settings
from .database import SessionLocal
from .models import MonitoredLocation, PollingRegion, ProviderHealth
from .polling import LocationPoint, deduplicate_flights, group_regions
from .providers import FlightProvider, FlightRadar24Provider, NormalizedFlight, ProviderError
from .tracking import MAP_BUFFER_KM, TrackingService
from .notifications import PushDispatcher

LOGGER = logging.getLogger(__name__)


class PollingWorker:
    def __init__(self, provider: FlightProvider, settings: Settings) -> None:
        self.provider = provider
        self.settings = settings
        self.tracker = TrackingService(settings.stale_after_seconds)
        self.dispatcher = PushDispatcher(settings)
        self.running = False
        self.last_cycle_finished_at: datetime | None = None
        self.active_region_count = 0
        self.deferred_region_count = 0
        self._region_offset = 0

    async def run(self) -> None:
        self.running = True
        try:
            while self.running:
                started = asyncio.get_running_loop().time()
                try:
                    await self.poll_once()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    LOGGER.exception("Unexpected polling cycle failure; retrying next interval")
                elapsed = asyncio.get_running_loop().time() - started
                await asyncio.sleep(max(1, self.settings.poll_interval_seconds - elapsed))
        finally:
            self.running = False

    def stop(self) -> None:
        self.running = False

    async def poll_once(self) -> None:
        now = datetime.now(timezone.utc)
        begin_cycle = getattr(self.provider, "begin_poll_cycle", None)
        if begin_cycle:
            begin_cycle()
        with SessionLocal() as db:
            health = db.get(ProviderHealth, self.provider.provider_name)
            if health is None:
                health = ProviderHealth(provider=self.provider.provider_name)
                db.add(health)
            health.last_attempt_at = now
            locations = db.scalars(select(MonitoredLocation).where(MonitoredLocation.enabled)).all()
            regions = group_regions(
                LocationPoint(row.id, row.latitude, row.longitude, row.radius_km + MAP_BUFFER_KM)
                for row in locations
            )
            flights_by_location: dict[str, list[NormalizedFlight]] = {}
            successful: set[str] = set()
            errors: list[str] = []
            region_items = sorted(regions.items(), key=lambda item: item[0].key)
            self.active_region_count = min(len(region_items), self.settings.max_regions_per_cycle)
            self.deferred_region_count = max(0, len(region_items) - self.active_region_count)
            if region_items:
                start = self._region_offset % len(region_items)
                rotated = region_items[start:] + region_items[:start]
                selected_regions = rotated[: self.settings.max_regions_per_cycle]
                self._region_offset = (start + len(selected_regions)) % len(region_items)
            else:
                selected_regions = []
            for region, location_ids in selected_regions:
                diagnostic = db.get(PollingRegion, region.key)
                if diagnostic is None:
                    diagnostic = PollingRegion(
                        key=region.key,
                        bounds={
                            "north": region.north,
                            "south": region.south,
                            "west": region.west,
                            "east": region.east,
                        },
                        request_count=0,
                        last_flight_count=0,
                    )
                    db.add(diagnostic)
                diagnostic.location_count = len(location_ids)
                diagnostic.request_count += 1
                diagnostic.last_polled_at = now
                try:
                    flights = deduplicate_flights(await self.provider.get_flights_in_region(region))
                    enriched: list[NormalizedFlight] = []
                    for flight in flights:
                        try:
                            enrich = getattr(self.provider, "enrich", None)
                            enriched.append(await enrich(flight) if enrich else flight)
                        except ProviderError:
                            enriched.append(flight)
                    diagnostic.last_flight_count = len(enriched)
                    diagnostic.last_error = None
                    successful.update(location_ids)
                    for location_id in location_ids:
                        flights_by_location.setdefault(location_id, []).extend(enriched)
                except ProviderError as error:
                    message = type(error).__name__
                    errors.append(message)
                    diagnostic.last_error = message
            if successful:
                flights_by_location = {
                    location_id: deduplicate_flights(flights)
                    for location_id, flights in flights_by_location.items()
                }
                self.tracker.process_cycle(db, flights_by_location, successful, now)
                health.last_success_at = now
                health.consecutive_failures = 0 if not errors else health.consecutive_failures
                health.status = "degraded" if errors else "healthy"
            else:
                health.consecutive_failures += 1
                health.status = "unavailable" if locations else "idle"
            health.last_error = ", ".join(errors[:3]) or None
            db.commit()
        await self.dispatcher.deliver_pending()
        self.last_cycle_finished_at = datetime.now(timezone.utc)


def build_worker(settings: Settings) -> tuple[PollingWorker, FlightRadar24Provider]:
    provider = FlightRadar24Provider(
        settings.provider_base_url,
        settings.provider_details_url,
        settings.provider_timeout_seconds,
        settings.provider_detail_ttl_seconds,
        settings.provider_detail_requests_per_cycle,
    )
    return PollingWorker(provider, settings), provider
