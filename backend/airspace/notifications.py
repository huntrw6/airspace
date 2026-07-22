import asyncio
import json
import logging
from datetime import datetime, time, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from pywebpush import WebPushException, webpush  # type: ignore[import-untyped]
from sqlalchemy import select

from .config import Settings
from .aircraft import aircraft_kind
from .aircraft_photos import AircraftPhotoService
from .database import SessionLocal, utcnow
from .models import NotificationDelivery, PushSubscription, Sighting
from .subscriptions import decrypt_subscription

LOGGER = logging.getLogger(__name__)

def in_quiet_hours(quiet_hours: dict | None, timezone_name: str, now: datetime) -> bool:
    if not quiet_hours or not quiet_hours.get("enabled", True):
        return False
    try:
        zone: tzinfo = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        zone = timezone.utc
    try:
        start = time.fromisoformat(str(quiet_hours["start"]))
        end = time.fromisoformat(str(quiet_hours["end"]))
    except (KeyError, ValueError):
        return False
    local = now.astimezone(zone).time().replace(tzinfo=None)
    if start == end:
        return True
    return start <= local < end if start < end else local >= start or local < end


def notification_payload(
    sighting: Sighting, public_url: str, image_url: str | None = None
) -> dict:
    flight = sighting.snapshot
    callsign = flight.get("callsign") or "An aircraft"
    airline = flight.get("airline")
    aircraft = flight.get("aircraft_type") or "Aircraft type unavailable"
    origin = flight.get("origin_city") or "an unknown origin"
    destination = flight.get("destination_city") or "an unknown destination"
    altitude = flight.get("altitude_ft")
    kind = flight.get("aircraft_kind") or aircraft_kind(
        flight.get("aircraft_type_code"), flight.get("aircraft_type")
    )
    aircraft_symbol = "🚁" if kind == "helicopter" else "✈️"
    flight_name = " ".join(value for value in (airline, callsign) if value)
    altitude_text = f" at {altitude:,.0f} feet" if isinstance(altitude, (int, float)) else ""
    payload = {
        "title": flight_name,
        "body": (
            f"📡 In Your AirSpace {aircraft_symbol}\n"
            f"{origin} ➤ {destination}\n"
            f"{aircraft}{altitude_text}"
        ),
        "tag": f"airspace-{sighting.id}",
        "url": f"{public_url.rstrip('/')}/?sighting={sighting.id}",
    }
    if image_url:
        payload["image"] = image_url
    return payload


class PushDispatcher:
    def __init__(
        self, settings: Settings, aircraft_photos: AircraftPhotoService | None = None
    ) -> None:
        self.settings = settings
        self.aircraft_photos = aircraft_photos

    async def _notification_image(self, sighting: Sighting) -> str | None:
        registration = sighting.snapshot.get("registration")
        if (
            not self.settings.aircraft_photos_enabled
            or self.aircraft_photos is None
            or not isinstance(registration, str)
            or not registration.strip()
        ):
            return None
        try:
            photo = await self.aircraft_photos.lookup(registration)
        except (httpx.HTTPError, ValueError):
            return None
        return photo.thumbnail_url if photo else None

    async def deliver_pending(self) -> int:
        if not self.settings.vapid_private_key:
            return 0
        delivered = 0
        with SessionLocal() as db:
            rows = db.scalars(
                select(NotificationDelivery)
                .where(
                    ~NotificationDelivery.success,
                    NotificationDelivery.retry_count < self.settings.push_max_retries,
                )
                .order_by(NotificationDelivery.attempted_at)
                .limit(100)
            ).all()
            for delivery in rows:
                device = db.get(PushSubscription, delivery.device_id)
                sighting = db.get(Sighting, delivery.sighting_id)
                if not device or not sighting or not device.enabled or device.permanent_failure:
                    continue
                try:
                    subscription = decrypt_subscription(device.subscription_json, self.settings)
                    image_url = await self._notification_image(sighting)
                    payload = notification_payload(
                        sighting, self.settings.public_url, image_url
                    )
                    await asyncio.to_thread(
                        webpush,
                        subscription_info=subscription,
                        data=json.dumps(payload),
                        vapid_private_key=self.settings.vapid_private_key.get_secret_value(),
                        vapid_claims={"sub": self.settings.vapid_subject},
                        ttl=120,
                    )
                    delivery.success = True
                    delivery.error_category = None
                    device.last_success_at = utcnow()
                    delivered += 1
                    LOGGER.info(
                        "Push delivery succeeded delivery=%s device=%s sighting=%s",
                        delivery.id,
                        device.id,
                        sighting.id,
                    )
                except ValueError as error:
                    delivery.error_category = "subscription_decryption"
                    delivery.retry_count = self.settings.push_max_retries
                    device.enabled = False
                    device.permanent_failure = True
                    device.last_failure_at = utcnow()
                    LOGGER.warning(
                        "Push delivery disabled unreadable subscription delivery=%s device=%s "
                        "error=%s",
                        delivery.id,
                        device.id,
                        type(error).__name__,
                    )
                except WebPushException as error:
                    status = error.response.status_code if error.response is not None else None
                    delivery.response_status = status
                    delivery.retry_count += 1
                    delivery.error_category = "permanent" if status in {404, 410} else "transient"
                    device.last_failure_at = utcnow()
                    if status in {404, 410}:
                        device.enabled = False
                        device.permanent_failure = True
                    LOGGER.warning(
                        "Push delivery failed delivery=%s device=%s status=%s category=%s "
                        "retry=%s/%s",
                        delivery.id,
                        device.id,
                        status,
                        delivery.error_category,
                        delivery.retry_count,
                        self.settings.push_max_retries,
                    )
                except Exception as error:
                    delivery.retry_count += 1
                    delivery.error_category = "transient"
                    device.last_failure_at = utcnow()
                    LOGGER.exception(
                        "Unexpected push delivery failure delivery=%s device=%s retry=%s/%s: %s",
                        delivery.id,
                        device.id,
                        delivery.retry_count,
                        self.settings.push_max_retries,
                        type(error).__name__,
                    )
                delivery.attempted_at = utcnow()
                db.commit()
        return delivered
