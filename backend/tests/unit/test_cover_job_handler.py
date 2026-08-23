from __future__ import annotations

import hashlib
import sqlite3

import pytest

from backend.core.job_queue import Job

pytestmark = pytest.mark.unit


@pytest.fixture
def cover_db(tmp_path, monkeypatch):
    from backend.core import db as db_module

    db_path = tmp_path / "stats.db"
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE albums(
            album_id INTEGER PRIMARY KEY,
            image_url TEXT,
            image_path TEXT
        );
        CREATE TABLE artists(
            artist_id INTEGER PRIMARY KEY,
            image_url TEXT,
            image_path TEXT
        );
        CREATE TABLE cover_cache_state (
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            source_url_hash TEXT NOT NULL,
            cached_source_url_hash TEXT,
            status TEXT NOT NULL,
            last_error TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY(entity_type, entity_id)
        );
        """
    )
    conn.commit()
    conn.close()
    return db_path


def _source_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def _stub_http(monkeypatch, *, status: int = 200, body: bytes | None = None) -> None:
    from backend.jobs import handlers

    response_body = body if body is not None else b"\xff\xd8\xff" + b"x" * 2048

    class StubClient:
        def __init__(self, **_kwargs):
            pass

        def get(self, _url):
            return type("Response", (), {"status": status, "body": response_body})()

    monkeypatch.setattr(handlers, "HttpClient", StubClient)


def _insert_album_state(
    db_path,
    *,
    image_url: str,
    state_url: str | None = None,
    image_path: str | None = None,
    status: str = "pending",
) -> None:
    effective_state_url = state_url or image_url
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO albums(album_id, image_url, image_path) VALUES (1, ?, ?)",
        (image_url, image_path),
    )
    conn.execute(
        """INSERT INTO cover_cache_state(
               entity_type, entity_id, source_url_hash,
               cached_source_url_hash, status, last_error
           ) VALUES ('albums', 1, ?, ?, ?, NULL)""",
        (
            _source_hash(effective_state_url),
            _source_hash(effective_state_url) if status == "ready" else None,
            status,
        ),
    )
    conn.commit()
    conn.close()


def test_cover_handler_publishes_file_and_ready_state_with_matching_source(cover_db, monkeypatch):
    from backend.jobs.handlers import handle_cover_download

    provider_url = "https://cdn.example/new-provider.jpg"
    _insert_album_state(
        cover_db,
        image_url="https://local.example/original.jpg",
        state_url=provider_url,
    )
    _stub_http(monkeypatch)
    job = Job.create(
        "cover_download",
        "albums",
        "1",
        cdn_url=provider_url,
        source_url_hash=_source_hash(provider_url),
    )

    handle_cover_download(job)

    cover_path = cover_db.parent / "covers" / "albums" / "1.jpg"
    assert cover_path.read_bytes().startswith(b"\xff\xd8\xff")
    conn = sqlite3.connect(cover_db)
    album = conn.execute("SELECT image_path FROM albums WHERE album_id=1").fetchone()
    state = conn.execute(
        """SELECT source_url_hash, cached_source_url_hash, status, last_error
           FROM cover_cache_state WHERE entity_type='albums' AND entity_id=1"""
    ).fetchone()
    conn.close()
    assert album == ("covers/albums/1.jpg",)
    assert state == (_source_hash(provider_url), _source_hash(provider_url), "ready", None)


def test_stale_cover_job_cannot_overwrite_newer_target(cover_db, monkeypatch):
    from backend.jobs.handlers import handle_cover_download

    old_url = "https://cdn.example/old.jpg"
    new_url = "https://cdn.example/new.jpg"
    _insert_album_state(
        cover_db,
        image_url=new_url,
        state_url=new_url,
        image_path="covers/albums/1.jpg",
        status="ready",
    )
    cover_path = cover_db.parent / "covers" / "albums" / "1.jpg"
    cover_path.parent.mkdir(parents=True)
    cover_path.write_bytes(b"new-cover" * 256)
    original_bytes = cover_path.read_bytes()
    _stub_http(monkeypatch, body=b"\xff\xd8\xff" + b"old" * 1024)
    old_job = Job.create(
        "cover_download",
        "albums",
        "1",
        cdn_url=old_url,
        source_url_hash=_source_hash(old_url),
    )

    handle_cover_download(old_job)

    assert cover_path.read_bytes() == original_bytes
    conn = sqlite3.connect(cover_db)
    state = conn.execute(
        """SELECT source_url_hash, cached_source_url_hash, status, last_error
           FROM cover_cache_state WHERE entity_type='albums' AND entity_id=1"""
    ).fetchone()
    conn.close()
    assert state == (_source_hash(new_url), _source_hash(new_url), "ready", None)


def test_cover_file_publication_error_marks_current_source_failed(cover_db, monkeypatch):
    from backend.jobs import handlers

    url = "https://cdn.example/current.jpg"
    _insert_album_state(cover_db, image_url=url)
    _stub_http(monkeypatch)

    def fail_replace(_source, _target):
        raise OSError("disk is full")

    monkeypatch.setattr(handlers.os, "replace", fail_replace)
    job = Job.create(
        "cover_download",
        "albums",
        "1",
        cdn_url=url,
        source_url_hash=_source_hash(url),
    )

    with pytest.raises(OSError, match="disk is full"):
        handlers.handle_cover_download(job)

    conn = sqlite3.connect(cover_db)
    state = conn.execute(
        "SELECT source_url_hash, status, last_error FROM cover_cache_state"
    ).fetchone()
    conn.close()
    assert state[0] == _source_hash(url)
    assert state[1] == "failed"
    assert "disk is full" in state[2]


def test_cover_db_error_after_file_publish_marks_current_source_failed(cover_db, monkeypatch):
    from backend.jobs.handlers import handle_cover_download

    url = "https://cdn.example/current.jpg"
    _insert_album_state(cover_db, image_url=url)
    conn = sqlite3.connect(cover_db)
    conn.executescript(
        """
        CREATE TRIGGER reject_album_image_path
        BEFORE UPDATE OF image_path ON albums
        BEGIN
            SELECT RAISE(ABORT, 'image path blocked');
        END;
        """
    )
    conn.close()
    _stub_http(monkeypatch)
    job = Job.create(
        "cover_download",
        "albums",
        "1",
        cdn_url=url,
        source_url_hash=_source_hash(url),
    )

    with pytest.raises(sqlite3.DatabaseError, match="image path blocked"):
        handle_cover_download(job)

    conn = sqlite3.connect(cover_db)
    album = conn.execute("SELECT image_path FROM albums WHERE album_id=1").fetchone()
    state = conn.execute("SELECT status, last_error FROM cover_cache_state").fetchone()
    conn.close()
    assert album == (None,)
    assert state[0] == "failed"
    assert "image path blocked" in state[1]


def test_stale_cover_download_error_does_not_fail_newer_target(cover_db, monkeypatch):
    from backend.jobs.handlers import handle_cover_download

    old_url = "https://cdn.example/old.jpg"
    new_url = "https://cdn.example/new.jpg"
    _insert_album_state(cover_db, image_url=new_url, state_url=new_url)
    _stub_http(monkeypatch, status=503)
    old_job = Job.create(
        "cover_download",
        "albums",
        "1",
        cdn_url=old_url,
        source_url_hash=_source_hash(old_url),
    )

    with pytest.raises(RuntimeError, match="HTTP 503"):
        handle_cover_download(old_job)

    conn = sqlite3.connect(cover_db)
    state = conn.execute(
        "SELECT source_url_hash, status, last_error FROM cover_cache_state"
    ).fetchone()
    conn.close()
    assert state == (_source_hash(new_url), "pending", None)
