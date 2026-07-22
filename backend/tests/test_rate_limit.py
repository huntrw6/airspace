from unittest.mock import patch

from airspace.rate_limit import SlidingWindowLimiter, privacy_key


def test_sliding_window_rejects_then_recovers() -> None:
    limiter = SlidingWindowLimiter()
    with patch("airspace.rate_limit.time.monotonic", side_effect=[0.0, 1.0, 2.0, 11.0]):
        assert limiter.check("client", 2, 10).allowed
        assert limiter.check("client", 2, 10).allowed
        rejected = limiter.check("client", 2, 10)
        assert not rejected.allowed
        assert rejected.retry_after == 9
        assert limiter.check("client", 2, 10).allowed


def test_privacy_key_does_not_retain_input() -> None:
    assert privacy_key("192.0.2.1") != "192.0.2.1"
    assert privacy_key("192.0.2.1") == privacy_key("192.0.2.1")
