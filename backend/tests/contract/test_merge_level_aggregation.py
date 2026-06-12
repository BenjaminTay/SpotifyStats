"""Contract tests — verify track group merge levels do not alter valid play events.

These tests lock the invariant that merge_level only changes aggregation keys,
never the underlying valid-play-event count.
"""

from __future__ import annotations

import pandas as pd
import pytest

from backend.core.db import load_plays
from backend.domains.playback.track_groups import load_track_group_keys
from backend.services.analysis_stats_service import chart_rows

pytestmark = pytest.mark.contract


class TestMergeLevelInvariants:
    def test_merge_level_does_not_change_valid_play_events(self, seed_conn):
        """Valid play events are identical regardless of merge level (R24b)."""
        df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
        total_events = len(df)

        for level in (1, 2, 3):
            _total, rows = chart_rows(
                seed_conn,
                df,
                entity="track",
                metric="plays",
                limit=500,
                offset=0,
                merge_level=level,
            )
            assert sum(row["plays"] for row in rows) == total_events, (
                f"L{level}: sum(plays)={sum(row['plays'] for row in rows)} != events={total_events}"
            )


class TestRecordingScopeMerge:
    """L2 (recording) merges remastered versions but not acoustic/live/demo."""

    def test_l2_merges_recording_group(self, seed_conn):
        df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
        _total, rows = chart_rows(
            seed_conn,
            df,
            entity="track",
            metric="plays",
            limit=500,
            offset=0,
            merge_level=2,
        )
        names = {row["track_name"]: row["plays"] for row in rows}

        # 905 (2 plays) + 906 (2 plays) → canonical "Fixture Recording Song" = 4
        assert names.get("Fixture Recording Song") == 4, (
            f"L2 should merge 905+906 into 'Fixture Recording Song' (4 plays), got {names}"
        )
        # Remastered name should not appear as a separate row
        assert "Fixture Recording Song - Remastered" not in names

    def test_l2_does_not_merge_composition_group(self, seed_conn):
        """Composition-scope groups (acoustic) are NOT merged at L2."""
        df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
        _total, rows = chart_rows(
            seed_conn,
            df,
            entity="track",
            metric="plays",
            limit=500,
            offset=0,
            merge_level=2,
        )
        names = {row["track_name"]: row["plays"] for row in rows}

        # 907 and 908 should remain separate at L2
        assert names.get("Fixture Composition Song") == 1
        assert names.get("Fixture Composition Song - Acoustic") == 1


class TestCompositionScopeMerge:
    """L3 (composition) additionally merges acoustic/live versions."""

    def test_l3_merges_composition_group(self, seed_conn):
        df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
        _total, rows = chart_rows(
            seed_conn,
            df,
            entity="track",
            metric="plays",
            limit=500,
            offset=0,
            merge_level=3,
        )
        names = {row["track_name"]: row["plays"] for row in rows}

        # 907 (1 play) + 908 (1 play) → canonical "Fixture Composition Song" = 2
        assert names.get("Fixture Composition Song") == 2, (
            f"L3 should merge 907+908 into 'Fixture Composition Song' (2 plays), got {names}"
        )
        assert "Fixture Composition Song - Acoustic" not in names

    def test_l3_does_not_merge_ungrouped_demo(self, seed_conn):
        """Track 909 (Demo) is intentionally excluded from groups — stays separate at L3."""
        df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
        _total, rows = chart_rows(
            seed_conn,
            df,
            entity="track",
            metric="plays",
            limit=500,
            offset=0,
            merge_level=3,
        )
        names = {row["track_name"]: row["plays"] for row in rows}

        assert names.get("Fixture Composition Song - Demo") == 1

    def test_l3_still_merges_recording_group(self, seed_conn):
        """L3 includes recording scope, so remaster merge still happens."""
        df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
        _total, rows = chart_rows(
            seed_conn,
            df,
            entity="track",
            metric="plays",
            limit=500,
            offset=0,
            merge_level=3,
        )
        names = {row["track_name"]: row["plays"] for row in rows}

        assert names.get("Fixture Recording Song") == 4
        assert "Fixture Recording Song - Remastered" not in names


class TestLoadTrackGroupKeys:
    """Direct tests for load_track_group_keys against seed DB."""

    def test_returns_empty_for_l1(self, seed_conn):
        keys = load_track_group_keys(seed_conn, merge_level=1)
        assert keys.empty
        assert list(keys.columns) == [
            "track_id",
            "track_agg_id",
            "track_agg_name",
            "track_group_scope",
        ]

    def test_l2_returns_recording_scope_groups(self, seed_conn):
        keys = load_track_group_keys(seed_conn, merge_level=2)
        assert not keys.empty
        assert set(keys["track_group_scope"].unique()) == {"recording"}
        track_ids = set(keys["track_id"])
        assert 905 in track_ids
        assert 906 in track_ids

    def test_l2_maps_remaster_to_canonical(self, seed_conn):
        keys = load_track_group_keys(seed_conn, merge_level=2)
        key_map = keys.set_index("track_id")
        assert key_map.loc[905, "track_agg_name"] == "Fixture Recording Song"
        assert key_map.loc[906, "track_agg_name"] == "Fixture Recording Song"
        assert key_map.loc[905, "track_agg_id"] == key_map.loc[906, "track_agg_id"]

    def test_l3_returns_both_scopes(self, seed_conn):
        keys = load_track_group_keys(seed_conn, merge_level=3)
        assert not keys.empty
        scopes = set(keys["track_group_scope"].unique())
        assert scopes == {"recording", "composition"}

    def test_l3_maps_composition_group_members(self, seed_conn):
        keys = load_track_group_keys(seed_conn, merge_level=3)
        key_map = keys.set_index("track_id")
        assert key_map.loc[907, "track_agg_name"] == "Fixture Composition Song"
        assert key_map.loc[908, "track_agg_name"] == "Fixture Composition Song"

    def test_l3_does_not_map_ungrouped_track(self, seed_conn):
        """Track 909 (Demo) is intentionally not in any group."""
        keys = load_track_group_keys(seed_conn, merge_level=3)
        assert 909 not in set(keys["track_id"])


class TestPreAggCrossAlbumMerge:
    """Issue 2: pre_agg path merges canonical tracks across different albums."""

    def test_pre_agg_merges_cross_album_canonical_tracks(self, seed_conn):
        """When pre_agg data has same canonical track from different albums,
        they should be merged into a single entry with canonical album_name."""
        from backend.domains.billboard.chart_ranking import compute_weekly_rankings

        # Load pre_agg data from seed DB
        agg_df = pd.read_sql_query("SELECT * FROM agg_weekly_tracks", seed_conn)
        # Filter to fixture recording group tracks only
        agg_df = agg_df[agg_df["track_id"].isin([905, 906])]
        # Convert billboard_week to string for consistency
        agg_df["billboard_week"] = agg_df["billboard_week"].astype(str)

        # Need artist_name and album_name for the ranking function
        agg_df["artist_name"] = "Fixture Artist Alpha"
        agg_df["album_name"] = agg_df["track_id"].map(
            {905: "Fixture LP", 906: "Fixture Release Album"}
        )
        agg_df["track_name"] = agg_df["track_id"].map(
            {905: "Fixture Recording Song", 906: "Fixture Recording Song - Remastered"}
        )

        result = compute_weekly_rankings(None, top_n=10, pre_agg=agg_df, merge_level=2)

        # After L2 canonicalization, 905+906 should merge into single canonical row
        canonical_rows = result[result["track_name"] == "Fixture Recording Song"]
        assert len(canonical_rows) > 0, "Canonical track should appear in result"

        # All canonical rows should share the same canonical album_name
        # (primary track 905's album: Fixture LP)
        album_names = set(canonical_rows["album_name"])
        assert album_names == {"Fixture LP"}, (
            f"Expected canonical album 'Fixture LP', got {album_names}"
        )

    def test_canonicalized_album_name_prevents_duplicate_rows(self, seed_conn):
        """Without album_name canonicalization, same canonical track would
        produce duplicate rows (one per original album). With the fix, one row."""
        from backend.domains.billboard.chart_ranking import compute_weekly_rankings

        agg_df = pd.read_sql_query("SELECT * FROM agg_weekly_tracks", seed_conn)
        agg_df = agg_df[agg_df["track_id"].isin([905, 906])]
        agg_df["billboard_week"] = agg_df["billboard_week"].astype(str)
        agg_df["artist_name"] = "Fixture Artist Alpha"
        agg_df["album_name"] = agg_df["track_id"].map(
            {905: "Fixture LP", 906: "Fixture Release Album"}
        )
        agg_df["track_name"] = agg_df["track_id"].map(
            {905: "Fixture Recording Song", 906: "Fixture Recording Song - Remastered"}
        )

        result = compute_weekly_rankings(None, top_n=10, pre_agg=agg_df, merge_level=2)

        # Each billboard_week should have at most one row for the canonical track
        weekly_counts = result.groupby("billboard_week")["track_id"].apply(list)
        for week, track_ids in weekly_counts.items():
            canonical_count = sum(
                1
                for tid in track_ids
                if result.loc[
                    (result["billboard_week"] == week) & (result["track_id"] == tid), "track_name"
                ].iloc[0]
                == "Fixture Recording Song"
            )
            assert canonical_count <= 1, (
                f"Week {week}: canonical track appears {canonical_count} times (expected ≤1)"
            )
