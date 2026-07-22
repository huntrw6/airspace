import httpx
import pytest

from airspace.aircraft_photos import AircraftPhotoService
from airspace.config import Settings


@pytest.mark.asyncio
async def test_photo_lookup_returns_attributed_thumbnail_and_caches_result():
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        assert request.url.path.endswith("/pub/photos/reg/N62889")
        return httpx.Response(200, json={"photos": [{
            "thumbnail_large": {"src": "https://t.plnspttrs.net/photo.jpg"},
            "link": "https://www.planespotters.net/photo/123/example",
            "photographer": "Example Photographer",
        }]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = AircraftPhotoService(Settings(), client=client)
    first = await service.lookup("n62889")
    second = await service.lookup("N62889")
    assert first == second
    assert first and first.photographer == "Example Photographer"
    assert requests == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_photo_lookup_rejects_untrusted_image_host():
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(
        200,
        json={"photos": [{
            "thumbnail": {"src": "https://attacker.invalid/photo.jpg"},
            "link": "https://www.planespotters.net/photo/123/example",
            "photographer": "Example Photographer",
        }]},
    )))
    service = AircraftPhotoService(Settings(), client=client)
    assert await service.lookup("N62889") is None
    await client.aclose()
