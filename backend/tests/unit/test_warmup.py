"""Unit tests for warmup module (no DB — monkeypatch only)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestWarmup:
    def test_warm_common_caches_invokes_hot_paths(self, monkeypatch):
        calls = []

        def fake_load_plays(conn, **kwargs):
            calls.append(("load_plays", kwargs))
            return None

        def fake_load_plays_for_artists(conn, **kwargs):
            calls.append(("load_plays_for_artists", kwargs))
            return None

        def fake_compute_billboard_data(**kwargs):
            calls.append(("compute_billboard_data", kwargs))
            return None

        def fake_analysis_stats(conn, **kwargs):
            calls.append(("get_analysis_stats", kwargs))
            return {}

        def fake_analysis_charts(conn, **kwargs):
            calls.append(("get_analysis_charts", kwargs))
            return {}

        def fake_account_summary(conn):
            calls.append(("get_account_summary", {}))
            return {}

        class FakeConn:
            def close(self):
                calls.append(("close", {}))

        # Patch before importing warmup — analysis functions discard the
        # passed conn and internally call backend.core.db.get_db(), so
        # failing to patch them causes a real DB open in CI (no DB file).
        monkeypatch.setattr("backend.core.warmup.get_db", lambda: FakeConn())
        monkeypatch.setattr("backend.core.warmup.load_plays", fake_load_plays)
        monkeypatch.setattr(
            "backend.core.warmup.load_plays_for_artists", fake_load_plays_for_artists
        )
        monkeypatch.setattr("backend.core.warmup.get_analysis_stats", fake_analysis_stats)
        monkeypatch.setattr("backend.core.warmup.get_analysis_charts", fake_analysis_charts)
        monkeypatch.setattr("backend.core.warmup.get_account_summary", fake_account_summary)
        monkeypatch.setattr(
            "backend.core.warmup.compute_billboard_data", fake_compute_billboard_data
        )

        from backend.core import warmup

        warmup.warm_common_caches()

        assert calls[0][0] == "load_plays"
        assert calls[1][0] == "load_plays_for_artists"
        assert calls[-3][0] == "get_account_summary"
        assert calls[-2][0] == "close"
        assert calls[-1][0] == "compute_billboard_data"
        assert calls[0][1]["min_ms"] == 30000
        assert calls[0][1]["merge_enabled"] is True
        assert calls[0][1]["dynamic_threshold"] is True
        assert calls[1][1]["dynamic_threshold"] is True
        assert calls[-1][1]["bb_top_n"] == 30
        assert calls[-1][1]["dynamic_threshold"] is True
        assert calls[-1][1]["merge_level"] == 2
