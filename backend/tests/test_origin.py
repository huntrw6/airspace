from airspace.origin import origin_is_allowed


def test_accepts_public_and_request_hosts() -> None:
    assert origin_is_allowed(
        "https://planes.example.com", "https://planes.example.com", "airspace:7373"
    )
    assert origin_is_allowed(
        "http://192.0.2.5:7373", "https://planes.example.com", "192.0.2.5:7373"
    )


def test_forwarded_host_requires_explicit_proxy_trust() -> None:
    args = (
        "https://planes.example.com",
        "http://internal:7373",
        "internal:7373",
        "planes.example.com",
    )
    assert not origin_is_allowed(*args, trust_forwarded=False)
    assert origin_is_allowed(*args, trust_forwarded=True)


def test_rejects_cross_origin_request() -> None:
    assert not origin_is_allowed(
        "https://attacker.invalid", "https://planes.example.com", "planes.example.com"
    )
