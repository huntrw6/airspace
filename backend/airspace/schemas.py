from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class QuietHours(BaseModel):
    enabled: bool = True
    start: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class LocationCreate(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    normalized_address: str | None = Field(None, max_length=250)
    radius_km: float = Field(8, gt=0, le=160)
    detection_mode: Literal["all", "directional"] = "all"
    facing_direction: float = Field(0, ge=0, lt=360)
    fov_width: float = Field(360, gt=0, le=360)
    minimum_altitude_ft: int | None = Field(None, ge=0, le=100000)
    maximum_altitude_ft: int | None = Field(None, ge=0, le=100000)
    overhead_threshold_km: float = Field(1, gt=0, le=10)
    notification_cooldown_seconds: int = Field(1800, ge=60, le=86400)
    quiet_hours: QuietHours | None = None

    @model_validator(mode="after")
    def validate_range(self) -> "LocationCreate":
        if self.minimum_altitude_ft is not None and self.maximum_altitude_ft is not None:
            if self.minimum_altitude_ft > self.maximum_altitude_ft:
                raise ValueError("Minimum altitude must not exceed maximum altitude.")
        if self.detection_mode == "all":
            self.fov_width = 360
        return self


class LocationView(LocationCreate):
    id: str
    enabled: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class ProfileCreate(BaseModel):
    timezone: str = Field("UTC", min_length=1, max_length=64)
    units: Literal["imperial", "metric"] = "imperial"


class ProfileView(BaseModel):
    timezone: str
    units: str
    created_at: datetime
    locations: list[LocationView]
    model_config = {"from_attributes": True}


class PushCreate(BaseModel):
    endpoint: str = Field(min_length=16, max_length=2048)
    keys: dict[str, str]
    platform: str | None = Field(None, max_length=120)


class PushDiagnostic(BaseModel):
    stage: str = Field(max_length=40)
    error_name: str = Field(max_length=80)
    error_message: str = Field(max_length=500)
    permission: str = Field(max_length=30)
    secure_context: bool
    service_worker_state: str | None = Field(None, max_length=40)
    push_manager_available: bool
    public_key_length: int | None = Field(None, ge=0, le=1000)
    platform: str = Field(max_length=300)
