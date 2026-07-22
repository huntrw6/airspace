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
