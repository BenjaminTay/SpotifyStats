"""Contract tests — merge level aggregation with seed DB track groups."""

from __future__ import annotations

import pytest

from backend.core.db import load_plays
from backend.domains.playback.track_groups import load_track_group_keys
from backend.services.analysis_stats_service import chart_rows

pytestmark = pytest.mark.contract


class TestTrackGroupKeys:
    def test_l1_returns_empty(self, seed_conn):
        keys = load_track_group_keys(seed_conn, merge_level=1)
        assert keys.empty

    def test_l2_returns_recording_scope(self, seed_conn):
        keys = load_track_group_keys(seed_conn, merge_level=2)
        assert not keys.empty
        assert set(keys["track_group_scope"]) == {"recording"}
        assert set(keys["track_id"]) == {905, 906}

    def test_l3_returns_both_scopes(self, seed_conn):
        keys = load_track_group_keys(seed_conn, merge_level=3)
        assert not keys.empty
        assert set(keys["track_group_scope"]) == {"recording", "composition"}
        assert set(keys["track_id"]) == {905, 906, 907, 908}


class TestMergeLevelAggregation:
    """Verify entity chart aggregation respects merge level."""

    def test_merge_level_does_not_change_valid_play_events(self, seed_conn):
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
            assert sum(row["plays"] for row in rows) == total_events

    def test_l2_merges_remaster_but_not_acoustic(self, seed_conn):
        """L2 (recording): 905+906 merged; 907+908 not merged."""
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
        # Recording group: 905(2 plays) + 906(2 plays) → 4 plays under canonical name
        assert names["Fixture Recording Song"] == 4
        # Not in recording group → remain separate
        assert names["Fixture Composition Song"] == 1
        assert names["Fixture Composition Song - Acoustic"] == 1

    def test_l3_merges_acoustic_but_not_demo(self, seed_conn):
        """L3 (composition): 907+908 merged; 909 not in group."""
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
        # Composition group: 907(1) + 908(1) → 2 plays under canonical name
        assert names["Fixture Composition Song"] == 2
        # Not in any group
        assert names["Fixture Composition Song - Demo"] == 1
        # Recording group still applied at L3
        assert names["Fixture Recording Song"] == 4

    def test_l1_no_merge_all_separate(self, seed_conn):
        """L1: no groups applied, each track counts individually."""
        df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
        _total, rows = chart_rows(
            seed_conn,
            df,
            entity="track",
            metric="plays",
            limit=500,
            offset=0,
            merge_level=1,
        )
        names = {row["track_name"]: row["plays"] for row in rows}
        # Each track counted individually (905=Fixture Recording Song has 2 plays)
        assert names["Fixture Recording Song"] == 2
        assert names["Fixture Recording Song - Remastered"] == 2
        assert names["Fixture Composition Song"] == 1
        assert names["Fixture Composition Song - Acoustic"] == 1
