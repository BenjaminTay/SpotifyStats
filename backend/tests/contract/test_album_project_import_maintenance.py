from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


def _ensure_album_spotify_links(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS album_spotify_links (
            album_id INTEGER NOT NULL,
            spotify_album_id TEXT NOT NULL,
            evidence TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.0,
            play_count INTEGER NOT NULL DEFAULT 0,
            track_count INTEGER NOT NULL DEFAULT 0,
            first_seen TEXT,
            last_seen TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(album_id, spotify_album_id, evidence)
        )"""
    )


def test_album_project_rebuild_uses_linked_album_when_name_match_points_to_single(use_seed_db):
    from backend.core.db import get_db
    from backend.domains.playback.album_projects import rebuild_album_projects

    conn = get_db(readonly=False)
    try:
        _ensure_album_spotify_links(conn)
        artist_id = conn.execute(
            "INSERT INTO artists(artist_name) VALUES ('Fixture Import Artist')"
        ).lastrowid
        album_id = conn.execute(
            "INSERT INTO albums(album_name, artist_id) VALUES ('Dinner Party Fixture', ?)",
            (artist_id,),
        ).lastrowid

        conn.execute(
            """INSERT INTO spotify_album_meta(
                   spotify_album_id, album_name, album_type, release_date,
                   album_artists, total_tracks, image_url)
               VALUES ('single-id', 'Dinner Party Fixture', 'single', '2026-03-20',
                       'Fixture Import Artist', 1, 'single.jpg')"""
        )
        conn.execute(
            """INSERT INTO spotify_album_meta(
                   spotify_album_id, album_name, album_type, release_date,
                   album_artists, total_tracks, image_url)
               VALUES ('album-id', 'Dinner Party Fixture', 'album', '2026-06-01',
                       'Fixture Import Artist', 11, 'album.jpg')"""
        )
        conn.execute(
            """INSERT INTO album_spotify_links(
                   album_id, spotify_album_id, evidence, confidence, play_count,
                   track_count, first_seen, last_seen)
               VALUES (?, 'album-id', 'play_track_api', 1.0, 11, 11, '2026-06-01', '2026-06-02')""",
            (album_id,),
        )
        for idx in range(11):
            track_id = 90_000 + idx
            conn.execute(
                "INSERT INTO tracks(track_id, track_name, artist_id, album_id, spotify_track_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (track_id, f"Fixture Import Track {idx}", artist_id, album_id, f"track-{idx}"),
            )
            conn.execute(
                "INSERT INTO track_albums(track_id, album_id) VALUES (?, ?)",
                (track_id, album_id),
            )
            conn.execute(
                """INSERT INTO plays(
                       ts, ts_year, ts_month, ts_week, ts_dow, ts_hour,
                       ts_date, platform, ms_played, track_id, source_album_id
                   ) VALUES (?, 2026, 6, 23, 0, 12, '2026-06-01',
                             'fixture', 180000, ?, ?)""",
                (f"2026-06-01T12:00:{idx:02d}Z", track_id, album_id),
            )
        conn.commit()

        rebuild_album_projects(conn)

        row = conn.execute(
            """SELECT ap.project_id, ap.release_date, COUNT(apt.track_id) AS tracks
               FROM album_projects ap
               JOIN album_project_albums apa ON apa.project_id = ap.project_id
               JOIN album_project_tracks apt ON apt.project_id = ap.project_id
               WHERE apa.album_id = ?
               GROUP BY ap.project_id""",
            (album_id,),
        ).fetchone()
        assert row is not None
        assert row["release_date"] == "2026-06-01"
        assert row["tracks"] == 11
    finally:
        conn.close()
