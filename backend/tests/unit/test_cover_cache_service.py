from __future__ import annotations

import sqlite3

import pytest

from backend.core.job_queue import Job, JobQueue

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
        CREATE TABLE background_jobs(
            job_id TEXT PRIMARY KEY, job_type TEXT NOT NULL,
            entity_type TEXT, entity_id TEXT, payload_json TEXT,
            status TEXT NOT NULL DEFAULT 'pending', created_at TEXT,
            updated_at TEXT, attempts INTEGER DEFAULT 0, error TEXT
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
    queue = JobQueue(max_workers=0)
    queue.prepare(str(db_path))

    initial = enqueue_missing_cover_downloads(conn, queue=queue, album_ids=set(), artist_ids={7})
    assert initial.jobs_enqueued == 1
    assert (
        conn.execute("SELECT cached_source_url_hash FROM cover_cache_state").fetchone()[0] is None
    )
    conn.execute(
        """UPDATE cover_cache_state
           SET cached_source_url_hash=source_url_hash, status='ready'"""
    )
    conn.execute("UPDATE background_jobs SET status='running'")
    conn.commit()

    conn.execute("UPDATE artists SET image_url='new.jpg' WHERE artist_id=7")
    changed = enqueue_missing_cover_downloads(conn, queue=queue, album_ids=set(), artist_ids={7})
    duplicate = enqueue_missing_cover_downloads(
        conn,
        queue=queue,
        album_ids=set(),
        artist_ids={7},
    )

    assert changed.stale_sources == 1
    assert changed.jobs_enqueued == 1
    assert duplicate.jobs_enqueued == 0
    jobs = queue._startup_jobs
    assert [job.payload["cdn_url"] for job in jobs] == ["old.jpg", "new.jpg"]
    assert jobs[0].target_key != jobs[1].target_key
    assert jobs[1].payload["source_url_hash"] == jobs[1].payload["target_revision"]


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


def test_startup_failed_cover_recovery_is_bounded_and_does_not_scan_all_missing(
    tmp_path, monkeypatch
):
    from backend.core import db as db_module
    from backend.services.cover_cache_service import enqueue_failed_cover_download_recovery

    db_path = tmp_path / "stats.db"
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    conn = sqlite3.connect(db_path)
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
        CREATE TABLE cover_cache_state(
            entity_type TEXT NOT NULL, entity_id INTEGER NOT NULL,
            source_url_hash TEXT NOT NULL, cached_source_url_hash TEXT,
            status TEXT NOT NULL, last_error TEXT, updated_at TEXT NOT NULL,
            PRIMARY KEY(entity_type, entity_id)
        );
        INSERT INTO artists VALUES
            (1, 'A1', NULL, 'a1.jpg', NULL),
            (2, 'A2', NULL, 'a2.jpg', NULL),
            (3, 'A3', NULL, 'a3.jpg', NULL),
            (4, 'A4', NULL, 'a4.jpg', NULL);
        INSERT INTO tracks VALUES (1, 1, NULL), (2, 2, NULL), (3, 3, NULL), (4, 4, NULL);
        INSERT INTO plays VALUES (1, 1, NULL), (2, 2, NULL), (3, 3, NULL), (4, 4, NULL);
        INSERT INTO cover_cache_state VALUES
            ('artists', 1, 'old-1', NULL, 'failed', 'x', '2026-01-01'),
            ('artists', 2, 'old-2', NULL, 'failed', 'x', '2026-01-02'),
            ('artists', 3, 'old-3', NULL, 'failed', 'x', '2026-01-03');
        """
    )
    conn.commit()
    conn.close()
    queue = _Queue()

    report = enqueue_failed_cover_download_recovery(queue, backlog_limit=2)

    assert report.sources_scanned == 2
    assert report.jobs_enqueued == 2
    assert [job.entity_id for job in queue.jobs] == ["1", "2"]
    assert all(job.entity_id != "4" for job in queue.jobs)
