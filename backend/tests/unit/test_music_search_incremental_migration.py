from __future__ import annotations

import sqlite3

import pytest

from backend.core.migrations import (
    LATEST_SCHEMA_VERSION,
    MIGRATIONS,
    migrate_042,
    migrate_046,
    migrate_047,
    migrate_055,
    migrate_056,
)


def _legacy_search_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE music_search_snapshot_meta (
            snapshot_key TEXT PRIMARY KEY,
            filter_fingerprint TEXT NOT NULL UNIQUE,
            source_revision TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            activated_at TEXT,
            last_accessed_at TEXT,
            last_error TEXT,
            semantic_base_key TEXT,
            merge_level INTEGER,
            dynamic_threshold INTEGER,
            builder_version TEXT
        );
        INSERT INTO music_search_snapshot_meta(
            snapshot_key, filter_fingerprint, source_revision, status,
            semantic_base_key, merge_level, dynamic_threshold, builder_version
        ) VALUES (
            'legacy-ready', 'legacy-ready', 'source-v1', 'ready',
            'base-v1', 2, 1, 'music_search_snapshot_v2'
        );
        """
    )
    return conn


def test_migrate_042_adds_lineage_without_invalidating_ready_snapshot() -> None:
    conn = _legacy_search_connection()
    try:
        migrate_042(conn)
        migrate_042(conn)

        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(music_search_snapshot_meta)")
        }
        assert {
            "policy_key",
            "source_generation_id",
            "source_dataset_digest",
            "base_snapshot_key",
            "build_strategy",
            "dependency_digest",
            "change_set_digest",
        } <= columns

        legacy = conn.execute(
            """SELECT status, policy_key, source_generation_id,
                      source_dataset_digest, base_snapshot_key, build_strategy,
                      dependency_digest, change_set_digest
               FROM music_search_snapshot_meta
               WHERE snapshot_key='legacy-ready'"""
        ).fetchone()
        assert tuple(legacy) == ("ready", None, None, None, None, None, None, None)

        indexes = {
            row["name"] for row in conn.execute("PRAGMA index_list(music_search_snapshot_meta)")
        }
        assert {
            "idx_music_search_snapshot_meta_lineage",
            "idx_music_search_snapshot_meta_base",
        } <= indexes
    finally:
        conn.close()


def test_migrate_042_creates_constrained_weekly_chart_ledger() -> None:
    conn = _legacy_search_connection()
    try:
        migrate_042(conn)
        conn.execute(
            """INSERT INTO music_search_weekly_chart_context(
                   snapshot_key, family, week, entity_key, rank,
                   play_count, total_ms, stable_sort_key
               ) VALUES ('legacy-ready', 'track', '2026-08-21', 'track:1',
                         1, 3, 180000, '0000000001')"""
        )

        row = conn.execute(
            """SELECT family, week, entity_key, rank, play_count, total_ms,
                      stable_sort_key
               FROM music_search_weekly_chart_context"""
        ).fetchone()
        assert tuple(row) == (
            "track",
            "2026-08-21",
            "track:1",
            1,
            3,
            180000,
            "0000000001",
        )

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO music_search_weekly_chart_context(
                       snapshot_key, family, week, entity_key, rank,
                       play_count, total_ms, stable_sort_key
                   ) VALUES ('legacy-ready', 'album', '2026-08-21', 'album_project:2',
                             0, 1, 1, 'album')"""
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO music_search_weekly_chart_context(
                       snapshot_key, family, week, entity_key, rank,
                       play_count, total_ms, stable_sort_key
                   ) VALUES ('legacy-ready', 'podcast', '2026-08-21', 'episode:2',
                             2, 1, 1, 'episode')"""
            )
    finally:
        conn.close()


def test_migrate_042_weekly_rows_follow_snapshot_lifecycle() -> None:
    conn = _legacy_search_connection()
    try:
        migrate_042(conn)
        conn.execute(
            """INSERT INTO music_search_snapshot_meta(
                   snapshot_key, filter_fingerprint, source_revision, status,
                   base_snapshot_key
               ) VALUES ('delta', 'delta', 'source-v2', 'ready', 'legacy-ready')"""
        )
        conn.execute(
            """INSERT INTO music_search_weekly_chart_context(
                   snapshot_key, family, week, entity_key, rank,
                   play_count, total_ms, stable_sort_key
               ) VALUES ('delta', 'artist', '2026-08-21', 'artist:3',
                         1, 2, 120000, '0000000003')"""
        )

        conn.execute("DELETE FROM music_search_snapshot_meta WHERE snapshot_key='legacy-ready'")
        assert (
            conn.execute(
                "SELECT base_snapshot_key FROM music_search_snapshot_meta WHERE snapshot_key='delta'"
            ).fetchone()[0]
            is None
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM music_search_weekly_chart_context WHERE snapshot_key='delta'"
            ).fetchone()[0]
            == 1
        )

        conn.execute("DELETE FROM music_search_snapshot_meta WHERE snapshot_key='delta'")
        assert (
            conn.execute("SELECT COUNT(*) FROM music_search_weekly_chart_context").fetchone()[0]
            == 0
        )
    finally:
        conn.close()


def test_migrate_046_creates_independent_constrained_year_end_projection() -> None:
    conn = _legacy_search_connection()
    try:
        migrate_042(conn)
        migrate_046(conn)
        migrate_046(conn)
        conn.execute(
            """INSERT INTO music_search_year_end_projection_state(
                   snapshot_key, builder_version, status
               ) VALUES ('legacy-ready', 'projection-v1', 'running')"""
        )
        conn.execute(
            """INSERT INTO music_search_year_end_meta(
                   snapshot_key, year, coverage_status, is_complete_year,
                   observed_weeks, expected_weeks,
                   first_billboard_week, last_billboard_week
               ) VALUES ('legacy-ready', 2025, 'complete', 1, 52, 52,
                         '2024-12-27', '2025-12-19')"""
        )
        conn.execute(
            """INSERT INTO music_search_entity_year_end(
                   snapshot_key, family, entity_key, year,
                   year_end_rank, year_end_score, peak_position,
                   weeks_on_chart, weeks_at_peak, weeks_at_no1,
                   weeks_top5, weeks_top10, chart_plays,
                   first_week, last_week
               ) VALUES ('legacy-ready', 'track', 'track:1', 2025,
                         3, 800, 1, 12, 2, 2, 4, 8, 30,
                         '2025-01-03', '2025-03-21')"""
        )

        assert tuple(
            conn.execute(
                """SELECT year, year_end_rank, peak_position, weeks_on_chart
                   FROM music_search_entity_year_end"""
            ).fetchone()
        ) == (2025, 3, 1, 12)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO music_search_year_end_projection_state(
                       snapshot_key, builder_version, status
                   ) VALUES ('missing', 'projection-v1', 'ready')"""
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO music_search_entity_year_end(
                       snapshot_key, family, entity_key, year,
                       year_end_rank, year_end_score, peak_position,
                       weeks_on_chart, weeks_at_peak, weeks_at_no1,
                       weeks_top5, weeks_top10, chart_plays
                   ) VALUES ('legacy-ready', 'track', 'track:2', 2024,
                             1, 1, 1, 1, 1, 1, 1, 1, 1)"""
            )
    finally:
        conn.close()


def test_migrate_046_projection_rows_follow_snapshot_lifecycle() -> None:
    conn = _legacy_search_connection()
    try:
        migrate_042(conn)
        migrate_046(conn)
        conn.execute(
            """INSERT INTO music_search_year_end_projection_state(
                   snapshot_key, builder_version, status
               ) VALUES ('legacy-ready', 'projection-v1', 'ready')"""
        )
        conn.execute(
            """INSERT INTO music_search_year_end_meta(
                   snapshot_key, year, coverage_status, is_complete_year,
                   observed_weeks, expected_weeks
               ) VALUES ('legacy-ready', 2025, 'partial_range', 0, 3, 52)"""
        )

        conn.execute("DELETE FROM music_search_snapshot_meta WHERE snapshot_key='legacy-ready'")
        assert (
            conn.execute("SELECT COUNT(*) FROM music_search_year_end_projection_state").fetchone()[
                0
            ]
            == 0
        )
        assert conn.execute("SELECT COUNT(*) FROM music_search_year_end_meta").fetchone()[0] == 0
    finally:
        conn.close()


def test_migrate_047_repairs_short_lived_v46_coverage_constraint() -> None:
    conn = _legacy_search_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE music_search_year_end_meta (
                snapshot_key TEXT NOT NULL,
                year INTEGER NOT NULL,
                coverage_status TEXT NOT NULL
                    CHECK (coverage_status IN ('complete', 'partial', 'empty')),
                is_complete_year INTEGER NOT NULL,
                observed_weeks INTEGER NOT NULL,
                expected_weeks INTEGER NOT NULL,
                first_billboard_week TEXT,
                last_billboard_week TEXT,
                PRIMARY KEY(snapshot_key, year)
            );
            INSERT INTO music_search_year_end_meta(
                snapshot_key, year, coverage_status, is_complete_year,
                observed_weeks, expected_weeks
            ) VALUES ('legacy-ready', 2025, 'partial', 0, 3, 52);
            """
        )

        migrate_047(conn)
        migrate_047(conn)

        assert (
            conn.execute("SELECT coverage_status FROM music_search_year_end_meta").fetchone()[0]
            == "partial_range"
        )
        conn.execute(
            """INSERT INTO music_search_year_end_meta(
                   snapshot_key, year, coverage_status, is_complete_year,
                   observed_weeks, expected_weeks
               ) VALUES ('legacy-ready', 2026, 'year_to_date', 0, 30, 52)"""
        )
    finally:
        conn.close()


def test_latest_schema_version_matches_registered_migrations() -> None:
    assert LATEST_SCHEMA_VERSION == 63
    assert max(version for version, _name, _migration in MIGRATIONS) == LATEST_SCHEMA_VERSION


def test_migrate_055_retires_only_public_l1_ready_snapshots() -> None:
    conn = _legacy_search_connection()
    try:
        conn.executemany(
            """INSERT INTO music_search_snapshot_meta(
                   snapshot_key, filter_fingerprint, source_revision, status,
                   merge_level, dynamic_threshold, builder_version
               ) VALUES (?, ?, 'revision', 'ready', ?, 1, 'legacy')""",
            [
                ("l1", "l1", 1),
                ("l2", "l2", 2),
                ("l3", "l3", 3),
                ("current-l2", "current-l2", 2),
            ],
        )
        conn.execute(
            """UPDATE music_search_snapshot_meta
                  SET builder_version='music_search_snapshot_v8_canonical_track'
                WHERE snapshot_key='current-l2'"""
        )
        migrate_055(conn)
        migrate_055(conn)
        states = {
            str(row[0]): str(row[1])
            for row in conn.execute(
                "SELECT snapshot_key, status FROM music_search_snapshot_meta ORDER BY snapshot_key"
            ).fetchall()
        }
        assert states == {
            "current-l2": "ready",
            "l1": "stale",
            "l2": "stale",
            "l3": "stale",
            "legacy-ready": "stale",
        }
    finally:
        conn.close()


def test_migrate_056_invalidates_derivatives_without_blocking_metadata_dependencies() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(
            """
            CREATE TABLE plays(play_id INTEGER PRIMARY KEY);
            INSERT INTO plays(play_id) VALUES (1);
            CREATE TABLE agg_weekly_tracks(value INTEGER);
            CREATE TABLE agg_weekly_track_sources(value INTEGER);
            CREATE TABLE agg_weekly_albums(value INTEGER);
            CREATE TABLE agg_weekly_artists(value INTEGER);
            CREATE TABLE agg_config(key TEXT PRIMARY KEY, value TEXT);
            INSERT INTO agg_config VALUES ('param_hash', 'stale');
            CREATE TABLE artist_identity_state(
                state_id INTEGER PRIMARY KEY,
                current_revision INTEGER,
                active_aggregate_revision INTEGER,
                rebuild_status TEXT,
                last_error TEXT,
                updated_at TEXT
            );
            INSERT INTO artist_identity_state VALUES (1, 3, 3, 'ready', NULL, NULL);
            CREATE TABLE track_credit_state(
                state_id INTEGER PRIMARY KEY,
                current_revision INTEGER,
                active_aggregate_revision INTEGER,
                rebuild_status TEXT,
                last_error TEXT,
                updated_at TEXT
            );
            INSERT INTO track_credit_state VALUES (1, 4, 4, 'ready', NULL, NULL);
            CREATE TABLE music_search_snapshot_meta(
                snapshot_key TEXT PRIMARY KEY,
                status TEXT,
                last_error TEXT
            );
            INSERT INTO music_search_snapshot_meta VALUES ('v8-l2', 'ready', NULL);
            """
        )
        migrate_056(conn)
        migrate_056(conn)
        artist = conn.execute(
            "SELECT active_aggregate_revision, rebuild_status FROM artist_identity_state"
        ).fetchone()
        credit = conn.execute(
            "SELECT active_aggregate_revision, rebuild_status FROM track_credit_state"
        ).fetchone()
        snapshot = conn.execute(
            "SELECT status FROM music_search_snapshot_meta WHERE snapshot_key='v8-l2'"
        ).fetchone()
        assert artist == (3, "ready")
        assert credit == (4, "ready")
        assert snapshot == ("stale",)
        assert conn.execute("SELECT COUNT(*) FROM agg_config").fetchone()[0] == 0
    finally:
        conn.close()
