from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import airspace.retention as retention_module
from airspace.config import Settings
from airspace.database import Base
from airspace.models import MonitoredLocation, Profile, PushSubscription, Sighting
from airspace.retention import cleanup_once


def factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def configured() -> Settings:
    return Settings(
        session_pepper="test",
        admin_password="test",
        history_retention_days=30,
        inactive_profile_days=90,
        invalid_subscription_retention_days=7,
    )


def test_cleanup_removes_old_history_and_invalid_subscription(monkeypatch):
    sessions = factory()
    monkeypatch.setattr(retention_module, "SessionLocal", sessions)
    now = datetime.now(timezone.utc)
    with sessions() as db:
        profile = Profile(session_hash="a" * 64, last_active_at=now)
        db.add(profile)
        db.flush()
        location = MonitoredLocation(
            profile_id=profile.id,
            label="Home",
            latitude=1,
            longitude=1,
            radius_km=5,
            detection_mode="all",
            facing_direction=0,
            fov_width=360,
            overhead_threshold_km=1,
            notification_cooldown_seconds=1800,
        )
        db.add(location)
        db.flush()
        db.add(
            Sighting(
                location_id=location.id,
                event_key="old",
                flight_id="old",
                last_seen_at=now - timedelta(days=31),
                state="historic",
                minimum_distance_km=1,
                snapshot={},
                trail=[],
            )
        )
        db.add(
            PushSubscription(
                profile_id=profile.id,
                endpoint_hash="b" * 64,
                subscription_json={},
                permanent_failure=True,
                enabled=False,
                last_failure_at=now - timedelta(days=8),
            )
        )
        db.commit()
    result = cleanup_once(configured(), now)
    assert result.sightings == 1 and result.subscriptions == 1


def test_inactive_profile_cleanup_cascades_personal_data(monkeypatch):
    sessions = factory()
    monkeypatch.setattr(retention_module, "SessionLocal", sessions)
    now = datetime.now(timezone.utc)
    with sessions() as db:
        profile = Profile(session_hash="c" * 64, last_active_at=now - timedelta(days=91))
        db.add(profile)
        db.flush()
        db.add(
            MonitoredLocation(
                profile_id=profile.id,
                label="Old home",
                latitude=1,
                longitude=1,
                radius_km=5,
                detection_mode="all",
                facing_direction=0,
                fov_width=360,
                overhead_threshold_km=1,
                notification_cooldown_seconds=1800,
            )
        )
        db.commit()
    result = cleanup_once(configured(), now)
    assert result.profiles == 1
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(Profile)) == 0
        assert db.scalar(select(func.count()).select_from(MonitoredLocation)) == 0
