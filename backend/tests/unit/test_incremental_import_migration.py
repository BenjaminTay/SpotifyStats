from __future__ import annotations

import sqlite3

import pytest

from backend.core.migrations import migrate_037, migrate_041


def _minimal_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE plays (
            play_id INTEGER PRIMARY KEY,
            content_type TEXT NOT NULL DEFAULT 'audio'
        )"""
    )
    return conn


def test_migrate_037_creates_import_identity_schema_idempotently() -> None:
    conn = _minimal_connection()
    try:
        migrate_037(conn)
        migrate_037(conn)

        play_columns = {row["name"] for row in conn.execute("PRAGMA table_info(plays)")}
        assert {
            "source_fingerprint",
            "source_fingerprint_version",
            "import_generation_id",
        } <= play_columns

        play_indexes = {row["name"] for row in conn.execute("PRAGMA index_list(plays)")}
        assert {
            "uq_plays_source_fingerprint",
            "idx_plays_import_generation",
        } <= play_indexes

        tables = {
            row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"playback_import_state", "playback_import_runs"} <= tables

        state = conn.execute("SELECT * FROM playback_import_state").fetchall()
        assert len(state) == 1
        assert state[0]["state_id"] == 1
        assert state[0]["record_count"] == 0
    finally:
        conn.close()


def test_migrate_037_repairs_partially_applied_play_columns() -> None:
    conn = _minimal_connection()
    try:
        conn.execute("ALTER TABLE plays ADD COLUMN source_fingerprint TEXT")
        conn.execute("ALTER TABLE plays ADD COLUMN import_generation_id TEXT")
        conn.execute(
            """INSERT INTO plays(
                   play_id, content_type, source_fingerprint, import_generation_id
               ) VALUES (1, 'audio', 'legacy-fingerprint', 'legacy-generation')"""
        )

        migrate_037(conn)

        row = conn.execute(
            """SELECT source_fingerprint, source_fingerprint_version,
                      import_generation_id
               FROM plays WHERE play_id=1"""
        ).fetchone()
        assert tuple(row) == ("legacy-fingerprint", None, "legacy-generation")
    finally:
        conn.close()


def test_migrate_037_fingerprint_index_separates_audio_and_video() -> None:
    conn = _minimal_connection()
    try:
        migrate_037(conn)
        rows = (
            (1, "audio", "same", 1, "generation-1"),
            (2, "video", "same", 1, "generation-1"),
            (3, "audio", None, None, None),
            (4, "audio", None, None, None),
        )
        conn.executemany(
            """INSERT INTO plays(
                   play_id, content_type, source_fingerprint,
                   source_fingerprint_version, import_generation_id
               ) VALUES (?, ?, ?, ?, ?)""",
            rows,
        )

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO plays(
                       play_id, content_type, source_fingerprint,
                       source_fingerprint_version, import_generation_id
                   ) VALUES (5, 'audio', 'same', 1, 'generation-2')"""
            )
    finally:
        conn.close()


def test_migrate_037_import_run_columns_match_phase_a_plan() -> None:
    conn = _minimal_connection()
    try:
        migrate_037(conn)

        state_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(playback_import_state)")
        }
        assert state_columns == {
            "state_id",
            "active_generation_id",
            "account_identity_hash",
            "fingerprint_version",
            "dataset_digest",
            "record_count",
            "first_ts",
            "latest_ts",
            "last_relation",
            "last_strategy",
            "updated_at",
        }

        run_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(playback_import_runs)")
        }
        assert run_columns == {
            "run_id",
            "requested_mode",
            "detected_relation",
            "status",
            "incoming_digest",
            "previous_digest",
            "incoming_count",
            "unchanged_count",
            "added_count",
            "removed_count",
            "first_ts",
            "latest_ts",
            "earliest_changed_ts",
            "latest_changed_ts",
            "plan_json",
            "started_at",
            "completed_at",
            "error_code",
        }

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO playback_import_state(state_id) VALUES (2)")
    finally:
        conn.close()


def test_migrate_041_upgrades_initial_year_partition_schema() -> None:
    conn = _minimal_connection()
    try:
        conn.execute(
            """CREATE TABLE playback_year_partition_state (
                   report_year INTEGER PRIMARY KEY,
                   direct_digest TEXT NOT NULL,
                   prefix_digest TEXT NOT NULL,
                   record_count INTEGER NOT NULL,
                   source_generation_id TEXT NOT NULL
            )"""
        )
        conn.execute(
            """INSERT INTO playback_year_partition_state(
                   report_year, direct_digest, prefix_digest, record_count,
                   source_generation_id
               ) VALUES (2025, 'direct', 'v1-prefix', 1, 'old')"""
        )

        migrate_041(conn)

        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(playback_year_partition_state)")
        }
        assert {"digest_version", "impact_revision"} <= columns
        assert conn.execute("SELECT COUNT(*) FROM playback_year_partition_state").fetchone()[0] == 0
    finally:
        conn.close()
