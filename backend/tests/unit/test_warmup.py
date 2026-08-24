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

        def fake_archive_overview(conn):
            calls.append(("get_archive_overview", {}))
            return {}

        def fake_yearly_review_prewarm():
            calls.append(("prewarm_latest_yearly_review", {}))
            return 2026

        def fake_home_prewarm():
            calls.append(("prewarm_default_home_overview", {}))

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
        monkeypatch.setattr("backend.core.warmup.get_archive_overview", fake_archive_overview)
        monkeypatch.setattr(
            "backend.core.warmup.compute_billboard_data", fake_compute_billboard_data
        )
        monkeypatch.setattr(
            "backend.services.yearly_review_service.prewarm_latest_yearly_review",
            fake_yearly_review_prewarm,
        )
        monkeypatch.setattr(
            "backend.services.home_service.prewarm_default_home_overview",
            fake_home_prewarm,
        )

        from backend.core import warmup

        warmup.warm_common_caches()

        assert calls[0][0] == "prewarm_default_home_overview"
        assert calls[1][0] == "load_plays"
        assert calls[2][0] == "load_plays_for_artists"
        assert calls[4][0] == "compute_billboard_data"
        assert calls[5][0] == "prewarm_default_home_overview"
        assert calls[-2][0] == "close"
        assert calls[-1][0] == "prewarm_latest_yearly_review"
        assert calls[1][1]["min_ms"] == 30000
        assert calls[1][1]["merge_enabled"] is True
        assert calls[1][1]["dynamic_threshold"] is True
        assert calls[2][1]["dynamic_threshold"] is True
        assert calls[4][1]["bb_top_n"] == 30
        assert calls[4][1]["dynamic_threshold"] is True
        assert calls[4][1]["merge_level"] == 2
