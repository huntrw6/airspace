import hashlib
import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from . import __version__
from .auth import COOKIE_NAME, current_profile, new_session, require_admin, session_hash
from .config import Settings, get_settings
from .database import SessionLocal, get_db
from .migrations import upgrade_database
from .models import (
    MonitoredLocation,
    NotificationDelivery,
    PollingRegion,
    Profile,
    ProviderHealth,
    PushSubscription,
    Sighting,
)
from .schemas import (
    LocationCreate,
    LocationView,
    ProfileCreate,
    ProfileView,
    PushCreate,
    PushDiagnostic,
)
from .subscriptions import encrypt_subscription
from .notifications import PushDispatcher
from .worker import PollingWorker, build_worker
from .retention import RetentionWorker, cleanup_once
from .geocoding import Geocoder
from .rate_limit import SlidingWindowLimiter, privacy_key
from .origin import origin_is_allowed
from .aircraft_photos import AircraftPhotoService

polling_worker: PollingWorker | None = None
polling_task: asyncio.Task | None = None
retention_worker: RetentionWorker | None = None
retention_task: asyncio.Task | None = None
rate_limiter = SlidingWindowLimiter()
geocoder: Geocoder | None = None
aircraft_photos: AircraftPhotoService | None = None
logger = logging.getLogger("airspace.push")
logger.setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(_: FastAPI):
    global polling_worker, polling_task, retention_worker, retention_task, geocoder, aircraft_photos
    upgrade_database()
    # Keep this explicit for deployments upgraded from versions whose migrations disabled it.
    logger.disabled = False
    settings = get_settings()
    geocoder = Geocoder(settings)
    aircraft_photos = AircraftPhotoService(settings)
    provider = None
    if settings.provider_enabled:
        polling_worker, provider = build_worker(settings, aircraft_photos)
        polling_task = asyncio.create_task(polling_worker.run(), name="airspace-regional-poller")
    retention_worker = RetentionWorker(settings)
    retention_task = asyncio.create_task(retention_worker.run(), name="airspace-retention")
    try:
        yield
    finally:
        if polling_worker:
            polling_worker.stop()
        if polling_task:
            polling_task.cancel()
            await asyncio.gather(polling_task, return_exceptions=True)
        if retention_worker:
            retention_worker.stop()
        if retention_task:
            retention_task.cancel()
            await asyncio.gather(retention_task, return_exceptions=True)
        if provider:
            await provider.close()
        if aircraft_photos:
            await aircraft_photos.close()


app = FastAPI(title="AirSpace API", version=__version__, lifespan=lifespan)


def utc_iso(value: datetime) -> str:
    aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return aware.isoformat().replace("+00:00", "Z")


@app.middleware("http")
async def security_headers(request, call_next):
    settings = get_settings()
    if request.url.path.startswith("/api/"):
        client_host = request.client.host if request.client else "unknown"
        if settings.trusted_proxy_hops:
            forwarded = [
                part.strip()
                for part in request.headers.get("X-Forwarded-For", "").split(",")
                if part.strip()
            ]
            if len(forwarded) >= settings.trusted_proxy_hops:
                client_host = forwarded[-settings.trusted_proxy_hops]
        identity = request.cookies.get(COOKIE_NAME) or client_host
        category = "mutation" if request.method in {"POST", "PUT", "PATCH", "DELETE"} else "public"
        maximum = (
            settings.rate_limit_mutation_requests
            if category == "mutation"
            else settings.rate_limit_public_requests
        )
        if request.url.path == "/api/profiles" and request.method == "POST":
            category = "profile"
            maximum = settings.rate_limit_profile_creations
        result = rate_limiter.check(
            f"{category}:{privacy_key(identity)}",
            maximum,
            settings.rate_limit_window_seconds,
        )
        if not result.allowed:
            return Response(
                content='{"detail":"Too many requests. Try again shortly."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(result.retry_after)},
            )
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("Origin")
        if not origin_is_allowed(
            origin,
            settings.public_url,
            request.headers.get("Host"),
            request.headers.get("X-Forwarded-Host"),
            trust_forwarded=bool(settings.trusted_proxy_hops),
        ):
            return Response(
                content='{"detail":"Cross-origin request rejected."}',
                status_code=403,
                media_type="application/json",
            )
    response = await call_next(request)
    response.headers.update(
        {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=(self)",
            "Content-Security-Policy": "default-src 'self'; img-src 'self' data: https://*.basemaps.cartocdn.com https://t.plnspttrs.net; connect-src 'self'; style-src 'self' 'unsafe-inline'",
        }
    )
    return response


@app.get("/api/geocoding/search")
async def search_addresses(
    q: str = Query(min_length=3, max_length=200),
    _: Profile = Depends(current_profile),
    settings: Settings = Depends(get_settings),
) -> list[dict]:
    if not settings.geocoding_enabled or geocoder is None:
        raise HTTPException(status_code=503, detail="Address search is not configured.")
    try:
        results = await geocoder.search(q)
    except (httpx.HTTPError, ValueError) as error:
        raise HTTPException(
            status_code=502, detail="Address search is temporarily unavailable."
        ) from error
    return [result.__dict__ for result in results]


@app.get("/api/aircraft-photos/{registration}")
async def aircraft_photo(
    registration: str,
    _: Profile = Depends(current_profile),
    settings: Settings = Depends(get_settings),
) -> dict:
    if not settings.aircraft_photos_enabled or aircraft_photos is None:
        return {"photo": None}
    try:
        photo = await aircraft_photos.lookup(registration)
    except (httpx.HTTPError, ValueError):
        return {"photo": None}
    return {"photo": photo.__dict__ if photo else None}


@app.get("/health/live")
def live() -> dict:
    return {"status": "ok", "version": __version__}


@app.get("/health/ready")
def ready(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
    except Exception as error:
        raise HTTPException(status_code=503, detail="Database unavailable") from error
    return {"status": "ready", "database": "available"}


@app.get("/api/status")
def api_status(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> dict:
    health = db.get(ProviderHealth, "flightradar24")
    provider_status = health.status if health else "not_configured"
    if settings.provider_enabled and (not polling_worker or not polling_worker.running):
        provider_status = "unavailable"
    elif health and polling_worker and polling_worker.active_region_count:
        attempted_at = health.last_attempt_at
        if attempted_at is not None:
            attempted_at = (
                attempted_at.replace(tzinfo=timezone.utc)
                if attempted_at.tzinfo is None
                else attempted_at.astimezone(timezone.utc)
            )
        stale_after = timedelta(seconds=max(60, settings.poll_interval_seconds * 3))
        if attempted_at is None or datetime.now(timezone.utc) - attempted_at > stale_after:
            provider_status = "unavailable"
    return {
        "application": "running",
        "database": "available",
        "provider": provider_status,
        "last_successful_poll": health.last_success_at if health else None,
        "last_polling_attempt": health.last_attempt_at if health else None,
        "active_polling_interval": settings.poll_interval_seconds,
        "push": "configured" if settings.vapid_public_key else "not_configured",
        "background_worker": "running" if polling_worker and polling_worker.running else "stopped",
        "retention_worker": "running"
        if retention_worker and retention_worker.running
        else "stopped",
        "active_regions": polling_worker.active_region_count if polling_worker else 0,
        "deferred_regions": polling_worker.deferred_region_count if polling_worker else 0,
        "last_feed_requests": polling_worker.last_feed_request_count if polling_worker else 0,
        "last_raw_aircraft": polling_worker.last_raw_aircraft_count if polling_worker else 0,
        "last_airborne_aircraft": (
            polling_worker.last_airborne_aircraft_count if polling_worker else 0
        ),
        "last_empty_feed_responses": (
            polling_worker.last_empty_response_count if polling_worker else 0
        ),
        "consecutive_all_empty_cycles": (
            polling_worker.consecutive_all_empty_cycles if polling_worker else 0
        ),
        "provider_session_resets": (
            polling_worker.provider_session_resets if polling_worker else 0
        ),
        "last_provider_session_reset": (
            polling_worker.last_provider_session_reset_at if polling_worker else None
        ),
    }


@app.post("/api/profiles", response_model=ProfileView, status_code=201)
def create_profile(
    body: ProfileCreate,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    token = new_session()
    profile = Profile(
        session_hash=session_hash(token, settings), timezone=body.timezone, units=body.units
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=int(timedelta(days=settings.session_days).total_seconds()),
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return profile


@app.get("/api/profile", response_model=ProfileView)
def get_profile(profile: Profile = Depends(current_profile)):
    return profile


@app.delete("/api/profile", status_code=204)
def delete_profile(
    response: Response, profile: Profile = Depends(current_profile), db: Session = Depends(get_db)
):
    db.delete(profile)
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")


@app.post("/api/locations", response_model=LocationView, status_code=201)
def add_location(
    body: LocationCreate,
    profile: Profile = Depends(current_profile),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    count = (
        db.scalar(
            select(func.count())
            .select_from(MonitoredLocation)
            .where(MonitoredLocation.profile_id == profile.id)
        )
        or 0
    )
    if count >= settings.max_locations_per_profile:
        raise HTTPException(
            409, f"This profile can monitor at most {settings.max_locations_per_profile} locations."
        )
    location = MonitoredLocation(profile_id=profile.id, **body.model_dump())
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


@app.put("/api/locations/{location_id}", response_model=LocationView)
def update_location(
    location_id: str,
    body: LocationCreate,
    profile: Profile = Depends(current_profile),
    db: Session = Depends(get_db),
):
    location = db.scalar(
        select(MonitoredLocation).where(
            MonitoredLocation.id == location_id, MonitoredLocation.profile_id == profile.id
        )
    )
    if location is None:
        raise HTTPException(404, "Monitored location not found.")
    for key, value in body.model_dump().items():
        setattr(location, key, value)
    db.commit()
    db.refresh(location)
    return location


@app.delete("/api/locations/{location_id}", status_code=204)
def delete_location(
    location_id: str, profile: Profile = Depends(current_profile), db: Session = Depends(get_db)
):
    location = db.scalar(
        select(MonitoredLocation).where(
            MonitoredLocation.id == location_id, MonitoredLocation.profile_id == profile.id
        )
    )
    if location is None:
        raise HTTPException(404, "Monitored location not found.")
    db.delete(location)
    db.commit()


@app.post("/api/push-subscriptions", status_code=201)
def add_push(
    body: PushCreate,
    profile: Profile = Depends(current_profile),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if not body.endpoint.startswith("https://"):
        raise HTTPException(422, "Push endpoints must use HTTPS.")
    digest = hashlib.sha256(body.endpoint.encode()).hexdigest()
    existing = db.scalar(
        select(PushSubscription).where(PushSubscription.endpoint_hash == digest)
    )
    count = (
        db.scalar(
            select(func.count())
            .select_from(PushSubscription)
            .where(PushSubscription.profile_id == profile.id)
        )
        or 0
    )
    if existing is None and count >= settings.max_subscriptions_per_profile:
        raise HTTPException(409, "Push subscription limit reached.")
    if (
        existing is not None
        and existing.profile_id != profile.id
        and count >= settings.max_subscriptions_per_profile
    ):
        raise HTTPException(409, "Push subscription limit reached.")
    encrypted = encrypt_subscription(
        {"endpoint": body.endpoint, "keys": body.keys}, settings
    )
    if existing is None:
        db.add(
            PushSubscription(
                profile_id=profile.id,
                endpoint_hash=digest,
                subscription_json=encrypted,
                platform=body.platform,
            )
        )
    else:
        existing.profile_id = profile.id
        existing.subscription_json = encrypted
        existing.platform = body.platform
        existing.permission_state = "granted"
        existing.enabled = True
        existing.permanent_failure = False
        existing.last_failure_at = None
    db.commit()
    return {"status": "registered"}


@app.get("/api/push-key")
def push_key(settings: Settings = Depends(get_settings)):
    if not settings.vapid_public_key:
        raise HTTPException(503, "Plane notifications are not configured on this server.")
    return {"public_key": settings.vapid_public_key}


@app.post("/api/push-diagnostics", status_code=202)
def record_push_diagnostic(
    body: PushDiagnostic,
    _: Profile = Depends(current_profile),
) -> dict[str, str]:
    diagnostic_id = str(uuid.uuid4())
    logger.warning(
        "Browser push diagnostic id=%s stage=%s error=%s message=%s permission=%s "
        "secure=%s worker=%s push_manager=%s key_length=%s platform=%s",
        diagnostic_id,
        body.stage,
        body.error_name,
        body.error_message,
        body.permission,
        body.secure_context,
        body.service_worker_state,
        body.push_manager_available,
        body.public_key_length,
        body.platform,
    )
    return {"diagnostic_id": diagnostic_id}


@app.post("/api/push-subscriptions/test")
async def test_push_notification(
    profile: Profile = Depends(current_profile),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if not settings.vapid_private_key or not settings.vapid_public_key:
        raise HTTPException(503, "Plane notifications are not configured on this server.")
    location = db.scalar(
        select(MonitoredLocation)
        .where(MonitoredLocation.profile_id == profile.id)
        .order_by(MonitoredLocation.created_at)
        .limit(1)
    )
    devices = db.scalars(
        select(PushSubscription).where(
            PushSubscription.profile_id == profile.id,
            PushSubscription.enabled,
            ~PushSubscription.permanent_failure,
        )
    ).all()
    if location is None or not devices:
        raise HTTPException(409, "Add a viewing location and enable notifications first.")
    now = datetime.now(timezone.utc)
    sighting = Sighting(
        location_id=location.id,
        event_key=f"test:{uuid.uuid4()}",
        flight_id="airspace-test",
        first_detected_at=now,
        last_seen_at=now,
        state="historic",
        minimum_distance_km=0,
        snapshot={
            "callsign": "AirSpace test",
            "aircraft_type": "Notifications are working",
        },
        trail=[],
    )
    db.add(sighting)
    db.flush()
    for device in devices:
        db.add(
            NotificationDelivery(
                profile_id=profile.id,
                device_id=device.id,
                location_id=location.id,
                sighting_id=sighting.id,
                notification_type="test",
            )
        )
    db.commit()
    delivered = await PushDispatcher(settings, aircraft_photos).deliver_pending()
    return {"queued": len(devices), "delivered": delivered}


@app.get("/api/sightings")
def sightings(profile: Profile = Depends(current_profile), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Sighting)
        .join(MonitoredLocation)
        .where(MonitoredLocation.profile_id == profile.id)
        .order_by(Sighting.last_seen_at.desc())
        .limit(100)
    ).all()
    return [
        {
            "id": r.id,
            "location_id": r.location_id,
            "provider_flight_id": r.provider_flight_id,
            "state": r.state,
            "first_detected_at": utc_iso(r.first_detected_at),
            "last_seen_at": utc_iso(r.last_seen_at),
            "minimum_distance_km": r.minimum_distance_km,
            "flight": r.snapshot,
        }
        for r in rows
    ]


@app.get("/api/events")
def events(profile: Profile = Depends(current_profile)):
    profile_id = profile.id

    async def stream():
        previous = ""
        while True:
            with SessionLocal() as event_db:
                rows = event_db.scalars(
                    select(Sighting)
                    .join(MonitoredLocation)
                    .where(MonitoredLocation.profile_id == profile_id)
                    .order_by(Sighting.last_seen_at.desc())
                    .limit(100)
                ).all()
                payload = json.dumps(
                    [
                        {
                            "id": row.id,
                            "location_id": row.location_id,
                            "provider_flight_id": row.provider_flight_id,
                            "state": row.state,
                            "first_detected_at": utc_iso(row.first_detected_at),
                            "last_seen_at": utc_iso(row.last_seen_at),
                            "minimum_distance_km": row.minimum_distance_km,
                            "flight": row.snapshot,
                        }
                        for row in rows
                    ],
                    separators=(",", ":"),
                )
            if payload != previous:
                yield f"event: sightings\ndata: {payload}\n\n"
                previous = payload
            else:
                yield ": keepalive\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )


@app.get("/api/admin/summary", dependencies=[Depends(require_admin)])
def admin_summary(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    regions = db.scalars(select(PollingRegion).order_by(PollingRegion.key)).all()
    provider = db.get(ProviderHealth, "flightradar24")
    return {
        "version": __version__,
        "profiles": db.scalar(select(func.count()).select_from(Profile)),
        "locations": db.scalar(select(func.count()).select_from(MonitoredLocation)),
        "active_subscriptions": db.scalar(
            select(func.count()).select_from(PushSubscription).where(PushSubscription.enabled)
        ),
        "disabled_subscriptions": db.scalar(
            select(func.count()).select_from(PushSubscription).where(~PushSubscription.enabled)
        ),
        "successful_deliveries": db.scalar(
            select(func.count())
            .select_from(NotificationDelivery)
            .where(NotificationDelivery.success)
        ),
        "pending_deliveries": db.scalar(
            select(func.count())
            .select_from(NotificationDelivery)
            .where(
                ~NotificationDelivery.success,
                NotificationDelivery.retry_count < settings.push_max_retries,
            )
        ),
        "failed_deliveries": db.scalar(
            select(func.count())
            .select_from(NotificationDelivery)
            .where(~NotificationDelivery.success, NotificationDelivery.error_category.is_not(None))
        ),
        "database": "available",
        "provider": {
            "status": provider.status if provider else "not_configured",
            "last_attempt_at": provider.last_attempt_at if provider else None,
            "last_success_at": provider.last_success_at if provider else None,
            "last_error": provider.last_error if provider else None,
        },
        "push": "configured" if settings.vapid_public_key else "not_configured",
        "background_worker": "running" if polling_worker and polling_worker.running else "stopped",
        "retention": {
            "running": bool(retention_worker and retention_worker.running),
            "last_success_at": retention_worker.last_success_at if retention_worker else None,
            "last_error": retention_worker.last_error if retention_worker else None,
            "history_days": settings.history_retention_days,
            "inactive_profile_days": settings.inactive_profile_days,
        },
        "configuration": {
            "poll_interval_seconds": settings.poll_interval_seconds,
            "provider_detail_requests_per_cycle": settings.provider_detail_requests_per_cycle,
            "max_regions_per_cycle": settings.max_regions_per_cycle,
            "max_locations_per_profile": settings.max_locations_per_profile,
            "max_subscriptions_per_profile": settings.max_subscriptions_per_profile,
            "geocoding_enabled": settings.geocoding_enabled,
            "rate_limit_window_seconds": settings.rate_limit_window_seconds,
            "rate_limit_public_requests": settings.rate_limit_public_requests,
            "rate_limit_mutation_requests": settings.rate_limit_mutation_requests,
            "trusted_proxy_hops": settings.trusted_proxy_hops,
        },
        "active_regions": [
            {
                "key": region.key,
                "location_count": region.location_count,
                "request_count": region.request_count,
                "last_polled_at": region.last_polled_at,
                "last_flight_count": region.last_flight_count,
                "last_error": region.last_error,
            }
            for region in regions
        ],
    }


@app.post("/api/admin/cleanup", dependencies=[Depends(require_admin)])
def admin_cleanup(settings: Settings = Depends(get_settings)):
    result = cleanup_once(settings)
    return {
        "deleted_sightings": result.sightings,
        "deleted_subscriptions": result.subscriptions,
        "deleted_profiles": result.profiles,
    }


static = Path(__file__).parent / "static"
if static.exists():
    app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        candidate = static / path
        return FileResponse(candidate if candidate.is_file() else static / "index.html")
