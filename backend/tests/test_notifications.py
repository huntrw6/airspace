from datetime import datetime, timezone

import pytest
import requests
from pywebpush import WebPushException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import airspace.notifications as notification_module
from airspace.config import Settings
from airspace.database import Base
from airspace.models import (
    MonitoredLocation,
    NotificationDelivery,
    Profile,
    PushSubscription,
    Sighting,
)
from airspace.notifications import (
    PushDispatcher,
    in_quiet_hours,
    is_helicopter,
    notification_payload,
)
from airspace.subscriptions import decrypt_subscription, encrypt_subscription
from airspace.generate_vapid import encoded_key_pair
from py_vapid import Vapid


def settings(**updates) -> Settings:
    values = {
        "session_pepper": "test-pepper",
        "admin_password": "test-admin",
        "vapid_private_key": "test-private-key",
        "vapid_public_key": "test-public-key",
        "public_url": "https://planes.example.com",
    }
    values.update(updates)
    return Settings(**values)


def test_subscription_encryption_round_trip_hides_endpoint():
    configured = settings()
    original = {"endpoint": "https://push.example/secret", "keys": {"p256dh": "a", "auth": "b"}}
    encrypted = encrypt_subscription(original, configured)
    assert "push.example" not in str(encrypted)
    assert decrypt_subscription(encrypted, configured) == original


def test_generated_vapid_keys_use_web_push_formats():
    public_key, private_key = encoded_key_pair()
    assert len(public_key) == 87
    assert Vapid.from_string(private_key).public_key is not None


def test_quiet_hours_cross_midnight_and_full_day():
    evening = datetime(2026, 7, 21, 23, 0, tzinfo=timezone.utc)
    morning = datetime(2026, 7, 21, 6, 0, tzinfo=timezone.utc)
    midday = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)
    quiet = {"enabled": True, "start": "22:00", "end": "07:00"}
    assert in_quiet_hours(quiet, "UTC", evening)
    assert in_quiet_hours(quiet, "UTC", morning)
    assert not in_quiet_hours(quiet, "UTC", midday)
    assert in_quiet_hours({"start": "00:00", "end": "00:00"}, "UTC", midday)


def seeded_delivery(db: Session, configured: Settings) -> tuple[PushSubscription, Sighting]:
    profile = Profile(session_hash="z" * 64)
    db.add(profile)
    db.flush()
    location = MonitoredLocation(
        profile_id=profile.id,
        label="Home",
        latitude=1,
        longitude=2,
        radius_km=5,
        detection_mode="all",
        facing_direction=0,
        fov_width=360,
        overhead_threshold_km=1,
        notification_cooldown_seconds=1800,
    )
    db.add(location)
    db.flush()
    device = PushSubscription(
        profile_id=profile.id,
        endpoint_hash="d" * 64,
        subscription_json=encrypt_subscription(
            {"endpoint": "https://push.invalid/gone", "keys": {"p256dh": "a", "auth": "b"}},
            configured,
        ),
    )
    sighting = Sighting(
        location_id=location.id,
        event_key="event",
        flight_id="flight",
        provider_flight_id="provider",
        state="in_view",
        minimum_distance_km=2,
        snapshot={"callsign": "AS1", "distance_km": 2},
        trail=[],
    )
    db.add_all([device, sighting])
    db.flush()
    db.add(
        NotificationDelivery(
            profile_id=profile.id,
            device_id=device.id,
            location_id=location.id,
            sighting_id=sighting.id,
            notification_type="nearby",
        )
    )
    db.commit()
    return device, sighting


@pytest.mark.asyncio
async def test_http_410_permanently_disables_subscription(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(notification_module, "SessionLocal", factory)
    configured = settings()
    with factory() as db:
        device, _ = seeded_delivery(db, configured)
        device_id = device.id

    response = requests.Response()
    response.status_code = 410

    def gone(**kwargs):
        raise WebPushException("gone", response=response)

    monkeypatch.setattr(notification_module, "webpush", gone)
    assert await PushDispatcher(configured).deliver_pending() == 0
    with factory() as db:
        disabled = db.get(PushSubscription, device_id)
        delivery = db.scalar(select(NotificationDelivery))
        assert disabled.permanent_failure and not disabled.enabled
        assert delivery.response_status == 410 and delivery.error_category == "permanent"


def test_notification_payload_contains_no_coordinates_or_endpoint():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _, sighting = seeded_delivery(db, settings())
        payload = notification_payload(sighting, "https://planes.example.com")
        serialized = str(payload)
        assert "latitude" not in serialized and "longitude" not in serialized
        assert payload["url"].startswith("https://planes.example.com/")


def test_notification_payload_uses_friendly_multiline_format():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _, sighting = seeded_delivery(db, settings())
        sighting.snapshot.update(
            airline="Hawaiian Airlines",
            callsign="ASA836",
            origin_city="Honolulu",
            destination_city="Phoenix",
            aircraft_type="Airbus A330",
            altitude_ft=39000,
        )
        payload = notification_payload(sighting, "https://planes.example.com")
        assert payload["title"] == "Hawaiian Airlines ASA836"
        assert payload["body"] == (
            "📡 In Your AirSpace ✈️\nHonolulu ➤ Phoenix\n"
            "Airbus A330 at 39,000 feet"
        )


def test_notification_payload_includes_aircraft_image_when_available():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _, sighting = seeded_delivery(db, settings())
        payload = notification_payload(
            sighting,
            "https://planes.example.com",
            "https://t.plnspttrs.net/photo.jpg",
        )
        assert payload["image"] == "https://t.plnspttrs.net/photo.jpg"


def test_helicopter_notification_uses_helicopter_symbol():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _, sighting = seeded_delivery(db, settings())
        sighting.snapshot["aircraft_type"] = "Airbus Helicopters H145"
        payload = notification_payload(sighting, "https://planes.example.com")
        assert payload["body"].startswith("📡 In Your AirSpace 🚁\n")
    assert is_helicopter("R44")
    assert not is_helicopter("B738")
