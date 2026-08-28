from __future__ import annotations

import sqlite3

import pytest

from backend.core.migrations import migrate_061, migrate_062

pytestmark = pytest.mark.unit


def test_migration_61_backfills_verified_lkg_and_keeps_new_target() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE music_search_snapshot_meta (
            snapshot_key TEXT PRIMARY KEY,
            filter_fingerprint TEXT NOT NULL,
            status TEXT NOT NULL,
            builder_version TEXT,
            merge_level INTEGER,
            dynamic_threshold INTEGER,
            created_at TEXT,
            activated_at TEXT,
            last_error TEXT
        );
        CREATE TABLE music_search_entity_context (
            snapshot_key TEXT NOT NULL,
            entity_key TEXT NOT NULL
        );
        INSERT INTO music_search_snapshot_meta VALUES (
            'old', 'old', 'stale', 'music_search_snapshot_v8_canonical_track',
            2, 1, '2026-01-01', '2026-01-01', NULL
        );
        INSERT INTO music_search_entity_context VALUES ('old', 'track:1');
        INSERT INTO music_search_snapshot_meta VALUES (
            'new', 'new', 'pending', 'music_search_snapshot_v8_canonical_track',
            2, 1, '2026-02-01', NULL, 'metadata changed'
        );
        """
    )

    migrate_061(conn)

    row = conn.execute(
        """SELECT * FROM music_search_snapshot_variant_state
           WHERE merge_level=2 AND dynamic_threshold=1"""
    ).fetchone()
    assert row["active_snapshot_key"] == "old"
    assert row["active_filter_fingerprint"] == "old"
    assert row["target_filter_fingerprint"] == "new"
    assert row["maintenance_status"] == "pending"


def test_migration_62_enforces_contiguous_unique_credit_revisions() -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE tracks (track_id INTEGER PRIMARY KEY);
        INSERT INTO tracks VALUES (1);
        """
    )
    migrate_062(conn)
    row = (
        1,
        2,
        1,
        "[1]",
        "[]",
        "[]",
        "{}",
        "{}",
        "[]",
        1,
        0,
    )
    conn.execute(
        """INSERT INTO track_credit_change_sets(
               from_revision, to_revision, track_id, canonical_track_ids_json,
               before_credits_json, after_credits_json, before_roles_json,
               after_roles_json, affected_artist_ids_json, candidate_changed,
               statistics_membership_changed
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        row,
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO track_credit_change_sets(
                   from_revision, to_revision, track_id, canonical_track_ids_json,
                   before_credits_json, after_credits_json, before_roles_json,
                   after_roles_json, affected_artist_ids_json, candidate_changed,
                   statistics_membership_changed
               ) VALUES (2, 4, 1, '[]', '[]', '[]', '{}', '{}', '[]', 1, 1)"""
        )
