"""Contract tests — source album attribution in play data."""

from __future__ import annotations

import pytest

from backend.core.db import load_plays

pytestmark = pytest.mark.contract


class TestSourceAlbumAttribution:
    def test_load_plays_exposes_source_album_id(self, seed_conn):
        """source_album_id column is present in the plays output."""
        df = load_plays(seed_conn, min_ms=0, music_only=True, merge_enabled=False, filtered=False)
        assert "source_album_id" in df.columns

    def test_load_plays_exposes_source_album_name(self, seed_conn):
        """source_album_name column is present when join_albums=True."""
        df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
        assert "source_album_name" in df.columns

    def test_fixture_track_on_multiple_source_albums(self, seed_conn):
        """Track 904 played under two source albums: 901 (Fixture Single) and 902 (Fixture LP).
        Use merge_enabled=False to avoid cross-day merge collapsing the two plays."""
        df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=False)
        rows = df[df["track_name"] == "Fixture Source Album Song"]
        assert len(rows) == 2
        assert set(rows["source_album_id"]) == {901, 902}
        assert set(rows["source_album_name"]) == {"Fixture Single", "Fixture LP"}

    def test_source_album_info_includes_track_album_id(self, seed_conn):
        """track_album_id (from tracks.album_id) is also available."""
        df = load_plays(seed_conn, min_ms=30000, music_only=True, merge_enabled=True)
        assert "track_album_id" in df.columns
        # Track 904's canonical album is 901 (Fixture Single)
        rows = df[df["track_name"] == "Fixture Source Album Song"]
        assert set(rows["track_album_id"]) == {901}
