"""Shared caching utilities: TTL cache, singleflight dedup, global invalidation."""

from __future__ import annotations

import time
from functools import wraps
from threading import Lock, RLock


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
    """Deduplicate concurrent calls by key without serializing unrelated work.

    The previous implementation used one global lock per wrapped function.  A
    slow cold miss for one entity therefore blocked cache hits and misses for
    every other entity.  Per-key locks retain identical-call deduplication while
    allowing independent home/detail/stat requests to proceed concurrently.
    """
    locks_guard = RLock()
    locks: dict[tuple, tuple[Lock, int]] = {}

    def call_key(args, kwargs) -> tuple:
        return args, tuple(sorted(kwargs.items()))

    @wraps(fn)
    def wrapper(*args, **kwargs):
        key = call_key(args, kwargs)
        with locks_guard:
            lock, users = locks.get(key, (Lock(), 0))
            locks[key] = (lock, users + 1)
        try:
            with lock:
                return fn(*args, **kwargs)
        finally:
            with locks_guard:
                current = locks.get(key)
                if current is not None:
                    current_lock, users = current
                    if users <= 1:
                        locks.pop(key, None)
                    else:
                        locks[key] = (current_lock, users - 1)

    if hasattr(fn, "cache_clear"):
        wrapper.cache_clear = fn.cache_clear
    if hasattr(fn, "cache_info"):
        wrapper.cache_info = fn.cache_info

    def singleflight_stats():
        with locks_guard:
            return {"active_keys": len(locks)}

    wrapper.singleflight_stats = singleflight_stats
    return wrapper


def clear_all_ttl():
    """Clear all registered caches across all namespaces.

    Delegates to the CacheManager which tracks registered @lru_cache
    and @ttl_cached functions by namespace. Safe to call at any time.
    """
    from backend.core.cache_manager import invalidate_all

    invalidate_all()
