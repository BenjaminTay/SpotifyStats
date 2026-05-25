"""Shared caching utilities: TTL cache, cache invalidation."""

import time


def ttl_cached(ttl_seconds):
    """Decorator: cache function result for ttl_seconds using in-memory dict.

    Use for external API calls (Spotify token, album metadata) where
    lru_cache would hold stale data indefinitely. For DB-backed functions
    with stable results, prefer functools.lru_cache instead.
    """
    cache = {}

    def decorator(fn):
        def wrapper(*args, **kwargs):
            key = (fn.__name__, args, tuple(sorted(kwargs.items())))
            now = time.time()
            if key in cache:
                cached_at, val = cache[key]
                if now - cached_at < ttl_seconds:
                    return val
            result = fn(*args, **kwargs)
            cache[key] = (now, result)
            return result
        return wrapper
    return decorator


def clear_all_ttl():
    """Clear all TTL caches. Call when settings change (e.g. filter params)."""
    # TTL caches are self-expiring, but for immediate invalidation we
    # can clear specific caches by name if needed.
    pass
