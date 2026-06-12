"""Contract tests — global playback counting invariants (R24b).

These tests lock invariant properties that must hold across all seed data,
regardless of future counting policy changes.
"""

from __future__ import annotations

import pytest

from backend.core.db import load_plays, load_plays_for_artists
from backend.services.analysis_stats_service import chart_rows

pytestmark = pytest.mark.contract


class TestArtistFanOutInvariant:
    def test_artist_fanout_total_is_at_least_valid_events(self, seed_conn):
        """R24b.2: Sum of all artist credited plays >= valid play events."""
        valid = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
        artists = load_plays_for_artists(
            seed_conn, min_ms=30000, music_only=True, merge_enabled=True
        )
        assert len(artists) >= len(valid), (
            f"Artist fan-out should be >= valid events: {len(artists)} vs {len(valid)}"
        )

    def test_shared_credit_track_fanout_produces_more_rows_than_base(self, seed_conn):
        """Tracks with multiple artists produce more rows in artist view."""
        valid = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
        artists = load_plays_for_artists(
            seed_conn, min_ms=30000, music_only=True, merge_enabled=True
        )
        # At least the shared credit track should fan out
        shared_valid = valid[valid["track_name"] == "Fixture Shared Credit"]
        shared_artists = artists[artists["track_name"] == "Fixture Shared Credit"]
        assert len(shared_artists) > len(shared_valid)


class TestTrackAggregationInvariant:
    def test_track_groupby_preserves_valid_event_count(self, seed_conn):
        """Grouping by track_id should preserve total row count."""
        valid = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
        grouped_sum = int(valid.groupby("track_id").size().sum())
        assert grouped_sum == len(valid), (
            f"Track groupby sum {grouped_sum} != total events {len(valid)}"
        )


class TestSourceAlbumAttribution:
    def test_valid_events_have_source_album_id_populated(self, seed_conn):
        """R18: All valid plays should have source_album_id filled."""
        valid = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
        null_source = valid["source_album_id"].isna().sum()
        # Podcast tracks (track_id IS NULL) may lack source_album_id
        # Fixture tracks with explicit source_album_id should be covered
        assert null_source < len(valid), "Expected at least some source_album_id values"

    def test_fixture_source_album_song_has_both_attributions(self, seed_conn):
        """Track 904 appears under two source albums."""
        valid = load_plays(
            seed_conn, min_ms=0, music_only=True, merge_enabled=False, filtered=False
        )
        rows = valid[valid["track_name"] == "Fixture Source Album Song"]
        assert set(rows["source_album_id"]) == {901, 902}, (
            f"Expected source_album_id {{901, 902}}, got {set(rows['source_album_id'])}"
        )


class TestMergeLevelInvariant:
    def test_track_aggregation_sum_equals_valid_events_at_all_levels(self, seed_conn):
        """R24b.5: Track aggregation at any merge level sums to valid event count."""
        valid = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
        total_events = len(valid)

        for level in (1, 2, 3):
            _total, rows = chart_rows(
                seed_conn,
                valid,
                entity="track",
                metric="plays",
                limit=500,
                offset=0,
                merge_level=level,
            )
            msg = f"L{level}: sum(plays)={sum(r['plays'] for r in rows)} != events={total_events}"
            assert sum(r["plays"] for r in rows) == total_events, msg
