from airspace.aircraft import ICAO_HELICOPTER_CODES, aircraft_kind


def test_current_icao_helicopter_snapshot_covers_common_families():
    assert len(ICAO_HELICOPTER_CODES) == 178
    for code in ("R44", "B407", "EC35", "H60", "H64", "H47", "S76", "A139", "MI8"):
        assert aircraft_kind(code) == "helicopter"


def test_only_positive_helicopter_evidence_changes_the_plane_fallback():
    assert aircraft_kind("B738", "Boeing 737-800") == "plane"
    assert aircraft_kind("V22", "Bell Boeing V-22 Osprey") == "plane"
    assert aircraft_kind(None, None) == "plane"
    assert aircraft_kind(None, "Airbus Helicopters H145") == "helicopter"
    assert aircraft_kind("UHEL") == "helicopter"
