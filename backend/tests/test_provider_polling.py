from datetime import datetime, timedelta, timezone

import httpx
import pytest
import airspace.providers as provider_module
from airspace.polling import LocationPoint, deduplicate_flights, group_regions
from airspace.providers import (
    FlightRadar24Provider,
    NormalizedFlight,
    ProviderError,
    ProviderRateLimited,
    merge_fr24_details,
    parse_flight_record,
    parse_fr24_feed_item,
)


def test_nearby_locations_share_request():
    regions = group_regions(
        [LocationPoint("a", 38.50, -121.49), LocationPoint("b", 38.51, -121.48)]
    )
    assert len(regions) == 1
    assert sorted(next(iter(regions.values()))) == ["a", "b"]


def test_radius_crossing_cell_boundary_queries_adjacent_cells():
    regions = group_regions([LocationPoint("edge", 38.50, -121.50, radius_km=3)])
    assert len(regions) == 4
    assert all(ids == ["edge"] for ids in regions.values())


def test_query_padding_expands_bounds_without_adding_regions():
    location = LocationPoint("buffered", 34.0, -117.9125, radius_km=8)
    original = group_regions([location])
    padded = group_regions([location], query_padding_km=2)
    assert len(original) == len(padded) == 2
    assert {region.key for region in original} == {region.key for region in padded}
    original_by_key = {region.key: region for region in original}
    for region in padded:
        before = original_by_key[region.key]
        assert region.north > before.north
        assert region.south < before.south
        assert region.east > before.east
        assert region.west < before.west


def test_duplicate_regional_results_keep_newest():
    now = datetime.now(timezone.utc)
    old = NormalizedFlight("x", "p", 1, 1, now)
    new = NormalizedFlight("x", "p", 2, 2, now + timedelta(seconds=1))
    assert deduplicate_flights([new, old]) == [new]


def test_parser_handles_missing_optional_fields():
    flight = parse_flight_record({"id": "abc", "latitude": 0, "longitude": 0, "altitude": None})
    assert flight.altitude_ft is None and flight.latitude == 0


@pytest.mark.parametrize(
    "record",
    [{}, {"id": "x", "latitude": "bad", "longitude": 2}, {"id": "", "latitude": 1, "longitude": 2}],
)
def test_malformed_record_isolated(record):
    with pytest.raises(ProviderError):
        parse_flight_record(record)


def test_fr24_positional_payload_is_centralized_and_typed():
    record = [
        "abc123",
        0,
        0,
        270,
        8500,
        220,
        "",
        "radar",
        "B738",
        "N123",
        1_700_000_000,
        "PHX",
        "SMF",
        "WN123",
        0,
        0,
        "WN123",
        0,
        "Southwest",
    ]
    parsed = parse_fr24_feed_item("provider-id", record)
    assert parsed.latitude == 0 and parsed.longitude == 0
    assert parsed.altitude_ft == 8500 and parsed.callsign == "WN123"


def test_details_handle_missing_fields_without_erasing_position():
    base = NormalizedFlight("x", "p", 1, 2, datetime.now(timezone.utc), callsign="X1")
    merged = merge_fr24_details(base, {"airline": {"name": "Example Air"}})
    assert merged.latitude == 1 and merged.callsign == "X1" and merged.airline == "Example Air"


@pytest.mark.asyncio
async def test_regional_feed_requests_all_airborne_position_sources():
    captured: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured
        captured = request
        return httpx.Response(200, json={"full_count": 0})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = FlightRadar24Provider(
        "https://feed.invalid", "https://details.invalid", client=client
    )
    region = next(iter(group_regions([LocationPoint("home", 38.5, -121.5)])))

    assert await provider.get_flights_in_region(region) == []
    assert captured is not None
    params = captured.url.params
    assert all(
        params[source] == "1"
        for source in ("faa", "satellite", "mlat", "flarm", "adsb", "air", "estimated", "gliders")
    )
    assert params["gnd"] == "0"
    assert params["vehicles"] == "0"
    assert params["limit"] == "5000"
    assert params["bounds"] == (f"{region.north},{region.south},{region.west},{region.east}")
    await client.aclose()


@pytest.mark.asyncio
async def test_detail_cache_reuses_successful_result():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"airline": {"name": "Cached Air"}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = FlightRadar24Provider(
        "https://feed.invalid", "https://details.invalid", client=client
    )
    base = NormalizedFlight("x", "provider-id", 1, 2, datetime.now(timezone.utc))
    assert (await provider.enrich(base)).airline == "Cached Air"
    assert (await provider.enrich(base)).airline == "Cached Air"
    assert calls == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_failed_detail_lookup_is_not_cached(monkeypatch):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls <= 3:
            return httpx.Response(500, json={})
        return httpx.Response(200, json={"airline": {"name": "Recovered Air"}})

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(provider_module.asyncio, "sleep", no_sleep)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = FlightRadar24Provider(
        "https://feed.invalid", "https://details.invalid", client=client
    )
    base = NormalizedFlight("x", "provider-id", 1, 2, datetime.now(timezone.utc))
    with pytest.raises(ProviderError):
        await provider.enrich(base)
    assert (await provider.enrich(base)).airline == "Recovered Air"
    assert calls == 4
    await client.aclose()


@pytest.mark.asyncio
async def test_rate_limit_fails_fast_and_enters_host_cooldown():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={"Retry-After": "120"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = FlightRadar24Provider(
        "https://feed.invalid", "https://details.invalid", client=client
    )
    region = next(iter(group_regions([LocationPoint("home", 38.5, -121.5)])))
    with pytest.raises(ProviderRateLimited, match="cooling down 120"):
        await provider.get_flights_in_region(region)
    with pytest.raises(ProviderRateLimited, match="cooling down"):
        await provider.get_flights_in_region(region)
    assert calls == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_detail_requests_are_budgeted_per_poll_cycle():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"airline": {"name": "Detailed Air"}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = FlightRadar24Provider(
        "https://feed.invalid",
        "https://details.invalid",
        detail_requests_per_cycle=1,
        client=client,
    )
    now = datetime.now(timezone.utc)
    first = NormalizedFlight("one", "provider-one", 1, 2, now)
    second = NormalizedFlight("two", "provider-two", 1, 2, now)
    assert (await provider.enrich(first)).airline == "Detailed Air"
    assert (await provider.enrich(second)).airline is None
    provider.begin_poll_cycle()
    assert (await provider.enrich(second)).airline == "Detailed Air"
    assert calls == 2
    await client.aclose()
