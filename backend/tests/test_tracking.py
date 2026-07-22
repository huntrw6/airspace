from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from airspace.database import Base
from airspace.models import (
    MonitoredLocation,
    NotificationDelivery,
    Profile,
    PushSubscription,
    Sighting,
)
from airspace.providers import NormalizedFlight
from airspace.tracking import TrackingService


def database() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def seed(db: Session) -> MonitoredLocation:
    profile = Profile(session_hash="x" * 64)
    db.add(profile)
    db.flush()
    location = MonitoredLocation(
        profile_id=profile.id,
        label="Home",
        latitude=38.5,
        longitude=-121.5,
        radius_km=10,
        detection_mode="all",
        facing_direction=0,
        fov_width=360,
        overhead_threshold_km=1,
        notification_cooldown_seconds=1800,
    )
    db.add(location)
    db.flush()
    db.add(
        PushSubscription(
            profile_id=profile.id,
            endpoint_hash="y" * 64,
            subscription_json={"endpoint": "https://push.invalid/a", "keys": {}},
        )
    )
    db.commit()
    return location


def flight(now: datetime) -> NormalizedFlight:
    return NormalizedFlight(
        flight_id="abc123",
        provider_flight_id="provider-1",
        latitude=38.51,
        longitude=-121.5,
        altitude_ft=8500,
        observed_at=now,
        callsign="WN123",
        airline="Southwest",
        origin_city="Phoenix",
        destination_city="Sacramento",
        aircraft_type="Boeing 737",
    )


def test_cycle_persists_one_sighting_and_notification():
    db = database()
    location = seed(db)
    now = datetime.now(timezone.utc)
    TrackingService(120).process_cycle(db, {location.id: [flight(now)]}, {location.id}, now)
    assert db.scalar(select(func.count()).select_from(Sighting)) == 1
    assert db.scalar(select(func.count()).select_from(NotificationDelivery)) == 1
    db.close()


def test_replay_in_new_session_does_not_duplicate():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as first:
        location = seed(first)
        location_id = location.id
        now = datetime.now(timezone.utc)
        TrackingService(120).process_cycle(first, {location_id: [flight(now)]}, {location_id}, now)
    with Session(engine) as restarted:
        replayed = flight(now + timedelta(seconds=20))
        TrackingService(120).process_cycle(
            restarted, {location_id: [replayed]}, {location_id}, replayed.observed_at
        )
        assert restarted.scalar(select(func.count()).select_from(Sighting)) == 1
        assert restarted.scalar(select(func.count()).select_from(NotificationDelivery)) == 1


def test_provider_outage_does_not_advance_or_hide_flight():
    db = database()
    location = seed(db)
    now = datetime.now(timezone.utc)
    service = TrackingService(120)
    service.process_cycle(db, {location.id: [flight(now)]}, {location.id}, now)
    before = db.scalar(select(Sighting))
    service.process_cycle(db, {}, set(), now + timedelta(minutes=10))
    db.refresh(before)
    assert before.state in {"in_view", "overhead"}


def test_successful_empty_poll_moves_visible_to_held_then_historic():
    db = database()
    location = seed(db)
    now = datetime.now(timezone.utc)
    service = TrackingService(120)
    service.process_cycle(db, {location.id: [flight(now)]}, {location.id}, now)
    service.process_cycle(db, {location.id: []}, {location.id}, now + timedelta(seconds=20))
    sighting = db.scalar(select(Sighting))
    assert sighting.state == "held"
    service.process_cycle(db, {location.id: []}, {location.id}, now + timedelta(minutes=3))
    db.refresh(sighting)
    assert sighting.state == "historic"


def test_stale_new_flight_creates_nothing():
    db = database()
    location = seed(db)
    now = datetime.now(timezone.utc)
    old = flight(now - timedelta(minutes=5))
    TrackingService(120).process_cycle(db, {location.id: [old]}, {location.id}, now)
    assert db.scalar(select(func.count()).select_from(Sighting)) == 0
    assert db.scalar(select(func.count()).select_from(NotificationDelivery)) == 0


def test_quiet_hours_suppress_notification_intent():
    db = database()
    location = seed(db)
    location.quiet_hours = {"enabled": True, "start": "00:00", "end": "00:00"}
    db.commit()
    now = datetime.now(timezone.utc)
    TrackingService(120).process_cycle(db, {location.id: [flight(now)]}, {location.id}, now)
    assert db.scalar(select(func.count()).select_from(Sighting)) == 1
    assert db.scalar(select(func.count()).select_from(NotificationDelivery)) == 0


def test_location_cooldown_suppresses_new_event_delivery():
    db = database()
    location = seed(db)
    now = datetime.now(timezone.utc)
    service = TrackingService(120)
    service.process_cycle(db, {location.id: [flight(now)]}, {location.id}, now)
    first = db.scalar(select(Sighting))
    first.state = "expired"
    db.commit()
    replay = flight(now + timedelta(minutes=5))
    service.process_cycle(db, {location.id: [replay]}, {location.id}, replay.observed_at)
    assert db.scalar(select(func.count()).select_from(Sighting)) == 2
    assert db.scalar(select(func.count()).select_from(NotificationDelivery)) == 1
