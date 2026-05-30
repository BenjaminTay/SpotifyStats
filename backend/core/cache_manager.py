"""Centralized cache manager: namespace registration, invalidation, metrics.

Replaces the empty clear_all_ttl() stub with real namespace-based
invalidation driven by settings changes and data imports.
"""

from __future__ import annotations

from collections.abc import Callable
from threading import RLock
from typing import Any

_registry_lock = RLock()
_lru_registry: dict[str, dict[str, Callable]] = {}  # namespace -> key -> fn
_ttl_registry: dict[str, dict[str, Any]] = {}  # namespace -> key -> wrapper


# ── Registration ──────────────────────────────────────────────────────────


def register_lru(namespace: str, key: str, fn: Callable) -> None:
    """Register an @lru_cache decorated function for invalidation and stats."""
    with _registry_lock:
        _lru_registry.setdefault(namespace, {})[key] = fn


def register_ttl(namespace: str, key: str, wrapper: Any) -> None:
    """Register a @ttl_cached decorated function wrapper for invalidation and stats."""
    with _registry_lock:
        _ttl_registry.setdefault(namespace, {})[key] = wrapper


# ── Invalidation ──────────────────────────────────────────────────────────


def invalidate(namespace: str) -> None:
    """Clear all registered caches within a namespace."""
    with _registry_lock:
        for fn in _lru_registry.get(namespace, {}).values():
            if hasattr(fn, "cache_clear"):
                fn.cache_clear()
        for wrapper in _ttl_registry.get(namespace, {}).values():
            if hasattr(wrapper, "cache_clear"):
                wrapper.cache_clear()


def invalidate_all() -> None:
    """Clear all registered caches across all namespaces."""
    with _registry_lock:
        for ns_fns in _lru_registry.values():
            for fn in ns_fns.values():
                if hasattr(fn, "cache_clear"):
                    fn.cache_clear()
        for ns_wrappers in _ttl_registry.values():
            for wrapper in ns_wrappers.values():
                if hasattr(wrapper, "cache_clear"):
                    wrapper.cache_clear()


# ── Stats ─────────────────────────────────────────────────────────────────


def get_stats() -> dict[str, dict[str, Any]]:
    """Return cache metrics grouped by namespace.

    Returns:
        {namespace: {"lru": {key: {hits, misses, currsize, maxsize}},
                      "ttl": {key: {hits, misses}}}}
    """
    result: dict[str, dict[str, Any]] = {}
    with _registry_lock:
        for ns, fns in _lru_registry.items():
            entry = result.setdefault(ns, {})
            lru_stats = {}
            for key, fn in fns.items():
                if hasattr(fn, "cache_info"):
                    info = fn.cache_info()
                    lru_stats[key] = {
                        "hits": info.hits,
                        "misses": info.misses,
                        "currsize": info.currsize,
                        "maxsize": info.maxsize,
                    }
            if lru_stats:
                entry["lru"] = lru_stats
        for ns, wrappers in _ttl_registry.items():
            entry = result.setdefault(ns, {})
            ttl_stats = {}
            for key, wrapper in wrappers.items():
                if hasattr(wrapper, "cache_stats"):
                    ttl_stats[key] = wrapper.cache_stats()
            if ttl_stats:
                entry["ttl"] = ttl_stats
    return result
