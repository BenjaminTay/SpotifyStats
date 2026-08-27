from __future__ import annotations

import sqlite3

import pytest

from backend.core.migrations import (
    migrate_043,
    migrate_044,
    migrate_045,
    migrate_052,
    migrate_054,
    migrate_058,
)
from backend.services.import_maintenance_service import _auto_group_tracks_by_spotify_id

pytestmark = pytest.mark.unit


def _legacy_production_schema() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        PRAGMA foreign_keys=ON;
        CREATE TABLE artists (
            artist_id INTEGER PRIMARY KEY,
            artist_name TEXT NOT NULL
        );
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            track_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
            spotify_track_id TEXT
        );
        CREATE TABLE plays (
            play_id INTEGER PRIMARY KEY AUTOINCREMENT,
            track_id INTEGER REFERENCES tracks(track_id)
        );
        CREATE TABLE track_groups (
            group_id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_name TEXT NOT NULL,
            primary_track_id INTEGER REFERENCES tracks(track_id),
            scope TEXT NOT NULL DEFAULT 'recording'
                CHECK(scope IN ('recording', 'composition')),
            parent_group_id INTEGER REFERENCES track_groups(group_id),
            is_manual INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(canonical_name, scope)
        );
        CREATE TABLE track_group_members (
            group_id INTEGER REFERENCES track_groups(group_id),
            track_id INTEGER REFERENCES tracks(track_id),
            UNIQUE(group_id, track_id)
        );
        """
    )
    conn.executemany(
        "INSERT INTO artists VALUES (?, ?)",
        ((10, "Artist A"), (20, "Artist B"), (30, "Manual Artist")),
    )
    conn.executemany(
        "INSERT INTO tracks VALUES (?, ?, ?, ?)",
        (
            (1, "Occupied title", 10, "spotify-a"),
            (2, "Initial title", 10, "spotify-a"),
            (3, "Initial title", 20, "spotify-b"),
            (4, "Initial title", 20, "spotify-b"),
            (5, "Manual track", 30, None),
        ),
    )
    conn.execute(
        """INSERT INTO track_groups
           (group_id, canonical_name, primary_track_id, scope, is_manual)
           VALUES (7, 'Initial title', 2, 'recording', 0)"""
    )
    conn.executemany(
        "INSERT INTO track_group_members VALUES (7, ?)",
        ((1,), (2,)),
    )
    conn.execute("INSERT INTO plays(track_id) VALUES (2)")
    conn.commit()
    return conn


def test_legacy_provider_group_migration_does_not_create_new_version_facts() -> None:
    conn = _legacy_production_schema()
    try:
        migrate_043(conn)

        columns = {row[1] for row in conn.execute("PRAGMA table_info(track_groups)")}
        assert {"automatic_spotify_track_id", "automatic_artist_id"} <= columns
        assert {
            row[2]
            for row in conn.execute("PRAGMA foreign_key_list(track_groups)")
            if row[3] == "parent_group_id"
        } == {"track_groups"}
        assert conn.execute(
            """SELECT group_id, automatic_spotify_track_id, automatic_artist_id
               FROM track_groups"""
        ).fetchone() == (7, "spotify-a", 10)

        # Same-provider source rows are identity evidence, not an L2 relation.
        assert _auto_group_tracks_by_spotify_id(
            conn,
            track_ids=frozenset({3}),
            spotify_track_ids=frozenset(),
        ) == (0, 0)
        assert conn.execute(
            """SELECT automatic_spotify_track_id, automatic_artist_id
               FROM track_groups WHERE is_manual=0
               ORDER BY automatic_artist_id"""
        ).fetchall() == [("spotify-a", 10)]
    finally:
        conn.close()


def test_track_group_identity_migration_is_idempotent() -> None:
    conn = _legacy_production_schema()
    try:
        migrate_043(conn)
        migrate_043(conn)
        assert conn.execute("SELECT COUNT(*) FROM track_groups").fetchone()[0] == 1
    finally:
        conn.close()


def test_followup_migration_repairs_short_lived_v43_parent_target() -> None:
    conn = _legacy_production_schema()
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.executescript(
            """
            DROP TABLE track_groups;
            CREATE TABLE track_groups (
                group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                canonical_name TEXT NOT NULL,
                primary_track_id INTEGER REFERENCES tracks(track_id),
                scope TEXT NOT NULL,
                parent_group_id INTEGER REFERENCES track_groups_new(group_id),
                is_manual INTEGER NOT NULL DEFAULT 0,
                automatic_spotify_track_id TEXT,
                automatic_artist_id INTEGER REFERENCES artists(artist_id),
                created_at TEXT DEFAULT (datetime('now'))
            );
            INSERT INTO track_groups (
                group_id, canonical_name, primary_track_id, scope, is_manual,
                automatic_spotify_track_id, automatic_artist_id
            ) VALUES (7, 'Initial title', 2, 'recording', 0, 'spotify-a', 10);
            """
        )
        conn.execute("PRAGMA foreign_keys=ON")

        migrate_044(conn)

        assert {
            row[2]
            for row in conn.execute("PRAGMA foreign_key_list(track_groups)")
            if row[3] == "parent_group_id"
        } == {"track_groups"}
        assert conn.execute(
            """SELECT group_id, automatic_spotify_track_id, automatic_artist_id
               FROM track_groups"""
        ).fetchone() == (7, "spotify-a", 10)
    finally:
        conn.close()


def test_followup_migration_removes_automatic_artist_foreign_key() -> None:
    conn = _legacy_production_schema()
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.executescript(
            """
            DROP TABLE track_groups;
            CREATE TABLE track_groups (
                group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                canonical_name TEXT NOT NULL,
                primary_track_id INTEGER REFERENCES tracks(track_id),
                scope TEXT NOT NULL,
                parent_group_id INTEGER REFERENCES track_groups(group_id),
                is_manual INTEGER NOT NULL DEFAULT 0,
                automatic_spotify_track_id TEXT,
                automatic_artist_id INTEGER REFERENCES artists(artist_id),
                created_at TEXT DEFAULT (datetime('now'))
            );
            INSERT INTO track_groups (
                group_id, canonical_name, primary_track_id, scope, is_manual,
                automatic_spotify_track_id, automatic_artist_id
            ) VALUES (7, 'Initial title', 2, 'recording', 0, 'spotify-a', 10);
            """
        )
        conn.execute("PRAGMA foreign_keys=ON")

        migrate_045(conn)

        assert not any(
            row[3] == "automatic_artist_id"
            for row in conn.execute("PRAGMA foreign_key_list(track_groups)")
        )
        assert conn.execute(
            """SELECT group_id, automatic_spotify_track_id, automatic_artist_id
               FROM track_groups"""
        ).fetchone() == (7, "spotify-a", 10)
    finally:
        conn.close()


def test_v52_archives_automatic_cross_l1_group_but_preserves_manual_group() -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE track_groups(
            group_id INTEGER PRIMARY KEY, scope TEXT NOT NULL,
            is_manual INTEGER NOT NULL, group_status TEXT NOT NULL,
            primary_l1_id INTEGER
        );
        CREATE TABLE track_group_l1_members(group_id INTEGER, l1_id INTEGER);
        CREATE TABLE track_group_candidates(
            candidate_id INTEGER PRIMARY KEY, scope TEXT NOT NULL,
            original_l1_id INTEGER NOT NULL, candidate_l1_id INTEGER NOT NULL,
            confidence REAL, evidence_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'pending',
            UNIQUE(scope, original_l1_id, candidate_l1_id)
        );
        CREATE TABLE track_group_migration_audit(
            audit_id INTEGER PRIMARY KEY, group_id INTEGER NOT NULL,
            action TEXT NOT NULL, distinct_l1_count INTEGER NOT NULL,
            details TEXT, created_at TEXT DEFAULT (datetime('now'))
        );
        INSERT INTO track_groups VALUES (1, 'recording', 0, 'active', 10);
        INSERT INTO track_groups VALUES (2, 'recording', 1, 'active', 20);
        INSERT INTO track_group_l1_members VALUES (1, 10), (1, 11);
        INSERT INTO track_group_l1_members VALUES (2, 20), (2, 21);
        """
    )

    migrate_052(conn)

    assert (
        conn.execute("SELECT group_status FROM track_groups WHERE group_id=1").fetchone()[0]
        == "archived"
    )
    assert (
        conn.execute("SELECT group_status FROM track_groups WHERE group_id=2").fetchone()[0]
        == "active"
    )
    assert conn.execute(
        """SELECT scope, original_l1_id, candidate_l1_id, status
             FROM track_group_candidates"""
    ).fetchall() == [("recording", 10, 11, "pending")]


def test_v54_quarantines_existing_overlap_and_enforces_scope_uniqueness() -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE track_groups(
            group_id INTEGER PRIMARY KEY, scope TEXT NOT NULL,
            is_manual INTEGER NOT NULL, group_status TEXT NOT NULL
        );
        CREATE TABLE track_group_l1_members(
            group_id INTEGER NOT NULL, l1_id INTEGER NOT NULL,
            PRIMARY KEY(group_id, l1_id)
        );
        CREATE TABLE track_group_candidates(
            candidate_id INTEGER PRIMARY KEY, scope TEXT NOT NULL,
            original_l1_id INTEGER NOT NULL, candidate_l1_id INTEGER NOT NULL
        );
        INSERT INTO track_groups VALUES
            (1, 'recording', 1, 'active'),
            (2, 'recording', 0, 'active'),
            (3, 'composition', 1, 'active'),
            (4, 'recording', 1, 'archived');
        INSERT INTO track_group_l1_members VALUES
            (1, 10), (2, 10), (3, 10), (4, 20), (4, 10);
        INSERT INTO track_group_candidates VALUES
            (1, 'recording', 10, 20), (2, 'recording', 20, 10);
        """
    )

    migrate_054(conn)

    assert (
        conn.execute("SELECT group_status FROM track_groups WHERE group_id=2").fetchone()[0]
        == "conflict"
    )
    assert conn.execute("SELECT COUNT(*) FROM track_group_candidates").fetchone()[0] == 1
    # The same canonical track may belong once in L2 and once in L3.
    conn.execute("INSERT INTO track_group_l1_members VALUES (3, 20)")
    # An archived group may retain members, but activation fails when it overlaps L2.
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE track_groups SET group_status='active' WHERE group_id=4")
    conn.execute("INSERT INTO track_groups VALUES (5, 'recording', 1, 'active')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO track_group_l1_members VALUES (5, 10)")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO track_group_candidates VALUES (3, 'recording', 20, 10)")


def test_v58_normalizes_governance_aliases_without_collapsing_real_owner() -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE tracks(
            track_id INTEGER PRIMARY KEY, track_name TEXT NOT NULL,
            spotify_track_id TEXT
        );
        CREATE TABLE track_l1_identities(
            l1_id INTEGER PRIMARY KEY, identity_status TEXT NOT NULL,
            representative_track_id INTEGER
        );
        CREATE TABLE track_l1_external_ids(
            provider TEXT NOT NULL, external_track_id TEXT NOT NULL,
            l1_id INTEGER NOT NULL
        );
        CREATE TABLE track_l1_source_links(
            l1_id INTEGER NOT NULL, track_id INTEGER NOT NULL,
            evidence_type TEXT NOT NULL
        );
        CREATE TABLE spotify_track_owners(
            spotify_track_id TEXT PRIMARY KEY, track_id INTEGER NOT NULL
        );
        CREATE TABLE track_groups(
            group_id INTEGER PRIMARY KEY, canonical_name TEXT NOT NULL,
            primary_track_id INTEGER, primary_l1_id INTEGER,
            scope TEXT NOT NULL, is_manual INTEGER NOT NULL,
            group_status TEXT NOT NULL
        );
        CREATE TABLE track_group_l1_members(
            group_id INTEGER NOT NULL, l1_id INTEGER NOT NULL,
            PRIMARY KEY(group_id, l1_id)
        );
        CREATE TABLE track_group_candidates(
            candidate_id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope TEXT NOT NULL, original_l1_id INTEGER NOT NULL,
            candidate_l1_id INTEGER NOT NULL, confidence REAL,
            evidence_json TEXT NOT NULL, status TEXT NOT NULL,
            created_at TEXT
        );
        CREATE TABLE track_group_migration_audit(
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL, action TEXT NOT NULL,
            distinct_l1_count INTEGER NOT NULL, details TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE track_identity_state(
            state_id INTEGER PRIMARY KEY, current_revision INTEGER NOT NULL,
            updated_at TEXT
        );
        CREATE TABLE music_search_snapshot_meta(
            status TEXT NOT NULL, last_error TEXT
        );

        INSERT INTO tracks VALUES
            (1, 'Owner A', 'spotify-a'),
            (2, 'Owner B', 'spotify-a'),
            (3, 'Historical alias', 'spotify-a');
        INSERT INTO track_l1_identities VALUES
            (1, 'active', 1), (2, 'active', 2), (3, 'active', 3);
        INSERT INTO spotify_track_owners VALUES
            ('spotify-a', 1), ('spotify-b', 2);
        INSERT INTO track_l1_external_ids VALUES
            ('spotify', 'spotify-a', 1), ('spotify', 'spotify-b', 2);
        INSERT INTO track_groups VALUES
            (10, 'Collapsed alias group', 1, 1, 'recording', 1, 'active'),
            (11, 'Valid versions', 2, 2, 'composition', 1, 'active');
        INSERT INTO track_group_l1_members VALUES
            (10, 1), (10, 3), (11, 2), (11, 3);
        INSERT INTO track_group_candidates(
            scope, original_l1_id, candidate_l1_id,
            confidence, evidence_json, status, created_at
        ) VALUES
            ('recording', 1, 3, 1.0, '{}', 'pending', '2026-01-01'),
            ('composition', 2, 3, 1.0, '{}', 'pending', '2026-01-01');
        INSERT INTO track_identity_state VALUES (1, 5, '2026-01-01');
        INSERT INTO music_search_snapshot_meta VALUES ('ready', NULL);
        """
    )

    migrate_058(conn)

    assert (
        conn.execute("SELECT group_status FROM track_groups WHERE group_id=10").fetchone()[0]
        == "archived"
    )
    assert (
        conn.execute("SELECT group_status FROM track_groups WHERE group_id=11").fetchone()[0]
        == "active"
    )
    assert conn.execute(
        "SELECT l1_id FROM track_group_l1_members WHERE group_id=11 ORDER BY l1_id"
    ).fetchall() == [(1,), (2,)]
    assert conn.execute(
        """SELECT scope, original_l1_id, candidate_l1_id, status
             FROM track_group_candidates"""
    ).fetchall() == [("composition", 1, 2, "accepted")]
    assert conn.execute("SELECT status FROM music_search_snapshot_meta").fetchone()[0] == "stale"
    assert (
        conn.execute(
            "SELECT current_revision FROM track_identity_state WHERE state_id=1"
        ).fetchone()[0]
        == 6
    )
