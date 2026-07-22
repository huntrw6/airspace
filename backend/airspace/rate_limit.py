import hashlib
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass(frozen=True)
class LimitResult:
    allowed: bool
    retry_after: int = 0


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, maximum: int, window_seconds: int) -> LimitResult:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= maximum:
                return LimitResult(False, max(1, int(events[0] + window_seconds - now) + 1))
            events.append(now)
            if not events:
                self._events.pop(key, None)
        return LimitResult(True)


def privacy_key(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
