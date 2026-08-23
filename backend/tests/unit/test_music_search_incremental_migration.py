from __future__ import annotations

import sqlite3

import pytest

from backend.core.migrations import LATEST_SCHEMA_VERSION, MIGRATIONS, migrate_042


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


def test_latest_schema_version_matches_registered_migrations() -> None:
    assert LATEST_SCHEMA_VERSION == 45
    assert max(version for version, _name, _migration in MIGRATIONS) == LATEST_SCHEMA_VERSION
