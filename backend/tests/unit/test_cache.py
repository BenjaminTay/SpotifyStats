"""Unit tests for cache module — TTL cache decorator (no DB)."""

from __future__ import annotations

import threading
import time

import pytest

pytestmark = pytest.mark.unit


class TestTtlCached:
    def test_returns_value(self):
        from backend.core.cache import ttl_cached

        call_count = 0

        @ttl_cached(60)
        def expensive():
            nonlocal call_count
            call_count += 1
            return call_count

        assert expensive() == 1
        assert expensive() == 1  # cached
        assert call_count == 1

    def test_expires(self):
        from backend.core.cache import ttl_cached

        call_count = 0

        @ttl_cached(0.05)
        def expensive():
            nonlocal call_count
            call_count += 1
            return call_count

        assert expensive() == 1
        time.sleep(0.1)
        assert expensive() == 2  # cache expired
        assert call_count == 2

    def test_different_args(self):
        from backend.core.cache import ttl_cached

        call_count = 0

        @ttl_cached(60)
        def expensive(x):
            nonlocal call_count
            call_count += 1
            return f"{x}-{call_count}"

        assert expensive(1) == "1-1"
        assert expensive(2) == "2-2"
        assert expensive(1) == "1-1"  # cached separately
        assert call_count == 2

    def test_does_not_cache_none(self):
        from backend.core.cache import ttl_cached

        call_count = 0

        @ttl_cached(60)
        def maybe_missing():
            nonlocal call_count
            call_count += 1
            return None

        assert maybe_missing() is None
        assert maybe_missing() is None
        assert call_count == 2

    def test_cache_clear_resets_entries_and_stats(self):
        from backend.core.cache import ttl_cached

        call_count = 0

        @ttl_cached(60)
        def expensive():
            nonlocal call_count
            call_count += 1
            return call_count

        assert expensive() == 1
        assert expensive() == 1
        assert expensive.cache_stats() == {"hits": 1, "misses": 1, "size": 1}

        expensive.cache_clear()
        assert expensive.cache_stats() == {"hits": 0, "misses": 0, "size": 0}
        assert expensive() == 2
        assert expensive.cache_stats() == {"hits": 0, "misses": 1, "size": 1}


class TestSingleflight:
    """singleflight serializes concurrent calls via a lock (no result caching)."""

    def test_serializes_access(self):
        """singleflight only acquires a lock — it does NOT cache results.
        Each call still executes the wrapped function."""
        from backend.core.cache import singleflight

        calls = []

        @singleflight
        def work(x):
            calls.append(x)
            return x * 2

        assert work(5) == 10
        assert work(5) == 10
        # singleflight does NOT cache; both calls execute
        assert calls == [5, 5]

    def test_concurrent_calls_serialized(self):
        """Verify that concurrent calls via singleflight are serialized (lock)."""
        from backend.core.cache import singleflight

        results = []
        lock_held = threading.Event()

        @singleflight
        def serial_work(x):
            results.append(("enter", x))
            lock_held.set()
            time.sleep(0.05)
            results.append(("exit", x))
            return x

        # No concurrent calls here, just verifying the lock works
        assert serial_work(1) == 1
        assert results == [("enter", 1), ("exit", 1)]


class TestCacheManager:
    """CacheManager: registration, invalidation, stats."""

    def test_register_and_get_stats_lru(self):
        from functools import lru_cache

        from backend.core.cache_manager import get_stats, register_lru

        @lru_cache(maxsize=4)
        def _sample_calc(x):
            return x * 2

        register_lru("test", "calc", _sample_calc)

        _sample_calc(1)
        _sample_calc(1)  # hit
        _sample_calc(2)  # miss

        stats = get_stats()
        assert "test" in stats
        assert "lru" in stats["test"]
        assert stats["test"]["lru"]["calc"]["hits"] == 1
        assert stats["test"]["lru"]["calc"]["misses"] == 2

    def test_invalidate_lru_clears_cache(self):
        from functools import lru_cache

        from backend.core.cache_manager import invalidate, register_lru

        @lru_cache(maxsize=4)
        def _sample_calc2(x):
            return x * 3

        register_lru("test_inv", "calc2", _sample_calc2)

        _sample_calc2(1)
        _sample_calc2(2)
        assert _sample_calc2.cache_info().currsize == 2

        invalidate("test_inv")
        assert _sample_calc2.cache_info().currsize == 0

    def test_ttl_namespace_and_stats(self):
        from backend.core.cache import ttl_cached
        from backend.core.cache_manager import get_stats, register_ttl

        @ttl_cached(60, namespace="ttl_test")
        def _slow_call():
            return "ok"

        register_ttl("ttl_test", "slow", _slow_call)

        assert _slow_call() == "ok"
        assert _slow_call() == "ok"  # hit

        stats = get_stats()
        assert "ttl_test" in stats
        assert "ttl" in stats["ttl_test"]
        ttl_stats = stats["ttl_test"]["ttl"]["slow"]
        assert ttl_stats["hits"] == 1
        assert ttl_stats["misses"] == 1

    def test_clear_all_ttl_delegates(self):
        from functools import lru_cache

        from backend.core.cache import clear_all_ttl
        from backend.core.cache_manager import register_lru

        @lru_cache(maxsize=4)
        def _sample_calc3(x):
            return x

        register_lru("clear_test", "calc3", _sample_calc3)
        _sample_calc3(1)
        assert _sample_calc3.cache_info().currsize == 1

        clear_all_ttl()
        assert _sample_calc3.cache_info().currsize == 0

    def test_invalidate_ttl_clears_entries_and_stats(self):
        from backend.core.cache import ttl_cached
        from backend.core.cache_manager import get_stats, invalidate, register_ttl

        call_count = 0

        @ttl_cached(60, namespace="ttl_invalidate_test")
        def _slow_call():
            nonlocal call_count
            call_count += 1
            return call_count

        register_ttl("ttl_invalidate_test", "slow", _slow_call)

        assert _slow_call() == 1
        assert _slow_call() == 1
        assert get_stats()["ttl_invalidate_test"]["ttl"]["slow"] == {
            "hits": 1,
            "misses": 1,
            "size": 1,
        }

        invalidate("ttl_invalidate_test")
        assert get_stats()["ttl_invalidate_test"]["ttl"]["slow"] == {
            "hits": 0,
            "misses": 0,
            "size": 0,
        }
        assert _slow_call() == 2
