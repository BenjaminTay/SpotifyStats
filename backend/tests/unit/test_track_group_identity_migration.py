from __future__ import annotations

import sqlite3

import pytest

from backend.core.migrations import migrate_043, migrate_044, migrate_045
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


def test_migrated_production_schema_uses_provider_identity_not_display_name() -> None:
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

        # Artist B has the same canonical title.  The legacy production UNIQUE
        # constraint rejected this row; provider identity now keeps it distinct.
        assert _auto_group_tracks_by_spotify_id(
            conn,
            track_ids=frozenset({3}),
            spotify_track_ids=frozenset(),
        ) == (1, 2)
        assert conn.execute(
            """SELECT automatic_spotify_track_id, automatic_artist_id
               FROM track_groups WHERE is_manual=0
               ORDER BY automatic_artist_id"""
        ).fetchall() == [("spotify-a", 10), ("spotify-b", 20)]

        # A manual group may occupy the next automatic display name.  A primary
        # ranking flip must retain the automatic group id and never mutate it.
        conn.execute(
            """INSERT INTO track_groups
               (canonical_name, primary_track_id, scope, is_manual)
               VALUES ('Occupied title', 5, 'recording', 1)"""
        )
        conn.executemany("INSERT INTO plays(track_id) VALUES (?)", ((1,), (1,)))
        assert _auto_group_tracks_by_spotify_id(
            conn,
            track_ids=frozenset({1}),
            spotify_track_ids=frozenset(),
        ) == (0, 0)

        assert conn.execute(
            """SELECT group_id, canonical_name, primary_track_id
               FROM track_groups
               WHERE automatic_spotify_track_id='spotify-a'
                 AND automatic_artist_id=10"""
        ).fetchone() == (7, "Occupied title", 1)
        assert (
            conn.execute(
                """SELECT COUNT(*) FROM track_groups
               WHERE canonical_name='Occupied title' AND scope='recording'"""
            ).fetchone()[0]
            == 2
        )
        assert conn.execute(
            """SELECT is_manual, primary_track_id FROM track_groups
               WHERE canonical_name='Occupied title'
               ORDER BY is_manual"""
        ).fetchall() == [(0, 1), (1, 5)]
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
