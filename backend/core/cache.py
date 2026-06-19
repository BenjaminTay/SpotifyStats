"""Shared caching utilities: TTL cache, singleflight dedup, global invalidation."""

from __future__ import annotations

import time
from functools import wraps
from threading import RLock


def ttl_cached(ttl_seconds: float, namespace: str = "default"):
    """Decorator: cache function result for ttl_seconds using in-memory dict.

    Use for external API calls (Spotify token, album metadata) where
    lru_cache would hold stale data indefinitely. For DB-backed functions
    with stable results, prefer functools.lru_cache instead.

    Args:
        ttl_seconds: Cache expiry in seconds.
        namespace: Cache namespace for invalidation (default "default").
    """
    cache: dict = {}
    _hits = 0
    _misses = 0
    _lock = RLock()

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            nonlocal _hits, _misses
            key = (fn.__name__, args, tuple(sorted(kwargs.items())))
            now = time.time()
            with _lock:
                if key in cache:
                    cached_at, val = cache[key]
                    if now - cached_at < ttl_seconds:
                        _hits += 1
                        return val
                _misses += 1
            result = fn(*args, **kwargs)
            if result is None:
                return result
            with _lock:
                cache[key] = (now, result)
            return result

        def cache_stats():
            with _lock:
                return {"hits": _hits, "misses": _misses, "size": len(cache)}

        def cache_clear():
            nonlocal _hits, _misses
            with _lock:
                cache.clear()
                _hits = 0
                _misses = 0

        wrapper.cache_clear = cache_clear
        wrapper.cache_stats = cache_stats
        return wrapper

    return decorator


def singleflight(fn):
    """Serialize cache misses so concurrent identical expensive calls don't duplicate work."""
    lock = RLock()

    @wraps(fn)
    def wrapper(*args, **kwargs):
        with lock:
            return fn(*args, **kwargs)

    if hasattr(fn, "cache_clear"):
        wrapper.cache_clear = fn.cache_clear
    if hasattr(fn, "cache_info"):
        wrapper.cache_info = fn.cache_info
    return wrapper


def clear_all_ttl():
    """Clear all registered caches across all namespaces.

    Delegates to the CacheManager which tracks registered @lru_cache
    and @ttl_cached functions by namespace. Safe to call at any time.
    """
    from backend.core.cache_manager import invalidate_all

    invalidate_all()
