"""Unit tests for warmup module (no DB — monkeypatch only)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestWarmup:
    def test_warm_common_caches_invokes_hot_paths(self, monkeypatch):
        from backend.core import warmup

        calls = []

        def fake_load_plays(conn, **kwargs):
            calls.append(("load_plays", kwargs))
            return None

        def fake_compute_billboard_data(**kwargs):
            calls.append(("compute_billboard_data", kwargs))
            return None

        class FakeConn:
            def close(self):
                calls.append(("close", {}))

        monkeypatch.setattr(warmup, "get_db", lambda: FakeConn())
        monkeypatch.setattr(warmup, "load_plays", fake_load_plays)
        monkeypatch.setattr(warmup, "compute_billboard_data", fake_compute_billboard_data)

        warmup.warm_common_caches()

        assert calls[0][0] == "load_plays"
        assert calls[1][0] == "close"
        assert calls[2][0] == "compute_billboard_data"
        assert calls[0][1]["min_ms"] == 30000
        assert calls[0][1]["merge_enabled"] is True
        assert calls[2][1]["bb_top_n"] == 30
