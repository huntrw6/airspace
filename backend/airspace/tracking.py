import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .detection import (
    LifecycleInput,
    altitude_matches,
    bearing_degrees,
    distance_km,
    next_state,
)
from .models import (
    FlightState,
    MonitoredLocation,
    NotificationDelivery,
    Profile,
    PushSubscription,
    Sighting,
)
from .providers import NormalizedFlight
from .notifications import in_quiet_hours

VISIBLE_STATES = {
    FlightState.detected.value,
    FlightState.approaching.value,
    FlightState.in_view.value,
    FlightState.overhead.value,
    FlightState.departing.value,
}
MAP_BUFFER_KM = 2.0


def aware_utc(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


def flight_snapshot(flight: NormalizedFlight, distance: float, bearing: float) -> dict:
    value = asdict(flight)
    value["observed_at"] = flight.observed_at.astimezone(timezone.utc).isoformat()
    value["distance_km"] = round(distance, 3)
    value["bearing"] = round(bearing, 1)
    return value


class TrackingService:
    def __init__(self, stale_after_seconds: int, trail_limit: int = 120) -> None:
        self._stale_after = timedelta(seconds=stale_after_seconds)
        self._trail_limit = trail_limit

    def process_cycle(
        self,
        db: Session,
        flights_by_location: dict[str, list[NormalizedFlight]],
        successful_location_ids: set[str],
        now: datetime | None = None,
    ) -> list[Sighting]:
        now = now or datetime.now(timezone.utc)
        created: list[Sighting] = []
        seen: set[tuple[str, str]] = set()
        if not successful_location_ids:
            return created
        locations = {
            row.id: row
            for row in db.scalars(
                select(MonitoredLocation).where(
                    MonitoredLocation.id.in_(successful_location_ids), MonitoredLocation.enabled
                )
            )
        }
        active_by_flight: dict[tuple[str, str], Sighting] = {}
        existing_sightings = db.scalars(
            select(Sighting)
            .where(
                Sighting.location_id.in_(successful_location_ids),
                Sighting.state.in_(VISIBLE_STATES | {FlightState.held.value}),
            )
            .order_by(Sighting.first_detected_at.desc())
        ).all()
        for sighting in existing_sightings:
            active_by_flight.setdefault((sighting.location_id, sighting.flight_id), sighting)
        for location_id, flights in flights_by_location.items():
            location = locations.get(location_id)
            if location is None:
                continue
            for flight in flights:
                distance = distance_km(
                    location.latitude, location.longitude, flight.latitude, flight.longitude
                )
                active = active_by_flight.get((location.id, flight.flight_id))
                if distance > location.radius_km + MAP_BUFFER_KM or not altitude_matches(
                    flight.altitude_ft,
                    location.minimum_altitude_ft,
                    location.maximum_altitude_ft,
                ):
                    if active is not None:
                        active.state = FlightState.historic.value
                    continue
                bearing = bearing_degrees(
                    location.latitude, location.longitude, flight.latitude, flight.longitude
                )
                stale = now - flight.observed_at > self._stale_after
                previous_value = active.snapshot.get("distance_km") if active else None
                previous_distance = (
                    float(previous_value) if isinstance(previous_value, (int, float, str)) else None
                )
                inside_notification_area = distance <= location.radius_km
                if inside_notification_area:
                    state = next_state(
                        FlightState(active.state) if active else None,
                        LifecycleInput(
                            in_view=True,
                            distance_km=distance,
                            previous_distance_km=previous_distance,
                            overhead_threshold_km=location.overhead_threshold_km,
                            stale=stale,
                        ),
                    )
                else:
                    state = (
                        FlightState.departing
                        if previous_distance is not None and distance > previous_distance
                        else FlightState.detected
                    )
                snapshot = flight_snapshot(flight, distance, bearing)
                point = {
                    "latitude": flight.latitude,
                    "longitude": flight.longitude,
                    "altitude_ft": flight.altitude_ft,
                    "observed_at": snapshot["observed_at"],
                }
                if active is None:
                    if stale:
                        continue
                    active = Sighting(
                        location_id=location.id,
                        event_key=f"{flight.flight_id}:{uuid.uuid4()}",
                        flight_id=flight.flight_id,
                        provider_flight_id=flight.provider_flight_id,
                        first_detected_at=now,
                        first_in_view_at=now if inside_notification_area else None,
                        last_seen_at=flight.observed_at,
                        state=state.value,
                        minimum_distance_km=distance,
                        snapshot=snapshot,
                        trail=[point],
                    )
                    db.add(active)
                    db.flush()
                    active_by_flight[(location.id, flight.flight_id)] = active
                    created.append(active)
                else:
                    active.last_seen_at = max(
                        aware_utc(active.last_seen_at), aware_utc(flight.observed_at)
                    )
                    active.state = state.value
                    active.minimum_distance_km = min(active.minimum_distance_km, distance)
                    active.snapshot = snapshot
                    trail = list(active.trail or [])
                    if not trail or (trail[-1]["latitude"], trail[-1]["longitude"]) != (
                        flight.latitude,
                        flight.longitude,
                    ):
                        trail.append(point)
                    active.trail = trail[-self._trail_limit :]
                    if inside_notification_area and active.first_in_view_at is None:
                        active.first_in_view_at = now
                if inside_notification_area:
                    self._create_notification_intents(db, location, active, state, now)
                seen.add((location.id, flight.flight_id))

        active_rows = db.scalars(
            select(Sighting).where(
                Sighting.location_id.in_(successful_location_ids),
                Sighting.state.in_(VISIBLE_STATES | {FlightState.held.value}),
            )
        ).all()
        for sighting in active_rows:
            if (sighting.location_id, sighting.flight_id) in seen:
                continue
            elapsed = now - aware_utc(sighting.last_seen_at)
            sighting.state = (
                FlightState.historic.value
                if elapsed > self._stale_after
                else FlightState.held.value
            )
        db.commit()
        return created

    @staticmethod
    def _create_notification_intents(
        db: Session,
        location: MonitoredLocation,
        sighting: Sighting,
        state: FlightState,
        now: datetime,
    ) -> None:
        profile = db.get(Profile, location.profile_id)
        if profile is None:
            return
        if in_quiet_hours(location.quiet_hours, profile.timezone, now):
            return
        devices = db.scalars(
            select(PushSubscription).where(
                PushSubscription.profile_id == profile.id,
                PushSubscription.enabled,
                ~PushSubscription.permanent_failure,
            )
        ).all()
        notification_type = "overhead" if state is FlightState.overhead else "nearby"
        for device in devices:
            cooldown_start = now - timedelta(seconds=location.notification_cooldown_seconds)
            recent = db.scalar(
                select(NotificationDelivery.id)
                .where(
                    NotificationDelivery.device_id == device.id,
                    NotificationDelivery.location_id == location.id,
                    NotificationDelivery.notification_type == notification_type,
                    NotificationDelivery.attempted_at >= cooldown_start,
                )
                .limit(1)
            )
            if recent is not None:
                continue
            exists = db.scalar(
                select(NotificationDelivery.id).where(
                    NotificationDelivery.device_id == device.id,
                    NotificationDelivery.sighting_id == sighting.id,
                    NotificationDelivery.notification_type == notification_type,
                )
            )
            if exists is None:
                db.add(
                    NotificationDelivery(
                        profile_id=profile.id,
                        device_id=device.id,
                        location_id=location.id,
                        sighting_id=sighting.id,
                        notification_type=notification_type,
                        success=False,
                    )
                )
