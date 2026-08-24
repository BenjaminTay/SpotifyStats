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

import json
import logging
import queue
import sqlite3
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import datetime, timezone
from os.path import realpath
from typing import Any

logger = logging.getLogger(__name__)

_NEXT_ATTEMPT_PAYLOAD_KEY = "__job_queue_next_attempt_at"


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
    next_attempt_at: str = ""

    def to_row(self) -> dict[str, Any]:
        import json

        persisted_payload = dict(self.payload)
        if self.next_attempt_at:
            persisted_payload[_NEXT_ATTEMPT_PAYLOAD_KEY] = self.next_attempt_at

        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "payload_json": json.dumps(persisted_payload, ensure_ascii=False),
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

    def __init__(
        self,
        max_workers: int = 3,
        *,
        retry_base_seconds: float = 2.0,
        retry_max_seconds: float = 30.0,
    ):
        self._q: queue.Queue[Job] = queue.Queue()
        self._handlers: dict[str, Callable[[Job], None]] = {}
        self._max_workers = max_workers
        self._workers: list[threading.Thread] = []
        self._running = False
        self._prepared = False
        self._startup_jobs: list[Job] = []
        self._lock = threading.Lock()
        self._db_path: str | None = None
        self._retry_base_seconds = max(0.0, retry_base_seconds)
        self._retry_max_seconds = max(self._retry_base_seconds, retry_max_seconds)
        self._retry_timers: dict[str, threading.Timer] = {}
        self._cpu_heavy_gate = threading.Semaphore(1)

    # ── Registration ───────────────────────────────────────────────────

    def register(self, job_type: str, handler: Callable[[Job], None]):
        self._handlers[job_type] = handler

    @property
    def database_path(self) -> str | None:
        """Return the persistence target used by this queue instance."""
        return self._db_path

    # ── Lifecycle ──────────────────────────────────────────────────────

    def prepare(self, db_path: str) -> None:
        """Recover persisted work without allowing any handler to run yet.

        Lifespan startup uses this phase to inspect durable application state and
        enqueue higher-priority recovery work before old generic jobs can be
        observed by a worker.
        """
        with self._lock:
            if self._running:
                return
            if self._prepared:
                if self._db_path != db_path:
                    raise RuntimeError("JobQueue is already prepared for another database")
                return
            self._db_path = db_path
            self._startup_jobs = self._recover_persisted_jobs()
            self._prepared = True

    def start(
        self,
        db_path: str,
        *,
        priority_job_types: tuple[str, ...] = (),
    ) -> None:
        """Run startup-priority work, then start the normal worker pool.

        Priority jobs are completed (including bounded retries) before any
        generic worker exists.  This is stronger than queue ordering alone:
        with multiple workers, a FIFO queue could otherwise start an old search
        or cover job concurrently with import maintenance.
        """
        self.prepare(db_path)
        with self._lock:
            if self._running:
                return
            startup_jobs = self._startup_jobs
            self._startup_jobs = []
            self._prepared = False
            self._running = True

        priority_types = set(priority_job_types)
        priority_jobs = deque(job for job in startup_jobs if job.job_type in priority_types)
        regular_jobs = [job for job in startup_jobs if job.job_type not in priority_types]
        failed_priority_jobs: list[Job] = []
        while priority_jobs:
            job = priority_jobs.popleft()
            if not self._process_job(job, retry=priority_jobs.append):
                failed_priority_jobs.append(job)

        if failed_priority_jobs:
            with self._lock:
                self._running = False
                self._startup_jobs = regular_jobs
                self._prepared = True
            failed_ids = ", ".join(job.job_id for job in failed_priority_jobs)
            raise RuntimeError(f"Startup-priority jobs failed: {failed_ids}")

        with self._lock:
            for i in range(self._max_workers):
                t = threading.Thread(
                    target=self._worker_loop,
                    name=f"job-worker-{i}",
                    daemon=True,
                )
                t.start()
                self._workers.append(t)
        for job in regular_jobs:
            self._enqueue_ready_or_delayed(job)
        logger.info("JobQueue started with %d workers.", self._max_workers)

    def _recover_persisted_jobs(self) -> list[Job]:
        """Recover pending work and reset jobs orphaned by an interrupted process."""
        if not self._db_path:
            return []

        conn: sqlite3.Connection | None = None
        recovered: list[Job] = []
        now = datetime.now(timezone.utc).isoformat()
        try:
            conn = sqlite3.connect(self._db_path, timeout=5)
            conn.row_factory = sqlite3.Row
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """UPDATE background_jobs
                   SET status='pending', updated_at=?, error=NULL
                   WHERE status='running'""",
                (now,),
            )
            rows = conn.execute(
                """SELECT job_id, job_type, entity_type, entity_id,
                          payload_json, created_at, attempts
                   FROM background_jobs
                   WHERE status='pending'
                   ORDER BY created_at, job_id"""
            ).fetchall()
            for row in rows:
                try:
                    payload = json.loads(row["payload_json"] or "{}")
                    if not isinstance(payload, dict):
                        raise ValueError("payload_json must contain an object")
                    next_attempt_at = str(payload.pop(_NEXT_ATTEMPT_PAYLOAD_KEY, "") or "")
                    recovered.append(
                        Job(
                            job_id=str(row["job_id"]),
                            job_type=str(row["job_type"]),
                            entity_type=str(row["entity_type"] or ""),
                            entity_id=str(row["entity_id"] or ""),
                            payload=payload,
                            created_at=str(row["created_at"] or ""),
                            attempts=int(row["attempts"] or 0),
                            next_attempt_at=next_attempt_at,
                        )
                    )
                except (TypeError, ValueError, json.JSONDecodeError) as exc:
                    conn.execute(
                        """UPDATE background_jobs
                           SET status='failed', updated_at=?, error=?
                           WHERE job_id=?""",
                        (now, f"Invalid persisted job payload: {exc}"[:500], row["job_id"]),
                    )
            conn.commit()
        except sqlite3.OperationalError:
            if conn is not None:
                conn.rollback()
            logger.debug("background_jobs table unavailable; no persisted jobs recovered.")
            return []
        finally:
            if conn is not None:
                conn.close()

        if recovered:
            logger.info("Recovered %d persisted background jobs.", len(recovered))
        return recovered

    def stop(self):
        """Graceful shutdown — workers finish current job then exit."""
        with self._lock:
            workers = list(self._workers)
            self._running = False
            retry_timers = list(self._retry_timers.values())
            self._retry_timers.clear()
            for timer in retry_timers:
                timer.cancel()
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

    def wait_until_idle(self) -> None:
        """Wait until every currently queued job has completed."""
        self._q.join()

    # ── Enqueue ────────────────────────────────────────────────────────

    def enqueue(self, job: Job) -> str:
        """Submit a job and return its ID. Non-blocking."""
        self._insert_db_job(job)
        with self._lock:
            if self._prepared and not self._running:
                self._startup_jobs.append(job)
            else:
                self._q.put(job)
        logger.debug("Job %s (%s) enqueued.", job.job_id, job.job_type)
        return job.job_id

    def enqueue_if_not_pending(self, job: Job) -> str | None:
        """Enqueue only if no pending/running job for the same entity+type exists."""
        if self._has_pending_job(job.job_type, job.entity_type, job.entity_id):
            return None
        return self.enqueue(job)

    def _has_pending_job(self, job_type: str, entity_type: str, entity_id: str) -> bool:
        """Check if a job for this entity+type is already pending or running."""
        if not self._db_path:
            return False
        try:
            conn = sqlite3.connect(self._db_path, timeout=5)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """SELECT 1 FROM background_jobs
                   WHERE job_type=? AND entity_type=? AND entity_id=?
                     AND status IN ('pending','running')
                   LIMIT 1""",
                (job_type, entity_type, entity_id),
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

    @staticmethod
    def _seconds_until(iso_timestamp: str) -> float:
        if not iso_timestamp:
            return 0.0
        try:
            target = datetime.fromisoformat(iso_timestamp)
            if target.tzinfo is None:
                target = target.replace(tzinfo=timezone.utc)
            return max(0.0, target.timestamp() - time.time())
        except ValueError:
            return 0.0

    def _enqueue_ready_or_delayed(self, job: Job) -> None:
        delay = self._seconds_until(job.next_attempt_at)
        if delay <= 0:
            self._q.put(job)
            return
        self._schedule_delayed(job, delay)

    def _schedule_delayed(self, job: Job, delay: float) -> None:
        """Wake a pending retry later without occupying a worker thread."""

        def release() -> None:
            with self._lock:
                self._retry_timers.pop(job.job_id, None)
                running = self._running
            if running:
                self._q.put(job)

        timer = threading.Timer(max(0.0, delay), release)
        timer.name = f"job-retry-{job.job_id}"
        timer.daemon = True
        with self._lock:
            if not self._running:
                return
            previous = self._retry_timers.pop(job.job_id, None)
            if previous is not None:
                previous.cancel()
            self._retry_timers[job.job_id] = timer
        timer.start()

    def _retry_delay(self, attempts: int) -> float:
        exponent = max(0, attempts - 1)
        return min(self._retry_max_seconds, self._retry_base_seconds * (2**exponent))

    def _process_job(
        self,
        job: Job,
        *,
        retry: Callable[[Job], None] | None = None,
    ) -> bool:
        handler = self._handlers.get(job.job_type)
        if handler is None:
            logger.warning("No handler registered for job type: %s", job.job_type)
            self._update_db_status(job.job_id, "failed", f"No handler for {job.job_type}")
            return False
        job.attempts += 1
        self._update_db_status(job.job_id, "running", attempts=job.attempts)
        try:
            cpu_heavy = job.job_type in {
                "artist_identity_rebuild",
                "track_credit_rebuild",
                "playback_import_maintenance",
                "music_search_snapshot_rebuild",
            }
            with self._cpu_heavy_gate if cpu_heavy else nullcontext():
                handler(job)
            self._update_db_status(job.job_id, "done")
            return True
        except Exception as exc:
            logger.exception("Job %s (%s) failed.", job.job_id, job.job_type)
            if job.attempts < job.max_attempts and self._running:
                if retry is not None:
                    # Startup-priority work remains a strict barrier and keeps
                    # its existing immediate, bounded retry behavior.
                    job.next_attempt_at = ""
                    self._persist_pending_retry(job, str(exc)[:500])
                    retry(job)
                else:
                    delay = self._retry_delay(job.attempts)
                    job.next_attempt_at = datetime.fromtimestamp(
                        time.time() + delay,
                        tz=timezone.utc,
                    ).isoformat()
                    self._persist_pending_retry(job, str(exc)[:500])
                    self._schedule_delayed(job, delay)
                return True
            else:
                self._update_db_status(
                    job.job_id,
                    "failed",
                    str(exc)[:500],
                    attempts=job.attempts,
                )
                return False

    def _persist_pending_retry(self, job: Job, error: str) -> None:
        if not self._db_path:
            return
        try:
            conn = sqlite3.connect(self._db_path, timeout=5)
            row = job.to_row()
            conn.execute(
                """UPDATE background_jobs
                   SET status='pending', updated_at=?, error=?, attempts=?, payload_json=?
                   WHERE job_id=?""",
                (
                    datetime.now(timezone.utc).isoformat(),
                    error,
                    job.attempts,
                    row["payload_json"],
                    job.job_id,
                ),
            )
            conn.commit()
            conn.close()
        except sqlite3.OperationalError:
            pass

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

    def _update_db_status(
        self,
        job_id: str,
        status: str,
        error: str | None = None,
        *,
        attempts: int | None = None,
    ):
        if not self._db_path:
            return
        try:
            conn = sqlite3.connect(self._db_path, timeout=5)
            if attempts is None:
                conn.execute(
                    "UPDATE background_jobs SET status=?, updated_at=?, error=? WHERE job_id=?",
                    (status, datetime.now(timezone.utc).isoformat(), error, job_id),
                )
            else:
                conn.execute(
                    """UPDATE background_jobs
                       SET status=?, updated_at=?, error=?, attempts=? WHERE job_id=?""",
                    (status, datetime.now(timezone.utc).isoformat(), error, attempts, job_id),
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
