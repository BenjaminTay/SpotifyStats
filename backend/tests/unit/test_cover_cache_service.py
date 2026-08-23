from __future__ import annotations

import sqlite3

import pytest

from backend.core.job_queue import Job

pytestmark = pytest.mark.unit


class _Queue:
    def __init__(self):
        self.jobs: list[Job] = []

    def enqueue_if_not_pending(self, job: Job) -> str:
        self.jobs.append(job)
        return job.job_id


def test_cover_backfill_syncs_effective_urls_and_separates_entity_types(tmp_path, monkeypatch):
    from backend.core import db as db_module
    from backend.services.cover_cache_service import enqueue_missing_cover_downloads

    db_path = tmp_path / "stats.db"
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE artists(
            artist_id INTEGER PRIMARY KEY, artist_name TEXT,
            spotify_artist_id TEXT, image_url TEXT, image_path TEXT
        );
        CREATE TABLE albums(
            album_id INTEGER PRIMARY KEY, album_name TEXT, artist_id INTEGER,
            spotify_album_id TEXT, image_url TEXT, image_path TEXT
        );
        CREATE TABLE tracks(
            track_id INTEGER PRIMARY KEY, artist_id INTEGER, album_id INTEGER
        );
        CREATE TABLE plays(
            play_id INTEGER PRIMARY KEY, track_id INTEGER, source_album_id INTEGER
        );
        CREATE TABLE track_artists(track_id INTEGER, artist_id INTEGER);
        CREATE TABLE album_spotify_links(
            album_id INTEGER, spotify_album_id TEXT, confidence REAL,
            play_count INTEGER, evidence TEXT
        );
        CREATE TABLE spotify_album_meta(
            spotify_album_id TEXT PRIMARY KEY, album_type TEXT, image_url TEXT
        );
        CREATE TABLE spotify_artist_meta(
            spotify_artist_id TEXT PRIMARY KEY, artist_name TEXT, image_url TEXT
        );
        INSERT INTO artists VALUES (42, 'Artist', 'artist-42', NULL, NULL);
        INSERT INTO albums VALUES (42, 'Album', 42, NULL, NULL, NULL);
        INSERT INTO tracks VALUES (1, 42, 42);
        INSERT INTO plays VALUES (1, 1, 42);
        INSERT INTO track_artists VALUES (1, 42);
        INSERT INTO album_spotify_links VALUES (42, 'album-42', 1.0, 1, 'test');
        INSERT INTO spotify_album_meta VALUES ('album-42', 'album', 'album.jpg');
        INSERT INTO spotify_artist_meta VALUES ('artist-42', 'Artist', 'artist.jpg');
        """
    )
    queue = _Queue()

    report = enqueue_missing_cover_downloads(conn, queue=queue)

    assert report.missing_albums == 1
    assert report.missing_artists == 1
    assert report.jobs_enqueued == 2
    assert {(job.entity_type, job.entity_id) for job in queue.jobs} == {
        ("albums", "42"),
        ("artists", "42"),
    }
    assert conn.execute("SELECT image_url FROM albums").fetchone()[0] == "album.jpg"
    assert conn.execute("SELECT image_url FROM artists").fetchone()[0] == "artist.jpg"
