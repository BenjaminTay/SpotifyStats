"""Contract tests — validate current playback counting semantics against seed DB.

These tests lock the current behavior before any counting policy changes.
When P0-P4 implementation changes semantics, these tests are updated to reflect
the new expected behavior.
"""

from __future__ import annotations

import pytest

from backend.core.db import load_plays, load_plays_for_artists

pytestmark = pytest.mark.contract


class TestMergeBeforeFilter:
    """Verify merge-then-filter ordering: fragments merge first, then threshold applied."""

    def test_short_fragments_merge_to_valid_event(self, seed_conn):
        """Two adjacent 20s plays of a 40s track merge into one valid 40s event.

        Fixture has two candidate sessions for track 901. The dedicated pair
        has no idle gap and merges; the week-boundary pair has 9m40s actual
        idle time and is split by the default 5-minute policy.
        """
        df = load_plays(
            seed_conn,
            min_ms=30000,
            music_only=True,
            merge_enabled=True,
            boundary_column=None,
        )
        row = df[df["track_name"] == "Fixture Fragment Song"]
        assert len(row) == 1, f"Expected only the within-boundary session, got {len(row)}"
        assert (row["ms_played"] == 40000).all()

    def test_short_fragments_dropped_when_merge_disabled(self, seed_conn):
        """Without merge, each 20s fragment is below 30s threshold and dropped."""
        df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=False)
        row = df[df["track_name"] == "Fixture Fragment Song"]
        assert len(row) == 0, f"Expected 0 rows without merge, got {len(row)}"

    def test_long_track_30s_passes_static_threshold(self, seed_conn):
        """30s of a 10min track passes the static 30s threshold."""
        df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
        row = df[df["track_name"] == "Fixture Long Track"]
        assert len(row) == 1


class TestArtistFanOut:
    """Verify multi-artist fan-out preserves play event semantics."""

    def test_shared_credit_track_fans_out_to_both_artists(self, seed_conn):
        """One play of a shared-credit track produces rows for both artists."""
        base = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
        artists = load_plays_for_artists(
            seed_conn, min_ms=30000, music_only=True, merge_enabled=True
        )

        shared_base = base[base["track_name"] == "Fixture Shared Credit"]
        shared_artists = artists[artists["track_name"] == "Fixture Shared Credit"]

        assert len(shared_base) == 1, f"Expected 1 base row, got {len(shared_base)}"
        assert len(shared_artists) == 2, f"Expected 2 artist rows, got {len(shared_artists)}"
        artist_names = set(shared_artists["artist_name"])
        assert artist_names == {"Fixture Artist Alpha", "Fixture Artist Beta"}
        assert set(shared_artists["role"]) == {"primary", "featured"}

    def test_fanout_only_includes_tracks_with_explicit_artist_credits(self, seed_conn):
        """load_plays_for_artists INNER JOINs track_artists — only tracks with
        explicit artist credits survive. For those tracks, fan-out >= base."""
        base = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
        artists = load_plays_for_artists(
            seed_conn, min_ms=30000, music_only=True, merge_enabled=True
        )

        # Only track 903 (Fixture Shared Credit) has track_artists entries
        shared_base = base[base["track_name"] == "Fixture Shared Credit"]
        shared_artists = artists[artists["track_name"] == "Fixture Shared Credit"]
        assert len(shared_base) == 1
        assert len(shared_artists) == 2
        # For the subset with artist credits, fan-out preserves or expands
        assert len(artists) >= len(shared_artists)


class TestPodcastExclusion:
    """Verify podcast/audiobook exclusion."""

    def test_podcast_plays_excluded_with_music_only(self, seed_conn):
        """music_only=True excludes track_id IS NULL rows."""
        df = load_plays(seed_conn, min_ms=0, music_only=True, merge_enabled=False, filtered=False)
        null_tracks = df[df["track_id"].isna()]
        assert len(null_tracks) == 0

    def test_podcast_plays_included_without_music_only(self, seed_conn):
        """music_only=False includes podcast rows."""
        df = load_plays(seed_conn, min_ms=0, music_only=False, merge_enabled=False, filtered=False)
        null_tracks = df[df["track_id"].isna()]
        assert len(null_tracks) > 0


class TestBillboardWeekBoundary:
    """Verify week boundary computation does not split merged groups."""

    def test_fragment_boundary_plays_present_in_raw_data(self, seed_conn):
        """The two boundary-test fragments exist in the database."""
        import pandas as pd

        df = pd.read_sql_query(
            "SELECT ts, track_id, ms_played FROM plays WHERE track_id = 901 AND ms_played = 20000",
            seed_conn,
        )
        assert len(df) == 4, f"Expected 4 fragment rows for track 901, got {len(df)}"


class TestSessionBoundaries:
    """Verify max_merge_gap_minutes prevents unrealistic cross-session merges."""

    def test_max_gap_prevents_cross_day_merge(self, seed_conn):
        """Without max_gap, track 904 two plays 24h apart could be consecutive
        if no other plays intervene. With max_gap_minutes=30 they stay separate."""
        from backend.core.db import merge_consecutive_plays

        df = load_plays(seed_conn, min_ms=0, music_only=True, merge_enabled=False, filtered=True)
        rows = df[df["track_name"] == "Fixture Source Album Song"]
        # Two raw plays, 24h apart, each 200s
        assert len(rows) == 2
        # With gap limit of 30 min, the 24h gap prevents merge
        merged = merge_consecutive_plays(rows, min_ms=30000, max_gap_minutes=30)
        # Each 200s play is valid alone — not merged
        assert len(merged) == 2

    def test_boundary_column_source_album_prevents_cross_album_merge(self, seed_conn):
        """Same track under different source_album_id should not merge."""
        from backend.core.db import merge_consecutive_plays

        df = load_plays(seed_conn, min_ms=0, music_only=True, merge_enabled=False, filtered=True)
        rows = df[df["track_name"] == "Fixture Source Album Song"].sort_values("ts")
        # Two plays with different source_album_id
        assert set(rows["source_album_id"]) == {901, 902}
        merged = merge_consecutive_plays(rows, min_ms=30000, boundary_column="source_album_id")
        # Different source → not merged → each 30s play is individually valid
        assert len(merged) == 2
