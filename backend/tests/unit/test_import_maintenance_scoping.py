from __future__ import annotations

import sqlite3

import pytest

from backend.services.import_maintenance_service import _auto_group_tracks_by_spotify_id

pytestmark = pytest.mark.unit


def _grouping_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            track_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL,
            spotify_track_id TEXT
        );
        CREATE TABLE plays (
            play_id INTEGER PRIMARY KEY,
            track_id INTEGER
        );
        CREATE TABLE track_groups (
            group_id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_name TEXT NOT NULL,
            primary_track_id INTEGER NOT NULL,
            scope TEXT NOT NULL,
            is_manual INTEGER NOT NULL,
            automatic_spotify_track_id TEXT,
            automatic_artist_id INTEGER
        );
        CREATE UNIQUE INDEX idx_track_groups_manual_name_scope
            ON track_groups(canonical_name, scope) WHERE is_manual=1;
        CREATE UNIQUE INDEX idx_track_groups_automatic_identity
            ON track_groups(scope, automatic_spotify_track_id, automatic_artist_id)
            WHERE is_manual=0 AND automatic_spotify_track_id IS NOT NULL
              AND automatic_artist_id IS NOT NULL;
        CREATE TABLE track_group_members (
            group_id INTEGER NOT NULL,
            track_id INTEGER NOT NULL,
            PRIMARY KEY(group_id, track_id)
        );
        """
    )
    conn.executemany(
        "INSERT INTO tracks VALUES (?, ?, ?, ?)",
        (
            (1, "A one", 10, "spotify-a"),
            (2, "A two", 10, "spotify-a"),
            (3, "B one", 20, "spotify-b"),
            (4, "B two", 20, "spotify-b"),
        ),
    )
    conn.executemany(
        "INSERT INTO plays(track_id) VALUES (?)",
        ((2,), (2,), (3,)),
    )
    return conn


def test_spotify_track_grouping_only_touches_impacted_pairs() -> None:
    conn = _grouping_db()
    try:
        assert _auto_group_tracks_by_spotify_id(
            conn,
            track_ids=frozenset({1}),
            spotify_track_ids=frozenset(),
        ) == (1, 2)
        assert conn.execute(
            """SELECT t.spotify_track_id
               FROM track_groups tg JOIN tracks t ON t.track_id=tg.primary_track_id"""
        ).fetchall() == [("spotify-a",)]

        assert _auto_group_tracks_by_spotify_id(
            conn,
            track_ids=frozenset(),
            spotify_track_ids=frozenset({"spotify-b"}),
        ) == (1, 2)
        assert conn.execute(
            """SELECT DISTINCT t.spotify_track_id
               FROM track_groups tg JOIN tracks t ON t.track_id=tg.primary_track_id
               ORDER BY t.spotify_track_id"""
        ).fetchall() == [("spotify-a",), ("spotify-b",)]

        assert _auto_group_tracks_by_spotify_id(
            conn,
            track_ids=frozenset({1}),
            spotify_track_ids=frozenset({"spotify-a"}),
        ) == (0, 0)
    finally:
        conn.close()


def test_spotify_track_grouping_reuses_group_when_primary_ranking_changes() -> None:
    conn = _grouping_db()
    try:
        assert _auto_group_tracks_by_spotify_id(
            conn,
            track_ids=frozenset({1}),
            spotify_track_ids=frozenset(),
        ) == (1, 2)
        original_group_id = conn.execute("SELECT group_id FROM track_groups").fetchone()[0]
        conn.executemany("INSERT INTO plays(track_id) VALUES (?)", ((1,), (1,), (1,)))

        assert _auto_group_tracks_by_spotify_id(
            conn,
            track_ids=frozenset({1}),
            spotify_track_ids=frozenset(),
        ) == (0, 0)

        assert conn.execute("SELECT COUNT(*) FROM track_groups").fetchone()[0] == 1
        group = conn.execute(
            "SELECT group_id, primary_track_id, canonical_name FROM track_groups"
        ).fetchone()
        assert group == (original_group_id, 1, "A one")
        assert conn.execute(
            "SELECT track_id FROM track_group_members ORDER BY track_id"
        ).fetchall() == [(1,), (2,)]
    finally:
        conn.close()


def test_spotify_track_grouping_allows_same_name_for_different_artists() -> None:
    conn = _grouping_db()
    try:
        conn.execute("UPDATE tracks SET track_name='Shared title'")

        assert _auto_group_tracks_by_spotify_id(conn) == (2, 4)

        assert conn.execute(
            """SELECT canonical_name, automatic_spotify_track_id, automatic_artist_id
               FROM track_groups ORDER BY automatic_artist_id"""
        ).fetchall() == [
            ("Shared title", "spotify-a", 10),
            ("Shared title", "spotify-b", 20),
        ]
    finally:
        conn.close()


def test_primary_flip_can_reuse_a_name_occupied_by_manual_group() -> None:
    conn = _grouping_db()
    try:
        assert _auto_group_tracks_by_spotify_id(
            conn,
            track_ids=frozenset({1}),
            spotify_track_ids=frozenset(),
        ) == (1, 2)
        automatic_group_id = conn.execute(
            "SELECT group_id FROM track_groups WHERE is_manual=0"
        ).fetchone()[0]
        conn.execute(
            """INSERT INTO track_groups
               (canonical_name, primary_track_id, scope, is_manual)
               VALUES ('A one', 4, 'recording', 1)"""
        )
        conn.executemany("INSERT INTO plays(track_id) VALUES (?)", ((1,), (1,), (1,)))

        assert _auto_group_tracks_by_spotify_id(
            conn,
            track_ids=frozenset({1}),
            spotify_track_ids=frozenset(),
        ) == (0, 0)

        automatic = conn.execute(
            """SELECT group_id, canonical_name, primary_track_id,
                      automatic_spotify_track_id, automatic_artist_id
               FROM track_groups WHERE is_manual=0"""
        ).fetchone()
        assert automatic == (automatic_group_id, "A one", 1, "spotify-a", 10)
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM track_groups WHERE canonical_name='A one'"
            ).fetchone()[0]
            == 2
        )
    finally:
        conn.close()


def test_manual_composition_with_same_primary_does_not_suppress_recording_group() -> None:
    conn = _grouping_db()
    try:
        assert _auto_group_tracks_by_spotify_id(
            conn,
            track_ids=frozenset({1}),
            spotify_track_ids=frozenset(),
        ) == (1, 2)
        automatic_group_id = conn.execute(
            "SELECT group_id FROM track_groups WHERE scope='recording' AND is_manual=0"
        ).fetchone()[0]
        conn.execute(
            """INSERT INTO track_groups
               (canonical_name, primary_track_id, scope, is_manual)
               VALUES ('A composition', 2, 'composition', 1)"""
        )

        assert _auto_group_tracks_by_spotify_id(
            conn,
            track_ids=frozenset({1}),
            spotify_track_ids=frozenset(),
        ) == (0, 0)

        assert conn.execute(
            """SELECT group_id, primary_track_id
               FROM track_groups WHERE scope='recording' AND is_manual=0"""
        ).fetchone() == (automatic_group_id, 2)
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM track_groups WHERE scope='composition' AND is_manual=1"
            ).fetchone()[0]
            == 1
        )
    finally:
        conn.close()
