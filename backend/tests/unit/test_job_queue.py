"""Unit tests for lightweight background job queue."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import threading
import time

import pytest

from backend.core.job_queue import Job, JobQueue

pytestmark = pytest.mark.unit


@pytest.fixture
def temp_db():
    """Create a temporary SQLite DB with background_jobs table."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS background_jobs (
            job_id TEXT PRIMARY KEY, job_type TEXT NOT NULL,
            entity_type TEXT, entity_id TEXT, payload_json TEXT,
            status TEXT NOT NULL DEFAULT 'pending', created_at TEXT,
            updated_at TEXT, attempts INTEGER DEFAULT 0, error TEXT
        )"""
    )
    conn.commit()
    conn.close()
    yield path
    os.unlink(path)


def test_job_create():
    job = Job.create("cover_download", "albums", "42", cdn_url="https://example.com/img.jpg")
    assert job.job_type == "cover_download"
    assert job.entity_type == "albums"
    assert job.entity_id == "42"
    assert job.payload["cdn_url"] == "https://example.com/img.jpg"
    assert len(job.job_id) == 12


def test_queue_enqueue_and_process(temp_db):
    processed = []

    def handler(job):
        processed.append(job.job_id)

    q = JobQueue(max_workers=1)
    q.register("test_type", handler)
    q.start(temp_db)

    job = Job.create("test_type", "entity", "123")
    q.enqueue(job)

    # Wait briefly for processing
    time.sleep(0.3)
    q.stop()

    assert job.job_id in processed
    conn = sqlite3.connect(temp_db)
    row = conn.execute(
        "SELECT status FROM background_jobs WHERE job_id = ?", (job.job_id,)
    ).fetchone()
    conn.close()
    assert row == ("done",)


def test_queue_stop_gracefully(temp_db):
    q = JobQueue(max_workers=2)
    q.register("test", lambda j: time.sleep(0.1))
    q.start(temp_db)
    q.stop()
    # No exception means clean shutdown
    assert True


def test_queue_stop_waits_for_running_job(temp_db):
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    def handler(job):
        started.set()
        release.wait(timeout=1)
        finished.set()

    q = JobQueue(max_workers=1)
    q.register("test", handler)
    q.start(temp_db)
    q.enqueue(Job.create("test", "entity", "running"))

    assert started.wait(timeout=1)
    timer = threading.Timer(0.05, release.set)
    timer.start()
    try:
        q.stop()
        assert finished.is_set()
    finally:
        timer.cancel()
        release.set()


def test_queue_can_restart_after_stopping_running_job(temp_db):
    started = threading.Event()
    release = threading.Event()
    processed = []

    def blocking_handler(job):
        started.set()
        release.wait(timeout=1)
        processed.append(job.entity_id)

    q = JobQueue(max_workers=1)
    q.register("blocking", blocking_handler)
    q.start(temp_db)
    q.enqueue(Job.create("blocking", "entity", "before-stop"))

    assert started.wait(timeout=1)
    timer = threading.Timer(0.05, release.set)
    timer.start()
    try:
        q.stop()
    finally:
        timer.cancel()
        release.set()

    q.register("after_restart", lambda job: processed.append(job.entity_id))
    q.start(temp_db)
    q.enqueue(Job.create("after_restart", "entity", "after-restart"))
    time.sleep(0.3)
    q.stop()

    assert processed == ["before-stop", "after-restart"]


def test_enqueue_if_not_pending_uses_db_state(temp_db):
    q = JobQueue(max_workers=1)
    q._db_path = temp_db
    first = Job.create("test_type", "entity", "same")
    second = Job.create("test_type", "entity", "same")

    assert q.enqueue_if_not_pending(first) == first.job_id
    assert q.enqueue_if_not_pending(second) is None


def test_revision_specific_entity_ids_do_not_drop_later_revision(temp_db):
    q = JobQueue(max_workers=1)
    q._db_path = temp_db
    revision_34 = Job.create(
        "track_credit_rebuild", "track_credit", "global:revision:34", revision=34
    )
    revision_35 = Job.create(
        "track_credit_rebuild", "track_credit", "global:revision:35", revision=35
    )

    assert q.enqueue_if_not_pending(revision_34) == revision_34.job_id
    assert q.enqueue_if_not_pending(revision_35) == revision_35.job_id

    with sqlite3.connect(temp_db) as conn:
        rows = conn.execute(
            """SELECT entity_id, status FROM background_jobs
               WHERE job_type='track_credit_rebuild' ORDER BY entity_id"""
        ).fetchall()
    assert rows == [
        ("global:revision:34", "pending"),
        ("global:revision:35", "pending"),
    ]


def test_pending_dedupe_keeps_album_and_artist_ids_separate(temp_db):
    q = JobQueue(max_workers=1)
    q._db_path = temp_db

    album = Job.create("cover_download", "albums", "42")
    artist = Job.create("cover_download", "artists", "42")

    assert q.enqueue_if_not_pending(album) == album.job_id
    assert q.enqueue_if_not_pending(artist) == artist.job_id


def test_failed_job_retries_and_records_attempt_count(temp_db):
    calls = []

    def flaky(job):
        calls.append(job.attempts)
        if len(calls) == 1:
            raise RuntimeError("temporary")

    q = JobQueue(max_workers=1, retry_base_seconds=0.01, retry_max_seconds=0.02)
    q.register("flaky", flaky)
    q.start(temp_db)
    job = Job.create("flaky", "entity", "retry")
    q.enqueue(job)
    time.sleep(0.4)
    q.stop()

    conn = sqlite3.connect(temp_db)
    row = conn.execute(
        "SELECT status, attempts, error FROM background_jobs WHERE job_id=?", (job.job_id,)
    ).fetchone()
    conn.close()
    assert calls == [1, 2]
    assert row == ("done", 2, None)


def test_regular_retry_is_delayed_and_persisted_without_sleep(temp_db, monkeypatch):
    scheduled: list[tuple[str, float]] = []

    def fail(_job):
        raise RuntimeError("rate limited")

    q = JobQueue(max_workers=0, retry_base_seconds=4, retry_max_seconds=10)
    q.register("flaky", fail)
    q._db_path = temp_db
    q._running = True
    monkeypatch.setattr(
        q,
        "_schedule_delayed",
        lambda job, delay: scheduled.append((job.job_id, delay)),
    )
    job = Job.create("flaky", "entity", "delayed")
    q._insert_db_job(job)

    assert q._process_job(job) is True

    conn = sqlite3.connect(temp_db)
    row = conn.execute(
        "SELECT status, attempts, error, payload_json FROM background_jobs WHERE job_id=?",
        (job.job_id,),
    ).fetchone()
    conn.close()
    payload = json.loads(row[3])
    assert scheduled == [(job.job_id, 4)]
    assert row[:3] == ("pending", 1, "rate limited")
    assert payload["__job_queue_next_attempt_at"] == job.next_attempt_at

    recovered = JobQueue(max_workers=0)
    recovered.prepare(temp_db)
    assert len(recovered._startup_jobs) == 1
    assert recovered._startup_jobs[0].next_attempt_at == job.next_attempt_at
    assert "__job_queue_next_attempt_at" not in recovered._startup_jobs[0].payload


def test_retry_delay_is_exponential_and_bounded():
    q = JobQueue(retry_base_seconds=3, retry_max_seconds=10)

    assert [q._retry_delay(attempt) for attempt in range(1, 6)] == [3, 6, 10, 10, 10]


def test_startup_priority_retry_stays_inside_barrier_without_delay(temp_db, monkeypatch):
    calls: list[int] = []
    delayed: list[float] = []

    def flaky(job):
        calls.append(job.attempts)
        if job.attempts == 1:
            raise RuntimeError("temporary")

    q = JobQueue(max_workers=0, retry_base_seconds=60, retry_max_seconds=60)
    q.register("maintenance", flaky)
    q.prepare(temp_db)
    job = Job.create("maintenance", "entity", "priority")
    q.enqueue(job)
    monkeypatch.setattr(q, "_schedule_delayed", lambda _job, delay: delayed.append(delay))

    q.start(temp_db, priority_job_types=("maintenance",))
    q.stop()

    assert calls == [1, 2]
    assert delayed == []
    conn = sqlite3.connect(temp_db)
    assert conn.execute(
        "SELECT status, attempts FROM background_jobs WHERE job_id=?", (job.job_id,)
    ).fetchone() == ("done", 2)
    conn.close()


def test_start_recovers_pending_and_orphan_running_jobs(temp_db):
    conn = sqlite3.connect(temp_db)
    conn.executemany(
        """INSERT INTO background_jobs(
               job_id, job_type, entity_type, entity_id, payload_json,
               status, created_at, attempts, error
           ) VALUES (?, 'recover', 'entity', ?, '{}', ?, ?, ?, ?)""",
        [
            ("pending-job", "pending", "pending", "2026-01-01T00:00:00+00:00", 0, None),
            (
                "orphan-job",
                "orphan",
                "running",
                "2026-01-02T00:00:00+00:00",
                1,
                "process interrupted",
            ),
        ],
    )
    conn.commit()
    conn.close()
    processed: list[tuple[str, int]] = []
    complete = threading.Event()

    def handler(job):
        processed.append((job.entity_id, job.attempts))
        if len(processed) == 2:
            complete.set()

    q = JobQueue(max_workers=1)
    q.register("recover", handler)
    q.start(temp_db)
    assert complete.wait(timeout=2)
    q.stop()

    conn = sqlite3.connect(temp_db)
    rows = conn.execute(
        """SELECT job_id, status, attempts, error
           FROM background_jobs ORDER BY job_id"""
    ).fetchall()
    conn.close()
    assert processed == [("pending", 1), ("orphan", 2)]
    assert rows == [
        ("orphan-job", "done", 2, None),
        ("pending-job", "done", 1, None),
    ]


def test_startup_priority_job_finishes_before_persisted_generic_workers_start(temp_db):
    conn = sqlite3.connect(temp_db)
    conn.executemany(
        """INSERT INTO background_jobs(
               job_id, job_type, entity_type, entity_id, payload_json,
               status, created_at, attempts
           ) VALUES (?, ?, 'entity', ?, '{}', 'pending', ?, 0)""",
        [
            ("old-cover", "cover_download", "cover", "2026-01-01T00:00:00+00:00"),
            ("old-search", "search_rebuild", "search", "2026-01-02T00:00:00+00:00"),
        ],
    )
    conn.commit()
    conn.close()

    events: list[str] = []
    generic_done = threading.Event()

    def maintenance_handler(_job):
        events.append("maintenance:start")
        time.sleep(0.05)
        events.append("maintenance:done")

    def generic_handler(job):
        events.append(job.entity_id)
        if "cover" in events and "search" in events:
            generic_done.set()

    q = JobQueue(max_workers=3)
    q.register("playback_import_maintenance", maintenance_handler)
    q.register("cover_download", generic_handler)
    q.register("search_rebuild", generic_handler)
    q.prepare(temp_db)
    maintenance_job = Job.create(
        "playback_import_maintenance",
        "playback_import_run",
        "import",
    )
    q.enqueue(maintenance_job)
    q.start(temp_db, priority_job_types=("playback_import_maintenance",))
    assert generic_done.wait(timeout=2)
    q.stop()

    assert events[:2] == ["maintenance:start", "maintenance:done"]
    assert set(events[2:]) == {"cover", "search"}

    conn = sqlite3.connect(temp_db)
    rows = conn.execute("SELECT job_type, status FROM background_jobs ORDER BY job_type").fetchall()
    conn.close()
    assert rows == [
        ("cover_download", "done"),
        ("playback_import_maintenance", "done"),
        ("search_rebuild", "done"),
    ]


def test_start_marks_invalid_persisted_payload_failed(temp_db):
    conn = sqlite3.connect(temp_db)
    conn.execute(
        """INSERT INTO background_jobs(
               job_id, job_type, entity_type, entity_id, payload_json,
               status, created_at, attempts
           ) VALUES ('invalid-job', 'recover', 'entity', '1', '[',
                     'pending', '2026-01-01T00:00:00+00:00', 0)"""
    )
    conn.commit()
    conn.close()

    q = JobQueue(max_workers=0)
    q.start(temp_db)
    q.stop()

    conn = sqlite3.connect(temp_db)
    row = conn.execute(
        "SELECT status, error FROM background_jobs WHERE job_id='invalid-job'"
    ).fetchone()
    conn.close()
    assert row[0] == "failed"
    assert row[1].startswith("Invalid persisted job payload:")


def test_get_job_queue_singleton():
    from backend.core.job_queue import get_job_queue

    q1 = get_job_queue()
    q2 = get_job_queue()
    assert q1 is q2


def test_cpu_heavy_jobs_are_serialized_across_workers(temp_db):
    active = 0
    max_active = 0
    state_lock = threading.Lock()

    def heavy_handler(_job):
        nonlocal active, max_active
        with state_lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.05)
        with state_lock:
            active -= 1

    q = JobQueue(max_workers=2)
    q.register("artist_identity_rebuild", heavy_handler)
    q.register("music_search_snapshot_rebuild", heavy_handler)
    q.start(temp_db)
    q.enqueue(Job.create("artist_identity_rebuild", "artist_identity", "all"))
    q.enqueue(Job.create("music_search_snapshot_rebuild", "music_search", "all"))
    q.wait_until_idle()
    q.stop()

    assert max_active == 1
