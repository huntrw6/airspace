import hashlib
import logging
import os

os.environ.update(
    AIRSPACE_DATABASE_URL="sqlite://",
    AIRSPACE_COOKIE_SECURE="false",
    AIRSPACE_SESSION_PEPPER="test-pepper",
    AIRSPACE_ADMIN_PASSWORD="admin-test",
)
from fastapi.testclient import TestClient
from sqlalchemy import select
from airspace.database import SessionLocal
from airspace.main import app
from airspace.models import PushSubscription


def test_migrations_keep_worker_logger_enabled():
    worker_logger = logging.getLogger("airspace.worker")
    worker_logger.disabled = False
    with TestClient(app):
        pass
    assert worker_logger.disabled is False


def test_profile_is_private_and_persists_in_cookie():
    with TestClient(app) as client:
        assert client.get("/api/profile").status_code == 401
        created = client.post("/api/profiles", json={"timezone": "UTC", "units": "metric"})
        assert created.status_code == 201
        assert client.get("/api/profile").json()["units"] == "metric"
        location = client.post(
            "/api/locations",
            json={"label": "Equator", "latitude": 0, "longitude": 0, "radius_km": 8},
        )
        assert location.status_code == 201 and location.json()["latitude"] == 0


def test_admin_protection():
    with TestClient(app) as client:
        assert client.get("/api/admin/summary").status_code == 401
        assert (
            client.get(
                "/api/admin/summary", headers={"Authorization": "Bearer admin-test"}
            ).status_code
            == 200
        )


def test_push_endpoint_can_move_to_a_recreated_browser_profile():
    payload = {
        "endpoint": "https://push.example.test/reused-browser-endpoint",
        "keys": {"p256dh": "new-public-key", "auth": "new-auth-secret"},
        "platform": "Test browser",
    }
    digest = hashlib.sha256(payload["endpoint"].encode()).hexdigest()
    with TestClient(app) as first_browser:
        assert first_browser.post(
            "/api/profiles", json={"timezone": "UTC", "units": "metric"}
        ).status_code == 201
        assert first_browser.post("/api/push-subscriptions", json=payload).status_code == 201
    with SessionLocal() as db:
        first_profile_id = db.scalar(
            select(PushSubscription.profile_id).where(
                PushSubscription.endpoint_hash == digest
            )
        )

    with TestClient(app) as recreated_browser:
        assert recreated_browser.post(
            "/api/profiles", json={"timezone": "UTC", "units": "metric"}
        ).status_code == 201
        assert recreated_browser.post("/api/push-subscriptions", json=payload).status_code == 201

    with SessionLocal() as db:
        rows = db.scalars(
            select(PushSubscription).where(
                PushSubscription.endpoint_hash == digest
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].profile_id != first_profile_id
        assert rows[0].platform == "Test browser"


def test_cross_origin_mutation_is_rejected():
    with TestClient(app) as client:
        response = client.post(
            "/api/profiles",
            json={"timezone": "UTC", "units": "metric"},
            headers={"Origin": "https://attacker.invalid"},
        )
        assert response.status_code == 403


def test_location_requests_are_normalized_to_all_directions():
    with TestClient(app, base_url="https://planes.example.test") as client:
        created = client.post(
            "/api/profiles",
            json={"timezone": "America/Los_Angeles", "units": "imperial"},
            headers={"Origin": "https://planes.example.test"},
        )
        assert created.status_code == 201
        location = client.post(
            "/api/locations",
            json={
                "label": "your circle",
                "latitude": 34.0,
                "longitude": -118.0,
                "radius_km": 8,
                "detection_mode": "directional",
                "facing_direction": 270,
                "fov_width": 120,
                "overhead_threshold_km": 1,
                "notification_cooldown_seconds": 1800,
            },
            headers={"Origin": "https://planes.example.test"},
        )
        assert location.status_code == 201, location.text
        assert location.json()["detection_mode"] == "all"
        assert location.json()["facing_direction"] == 0
        assert location.json()["fov_width"] == 360


def test_browser_push_diagnostic_is_accepted_without_secrets():
    with TestClient(app) as client:
        client.post("/api/profiles", json={"timezone": "UTC", "units": "metric"})
        response = client.post(
            "/api/push-diagnostics",
            json={
                "stage": "push-service-subscribe",
                "error_name": "AbortError",
                "error_message": "Registration failed - push service error",
                "permission": "granted",
                "secure_context": True,
                "service_worker_state": "activated",
                "push_manager_available": True,
                "public_key_length": 87,
                "platform": "Test browser",
            },
        )
        assert response.status_code == 202
        assert response.json()["diagnostic_id"]
