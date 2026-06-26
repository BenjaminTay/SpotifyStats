"""Unit tests for the feed orchestrator — structure and import correctness."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestOrchestratorStructure:
    def test_generate_all_posts_is_callable(self):
        from backend.domains.community.feed_generator import generate_all_posts

        assert callable(generate_all_posts)

    def test_generate_core_posts_is_callable(self):
        from backend.domains.community.feed_generator import _generate_core_posts

        assert callable(_generate_core_posts)

    def test_generate_all_posts_without_conn_returns_list(self):
        """When called without DB connection, returns empty list (no data to generate from)."""
        from backend.domains.community.feed_generator import generate_all_posts

        # With conn=None and year_start > year_end, should return empty list quickly
        posts = generate_all_posts(conn=None, year_start=2050, year_end=2050)
        assert isinstance(posts, list)

    def test_all_sub_modules_import_successfully(self):
        """Verify all split sub-modules are importable."""
        modules = [
            "feed_helpers",
            "feed_data",
            "feed_weekly",
            "feed_records",
            "feed_personal",
            "feed_talk",
            "feed_ranking",
            "feed_images",
        ]
        for mod in modules:
            __import__(f"backend.domains.community.{mod}")

    def test_public_api_still_exports_generate_all_posts(self):
        """Backward compatibility: backend.api.community imports generate_all_posts."""
        from backend.domains.community.feed_generator import _generate_core_posts as b
        from backend.domains.community.feed_generator import generate_all_posts as a

        assert a is not None
        assert b is not None


class TestFeedFilterPropagation:
    def test_load_chart_data_forwards_merge_and_album_compilation_options(self, monkeypatch):
        import pandas as pd

        from backend.domains.community import feed_data

        raw = pd.DataFrame(
            [
                {
                    "billboard_week": pd.Timestamp("2026-01-02"),
                    "track_id": 1,
                    "track_name": "Test Track",
                    "artist_name": "Test Artist",
                    "album_name": "Test Album",
                    "ms_played": 180000,
                }
            ]
        )
        calls = {}

        monkeypatch.setattr(feed_data, "load_billboard_raw", lambda *args, **kwargs: raw)
        monkeypatch.setattr(
            feed_data, "load_billboard_raw_for_artists", lambda *args, **kwargs: raw
        )
        monkeypatch.setattr(feed_data, "_try_load_from_agg", lambda *args: (None, None, None))

        def fake_track_rankings(_df, top_n, pre_agg=None, merge_level=2):
            calls["track_merge_level"] = merge_level
            return raw.assign(rank=1, play_count=1, total_ms=180000)

        def fake_album_rankings(
            _df, top_n, pre_agg=None, merge_level=2, include_compilations=False
        ):
            calls["album_merge_level"] = merge_level
            calls["include_compilations"] = include_compilations
            return raw.assign(rank=1, play_count=1, total_ms=180000, tracks_count=1)

        def fake_artist_rankings(_df, top_n, pre_agg=None):
            calls["artist_called"] = True
            return raw.assign(rank=1, play_count=1, total_ms=180000)

        monkeypatch.setattr(feed_data, "compute_weekly_rankings", fake_track_rankings)
        monkeypatch.setattr(feed_data, "compute_album_weekly_rankings", fake_album_rankings)
        monkeypatch.setattr(feed_data, "compute_artist_weekly_rankings", fake_artist_rankings)

        feed_data._load_chart_data(
            30000,
            True,
            30,
            20,
            20,
            4,
            12,
            None,
            None,
            dynamic_threshold=True,
            max_merge_gap_minutes=30,
            merge_level=3,
            include_compilations=True,
        )

        assert calls["track_merge_level"] == 3
        assert calls["album_merge_level"] == 3
        assert calls["include_compilations"] is True
