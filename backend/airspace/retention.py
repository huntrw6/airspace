import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult

from .config import Settings
from .database import SessionLocal
from .models import Profile, PushSubscription, Sighting


@dataclass(frozen=True)
class CleanupResult:
    sightings: int
    subscriptions: int
    profiles: int


def cleanup_once(settings: Settings, now: datetime | None = None) -> CleanupResult:
    now = now or datetime.now(timezone.utc)
    sighting_cutoff = now - timedelta(days=settings.history_retention_days)
    subscription_cutoff = now - timedelta(days=settings.invalid_subscription_retention_days)
    profile_cutoff = now - timedelta(days=settings.inactive_profile_days)
    with SessionLocal() as db:
        sighting_result = cast(
            CursorResult[Any],
            db.execute(delete(Sighting).where(Sighting.last_seen_at < sighting_cutoff)),
        )
        subscription_result = cast(
            CursorResult[Any],
            db.execute(
                delete(PushSubscription).where(
                    PushSubscription.permanent_failure,
                    PushSubscription.last_failure_at.is_not(None),
                    PushSubscription.last_failure_at < subscription_cutoff,
                )
            ),
        )
        sightings = sighting_result.rowcount
        subscriptions = subscription_result.rowcount
        abandoned = db.scalars(select(Profile).where(Profile.last_active_at < profile_cutoff)).all()
        profiles = len(abandoned)
        for profile in abandoned:
            db.delete(profile)
        db.commit()
    return CleanupResult(sightings or 0, subscriptions or 0, profiles)


class RetentionWorker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.running = False
        self.last_success_at: datetime | None = None
        self.last_error: str | None = None
        self.last_result: CleanupResult | None = None

    async def run(self) -> None:
        self.running = True
        try:
            while self.running:
                try:
                    self.last_result = await asyncio.to_thread(cleanup_once, self.settings)
                    self.last_success_at = datetime.now(timezone.utc)
                    self.last_error = None
                except Exception as error:
                    self.last_error = type(error).__name__
                await asyncio.sleep(self.settings.cleanup_interval_seconds)
        finally:
            self.running = False

    def stop(self) -> None:
        self.running = False
