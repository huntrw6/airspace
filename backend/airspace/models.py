import enum
import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base, utcnow


def uid() -> str:
    return str(uuid.uuid4())


class FlightState(str, enum.Enum):
    detected = "detected"
    approaching = "approaching"
    in_view = "in_view"
    overhead = "overhead"
    departing = "departing"
    held = "held"
    historic = "historic"
    expired = "expired"


class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    session_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    units: Mapped[str] = mapped_column(String(16), default="imperial")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locations: Mapped[list["MonitoredLocation"]] = relationship(cascade="all, delete-orphan")
    devices: Mapped[list["PushSubscription"]] = relationship(cascade="all, delete-orphan")


class MonitoredLocation(Base):
    __tablename__ = "monitored_locations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(80))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    normalized_address: Mapped[str | None] = mapped_column(String(250))
    radius_km: Mapped[float] = mapped_column(Float, default=8.0)
    detection_mode: Mapped[str] = mapped_column(String(16), default="all")
    facing_direction: Mapped[float] = mapped_column(Float, default=0.0)
    fov_width: Mapped[float] = mapped_column(Float, default=360.0)
    minimum_altitude_ft: Mapped[int | None] = mapped_column(Integer)
    maximum_altitude_ft: Mapped[int | None] = mapped_column(Integer)
    overhead_threshold_km: Mapped[float] = mapped_column(Float, default=1.0)
    notification_cooldown_seconds: Mapped[int] = mapped_column(Integer, default=1800)
    quiet_hours: Mapped[dict | None] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    endpoint_hash: Mapped[str] = mapped_column(String(64), unique=True)
    subscription_json: Mapped[dict] = mapped_column(JSON)
    platform: Mapped[str | None] = mapped_column(String(120))
    permission_state: Mapped[str] = mapped_column(String(16), default="granted")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    permanent_failure: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Sighting(Base):
    __tablename__ = "sightings"
    __table_args__ = (UniqueConstraint("location_id", "event_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    location_id: Mapped[str] = mapped_column(
        ForeignKey("monitored_locations.id", ondelete="CASCADE"), index=True
    )
    event_key: Mapped[str] = mapped_column(String(160))
    flight_id: Mapped[str] = mapped_column(String(100), index=True)
    provider_flight_id: Mapped[str | None] = mapped_column(String(100))
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    first_in_view_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    state: Mapped[str] = mapped_column(String(20), default=FlightState.detected.value)
    minimum_distance_km: Mapped[float] = mapped_column(Float)
    snapshot: Mapped[dict] = mapped_column(JSON)
    trail: Mapped[list] = mapped_column(JSON, default=list)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (UniqueConstraint("device_id", "sighting_id", "notification_type"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    device_id: Mapped[str] = mapped_column(ForeignKey("push_subscriptions.id", ondelete="CASCADE"))
    location_id: Mapped[str] = mapped_column(
        ForeignKey("monitored_locations.id", ondelete="CASCADE")
    )
    sighting_id: Mapped[str] = mapped_column(ForeignKey("sightings.id", ondelete="CASCADE"))
    notification_type: Mapped[str] = mapped_column(String(24))
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    response_status: Mapped[int | None] = mapped_column(Integer)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_category: Mapped[str | None] = mapped_column(String(64))


class ProviderHealth(Base):
    __tablename__ = "provider_health"
    provider: Mapped[str] = mapped_column(String(40), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="unknown")
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)


class PollingRegion(Base):
    __tablename__ = "polling_regions"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    bounds: Mapped[dict] = mapped_column(JSON)
    location_count: Mapped[int] = mapped_column(Integer, default=0)
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_flight_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
