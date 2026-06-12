"""Contract tests — album release group canonicalization."""

from __future__ import annotations

import pytest

from backend.core.db import load_plays
from backend.domains.playback.release_groups import load_album_release_group_map
from backend.services.analysis_stats_service import chart_rows

pytestmark = pytest.mark.contract


class TestReleaseGroupScope:
    def test_load_map_level2_returns_release_scope(self, seed_conn):
        """L2 maps album_id to canonical_name via scope='release'."""
        mapping = load_album_release_group_map(seed_conn, merge_level=2)
        # Seed DB has two release groups
        assert set(mapping["scope"]) == {"release"}
        # Alpha Debut group: albums 1 and 2
        alpha_rows = mapping[mapping["canonical_name"] == "Alpha Debut (Combined)"]
        assert set(alpha_rows["album_id"]) == {1, 2}

    def test_load_map_level1_returns_empty(self, seed_conn):
        """L1 (no merge) returns empty DataFrame."""
        mapping = load_album_release_group_map(seed_conn, merge_level=1)
        assert mapping.empty

    def test_load_map_level3_returns_composition_scope(self, seed_conn):
        """L3 returns composition scope groups (empty unless populated)."""
        mapping = load_album_release_group_map(seed_conn, merge_level=3)
        assert mapping.empty or set(mapping["scope"]) == {"composition"}


class TestPersonalAlbumChartCanonical:
    def test_alpha_debut_merged_in_personal_chart(self, seed_conn):
        """Personal album chart merges Alpha Debut + Alpha Debut Deluxe → canonical."""
        df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
        total, rows = chart_rows(
            seed_conn, df, entity="album", metric="plays", limit=100, offset=0, merge_level=2
        )
        album_names = {row["album_name"] for row in rows}
        # Canonical name should appear instead of individual versions
        assert "Alpha Debut (Combined)" in album_names
        assert "Alpha Debut" not in album_names
        assert "Alpha Debut Deluxe" not in album_names

    def test_fixture_single_excluded_from_default_album_chart(self, seed_conn):
        """Fixture Single (category=single) should not appear in default album chart."""
        df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
        total, rows = chart_rows(
            seed_conn, df, entity="album", metric="plays", limit=100, offset=0, merge_level=2
        )
        album_names = {row["album_name"] for row in rows}
        assert "Fixture Single" not in album_names
