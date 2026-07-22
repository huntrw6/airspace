from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import airspace.worker as worker_module
from airspace.config import Settings
from airspace.database import Base
from airspace.models import (
    MonitoredLocation,
    NotificationDelivery,
    Profile,
    ProviderHealth,
    PushSubscription,
    Sighting,
)
from airspace.providers import NormalizedFlight, Region
from airspace.worker import PollingWorker


class FakeProvider:
    provider_name = "fake"

    def __init__(self) -> None:
        self.calls: list[Region] = []
        self.now = datetime.now(timezone.utc)

    async def get_flights_in_region(self, region: Region) -> list[NormalizedFlight]:
        self.calls.append(region)
        return [
            NormalizedFlight(
                "shared-flight",
                "provider-1",
                38.605,
                -121.395,
                self.now,
                altitude_ft=9000,
                callsign="AS123",
            )
        ]

    async def get_flight_details(self, flight_id: str):
        return None

    async def health_check(self) -> bool:
        return True

    def supports_feature(self, feature: str) -> bool:
        return True


class IntermittentlyEmptyProvider(FakeProvider):
    def __init__(self) -> None:
        super().__init__()
        self.empty = False
        self.cycle_feed_requests = 0
        self.cycle_raw_aircraft = 0
        self.cycle_airborne_aircraft = 0
        self.cycle_empty_responses = 0
        self.session_resets = 0

    def begin_poll_cycle(self) -> None:
        self.cycle_feed_requests = 0
        self.cycle_raw_aircraft = 0
        self.cycle_airborne_aircraft = 0
        self.cycle_empty_responses = 0

    async def get_flights_in_region(self, region: Region) -> list[NormalizedFlight]:
        if self.empty:
            self.cycle_feed_requests += 2
            self.cycle_empty_responses += 1
            return []
        flights = await super().get_flights_in_region(region)
        self.cycle_feed_requests += 1
        self.cycle_raw_aircraft += len(flights)
        self.cycle_airborne_aircraft += len(flights)
        return flights

    async def reset_connection(self) -> bool:
        self.session_resets += 1
        return True


def add_profile(db: Session, suffix: str, latitude: float, longitude: float) -> None:
    profile = Profile(session_hash=suffix * 64)
    db.add(profile)
    db.flush()
    db.add(
        MonitoredLocation(
            profile_id=profile.id,
            label=f"Home {suffix}",
            latitude=latitude,
            longitude=longitude,
            radius_km=2,
            detection_mode="all",
            facing_direction=0,
            fov_width=360,
            overhead_threshold_km=1,
            notification_cooldown_seconds=1800,
        )
    )
    db.add(
        PushSubscription(
            profile_id=profile.id,
            endpoint_hash=suffix * 64,
            subscription_json={"endpoint": f"https://push.invalid/{suffix}", "keys": {}},
        )
    )


@pytest.mark.asyncio
async def test_two_profiles_share_region_and_replay_is_deduplicated(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(worker_module, "SessionLocal", factory)
    with factory() as db:
        add_profile(db, "a", 38.60, -121.40)
        add_profile(db, "b", 38.61, -121.39)
        db.commit()

    provider = FakeProvider()
    settings = Settings(
        database_url="sqlite://",
        session_days=365,
        max_locations_per_profile=5,
        max_subscriptions_per_profile=5,
        poll_interval_seconds=30,
        stale_after_seconds=120,
        history_retention_days=60,
        max_regions_per_cycle=10,
        provider_enabled=False,
    )
    worker = PollingWorker(provider, settings)
    await worker.poll_once()
    assert len(provider.calls) == 1
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Sighting)) == 2
        assert db.scalar(select(func.count()).select_from(NotificationDelivery)) == 2

    provider.now += timedelta(seconds=20)
    await worker.poll_once()
    assert len(provider.calls) == 2
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Sighting)) == 2
        assert db.scalar(select(func.count()).select_from(NotificationDelivery)) == 2


@pytest.mark.asyncio
async def test_worker_retries_after_unexpected_cycle_failure(monkeypatch):
    worker = PollingWorker(FakeProvider(), Settings(provider_enabled=False))
    attempts = 0

    async def failing_poll() -> None:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("unexpected")

    async def stop_after_interval(_: float) -> None:
        worker.stop()

    monkeypatch.setattr(worker, "poll_once", failing_poll)
    monkeypatch.setattr(worker_module.asyncio, "sleep", stop_after_interval)
    await worker.run()
    assert attempts == 1
    assert not worker.running


@pytest.mark.asyncio
async def test_transport_failure_is_contained_and_recorded(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(worker_module, "SessionLocal", factory)
    with factory() as db:
        add_profile(db, "c", 38.60, -121.40)
        db.commit()

    provider = FakeProvider()

    async def connection_failure(_: Region) -> list[NormalizedFlight]:
        request = httpx.Request("GET", "https://feed.invalid")
        raise httpx.ConnectError("upstream unavailable", request=request)

    monkeypatch.setattr(provider, "get_flights_in_region", connection_failure)
    worker = PollingWorker(provider, Settings(provider_enabled=False))
    await worker.poll_once()

    with factory() as db:
        health = db.get(ProviderHealth, "fake")
        assert health is not None
        assert health.status == "unavailable"
        assert health.last_error == "ConnectError"
        assert health.consecutive_failures == 1


@pytest.mark.asyncio
async def test_repeated_all_empty_feeds_preserve_aircraft_and_reset_session(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(worker_module, "SessionLocal", factory)
    with factory() as db:
        add_profile(db, "e", 38.60, -121.40)
        db.commit()

    provider = IntermittentlyEmptyProvider()
    worker = PollingWorker(
        provider,
        Settings(provider_enabled=False, provider_empty_cycles_before_reset=2),
    )
    await worker.poll_once()
    with factory() as db:
        initial_health = db.get(ProviderHealth, "fake")
        sighting = db.scalar(select(Sighting))
        assert initial_health is not None and sighting is not None
        successful_at = initial_health.last_success_at
        original_last_seen = sighting.last_seen_at

    provider.empty = True
    await worker.poll_once()
    with factory() as db:
        health = db.get(ProviderHealth, "fake")
        sighting = db.scalar(select(Sighting))
        assert health is not None and sighting is not None
        assert health.status == "degraded"
        assert health.last_success_at == successful_at
        assert health.last_error == "All 1 provider regions returned empty feeds after fallback"
        assert sighting.last_seen_at == original_last_seen
        assert health.consecutive_failures == 1
    assert worker.consecutive_all_empty_cycles == 1
    assert provider.session_resets == 0

    await worker.poll_once()
    assert provider.session_resets == 1
    assert worker.provider_session_resets == 1
    assert worker.consecutive_all_empty_cycles == 0
    assert worker.last_provider_session_reset_at is not None
