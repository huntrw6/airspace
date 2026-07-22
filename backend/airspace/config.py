from functools import lru_cache
from pathlib import Path
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AIRSPACE_", env_file=".env", extra="ignore")
    environment: str = "development"
    database_url: str = "sqlite:///./data/airspace.db"
    public_url: str = "http://localhost:7373"
    cookie_secure: bool = False
    session_days: int = Field(365, ge=1, le=730)
    admin_password: SecretStr = SecretStr("ReplaceThisWithSecretAdminPassword")
    session_pepper: SecretStr = SecretStr("development-only-change-me")
    max_locations_per_profile: int = Field(5, ge=1, le=25)
    max_subscriptions_per_profile: int = Field(5, ge=1, le=25)
    poll_interval_seconds: int = Field(30, ge=15, le=900)
    provider_enabled: bool = False
    provider_base_url: str = "https://data-cloud.flightradar24.com"
    provider_details_url: str = "https://data-live.flightradar24.com"
    provider_timeout_seconds: float = Field(10, ge=2, le=30)
    provider_detail_ttl_seconds: int = Field(900, ge=60, le=86400)
    max_regions_per_cycle: int = Field(40, ge=1, le=500)
    stale_after_seconds: int = Field(120, ge=30, le=3600)
    history_retention_days: int = Field(60, ge=1, le=365)
    inactive_profile_days: int = Field(365, ge=30, le=1825)
    invalid_subscription_retention_days: int = Field(7, ge=1, le=90)
    cleanup_interval_seconds: int = Field(86400, ge=300, le=604800)
    rate_limit_window_seconds: int = Field(60, ge=10, le=3600)
    rate_limit_public_requests: int = Field(120, ge=10, le=10000)
    rate_limit_mutation_requests: int = Field(30, ge=5, le=1000)
    rate_limit_profile_creations: int = Field(10, ge=1, le=100)
    trusted_proxy_hops: int = Field(0, ge=0, le=5)
    geocoding_enabled: bool = True
    geocoding_base_url: str = "https://nominatim.openstreetmap.org"
    geocoding_user_agent: str = "Airspace/0.1 (self-hosted flight tracker)"
    geocoding_timeout_seconds: float = Field(8, ge=2, le=30)
    geocoding_cache_seconds: int = Field(86400, ge=60, le=604800)
    vapid_public_key: str | None = None
    vapid_private_key: SecretStr | None = None
    vapid_subject: str = "mailto:hunter.wegner6@gmail.com"
    push_encryption_key: SecretStr | None = None
    push_max_retries: int = Field(3, ge=1, le=10)

    @field_validator("database_url")
    @classmethod
    def ensure_data_dir(cls, value: str) -> str:
        if value.startswith("sqlite:///./"):
            Path(value.removeprefix("sqlite:///./")).parent.mkdir(parents=True, exist_ok=True)
        return value

    @field_validator("geocoding_base_url")
    @classmethod
    def validate_geocoder_url(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("geocoding_base_url must use HTTPS")
        return value.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # BaseSettings reads defaults and environment.
