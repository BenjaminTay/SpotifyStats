"""Unit tests for lightweight background job queue."""

from __future__ import annotations

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


def test_get_job_queue_singleton():
    from backend.core.job_queue import get_job_queue

    q1 = get_job_queue()
    q2 = get_job_queue()
    assert q1 is q2
