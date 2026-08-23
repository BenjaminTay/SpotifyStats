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


def test_cover_backfill_requeues_valid_file_when_source_url_changes(tmp_path, monkeypatch):
    from backend.core import db as db_module
    from backend.core.migrations import migrate_039
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
        CREATE TABLE tracks(track_id INTEGER PRIMARY KEY, artist_id INTEGER, album_id INTEGER);
        CREATE TABLE plays(play_id INTEGER PRIMARY KEY, track_id INTEGER, source_album_id INTEGER);
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
        INSERT INTO artists VALUES (7, 'Artist', 'artist-7', 'old.jpg', NULL);
        INSERT INTO tracks VALUES (1, 7, NULL);
        INSERT INTO plays VALUES (1, 1, NULL);
        INSERT INTO track_artists VALUES (1, 7);
        """
    )
    migrate_039(conn)
    cover_path = tmp_path / "covers" / "artists" / "7.jpg"
    cover_path.parent.mkdir(parents=True)
    cover_path.write_bytes(b"x" * 2048)
    queue = _Queue()

    initial = enqueue_missing_cover_downloads(conn, queue=queue, album_ids=set(), artist_ids={7})
    assert initial.jobs_enqueued == 1
    assert (
        conn.execute("SELECT cached_source_url_hash FROM cover_cache_state").fetchone()[0] is None
    )
    conn.execute(
        """UPDATE cover_cache_state
           SET cached_source_url_hash=source_url_hash, status='ready'"""
    )
    conn.commit()
    queue.jobs.clear()

    conn.execute("UPDATE artists SET image_url='new.jpg' WHERE artist_id=7")
    changed = enqueue_missing_cover_downloads(conn, queue=queue, album_ids=set(), artist_ids={7})

    assert changed.stale_sources == 1
    assert changed.jobs_enqueued == 1
    assert queue.jobs[-1].payload["cdn_url"] == "new.jpg"


def test_cover_backfill_observes_provider_url_change_without_overwriting_local_url(
    tmp_path, monkeypatch
):
    from backend.core import db as db_module
    from backend.core.migrations import migrate_039
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
        CREATE TABLE tracks(track_id INTEGER PRIMARY KEY, artist_id INTEGER, album_id INTEGER);
        CREATE TABLE plays(play_id INTEGER PRIMARY KEY, track_id INTEGER, source_album_id INTEGER);
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
        INSERT INTO artists VALUES (8, 'Artist', 'artist-8', 'manual.jpg', NULL);
        INSERT INTO albums VALUES (8, 'Album', 8, 'album-8', 'old-local.jpg', NULL);
        INSERT INTO tracks VALUES (8, 8, 8);
        INSERT INTO plays VALUES (8, 8, 8);
        INSERT INTO album_spotify_links VALUES (8, 'album-8', 1.0, 1, 'test');
        INSERT INTO spotify_album_meta VALUES ('album-8', 'album', 'new-provider.jpg');
        """
    )
    migrate_039(conn)
    queue = _Queue()

    report = enqueue_missing_cover_downloads(conn, queue=queue, album_ids={8}, artist_ids=set())

    assert report.jobs_enqueued == 1
    assert queue.jobs[0].payload["cdn_url"] == "new-provider.jpg"
    assert conn.execute("SELECT image_url FROM albums WHERE album_id=8").fetchone()[0] == (
        "old-local.jpg"
    )
