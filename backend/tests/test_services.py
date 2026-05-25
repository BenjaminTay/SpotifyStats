"""Service layer tests — validate computation logic directly.

These tests call service functions directly (bypassing HTTP) to verify
computation correctness with concrete data assertions.
"""

import pytest


# ═══════════════════════════════════════════════════════════════════════════
# Play Service
# ═══════════════════════════════════════════════════════════════════════════

class TestPlayService:
    def test_dashboard_summary(self):
        from backend.services.play_service import get_dashboard_summary
        from backend.core.db import get_db

        conn = get_db()
        try:
            result = get_dashboard_summary(conn, min_ms=30000, music_only=True, merge_enabled=True)
            assert result["total_plays"] > 50000
            assert result["total_hours"] > 3000
            assert result["total_tracks"] > 4000
            assert result["total_artists"] > 500
            assert result["total_plays"] >= result["total_tracks"]
        finally:
            conn.close()

    def test_dashboard_summary_numeric_types(self):
        from backend.services.play_service import get_dashboard_summary
        from backend.core.db import get_db

        conn = get_db()
        try:
            result = get_dashboard_summary(conn, min_ms=30000, music_only=True, merge_enabled=True)
            for k, v in result.items():
                assert isinstance(v, (int, float)), f"{k} is {type(v)}"
        finally:
            conn.close()

    def test_dashboard_monthly_trend(self):
        from backend.services.play_service import get_monthly_trend
        from backend.core.db import get_db

        conn = get_db()
        try:
            data = get_monthly_trend(conn, min_ms=30000, music_only=True, merge_enabled=True)
            assert len(data) > 40
            for m in data:
                assert "period" in m
                assert "plays" in m
                assert "hours" in m
        finally:
            conn.close()

    def test_timeline_annual(self):
        from backend.services.play_service import get_annual_timeline
        from backend.core.db import get_db

        conn = get_db()
        try:
            data = get_annual_timeline(conn, min_ms=30000, music_only=True, merge_enabled=True)
            assert len(data) >= 4
            years = [y["year"] for y in data]
            assert years == sorted(years)
            for y in data:
                assert y["plays"] > 0
                assert y["hours"] > 0
                assert y["unique_tracks"] > 0
        finally:
            conn.close()

    def test_leaderboard_tracks(self):
        from backend.services.play_service import get_leaderboard
        from backend.core.db import get_db

        conn = get_db()
        try:
            data = get_leaderboard(conn, min_ms=30000, music_only=True, merge_enabled=True,
                                   entity="track", metric="plays", top_n=10)
            assert len(data["rows"]) == 10
            for row in data["rows"]:
                assert row["rank"] >= 1
                assert row["plays"] > 0
                assert row["track_name"]
                assert row["artist_name"]
        finally:
            conn.close()

    def test_leaderboard_artists(self):
        from backend.services.play_service import get_leaderboard
        from backend.core.db import get_db

        conn = get_db()
        try:
            data = get_leaderboard(conn, min_ms=30000, music_only=True, merge_enabled=True,
                                   entity="artist", metric="hours", top_n=10)
            assert len(data["rows"]) == 10
            assert data["rows"][0]["artist_name"] == "Taylor Swift"
        finally:
            conn.close()

    def test_behavior_data(self):
        from backend.services.play_service import get_behavior_data
        from backend.core.db import get_db

        conn = get_db()
        try:
            data = get_behavior_data(conn, min_ms=30000, music_only=True, merge_enabled=True)
            assert len(data["reason_end"]) >= 5
            assert len(data["reason_start"]) >= 5
            assert len(data["fwdbtn_by_hour"]) == 24
            assert len(data["most_forwarded"]) > 0
            assert len(data["shuffle_rate_by_platform"]) > 0
        finally:
            conn.close()

    def test_wrapped_2024(self):
        from backend.services.play_service import get_wrapped_data
        from backend.core.db import get_db

        conn = get_db()
        try:
            data = get_wrapped_data(conn, min_ms=30000, music_only=True, merge_enabled=True, year=2024)
            assert data["year"] == 2024
            assert data["empty"] is False
            assert data["hero"] is not None
            assert len(data["top_artists"]) == 5
            assert len(data["top_tracks"]) == 5
            assert len(data["monthly_pulse"]) == 12
        finally:
            conn.close()

    def test_wrapped_empty_year(self):
        from backend.services.play_service import get_wrapped_data
        from backend.core.db import get_db

        conn = get_db()
        try:
            data = get_wrapped_data(conn, min_ms=30000, music_only=True, merge_enabled=True, year=2010)
            assert data["year"] == 2010
            assert data["empty"] is True
        finally:
            conn.close()

    def test_listening_heatmap(self):
        from backend.services.play_service import get_listening_heatmap
        from backend.core.db import get_db

        conn = get_db()
        try:
            data = get_listening_heatmap(conn, min_ms=30000, music_only=True, merge_enabled=True)
            assert len(data["z"]) == 7
            assert len(data["z"][0]) == 24
            assert data["x"] == list(range(24))
            assert len(data["y"]) == 7
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# Billboard Service
# ═══════════════════════════════════════════════════════════════════════════

class TestBillboardService:
    def test_compute_billboard_data_meta(self):
        from backend.services.billboard_service import compute_billboard_data

        result = compute_billboard_data(
            min_ms=30000, music_only=True,
            bb_top_n=30, bb_album_top_n=20, bb_artist_top_n=20,
        )
        meta = result["meta"]
        assert meta["total_weeks"] >= 150
        assert meta["total_filtered_records"] > 50000
        assert len(meta["all_weeks_asc"]) == meta["total_weeks"]

    def test_compute_billboard_data_weekly(self):
        from backend.services.billboard_service import compute_billboard_data

        result = compute_billboard_data(bb_top_n=30)
        weekly = result["weekly"]
        assert len(weekly) > 5000
        entry = weekly[0]
        assert 1 <= entry["rank"] <= 30
        assert isinstance(entry["billboard_week"], str)
        assert isinstance(entry["track_name"], str)

    def test_compute_billboard_data_track_summary(self):
        from backend.services.billboard_service import compute_billboard_data

        result = compute_billboard_data(bb_top_n=30)
        ts = result["track_summary"]
        assert len(ts) > 500
        assert ts[0]["peak_position"] >= 1
        assert ts[0]["weeks_on_chart"] >= 1

    def test_compute_billboard_data_records(self):
        from backend.services.billboard_service import compute_billboard_data

        result = compute_billboard_data(bb_top_n=30)
        assert len(result["records"]) >= 12

    def test_compute_billboard_data_power_scores(self):
        from backend.services.billboard_service import compute_billboard_data

        result = compute_billboard_data(bb_top_n=30)
        assert len(result["power_scores"]) > 0
        assert len(result["album_power_scores"]) > 0
        assert len(result["artist_power_scores"]) > 0

    def test_year_filter(self):
        from backend.services.billboard_service import compute_billboard_data

        result_all = compute_billboard_data(bb_top_n=30)
        result_2024 = compute_billboard_data(bb_top_n=30, year_start=2024, year_end=2024)

        assert result_2024["meta"]["total_weeks"] < result_all["meta"]["total_weeks"]
        assert result_2024["meta"]["total_weeks"] == 52
        assert len(result_2024["weekly"]) < len(result_all["weekly"])


# ═══════════════════════════════════════════════════════════════════════════
# Release Cycle Service
# ═══════════════════════════════════════════════════════════════════════════

class TestReleaseCycleService:
    @pytest.fixture(scope="class")
    def _df_raw(self):
        from backend.services.billboard_service import load_billboard_raw
        return load_billboard_raw(30000, True, week_start_dow=4, week_start_hour=0)

    def test_load_artist_list(self, _df_raw):
        from backend.services.release_cycle_service import load_artist_list

        data = load_artist_list(_df_raw)
        assert len(data) > 100
        assert isinstance(data[0], dict)
        assert "artist_name" in data[0]
        assert "track_count" in data[0]
        assert data[0]["track_count"] > 0

    def test_load_artist_releases(self):
        from backend.services.release_cycle_service import load_artist_releases

        releases = load_artist_releases("Taylor Swift")
        assert len(releases) > 10
        cols = releases.columns.tolist()
        for c in ["album_name", "release_date", "album_type"]:
            assert c in cols

    def test_compute_artist_summary(self):
        from backend.services.release_cycle_service import (
            load_artist_releases, compute_artist_summary,
        )
        from backend.services.billboard_service import (
            load_billboard_raw, compute_weekly_rankings,
            compute_artist_weekly_rankings, compute_album_weekly_rankings,
        )

        df_raw = load_billboard_raw(30000, True, week_start_dow=4, week_start_hour=0)
        releases = load_artist_releases("Taylor Swift")
        weekly = compute_weekly_rankings(df_raw, 30)
        weekly_artist = compute_artist_weekly_rankings(df_raw, 20)
        weekly_album = compute_album_weekly_rankings(df_raw, 20)

        summary = compute_artist_summary(
            "Taylor Swift", releases, weekly, weekly_artist, weekly_album,
        )
        assert summary["total_albums"] > 0
        assert summary["total_singles"] > 0


# ═══════════════════════════════════════════════════════════════════════════
# Core Utilities
# ═══════════════════════════════════════════════════════════════════════════

class TestJsonHelpers:
    def test_py_val_none(self):
        from backend.core.json_helpers import py_val
        assert py_val(None) is None

    def test_py_val_int(self):
        from backend.core.json_helpers import py_val
        assert py_val(42) == 42
        assert isinstance(py_val(42), int)

    def test_py_val_float(self):
        from backend.core.json_helpers import py_val
        assert py_val(3.14) == 3.14

    def test_py_val_numpy_int(self):
        import numpy as np
        from backend.core.json_helpers import py_val
        v = py_val(np.int64(42))
        assert v == 42
        assert isinstance(v, int)

    def test_py_val_numpy_float(self):
        import numpy as np
        from backend.core.json_helpers import py_val
        v = py_val(np.float64(3.14))
        assert isinstance(v, float)

    def test_py_val_nan(self):
        import numpy as np
        from backend.core.json_helpers import py_val
        assert py_val(np.nan) is None
        assert py_val(float("nan")) is None

    def test_df_to_json_empty(self):
        from backend.core.json_helpers import df_to_json
        assert df_to_json(None) == []

    def test_df_to_json_basic(self):
        import pandas as pd
        from backend.core.json_helpers import df_to_json

        df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
        result = df_to_json(df)
        assert len(result) == 2
        assert result[0] == {"a": 1, "b": "x"}
        assert result[1] == {"a": 2, "b": "y"}


class TestCache:
    def test_ttl_cached_returns_value(self):
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

    def test_ttl_cached_expires(self):
        import time
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

    def test_ttl_cached_different_args(self):
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
