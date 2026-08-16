"""Lightweight in-process background job queue.

Uses threading + queue.Queue for task scheduling and SQLite for
job persistence. Designed for single-user local deployments — no
Celery, Redis, or external broker required.

Job types:
  - cover_download: cache album/artist cover images to disk
  - wikipedia_enrich: fetch Wikipedia data + translate + LLM-structured enrich
  - genius_lyrics: fetch and cache Genius lyrics
"""

from __future__ import annotations

import logging
import queue
import sqlite3
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from os.path import realpath
from typing import Any

logger = logging.getLogger(__name__)


def queue_targets_connection(queue_instance: object, conn: sqlite3.Connection) -> bool:
    """Return whether a persistent queue and connection use the same database."""
    queue_path = getattr(queue_instance, "database_path", None)
    if not queue_path:
        return True
    row = conn.execute("PRAGMA database_list").fetchone()
    connection_path = str(row[2] or "") if row is not None else ""
    return bool(connection_path) and realpath(connection_path) == realpath(str(queue_path))


# ── Data model ───────────────────────────────────────────────────────────


@dataclass
class Job:
    job_id: str
    job_type: str  # cover_download | wikipedia_enrich | genius_lyrics
    entity_type: str  # album | artist | track
    entity_id: str  # unique identifier (e.g. album_name, track_id)
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    attempts: int = 0
    max_attempts: int = 3

    def to_row(self) -> dict[str, Any]:
        import json

        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "payload_json": json.dumps(self.payload, ensure_ascii=False),
            "status": "pending",
            "created_at": self.created_at,
            "attempts": self.attempts,
        }

    @classmethod
    def create(cls, job_type: str, entity_type: str, entity_id: str, **payload):
        return cls(
            job_id=str(uuid.uuid4())[:12],
            job_type=job_type,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
            created_at=datetime.now(timezone.utc).isoformat(),
        )


# ── Job Queue ────────────────────────────────────────────────────────────


class JobQueue:
    """In-process job queue backed by a Python Queue + worker threads."""

    def __init__(self, max_workers: int = 3):
        self._q: queue.Queue[Job] = queue.Queue()
        self._handlers: dict[str, Callable[[Job], None]] = {}
        self._max_workers = max_workers
        self._workers: list[threading.Thread] = []
        self._running = False
        self._lock = threading.Lock()
        self._db_path: str | None = None

    # ── Registration ───────────────────────────────────────────────────

    def register(self, job_type: str, handler: Callable[[Job], None]):
        self._handlers[job_type] = handler

    @property
    def database_path(self) -> str | None:
        """Return the persistence target used by this queue instance."""
        return self._db_path

    # ── Lifecycle ──────────────────────────────────────────────────────

    def start(self, db_path: str):
        """Start worker threads. Call once during app startup."""
        self._db_path = db_path
        self._running = True
        for i in range(self._max_workers):
            t = threading.Thread(
                target=self._worker_loop,
                name=f"job-worker-{i}",
                daemon=True,
            )
            t.start()
            self._workers.append(t)
        logger.info("JobQueue started with %d workers.", self._max_workers)

    def stop(self):
        """Graceful shutdown — workers finish current job then exit."""
        with self._lock:
            workers = list(self._workers)
            self._running = False
            for _ in workers:
                self._q.put(Job.create("_sentinel", "_", "_"))

        for worker in workers:
            if worker is threading.current_thread():
                continue
            worker.join()

        with self._lock:
            self._workers = [worker for worker in self._workers if worker.is_alive()]
            if not self._workers:
                self._drain_queue()

    # ── Enqueue ────────────────────────────────────────────────────────

    def enqueue(self, job: Job) -> str:
        """Submit a job and return its ID. Non-blocking."""
        self._insert_db_job(job)
        self._q.put(job)
        logger.debug("Job %s (%s) enqueued.", job.job_id, job.job_type)
        return job.job_id

    def enqueue_if_not_pending(self, job: Job) -> str | None:
        """Enqueue only if no pending/running job for the same entity+type exists."""
        if self._has_pending_job(job.job_type, job.entity_id):
            return None
        return self.enqueue(job)

    def _has_pending_job(self, job_type: str, entity_id: str) -> bool:
        """Check if a job for this entity+type is already pending or running."""
        if not self._db_path:
            return False
        try:
            conn = sqlite3.connect(self._db_path, timeout=5)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """SELECT 1 FROM background_jobs
                   WHERE job_type=? AND entity_id=? AND status IN ('pending','running')
                   LIMIT 1""",
                (job_type, entity_id),
            ).fetchone()
            conn.close()
            return row is not None
        except sqlite3.OperationalError:
            return False

    # ── Worker ─────────────────────────────────────────────────────────

    def _worker_loop(self):
        while self._running:
            try:
                job = self._q.get(timeout=2)
            except queue.Empty:
                continue
            try:
                if job.job_type == "_sentinel":
                    break
                self._process_job(job)
            finally:
                self._q.task_done()

    def _drain_queue(self):
        """Drop queued sentinel/pending jobs after workers have stopped."""
        while True:
            try:
                self._q.get_nowait()
            except queue.Empty:
                break
            self._q.task_done()

    def _process_job(self, job: Job):
        handler = self._handlers.get(job.job_type)
        if handler is None:
            logger.warning("No handler registered for job type: %s", job.job_type)
            self._update_db_status(job.job_id, "failed", f"No handler for {job.job_type}")
            return
        self._update_db_status(job.job_id, "running")
        try:
            handler(job)
            self._update_db_status(job.job_id, "done")
        except Exception as exc:
            logger.exception("Job %s (%s) failed.", job.job_id, job.job_type)
            self._update_db_status(job.job_id, "failed", str(exc)[:500])

    def _insert_db_job(self, job: Job):
        if not self._db_path:
            return
        try:
            conn = sqlite3.connect(self._db_path, timeout=5)
            row = job.to_row()
            conn.execute(
                """INSERT OR IGNORE INTO background_jobs
                   (job_id, job_type, entity_type, entity_id, payload_json,
                    status, created_at, attempts)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row["job_id"],
                    row["job_type"],
                    row["entity_type"],
                    row["entity_id"],
                    row["payload_json"],
                    row["status"],
                    row["created_at"],
                    row["attempts"],
                ),
            )
            conn.commit()
            conn.close()
        except sqlite3.OperationalError:
            logger.debug("background_jobs table unavailable; job will run in-memory only.")

    def _update_db_status(self, job_id: str, status: str, error: str | None = None):
        if not self._db_path:
            return
        try:
            conn = sqlite3.connect(self._db_path, timeout=5)
            conn.execute(
                "UPDATE background_jobs SET status=?, updated_at=?, error=? WHERE job_id=?",
                (status, datetime.now(timezone.utc).isoformat(), error, job_id),
            )
            conn.commit()
            conn.close()
        except sqlite3.OperationalError:
            pass


# ── Singleton ────────────────────────────────────────────────────────────

_queue: JobQueue | None = None
_lock = threading.Lock()


def get_job_queue() -> JobQueue:
    global _queue
    with _lock:
        if _queue is None:
            _queue = JobQueue(max_workers=3)
        return _queue
