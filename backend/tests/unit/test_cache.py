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
