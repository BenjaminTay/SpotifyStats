"""Unit tests for album project bootstrap and resolver helpers."""

from __future__ import annotations

import sqlite3

import pandas as pd

from backend.core.db import SCHEMA
from backend.domains.playback.album_projects import (
    compute_album_project_plays,
    compute_album_project_weekly_plays,
    ensure_album_projects,
)


def test_ensure_album_projects_is_idempotent():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        conn.execute("INSERT INTO artists(artist_id, artist_name) VALUES (1, 'Artist')")
        conn.execute("INSERT INTO albums(album_id, album_name, artist_id) VALUES (1, 'Album', 1)")
        conn.execute(
            "INSERT INTO tracks(track_id, track_name, artist_id, album_id) VALUES (1, 'Song', 1, 1)"
        )
        conn.execute(
            """INSERT INTO spotify_album_meta
               (spotify_album_id, album_name, album_type, release_date, total_tracks)
               VALUES ('spotify:album:unit1', 'Album', 'album', '2026-01-01', 10)"""
        )
        conn.execute(
            """INSERT INTO spotify_track_meta
               (spotify_track_id, track_name, spotify_album_id)
               VALUES ('unittrack1', 'Song', 'spotify:album:unit1')"""
        )
        conn.execute(
            "INSERT INTO release_groups(group_id, canonical_name, artist_id, primary_album_id, scope)"
            " VALUES (1, 'Album', 1, 1, 'release')"
        )
        conn.execute("INSERT INTO release_group_members(group_id, album_id) VALUES (1, 1)")
        conn.commit()

        ensure_album_projects(conn)
        first_count = conn.execute("SELECT COUNT(*) FROM album_projects").fetchone()[0]
        ensure_album_projects(conn)
        second_count = conn.execute("SELECT COUNT(*) FROM album_projects").fetchone()[0]

        assert first_count == 1
        assert second_count == first_count
    finally:
        conn.close()


def test_album_project_plays_accepts_preaggregated_weighted_rows():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        conn.execute("INSERT INTO artists(artist_id, artist_name) VALUES (1, 'Artist')")
        conn.execute("INSERT INTO albums(album_id, album_name, artist_id) VALUES (1, 'Album', 1)")
        conn.execute(
            "INSERT INTO tracks(track_id, track_name, artist_id, album_id) VALUES (1, 'Song', 1, 1)"
        )
        conn.execute(
            """INSERT INTO spotify_album_meta
               (spotify_album_id, album_name, album_type, release_date, total_tracks)
               VALUES ('spotify:album:unit1', 'Album', 'album', '2026-01-01', 10)"""
        )
        conn.execute(
            "INSERT INTO release_groups(group_id, canonical_name, artist_id, primary_album_id, scope)"
            " VALUES (1, 'Album', 1, 1, 'release')"
        )
        conn.execute("INSERT INTO release_group_members(group_id, album_id) VALUES (1, 1)")
        conn.commit()
        ensure_album_projects(conn)

        preagg = pd.DataFrame(
            [
                {
                    "track_id": 1,
                    "track_name": "Song",
                    "artist_name": "Artist",
                    "album_name": "Album",
                    "source_album_id": 1,
                    "play_count": 3,
                    "total_ms": 600000,
                    "ts_date": "2026-01-05",
                }
            ]
        )

        result = compute_album_project_plays(
            preagg,
            conn,
            merge_level=2,
            include_compilations=False,
            billboard_mode=True,
        )

        assert int(result.iloc[0]["play_count"]) == 3
        assert int(result.iloc[0]["total_ms"]) == 600000
        assert int(result.iloc[0]["unique_canonical_songs"]) == 1
    finally:
        conn.close()


def test_album_project_weekly_plays_groups_weighted_rows_by_billboard_week():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        conn.execute("INSERT INTO artists(artist_id, artist_name) VALUES (1, 'Artist')")
        conn.execute("INSERT INTO albums(album_id, album_name, artist_id) VALUES (1, 'Album', 1)")
        conn.execute(
            "INSERT INTO tracks(track_id, track_name, artist_id, album_id) VALUES (1, 'Song', 1, 1)"
        )
        conn.execute(
            """INSERT INTO spotify_album_meta
               (spotify_album_id, album_name, album_type, release_date, total_tracks)
               VALUES ('spotify:album:unit1', 'Album', 'album', '2026-01-01', 10)"""
        )
        conn.execute(
            "INSERT INTO release_groups(group_id, canonical_name, artist_id, primary_album_id, scope)"
            " VALUES (1, 'Album', 1, 1, 'release')"
        )
        conn.execute("INSERT INTO release_group_members(group_id, album_id) VALUES (1, 1)")
        conn.commit()
        ensure_album_projects(conn)

        preagg = pd.DataFrame(
            [
                {
                    "billboard_week": "2026-01-02",
                    "track_id": 1,
                    "track_name": "Song",
                    "artist_name": "Artist",
                    "album_name": "Album",
                    "source_album_id": 1,
                    "play_count": 3,
                    "total_ms": 600000,
                    "ts_date": "2026-01-05",
                },
                {
                    "billboard_week": "2026-01-09",
                    "track_id": 1,
                    "track_name": "Song",
                    "artist_name": "Artist",
                    "album_name": "Album",
                    "source_album_id": 1,
                    "play_count": 2,
                    "total_ms": 400000,
                    "ts_date": "2026-01-12",
                },
            ]
        )

        result = compute_album_project_weekly_plays(
            preagg,
            conn,
            merge_level=2,
            include_compilations=False,
            billboard_mode=True,
        )

        by_week = {
            str(row["billboard_week"]): int(row["play_count"]) for _, row in result.iterrows()
        }
        assert by_week == {"2026-01-02": 3, "2026-01-09": 2}
    finally:
        conn.close()
