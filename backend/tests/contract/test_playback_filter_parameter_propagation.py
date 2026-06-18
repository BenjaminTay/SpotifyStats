"""Contract tests for playback filter parameter propagation.

These lock the promise that public endpoints using PlayFilters/BillboardFilters
actually pass dynamic_threshold and max_merge_gap_minutes into the counting
pipeline instead of exposing inert query parameters.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


def _sum_rows(rows, key="plays"):
    return sum(int(row.get(key, 0)) for row in rows)


class TestPlayFilterPropagation:
    def test_dashboard_summary_applies_dynamic_threshold(self, client):
        static = client.get(
            "/api/dashboard/summary",
            params={
                "min_ms": 30000,
                "music_only": True,
                "merge_enabled": True,
                "dynamic_threshold": False,
            },
        ).json()
        dynamic = client.get(
            "/api/dashboard/summary",
            params={
                "min_ms": 30000,
                "music_only": True,
                "merge_enabled": True,
                "dynamic_threshold": True,
            },
        ).json()

        assert static["total_plays"] > dynamic["total_plays"]

    def test_leaderboard_applies_dynamic_threshold(self, client):
        params = {
            "min_ms": 30000,
            "music_only": True,
            "merge_enabled": True,
            "entity": "track",
            "top_n": 100,
            "merge_level": 1,
        }
        static = client.get(
            "/api/leaderboard",
            params={**params, "dynamic_threshold": False},
        ).json()
        dynamic = client.get(
            "/api/leaderboard",
            params={**params, "dynamic_threshold": True},
        ).json()

        assert _sum_rows(static["rows"]) > _sum_rows(dynamic["rows"])

    def test_timeline_applies_dynamic_threshold(self, client):
        params = {"min_ms": 30000, "music_only": True, "merge_enabled": True}
        static = client.get(
            "/api/timeline/annual",
            params={**params, "dynamic_threshold": False},
        ).json()
        dynamic = client.get(
            "/api/timeline/annual",
            params={**params, "dynamic_threshold": True},
        ).json()

        assert _sum_rows(static) > _sum_rows(dynamic)

    def test_music_entity_stats_apply_dynamic_threshold(self, client):
        params = {"min_ms": 30000, "music_only": True, "merge_enabled": True}
        static = client.get(
            "/api/music/tracks/902/stats",
            params={**params, "dynamic_threshold": False},
        ).json()
        dynamic = client.get(
            "/api/music/tracks/902/stats",
            params={**params, "dynamic_threshold": True},
        ).json()

        assert static["found"] is True
        assert dynamic["found"] is False


class TestReleaseCycleFilterPropagation:
    def test_release_cycle_weekly_data_uses_filters_and_year_bounds(self, seed_conn):
        from backend.api.billboard.release_cycle import _get_weekly_data
        from backend.dependencies import BillboardFilters

        filters = BillboardFilters(
            min_ms=30000,
            music_only=True,
            bb_top_n=100,
            bb_album_top_n=100,
            bb_artist_top_n=100,
            bb_week_start_dow=4,
            bb_week_start_hour=0,
            year_start=2026,
            year_end=2026,
            dynamic_threshold=True,
            max_merge_gap_minutes=30,
        )

        df_raw, weekly, weekly_artist, weekly_album = _get_weekly_data(
            filters,
            merge_level=1,
            include_compilations=True,
        )

        assert not df_raw.empty
        assert "Fixture Long Track" not in set(df_raw["track_name"])
        assert all(df_raw["billboard_week"].apply(lambda week: week.year == 2026))
        assert weekly is not None
        assert weekly_artist is not None
        assert weekly_album is not None
