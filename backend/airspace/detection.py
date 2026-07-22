import math
from dataclasses import dataclass
from .models import FlightState

EARTH_RADIUS_KM = 6371.0088


def validate_coordinates(latitude: float, longitude: float) -> None:
    if not math.isfinite(latitude) or not -90 <= latitude <= 90:
        raise ValueError("Latitude must be between -90 and 90 degrees.")
    if not math.isfinite(longitude) or not -180 <= longitude <= 180:
        raise ValueError("Longitude must be between -180 and 180 degrees.")


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    validate_coordinates(lat1, lon1)
    validate_coordinates(lat2, lon2)
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def bearing_degrees(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    validate_coordinates(lat1, lon1)
    validate_coordinates(lat2, lon2)
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return math.degrees(math.atan2(y, x)) % 360


def within_fov(bearing: float, facing: float, width: float) -> bool:
    if not 0 < width <= 360:
        raise ValueError("Field of view must be greater than 0 and at most 360 degrees.")
    if width == 360:
        return True
    difference = (bearing - facing + 180) % 360 - 180
    return abs(difference) <= width / 2


def altitude_matches(altitude_ft: int | None, minimum: int | None, maximum: int | None) -> bool:
    if altitude_ft is None:
        return minimum is None and maximum is None
    return (minimum is None or altitude_ft >= minimum) and (
        maximum is None or altitude_ft <= maximum
    )


@dataclass(frozen=True)
class LifecycleInput:
    in_view: bool
    distance_km: float
    previous_distance_km: float | None
    overhead_threshold_km: float
    stale: bool = False
    hold_elapsed: bool = False


def next_state(previous: FlightState | None, item: LifecycleInput) -> FlightState:
    if item.stale:
        return previous or FlightState.detected
    if not item.in_view:
        if previous in {FlightState.held, FlightState.historic, FlightState.expired}:
            return FlightState.historic if item.hold_elapsed else FlightState.held
        return FlightState.held
    if item.distance_km <= item.overhead_threshold_km:
        return FlightState.overhead
    if item.previous_distance_km is None:
        return FlightState.in_view
    if item.distance_km < item.previous_distance_km:
        return FlightState.approaching
    if previous in {FlightState.approaching, FlightState.in_view, FlightState.overhead}:
        return FlightState.departing
    return FlightState.in_view
