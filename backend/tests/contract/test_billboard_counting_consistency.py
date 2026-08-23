"""Contract tests — Billboard raw fallback vs pre-aggregation consistency.

Verifies that load_billboard_raw() and build_aggregations() produce the same
results for the same parameters by using the same counting policy
(merge before filter).
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile

import pandas as pd
import pytest

from backend.core.db import build_aggregations

pytestmark = pytest.mark.contract


def _clear_billboard_runtime_caches():
    """Clear caches that can mask cold Billboard endpoint failures."""
    import backend.core.db as db_mod
    from backend.domains.billboard.chart_compute import (
        _compute_power_scores_cached,
        _compute_records_cached,
        _compute_summaries_cached,
        _compute_weekly_data_cached,
        _load_and_rank_cached,
    )
    from backend.domains.billboard.data_loader import (
        load_billboard_raw,
        load_billboard_raw_for_artists,
    )

    db_mod._load_plays_cached.cache_clear()
    db_mod._load_plays_for_artists_cached.cache_clear()
    load_billboard_raw.cache_clear()
    load_billboard_raw_for_artists.cache_clear()
    _compute_weekly_data_cached.cache_clear()
    _compute_power_scores_cached.cache_clear()
    _compute_summaries_cached.cache_clear()
    _compute_records_cached.cache_clear()
    _load_and_rank_cached.cache_clear()


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
    _clear_billboard_runtime_caches()


class TestRawFallbackConsistency:
    @pytest.mark.parametrize("dynamic_threshold", [False, True])
    def test_tail_partition_build_matches_full_rebuild_for_all_four_tables(
        self,
        isolated_seed_db,
        dynamic_threshold,
    ):
        import backend.core.db as db_mod
        from backend.core.db import build_aggregations_for_weeks, get_db
        from backend.core.migrations import run_migrations
        from backend.domains.imports.change_set import (
            _logical_billboard_contribution_weeks,
        )

        run_migrations()
        conn = get_db(readonly=False)
        conn.execute(
            """UPDATE playback_import_state
               SET active_generation_id='base-generation',
                   dataset_digest='base-digest'
               WHERE state_id=1"""
        )
        conn.commit()
        conn.close()
        baseline = build_aggregations(
            min_ms=30_000,
            music_only=True,
            week_start_dow=4,
            week_start_hour=0,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=5,
            expected_generation_id="base-generation",
        )
        assert baseline["build_strategy"] == "full"

        fd, full_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        source = sqlite3.connect(isolated_seed_db)
        destination = sqlite3.connect(full_path)
        source.backup(destination)
        source.close()
        destination.close()

        def append_tail(path: str) -> set[str]:
            db_mod.DB_PATH = path
            local_conn = get_db(readonly=False)
            local_conn.row_factory = sqlite3.Row
            last = local_conn.execute(
                """SELECT p.* FROM plays p
                   JOIN tracks t ON t.track_id=p.track_id
                   WHERE p.track_id IS NOT NULL
                   ORDER BY p.ts DESC, p.play_id DESC LIMIT 1"""
            ).fetchone()
            assert last is not None
            end = pd.Timestamp(last["ts"]).tz_convert("UTC") + pd.Timedelta(days=1)
            local = end.tz_convert("Asia/Shanghai")
            values = dict(last)
            values.update(
                {
                    "ts": end.isoformat().replace("+00:00", "Z"),
                    "ts_date": str(local.date()),
                    "ts_year": int(local.year),
                    "ts_month": int(local.month),
                    "ts_week": int(local.isocalendar().week),
                    "ts_dow": int(local.dayofweek),
                    "ts_hour": int(local.hour),
                    "ms_played": 60_000,
                    "content_type": "audio",
                    "source_fingerprint": "f" * 64,
                    "source_fingerprint_version": 1,
                    "import_generation_id": "append-generation",
                }
            )
            columns = [
                str(row[1])
                for row in local_conn.execute("PRAGMA table_info(plays)").fetchall()
                if str(row[1]) != "play_id"
            ]
            local_conn.execute(
                f"INSERT INTO plays({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                [values.get(column) for column in columns],
            )
            local_conn.execute(
                """UPDATE playback_import_state
                   SET active_generation_id='append-generation',
                       dataset_digest='append-digest'
                   WHERE state_id=1"""
            )
            local_conn.commit()
            weeks = _logical_billboard_contribution_weeks(
                local_conn,
                generation_id="append-generation",
                min_ms=30_000,
                music_only=True,
                dynamic_threshold=dynamic_threshold,
                max_gap_minutes=5,
                week_start_dow=4,
                week_start_hour=0,
            )
            local_conn.close()
            return weeks

        try:
            affected_weeks = append_tail(isolated_seed_db)
            partition = build_aggregations_for_weeks(
                affected_weeks,
                change_generation_id="append-generation",
                previous_dataset_digest="base-digest",
                billboard_scope_exact=True,
                min_ms=30_000,
                music_only=True,
                week_start_dow=4,
                week_start_hour=0,
                dynamic_threshold=dynamic_threshold,
                max_merge_gap_minutes=5,
                expected_generation_id="append-generation",
            )
            assert partition.get("fallback_reason") is None
            assert partition["build_strategy"] == "partition"

            append_tail(full_path)
            full = build_aggregations(
                min_ms=30_000,
                music_only=True,
                week_start_dow=4,
                week_start_hour=0,
                dynamic_threshold=dynamic_threshold,
                max_merge_gap_minutes=5,
                expected_generation_id="append-generation",
            )
            assert full["build_strategy"] == "full"

            partition_conn = sqlite3.connect(isolated_seed_db)
            full_conn = sqlite3.connect(full_path)
            for table in (
                "agg_weekly_tracks",
                "agg_weekly_albums",
                "agg_weekly_track_sources",
                "agg_weekly_artists",
            ):
                partition_rows = partition_conn.execute(
                    f'SELECT * FROM "{table}" ORDER BY 1, 2, 3'
                ).fetchall()
                full_rows = full_conn.execute(
                    f'SELECT * FROM "{table}" ORDER BY 1, 2, 3'
                ).fetchall()
                assert partition_rows == full_rows, table
            config = dict(partition_conn.execute("SELECT key, value FROM agg_config"))
            assert config["data_generation_id"] == "append-generation"
            assert config["source_dataset_digest"] == "append-digest"
            assert config["build_strategy"] == "partition"
            for key in (
                "builder_version",
                "playback_policy_version",
                "identity_revision",
                "track_credit_revision",
                "album_project_revision",
                "duration_revision",
                "credit_membership_revision",
            ):
                assert config[key]
            partition_conn.close()
            full_conn.close()
        finally:
            db_mod.DB_PATH = isolated_seed_db
            os.unlink(full_path)

    def test_aggregation_publish_rolls_back_as_one_snapshot(self, isolated_seed_db):
        from backend.core.db import (
            _AGG_SHADOW_TABLES,
            _active_playback_generation,
            _prepare_aggregation_shadows,
            _publish_aggregation_shadows,
            get_db,
        )

        conn = get_db(readonly=False)
        try:
            before_counts = {
                table: conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                for table in _AGG_SHADOW_TABLES
            }
            before_hash = conn.execute(
                "SELECT value FROM agg_config WHERE key='param_hash'"
            ).fetchone()[0]
            _prepare_aggregation_shadows(conn)
            for live_table, shadow_table in _AGG_SHADOW_TABLES.items():
                conn.execute(f'INSERT INTO temp."{shadow_table}" SELECT * FROM main."{live_table}"')
            conn.commit()
            conn.execute(
                """CREATE TEMP TRIGGER abort_album_publish
                   BEFORE INSERT ON agg_weekly_albums
                   BEGIN SELECT RAISE(ABORT, 'forced publish failure'); END"""
            )

            with pytest.raises(Exception, match="forced publish failure"):
                _publish_aggregation_shadows(
                    conn,
                    param_hash="should-not-publish",
                    data_generation_id=_active_playback_generation(conn),
                )

            after_counts = {
                table: conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                for table in _AGG_SHADOW_TABLES
            }
            after_hash = conn.execute(
                "SELECT value FROM agg_config WHERE key='param_hash'"
            ).fetchone()[0]
            assert after_counts == before_counts
            assert after_hash == before_hash
        finally:
            conn.close()

    def test_l2_endpoints_bootstrap_album_projects_without_readonly_500(self, isolated_seed_db):
        """Cold L2 Billboard endpoints may need to build album projects lazily."""
        from fastapi.testclient import TestClient

        from backend.core.db import get_db
        from backend.domains.playback.album_projects import ensure_album_project_schema
        from backend.main import app

        conn = get_db(readonly=False)
        try:
            ensure_album_project_schema(conn)
            conn.execute("DELETE FROM album_project_tracks")
            conn.execute("DELETE FROM album_project_albums")
            conn.execute("DELETE FROM album_projects")
            conn.commit()
        finally:
            conn.close()

        _clear_billboard_runtime_caches()

        with TestClient(app) as client:
            weekly = client.get(
                "/api/billboard/weekly",
                params={"merge_level": 2, "include_compilations": "false"},
            )
            all_time = client.get("/api/billboard/all-time", params={"merge_level": 2})

        assert weekly.status_code == 200, weekly.text
        assert all_time.status_code == 200, all_time.text
        assert isinstance(weekly.json()["weekly_album"], list)
        assert isinstance(all_time.json()["weekly_album"], list)

        conn = get_db(readonly=True)
        try:
            project_count = conn.execute("SELECT COUNT(*) FROM album_projects").fetchone()[0]
        finally:
            conn.close()
        assert project_count > 0

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

    def test_merge_disabled_bypasses_preaggregation_and_preserves_raw_row_eligibility(
        self, isolated_seed_db
    ):
        """The aggregate represents only the merge-enabled logical timeline."""
        build_aggregations(min_ms=30_000, music_only=True, week_start_dow=4, week_start_hour=0)

        from backend.domains.billboard.data_loader import (
            _try_load_from_agg,
            load_billboard_raw,
        )

        merged = load_billboard_raw(30_000, True, 4, 0, merge_enabled=True)
        unmerged = load_billboard_raw(30_000, True, 4, 0, merge_enabled=False)
        aggregate = _try_load_from_agg(30_000, True, 4, 0, merge_enabled=False)

        assert aggregate == (None, None, None)
        assert len(merged[merged["track_name"] == "Fixture Fragment Song"]) == 1
        assert unmerged[unmerged["track_name"] == "Fixture Fragment Song"].empty

    def test_billboard_weekly_endpoint_separates_merge_enabled_cache_keys(self, isolated_seed_db):
        from fastapi.testclient import TestClient

        from backend.main import app

        _clear_billboard_runtime_caches()
        with TestClient(app) as client:
            merged = client.get(
                "/api/billboard/weekly",
                params={
                    "merge_enabled": "true",
                    "dynamic_threshold": "false",
                    "bb_top_n": 100,
                },
            )
            unmerged = client.get(
                "/api/billboard/weekly",
                params={
                    "merge_enabled": "false",
                    "dynamic_threshold": "false",
                    "bb_top_n": 100,
                },
            )
            merged_again = client.get(
                "/api/billboard/weekly",
                params={
                    "merge_enabled": "true",
                    "dynamic_threshold": "false",
                    "bb_top_n": 100,
                },
            )

        assert merged.status_code == 200, merged.text
        assert unmerged.status_code == 200, unmerged.text
        merged_tracks = {row["track_name"] for row in merged.json()["weekly"]}
        unmerged_tracks = {row["track_name"] for row in unmerged.json()["weekly"]}
        assert "Fixture Fragment Song" in merged_tracks
        assert "Fixture Fragment Song" not in unmerged_tracks
        assert merged_again.json() == merged.json()

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

    def test_preagg_and_raw_produce_same_artist_counts_for_expanded_events(self, isolated_seed_db):
        """Artist pre-aggregation must retain multiple logical events from one play.

        A long consecutive session can expand into multiple logical plays while
        retaining the same source play_id.  The artist path must dedupe aliases
        by logical event identity, not by source play_id.
        """
        from backend.core.db import get_db
        from backend.domains.billboard.data_loader import (
            _try_load_from_agg,
            load_billboard_raw_for_artists,
        )

        conn = get_db(readonly=False)
        try:
            conn.executemany(
                """INSERT INTO plays(
                    ts, ts_year, ts_month, ts_week, ts_dow, ts_hour, ts_date,
                    platform, ms_played, conn_country, track_id,
                    reason_start, reason_end, shuffle, skipped, offline,
                    incognito_mode, content_type, source_album_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        "2026-06-08T02:00:00Z",
                        2026,
                        6,
                        24,
                        0,
                        10,
                        "2026-06-08",
                        "ios",
                        600_000,
                        "CN",
                        902,
                        "trackdone",
                        "trackdone",
                        0,
                        0,
                        0,
                        0,
                        "audio",
                        None,
                    ),
                    (
                        "2026-06-08T02:01:00Z",
                        2026,
                        6,
                        24,
                        0,
                        10,
                        "2026-06-08",
                        "ios",
                        600_000,
                        "CN",
                        902,
                        "trackdone",
                        "trackdone",
                        0,
                        0,
                        0,
                        0,
                        "audio",
                        None,
                    ),
                ],
            )
            conn.commit()
        finally:
            conn.close()

        build_aggregations(min_ms=30_000, music_only=True, week_start_dow=4, week_start_hour=0)
        agg_tracks, _agg_albums, agg_artists = _try_load_from_agg(30_000, True, 4, 0)
        raw_artists = load_billboard_raw_for_artists(30_000, True, 4, 0)

        raw_long = raw_artists[raw_artists["track_name"] == "Fixture Long Track"]
        agg_long = agg_tracks[agg_tracks["track_name"] == "Fixture Long Track"]
        assert int(raw_long.groupby("billboard_week").size().sum()) == 3
        assert int(agg_long["play_count"].sum()) == 3
        assert int((raw_long["billboard_week"].astype(str) == "2026-06-05").sum()) == 2

        raw_artist_counts = (
            raw_artists.groupby(["billboard_week", "artist_id"], as_index=False)
            .agg(play_count=("ms_played", "count"), total_ms=("ms_played", "sum"))
            .assign(billboard_week=lambda frame: frame["billboard_week"].astype(str))
            .sort_values(["billboard_week", "artist_id"])
            .reset_index(drop=True)
        )
        agg_artist_counts = (
            agg_artists[["billboard_week", "artist_id", "play_count", "total_ms"]]
            .assign(billboard_week=lambda frame: frame["billboard_week"].astype(str))
            .sort_values(["billboard_week", "artist_id"])
            .reset_index(drop=True)
        )
        pd.testing.assert_frame_equal(raw_artist_counts, agg_artist_counts, check_dtype=False)

    def test_album_project_raw_and_track_source_preagg_match(self, isolated_seed_db):
        """Album project rankings must be identical from raw and track-source pre-agg.

        The album chart cannot use album-container pre-aggregation under L2/L3 because
        project totals are derived from de-duplicated canonical songs, not from album rows.
        """
        build_aggregations(min_ms=30_000, music_only=True, week_start_dow=4, week_start_hour=0)

        from backend.core.db import get_db, load_agg_weekly_track_sources
        from backend.domains.billboard.chart_ranking import compute_album_weekly_rankings
        from backend.domains.billboard.data_loader import load_billboard_raw

        conn = get_db(readonly=True)
        try:
            raw = load_billboard_raw(30_000, True, 4, 0)
            raw_weekly = compute_album_weekly_rankings(
                raw,
                top_n=50,
                merge_level=2,
                include_compilations=True,
            )
            preagg = load_agg_weekly_track_sources(conn)
            preagg_weekly = compute_album_weekly_rankings(
                None,
                top_n=50,
                pre_agg=preagg,
                merge_level=2,
                include_compilations=True,
            )
        finally:
            conn.close()

        cols = ["billboard_week", "album_name", "artist_name", "play_count"]
        raw_rows = raw_weekly[cols].sort_values(cols).reset_index(drop=True)
        preagg_rows = preagg_weekly[cols].sort_values(cols).reset_index(drop=True)
        assert raw_rows.equals(preagg_rows)
