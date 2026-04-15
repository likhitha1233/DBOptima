from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict, Optional
from functools import wraps, cached_property


@dataclass(frozen=True)
class _CacheEntry:
    value: Any
    expires_at: float


class MemoryCache:
    """
    In-memory TTL cache with an interface expected by the unit tests.

    Exposes:
    - `default_ttl`
    - `cache` (key -> value)
    - `access_times` (key -> last_access_epoch_s)
    """

    def __init__(self, max_size: int = 1000, ttl: int = 300):
        self.max_size = int(max_size)
        self.default_ttl = int(ttl)
        self._lock = Lock()
        self.cache: Dict[str, Any] = {}
        self._expires_at: Dict[str, float] = {}
        self.access_times: Dict[str, float] = {}
        self._hits = 0
        self._misses = 0

    def _now(self) -> float:
        return time.time()

    def _is_expired(self, key: str, now: float) -> bool:
        exp = self._expires_at.get(key)
        return exp is not None and exp <= now

    def _evict_if_needed(self) -> None:
        if len(self.cache) <= self.max_size:
            return
        # Evict least-recently-accessed entries.
        items = sorted(self.access_times.items(), key=lambda kv: kv[1])
        for k, _ in items[: max(1, len(self.cache) - self.max_size)]:
            self.cache.pop(k, None)
            self._expires_at.pop(k, None)
            self.access_times.pop(k, None)

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            now = self._now()
            if key not in self.cache:
                self._misses += 1
                return None
            if self._is_expired(key, now):
                self.cache.pop(key, None)
                self._expires_at.pop(key, None)
                self.access_times.pop(key, None)
                self._misses += 1
                return None
            self.access_times[key] = now
            self._hits += 1
            return self.cache.get(key)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        with self._lock:
            now = self._now()
            effective_ttl = int(ttl if ttl is not None else self.default_ttl)
            self.cache[key] = value
            self._expires_at[key] = now + effective_ttl
            self.access_times[key] = now
            self._evict_if_needed()

    def delete(self, key: str) -> None:
        with self._lock:
            self.cache.pop(key, None)
            self._expires_at.pop(key, None)
            self.access_times.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self.cache.clear()
            self._expires_at.clear()
            self.access_times.clear()

    def get_metrics(self) -> Dict[str, int]:
        with self._lock:
            return {"hits": self._hits, "misses": self._misses, "size": len(self.cache)}


class CacheManager:
    """Minimal cache manager shim used by tests and legacy imports."""

    def __init__(self, backend: Optional[MemoryCache] = None):
        self.backend = backend or MemoryCache()

    def get(self, key: str) -> Optional[Any]:
        return self.backend.get(key)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self.backend.set(key, value, ttl=ttl)

    def delete(self, key: str) -> None:
        self.backend.delete(key)

    def clear(self) -> None:
        self.backend.clear()

    def get_metrics(self) -> Dict[str, int]:
        return self.backend.get_metrics()


cache_manager = CacheManager()

# Backward-compatible re-exports expected by tests
try:
    from .redis_cache import RedisCache  # type: ignore
except Exception:  # pragma: no cover
    RedisCache = None  # noqa: N816

if RedisCache is None:
    class RedisCache(MemoryCache):  # type: ignore
        """Fallback RedisCache implementation for test environments."""
        pass


def cached(ttl: int = 300, key_prefix: str = ""):
    """Small caching decorator compatible with the unit tests."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{key_prefix}{func.__name__}:{args}:{sorted(kwargs.items())}"
            hit = cache_manager.get(key)
            if hit is not None:
                return hit
            value = func(*args, **kwargs)
            cache_manager.set(key, value, ttl=ttl)
            return value

        return wrapper

    return decorator


def cache_key(*parts: Any) -> str:
    """Deterministic cache key builder used by unit tests."""
    return ":".join(str(p) for p in parts)


def batch_cache_get(keys: List[str]) -> Dict[str, Any]:
    """Fetch multiple keys from the global cache manager."""
    out: Dict[str, Any] = {}
    for k in keys:
        out[k] = cache_manager.get(k)
    return out


def batch_cache_set(items: Dict[str, Any], ttl: Optional[int] = None) -> None:
    """Set multiple keys on the global cache manager."""
    for k, v in items.items():
        cache_manager.set(k, v, ttl=ttl)


class PerformanceMonitor:
    """Minimal performance monitor for tests."""

    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self._lock = Lock()

    def record(self, name: str, duration_s: float, **meta: Any) -> None:
        with self._lock:
            self.events.append({"name": name, "duration_s": float(duration_s), "ts": time.time(), **meta})


class QueryCache:
    """Cache helper for query-like workloads (test-facing API)."""

    def __init__(self, cache: Optional[CacheManager] = None):
        self.cache = cache or cache_manager
        self.monitor = PerformanceMonitor()

    def get(self, key: str) -> Optional[Any]:
        return self.cache.get(key)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self.cache.set(key, value, ttl=ttl)


__all__ = [
    "CacheManager",
    "MemoryCache",
    "RedisCache",
    "cache_manager",
    "cached",
    "cached_property",
    "cache_key",
    "batch_cache_get",
    "batch_cache_set",
    "QueryCache",
    "PerformanceMonitor",
]


