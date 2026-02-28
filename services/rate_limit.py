"""Simple sliding-window rate limiter."""

import time
import threading


class _RateLimiter:
    def __init__(self):
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_sec: int) -> bool:
        now = time.monotonic()
        with self._lock:
            times = self._hits.get(key, [])
            # Remove entries outside the window
            times = [t for t in times if now - t < window_sec]
            if not times:
                # Clean up empty keys to prevent memory leak
                self._hits.pop(key, None)
            if len(times) >= limit:
                self._hits[key] = times
                return False
            times.append(now)
            self._hits[key] = times
            return True


_instance = _RateLimiter()


def rate_limit_allow(key: str, limit: int, window_sec: int) -> bool:
    return _instance.allow(key, limit, window_sec)
