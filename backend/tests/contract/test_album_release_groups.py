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

    def test_load_map_level3_returns_all_scopes(self, seed_conn):
        """L3 returns release groups with scope resolved through parent chain.
        Standalone release groups keep scope='release'; child release groups
        under a composition parent get scope='composition' (R10)."""
        mapping = load_album_release_group_map(seed_conn, merge_level=3)
        # Seed has no composition groups, so all are standalone release groups
        assert not mapping.empty
        assert set(mapping["scope"]) == {"release"}


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


class TestBillboardApplyAlbumReleaseGroups:
    """Verify Billboard _apply_album_release_groups matches playback resolver behavior."""

    def test_apply_l2_returns_release_only(self, seed_conn):
        """L2: only scope='release' groups are applied (unchanged from old behavior)."""
        import pandas as pd

        from backend.domains.billboard.version_merge import _apply_album_release_groups

        df = pd.DataFrame(
            {
                "billboard_week": ["2026-01-01", "2026-01-01"],
                "album_name": ["Alpha Debut", "Alpha Debut Deluxe"],
                "artist_name": ["Alpha", "Alpha"],
                "play_count": [10, 5],
                "total_ms": [2000000, 1000000],
                "tracks_count": [4, 3],
            }
        )
        result = _apply_album_release_groups(df, merge_level=2)
        names = set(result["album_name"])
        assert "Alpha Debut (Combined)" in names
        assert "Alpha Debut" not in names
        assert "Alpha Debut Deluxe" not in names
        # Both rows merged into one
        assert len(result) == 1

    def test_apply_l3_includes_all_scopes_and_does_not_crash(self, seed_conn):
        """L3: all scope IN ('composition','release') groups returned via COALESCE
        parent resolution (R10). With seed data having no composition parents, this
        is equivalent to L2 — but the query structure is verified."""
        import pandas as pd

        from backend.domains.billboard.version_merge import _apply_album_release_groups

        df = pd.DataFrame(
            {
                "billboard_week": ["2026-01-01", "2026-01-01"],
                "album_name": ["Alpha Debut", "Alpha Debut Deluxe"],
                "artist_name": ["Alpha", "Alpha"],
                "play_count": [10, 5],
                "total_ms": [2000000, 1000000],
                "tracks_count": [4, 3],
            }
        )
        result = _apply_album_release_groups(df, merge_level=3)
        assert len(result) == 1
        assert result.iloc[0]["album_name"] == "Alpha Debut (Combined)"

    def test_apply_l1_no_merge(self, seed_conn):
        """L1: no merge, albums keep original names."""
        import pandas as pd

        from backend.domains.billboard.version_merge import _apply_album_release_groups

        df = pd.DataFrame(
            {
                "billboard_week": ["2026-01-01", "2026-01-01"],
                "album_name": ["Alpha Debut", "Alpha Debut Deluxe"],
                "artist_name": ["Alpha", "Alpha"],
                "play_count": [10, 5],
                "total_ms": [2000000, 1000000],
                "tracks_count": [4, 3],
            }
        )
        result = _apply_album_release_groups(df, merge_level=1)
        assert len(result) == 2
        assert set(result["album_name"]) == {"Alpha Debut", "Alpha Debut Deluxe"}
