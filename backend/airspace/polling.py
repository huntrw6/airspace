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


def group_regions(locations: Iterable[LocationPoint]) -> dict[Region, list[str]]:
    cells: dict[tuple[int, int], list[str]] = {}
    for location in locations:
        latitude_delta = location.radius_km / 111.32
        longitude_scale = max(0.1, math.cos(math.radians(location.latitude)))
        longitude_delta = location.radius_km / (111.32 * longitude_scale)
        south_row, west_column = cell_key(
            max(-90, location.latitude - latitude_delta),
            max(-180, location.longitude - longitude_delta),
        )
        north_row, east_column = cell_key(
            min(90, location.latitude + latitude_delta),
            min(180, location.longitude + longitude_delta),
        )
        for row in range(south_row, north_row + 1):
            for column in range(west_column, east_column + 1):
                ids = cells.setdefault((row, column), [])
                if location.id not in ids:
                    ids.append(location.id)
    result: dict[Region, list[str]] = {}
    for (row, column), ids in cells.items():
        south, west = row * CELL_DEGREES - 90, column * CELL_DEGREES - 180
        region = Region(
            south=south,
            north=south + CELL_DEGREES,
            west=west,
            east=west + CELL_DEGREES,
            key=f"{row}:{column}",
        )
        result[region] = ids
    return result


def deduplicate_flights(flights: Iterable[NormalizedFlight]) -> list[NormalizedFlight]:
    newest: dict[str, NormalizedFlight] = {}
    for flight in flights:
        current = newest.get(flight.flight_id)
        if current is None or flight.observed_at > current.observed_at:
            newest[flight.flight_id] = flight
    return list(newest.values())
