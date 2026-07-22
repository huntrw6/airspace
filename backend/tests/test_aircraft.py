from airspace.aircraft import ICAO_HELICOPTER_CODES, aircraft_kind


def test_known_icao_helicopters_are_classified_without_affecting_unknowns():
    assert len(ICAO_HELICOPTER_CODES) == 178
    for code in ("R44", "B407", "EC35", "H60", "S76", "MI8", "H145"):
        assert aircraft_kind(code) == "helicopter"
    assert aircraft_kind("B738") == "plane"
    assert aircraft_kind(None) == "plane"


def test_model_description_is_a_backward_compatible_fallback():
    assert aircraft_kind(None, "Airbus Helicopters H145") == "helicopter"
    assert aircraft_kind(None, "Experimental rotorcraft") == "helicopter"
    assert aircraft_kind(None, "Airbus A330") == "plane"
