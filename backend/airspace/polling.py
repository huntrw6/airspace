import math
from collections.abc import Iterable
from dataclasses import dataclass
from .providers import NormalizedFlight, Region

CELL_DEGREES = 0.25


@dataclass(frozen=True)
class LocationPoint:
    id: str
    latitude: float
    longitude: float
    radius_km: float = 0


def cell_key(latitude: float, longitude: float) -> tuple[int, int]:
    max_row = math.ceil(180 / CELL_DEGREES) - 1
    max_column = math.ceil(360 / CELL_DEGREES) - 1
    row = math.floor((latitude + 90) / CELL_DEGREES)
    column = math.floor((longitude + 180) / CELL_DEGREES)
    return min(max(row, 0), max_row), min(max(column, 0), max_column)


def group_regions(
    locations: Iterable[LocationPoint], query_padding_km: float = 0
) -> dict[Region, list[str]]:
    cells: dict[tuple[int, int], list[LocationPoint]] = {}
    for location in locations:
        cells.setdefault(cell_key(location.latitude, location.longitude), []).append(location)
    result: dict[Region, list[str]] = {}
    for (row, column), grouped_locations in cells.items():
        bounds: list[tuple[float, float, float, float]] = []
        for location in grouped_locations:
            covered_km = max(0, location.radius_km) + max(0, query_padding_km)
            latitude_delta = covered_km / 111.32
            longitude_scale = max(0.1, math.cos(math.radians(location.latitude)))
            longitude_delta = covered_km / (111.32 * longitude_scale)
            bounds.append(
                (
                    location.latitude - latitude_delta,
                    location.latitude + latitude_delta,
                    location.longitude - longitude_delta,
                    location.longitude + longitude_delta,
                )
            )
        region = Region(
            south=max(-90, min(bound[0] for bound in bounds)),
            north=min(90, max(bound[1] for bound in bounds)),
            west=max(-180, min(bound[2] for bound in bounds)),
            east=min(180, max(bound[3] for bound in bounds)),
            key=f"{row}:{column}",
        )
        result[region] = [location.id for location in grouped_locations]
    return result


def deduplicate_flights(flights: Iterable[NormalizedFlight]) -> list[NormalizedFlight]:
    newest: dict[str, NormalizedFlight] = {}
    for flight in flights:
        current = newest.get(flight.flight_id)
        if current is None or flight.observed_at > current.observed_at:
            newest[flight.flight_id] = flight
    return list(newest.values())
