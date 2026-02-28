"""In-memory cache with TTL, max size, and automatic cleanup."""

import time
import threading

MAX_CACHE_SIZE = 2000
_CLEANUP_INTERVAL = 100  # run cleanup every N sets


class _Cache:
    def __init__(self, max_size: int = MAX_CACHE_SIZE):
        self._store: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()
        self._max_size = max_size
        self._set_count = 0

    def get(self, key: str):
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires, value = entry
            if time.monotonic() > expires:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value, ttl_seconds: int):
        with self._lock:
            self._store[key] = (time.monotonic() + ttl_seconds, value)
            self._set_count += 1
            # Periodic cleanup
            if self._set_count % _CLEANUP_INTERVAL == 0:
                self._cleanup_locked()
            # Evict oldest entries if over max size
            if len(self._store) > self._max_size:
                self._evict_oldest_locked()

    def delete(self, key: str):
        with self._lock:
            self._store.pop(key, None)

    def delete_prefix(self, prefix: str):
        with self._lock:
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                del self._store[k]

    def clear(self):
        with self._lock:
            self._store.clear()

    def cleanup(self):
        """Remove all expired entries (public API)."""
        with self._lock:
            self._cleanup_locked()

    def _cleanup_locked(self):
        """Remove expired entries (must hold lock)."""
        now = time.monotonic()
        expired = [k for k, (exp, _) in self._store.items() if now > exp]
        for k in expired:
            del self._store[k]

    def _evict_oldest_locked(self):
        """Remove oldest entries until under max_size (must hold lock)."""
        # First, remove expired
        self._cleanup_locked()
        # If still over, evict by earliest expiration
        while len(self._store) > self._max_size:
            oldest_key = min(self._store, key=lambda k: self._store[k][0])
            del self._store[oldest_key]


_instance = _Cache()


def cache_get(key: str):
    return _instance.get(key)


def cache_set(key: str, value, ttl_seconds: int):
    _instance.set(key, value, ttl_seconds)


def cache_delete(key: str):
    _instance.delete(key)


def cache_delete_prefix(prefix: str):
    _instance.delete_prefix(prefix)


def cache_clear():
    _instance.clear()
