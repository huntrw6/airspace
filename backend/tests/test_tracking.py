from dataclasses import replace
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, event, func, select
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


def test_two_kilometer_map_buffer_does_not_notify_until_circle_entry():
    db = database()
    location = seed(db)
    now = datetime.now(timezone.utc)
    service = TrackingService(120)
    preview = replace(flight(now), latitude=location.latitude + 11 / 111.32)
    service.process_cycle(db, {location.id: [preview]}, {location.id}, now)
    sighting = db.scalar(select(Sighting))
    assert sighting is not None
    assert sighting.state == "detected"
    assert sighting.first_in_view_at is None
    assert db.scalar(select(func.count()).select_from(NotificationDelivery)) == 0

    entered = replace(
        flight(now + timedelta(seconds=20)),
        latitude=location.latitude + 9 / 111.32,
    )
    service.process_cycle(db, {location.id: [entered]}, {location.id}, now + timedelta(seconds=20))
    db.refresh(sighting)
    assert sighting.state in {"approaching", "in_view"}
    assert sighting.first_in_view_at is not None
    assert db.scalar(select(func.count()).select_from(NotificationDelivery)) == 1


def test_observed_flight_leaving_map_buffer_moves_to_history_immediately():
    db = database()
    location = seed(db)
    now = datetime.now(timezone.utc)
    service = TrackingService(120)
    service.process_cycle(db, {location.id: [flight(now)]}, {location.id}, now)
    sighting = db.scalar(select(Sighting))
    outside = replace(
        flight(now + timedelta(seconds=20)),
        latitude=location.latitude + 12.5 / 111.32,
    )
    service.process_cycle(db, {location.id: [outside]}, {location.id}, now + timedelta(seconds=20))
    db.refresh(sighting)
    assert sighting.state == "historic"


def test_saved_directional_settings_no_longer_filter_aircraft():
    db = database()
    location = seed(db)
    location.detection_mode = "directional"
    location.facing_direction = 180
    location.fov_width = 30
    db.commit()
    now = datetime.now(timezone.utc)
    TrackingService(120).process_cycle(db, {location.id: [flight(now)]}, {location.id}, now)
    assert db.scalar(select(func.count()).select_from(Sighting)) == 1
    assert db.scalar(select(func.count()).select_from(NotificationDelivery)) == 1


def test_outside_aircraft_do_not_create_per_flight_sighting_queries():
    db = database()
    location = seed(db)
    now = datetime.now(timezone.utc)
    statements: list[str] = []

    def capture_statement(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(db.get_bind(), "before_cursor_execute", capture_statement)
    flights = [
        NormalizedFlight(
            flight_id=f"outside-{index}",
            provider_flight_id=f"provider-{index}",
            latitude=location.latitude + 0.2,
            longitude=location.longitude,
            altitude_ft=10000,
            observed_at=now,
        )
        for index in range(250)
    ]
    TrackingService(120).process_cycle(db, {location.id: flights}, {location.id}, now)
    sighting_selects = [
        statement
        for statement in statements
        if statement.lstrip().upper().startswith("SELECT") and "FROM sightings" in statement
    ]
    assert len(sighting_selects) <= 2


def test_quiet_hours_suppress_notification_intent():
    db = database()
    location = seed(db)
    location.quiet_hours = {"enabled": True, "start": "00:00", "end": "00:00"}
    db.commit()
    now = datetime.now(timezone.utc)
    TrackingService(120).process_cycle(db, {location.id: [flight(now)]}, {location.id}, now)
    assert db.scalar(select(func.count()).select_from(Sighting)) == 1
    assert db.scalar(select(func.count()).select_from(NotificationDelivery)) == 0


def test_location_cooldown_suppresses_repeat_delivery_for_same_aircraft():
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


def test_location_cooldown_does_not_suppress_a_different_aircraft():
    db = database()
    location = seed(db)
    now = datetime.now(timezone.utc)
    service = TrackingService(120)
    service.process_cycle(db, {location.id: [flight(now)]}, {location.id}, now)
    other = replace(
        flight(now + timedelta(minutes=5)),
        flight_id="different-aircraft",
        provider_flight_id="provider-2",
        callsign="AS456",
    )
    service.process_cycle(db, {location.id: [other]}, {location.id}, other.observed_at)
    assert db.scalar(select(func.count()).select_from(Sighting)) == 2
    assert db.scalar(select(func.count()).select_from(NotificationDelivery)) == 2
