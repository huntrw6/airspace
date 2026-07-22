import os

os.environ.update(
    AIRSPACE_DATABASE_URL="sqlite://",
    AIRSPACE_COOKIE_SECURE="false",
    AIRSPACE_SESSION_PEPPER="test-pepper",
    AIRSPACE_ADMIN_PASSWORD="admin-test",
)
from fastapi.testclient import TestClient
from airspace.main import app


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


def test_cross_origin_mutation_is_rejected():
    with TestClient(app) as client:
        response = client.post(
            "/api/profiles",
            json={"timezone": "UTC", "units": "metric"},
            headers={"Origin": "https://attacker.invalid"},
        )
        assert response.status_code == 403


def test_onboarding_directional_location_through_request_host():
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
                "label": "My viewing spot",
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
