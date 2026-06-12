"""Contract tests — Billboard raw fallback vs pre-aggregation consistency.

Verifies that load_billboard_raw() and build_aggregations() produce the same
results for the same parameters by using the same counting policy
(merge before filter).
"""

from __future__ import annotations

import os
import shutil
import tempfile

import pytest

from backend.core.db import build_aggregations

pytestmark = pytest.mark.contract


@pytest.fixture(scope="function")
def isolated_seed_db(use_seed_db):
    """Copy seed.db to a temp file so build_aggregations can write without
    corrupting the shared seed fixture."""
    import backend.core.db as db_mod

    fd, tmp_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    shutil.copy2(db_mod.DB_PATH, tmp_path)

    original = db_mod.DB_PATH
    db_mod.DB_PATH = tmp_path

    yield tmp_path

    db_mod.DB_PATH = original
    os.unlink(tmp_path)
    # Clear caches polluted with the temp DB
    db_mod._load_plays_cached.cache_clear()
    db_mod._load_plays_for_artists_cached.cache_clear()
    from backend.domains.billboard.chart_compute import (
        _compute_weekly_data_cached,
    )
    from backend.domains.billboard.data_loader import (
        load_billboard_raw,
        load_billboard_raw_for_artists,
    )

    load_billboard_raw.cache_clear()
    load_billboard_raw_for_artists.cache_clear()
    _compute_weekly_data_cached.cache_clear()


class TestRawFallbackConsistency:
    def test_raw_uses_min_ms_zero_before_merge(self, isolated_seed_db):
        """After fix, raw fallback loads with min_ms=0, merges, then filters.

        Before fix: raw fallback filtered in SQL (min_ms=30000), then merged.
        This test verifies short fragments survive SQL and get merged properly.
        """
        from backend.domains.billboard.data_loader import load_billboard_raw

        # Load with merge enabled — fragments should merge and pass threshold
        raw = load_billboard_raw(30_000, True, 4, 0)
        fragment_rows = raw[raw["track_name"] == "Fixture Fragment Song"]
        # Each session (two 20s fragments) → one 40s valid event after merge
        assert len(fragment_rows) > 0, "Fragments should merge into valid events"

    def test_preagg_and_raw_produce_same_track_counts(self, isolated_seed_db):
        """Build aggregations, then compare raw fallback per-track counts."""
        build_aggregations(min_ms=30_000, music_only=True, week_start_dow=4, week_start_hour=0)

        from backend.domains.billboard.data_loader import (
            _try_load_from_agg,
            load_billboard_raw,
        )

        agg_tracks, _agg_albums, _agg_artists = _try_load_from_agg(30_000, True, 4, 0)
        raw = load_billboard_raw(30_000, True, 4, 0)

        # Compare fragment track: same count in raw and pre-agg
        raw_frag = raw[raw["track_name"] == "Fixture Fragment Song"]
        agg_frag = agg_tracks[agg_tracks["track_name"] == "Fixture Fragment Song"]

        raw_count = int(raw_frag.groupby("billboard_week").size().sum())
        agg_count = int(agg_frag["play_count"].sum())

        assert raw_count == agg_count, (
            f"Raw fallback count ({raw_count}) differs from pre-agg ({agg_count})"
        )

    def test_artist_raw_path_also_uses_min_ms_zero(self, isolated_seed_db):
        """Artist raw path mirror fix: load with min_ms=0, merge, then filter."""
        build_aggregations(min_ms=30_000, music_only=True, week_start_dow=4, week_start_hour=0)

        from backend.domains.billboard.data_loader import load_billboard_raw_for_artists

        raw_artists = load_billboard_raw_for_artists(30_000, True, 4, 0)
        shared = raw_artists[raw_artists["track_name"] == "Fixture Shared Credit"]
        # One play, two artists
        assert len(shared) == 2, f"Expected 2 artist rows, got {len(shared)}"
