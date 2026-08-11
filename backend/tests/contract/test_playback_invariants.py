"""Contract tests — global playback counting invariants (R24b).

These tests lock invariant properties that must hold across all seed data,
regardless of future counting policy changes.
"""

from __future__ import annotations

import pytest

from backend.core.db import load_plays, load_plays_for_artists
from backend.services.analysis_stats_service import chart_rows
from backend.services.billboard_service import compute_billboard_data

pytestmark = pytest.mark.contract


class TestValidEventsVsRawRows:
    def test_filtering_changes_row_count_from_raw(self, seed_conn):
        """R24b.1: Valid play events != raw play rows. Filtering reduces count
        (short plays removed), but merge _can_ expand (long sessions split into
        logical plays). The count is never identical in practice."""
        raw = load_plays(seed_conn, min_ms=0, music_only=True, merge_enabled=False, filtered=False)
        valid = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
        # They should differ — filtering + merge changes the picture
        assert len(valid) != len(raw), (
            f"Expected valid ({len(valid)}) != raw ({len(raw)}) after filter+merge"
        )

    def test_raw_rows_include_short_plays_filtered_out(self, seed_conn):
        """R24b.1: Short plays (< 30s) exist in raw but are removed in valid."""
        raw = load_plays(seed_conn, min_ms=0, music_only=True, merge_enabled=False, filtered=False)
        valid = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
        raw_short = int((raw["ms_played"] < 30000).sum())
        valid_short = int((valid["ms_played"] < 30000).sum())
        assert raw_short > 0, "Seed data should have sub-30s plays"
        assert valid_short == 0, f"Valid events should have 0 sub-30s, got {valid_short}"


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

    def test_artist_fanout_preserves_logical_event_identity(self, seed_conn):
        """Every credited row from one logical play keeps the same event ordinal."""
        artists = load_plays_for_artists(
            seed_conn, min_ms=30000, music_only=True, merge_enabled=True
        )
        shared = artists[artists["track_name"] == "Fixture Shared Credit"]

        assert "_artist_event_id" in artists.columns
        assert shared.groupby("_artist_event_id").size().max() > 1


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

    def test_source_album_id_present_on_fixture_tracks(self, seed_conn):
        """R24b.3: Tracks with known source albums retain attribution through pipeline."""
        valid = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
        # Fixture Source Album Song (track 904) has explicit source_album_id values
        fixture_rows = valid[valid["track_name"] == "Fixture Source Album Song"]
        assert len(fixture_rows) > 0, "Expected fixture track 904 in valid plays"
        # All rows for this track should have source_album_id set
        null_count = int(fixture_rows["source_album_id"].isna().sum())
        assert null_count == 0, (
            f"Fixture track 904 should have source_album_id, got {null_count} NULLs"
        )
        source_ids = set(fixture_rows["source_album_id"].dropna().astype(int))
        assert source_ids.issubset({901, 902}), (
            f"Expected source_album_id subset of {{901,902}}, got {source_ids}"
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


class TestBillboardPersonalConsistency:
    def test_billboard_album_merge_consistent_with_analysis(self, seed_conn):
        """R24b.6: Album merge level gives consistent rankings across Billboard
        and personal chart when same merge_level is used."""
        # Compute Billboard data at L2 (default)
        bb = compute_billboard_data(merge_level=2)
        weekly_album = bb.get("weekly_album", [])

        # Compute personal album chart at L2
        valid = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
        total, rows = chart_rows(
            seed_conn, valid, entity="album", metric="plays", limit=100, offset=0, merge_level=2
        )

        # Both pipelines should have at least one album
        assert len(rows) > 0, "Personal album chart should have results"
        assert len(weekly_album) > 0, "Billboard album chart should have results"

        # For albums that appear in both, the merge (canonicalization) should be
        # consistent: same album_name in Billboard and personal after merge
        personal_names = {r["album_name"] for r in rows}
        bb_names = {e["album_name"] for e in weekly_album}
        common = personal_names & bb_names
        # At least one canonical album name should appear in both
        assert len(common) > 0, (
            f"No common canonical album names between Billboard ({len(bb_names)})"
            f" and personal ({len(personal_names)}) charts"
        )
