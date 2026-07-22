import pytest
from airspace.detection import (
    LifecycleInput,
    altitude_matches,
    bearing_degrees,
    distance_km,
    next_state,
    within_fov,
)
from airspace.models import FlightState


def test_zero_coordinates_are_valid():
    assert distance_km(0, 0, 0, 1) == pytest.approx(111.195, rel=0.001)
    assert bearing_degrees(0, 0, 1, 0) == pytest.approx(0)


@pytest.mark.parametrize(
    ("bearing", "expected"), [(350, True), (10, True), (40, False), (0, True), (360, True)]
)
def test_fov_crosses_north(bearing, expected):
    assert within_fov(bearing, 0, 60) is expected


def test_fov_edges_are_inclusive():
    assert within_fov(45, 90, 90)
    assert within_fov(135, 90, 90)


def test_unknown_altitude_does_not_become_zero():
    assert altitude_matches(None, None, None)
    assert not altitude_matches(None, 0, 60000)


def test_lifecycle_held_is_not_visible():
    held = next_state(FlightState.in_view, LifecycleInput(False, 4, 3, 1))
    assert held is FlightState.held
    assert (
        next_state(held, LifecycleInput(False, 4, 3, 1, hold_elapsed=True)) is FlightState.historic
    )


def test_stale_data_cannot_advance_state():
    assert (
        next_state(FlightState.detected, LifecycleInput(True, 0.2, 3, 1, stale=True))
        is FlightState.detected
    )
