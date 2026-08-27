from __future__ import annotations

import sqlite3

import pytest

from backend.services.import_maintenance_service import _auto_group_tracks_by_spotify_id

pytestmark = pytest.mark.unit


def test_same_spotify_id_never_creates_a_version_group() -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE tracks(
            track_id INTEGER PRIMARY KEY,
            track_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL,
            spotify_track_id TEXT
        );
        CREATE TABLE track_groups(group_id INTEGER PRIMARY KEY);
        INSERT INTO tracks VALUES
            (1, '同一曲目', 10, 'spotify-a'),
            (2, '同一曲目', 10, 'spotify-a');
        """
    )

    assert _auto_group_tracks_by_spotify_id(conn) == (0, 0)
    assert conn.execute("SELECT COUNT(*) FROM track_groups").fetchone()[0] == 0


def test_retired_grouping_ignores_target_scopes() -> None:
    conn = sqlite3.connect(":memory:")
    assert _auto_group_tracks_by_spotify_id(
        conn,
        track_ids=frozenset({1, 2}),
        spotify_track_ids=frozenset({"spotify-a"}),
    ) == (0, 0)
