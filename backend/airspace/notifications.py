import asyncio
import json
from datetime import datetime, time, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pywebpush import WebPushException, webpush  # type: ignore[import-untyped]
from sqlalchemy import select

from .config import Settings
from .database import SessionLocal, utcnow
from .models import NotificationDelivery, PushSubscription, Sighting
from .subscriptions import decrypt_subscription


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


def notification_payload(sighting: Sighting, public_url: str) -> dict:
    flight = sighting.snapshot
    callsign = flight.get("callsign") or "An aircraft"
    airline = flight.get("airline")
    aircraft = flight.get("aircraft_type") or "Aircraft type unavailable"
    origin = flight.get("origin_city") or "an unknown origin"
    destination = flight.get("destination_city") or "an unknown destination"
    altitude = flight.get("altitude_ft")
    flight_name = " ".join(value for value in (airline, callsign) if value)
    altitude_text = f" at {altitude:,.0f} feet" if isinstance(altitude, (int, float)) else ""
    return {
        "title": (
            "📡 In Your AirSpace ✈️\n"
            f"{flight_name}\n"
            f"{origin} ➤ {destination}\n"
            f"{aircraft}{altitude_text}"
        ),
        "tag": f"airspace-{sighting.id}",
        "url": f"{public_url.rstrip('/')}/?sighting={sighting.id}",
    }


class PushDispatcher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

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
                    payload = notification_payload(sighting, self.settings.public_url)
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
                except ValueError:
                    delivery.error_category = "subscription_decryption"
                    delivery.retry_count = self.settings.push_max_retries
                    device.enabled = False
                    device.permanent_failure = True
                    device.last_failure_at = utcnow()
                except WebPushException as error:
                    status = error.response.status_code if error.response is not None else None
                    delivery.response_status = status
                    delivery.retry_count += 1
                    delivery.error_category = "permanent" if status in {404, 410} else "transient"
                    device.last_failure_at = utcnow()
                    if status in {404, 410}:
                        device.enabled = False
                        device.permanent_failure = True
                delivery.attempted_at = utcnow()
                db.commit()
        return delivered
