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

from backend.core.db import connect_sqlite_path

logger = logging.getLogger(__name__)

_NEXT_ATTEMPT_PAYLOAD_KEY = "__job_queue_next_attempt_at"
_PRIORITY_PAYLOAD_KEY = "__job_queue_priority"
_RESOURCE_CLASS_PAYLOAD_KEY = "__job_queue_resource_class"
_TARGET_KEY_PAYLOAD_KEY = "__job_queue_target_key"

_RESOURCE_CRITICAL = "critical"
_RESOURCE_DEFAULT = "default"
_RESOURCE_NETWORK = "network"
_RESOURCE_CLASSES = {_RESOURCE_CRITICAL, _RESOURCE_DEFAULT, _RESOURCE_NETWORK}

_NETWORK_JOB_TYPES = {"cover_download", "wikipedia_enrich", "genius_lyrics"}
_CRITICAL_JOB_TYPES = {
    "playback_import_maintenance",
    "artist_identity_rebuild",
    "track_credit_rebuild",
    "music_search_snapshot_rebuild",
    "billboard_snapshot_rebuild",
    "analysis_snapshot_rebuild",
    "community_snapshot_rebuild",
    "account_archive_snapshot_rebuild",
    "governance_snapshot_rebuild",
    "entity_rank_context_rebuild",
}

# Capture the primitives before application tests monkeypatch the shared
# ``threading.Thread`` symbol. ``threading.Timer`` resolves that global at
# construction time, which made delayed retries fail in unrelated importer tests.
_THREAD_CLASS = threading.Thread
_EVENT_CLASS = threading.Event


class _DelayedCall:
    """Minimal cancellable timer built from the captured thread primitive."""

    def __init__(self, delay: float, callback: Callable[[], None], *, name: str):
        self._delay = max(0.0, delay)
        self._callback = callback
        self._cancelled = _EVENT_CLASS()
        self._thread = _THREAD_CLASS(target=self._run, name=name, daemon=True)

    def _run(self) -> None:
        if not self._cancelled.wait(self._delay):
            self._callback()

    def start(self) -> None:
        self._thread.start()

    def cancel(self) -> None:
        self._cancelled.set()


def _default_resource_class(job_type: str) -> str:
    if job_type in _CRITICAL_JOB_TYPES:
        return _RESOURCE_CRITICAL
    if job_type in _NETWORK_JOB_TYPES:
        return _RESOURCE_NETWORK
    return _RESOURCE_DEFAULT


def _default_priority(resource_class: str) -> int:
    return {
        _RESOURCE_CRITICAL: 10,
        _RESOURCE_DEFAULT: 50,
        _RESOURCE_NETWORK: 100,
    }[resource_class]


def _target_key(
    entity_id: str,
    payload: dict[str, Any],
    target_revision: object | None = None,
) -> str:
    revision = target_revision
    if revision is None:
        revision = payload.get("target_revision", payload.get("revision"))
    if revision is None or ":revision:" in entity_id:
        return entity_id
    return f"{entity_id}:revision:{revision}"


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
    priority: int = 50
    resource_class: str = _RESOURCE_DEFAULT
    target_key: str = ""

    def __post_init__(self) -> None:
        if self.resource_class not in _RESOURCE_CLASSES:
            self.resource_class = _default_resource_class(self.job_type)
        try:
            self.priority = int(self.priority)
        except (TypeError, ValueError):
            self.priority = _default_priority(self.resource_class)
        if not self.target_key:
            self.target_key = _target_key(self.entity_id, self.payload)

    def to_row(self) -> dict[str, Any]:
        import json

        persisted_payload = dict(self.payload)
        persisted_payload[_PRIORITY_PAYLOAD_KEY] = self.priority
        persisted_payload[_RESOURCE_CLASS_PAYLOAD_KEY] = self.resource_class
        persisted_payload[_TARGET_KEY_PAYLOAD_KEY] = self.target_key
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
    def create(
        cls,
        job_type: str,
        entity_type: str,
        entity_id: str,
        *,
        priority: int | None = None,
        resource_class: str | None = None,
        target_key: str | None = None,
        target_revision: object | None = None,
        **payload: Any,
    ) -> Job:
        resolved_resource = resource_class or _default_resource_class(job_type)
        if resolved_resource not in _RESOURCE_CLASSES:
            raise ValueError(f"Unsupported job resource class: {resolved_resource}")
        if target_revision is not None:
            payload.setdefault("target_revision", target_revision)
        return cls(
            job_id=str(uuid.uuid4())[:12],
            job_type=job_type,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
            created_at=datetime.now(timezone.utc).isoformat(),
            priority=(_default_priority(resolved_resource) if priority is None else int(priority)),
            resource_class=resolved_resource,
            target_key=target_key or _target_key(entity_id, payload, target_revision),
        )


# ── Job Queue ────────────────────────────────────────────────────────────


class JobQueue:
    """In-process priority queue with isolated critical and network lanes."""

    def __init__(
        self,
        max_workers: int = 3,
        *,
        retry_base_seconds: float = 2.0,
        retry_max_seconds: float = 30.0,
    ):
        self._queues: dict[str, queue.PriorityQueue[tuple[int, str, str, Job]]] = {
            lane: queue.PriorityQueue() for lane in _RESOURCE_CLASSES
        }
        # Compatibility for callers that only observed the old default queue.
        self._q = self._queues[_RESOURCE_DEFAULT]
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
        self._retry_timers: dict[str, _DelayedCall] = {}
        self._cpu_heavy_gate = threading.Semaphore(1)
        self._wake_workers = _EVENT_CLASS()
        self._active_targets: set[tuple[str, str, str]] = set()

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
            self._active_targets.update(self._job_identity(job) for job in self._startup_jobs)
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
            startup_jobs = sorted(self._startup_jobs, key=self._sort_key)
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
            for i, lanes in enumerate(self._worker_assignments()):
                t = _THREAD_CLASS(
                    target=self._worker_loop,
                    args=(lanes,),
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
            conn = connect_sqlite_path(self._db_path, timeout=5)
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
                    resource_class = str(
                        payload.pop(
                            _RESOURCE_CLASS_PAYLOAD_KEY,
                            _default_resource_class(str(row["job_type"])),
                        )
                    )
                    if resource_class not in _RESOURCE_CLASSES:
                        resource_class = _default_resource_class(str(row["job_type"]))
                    raw_priority = payload.pop(
                        _PRIORITY_PAYLOAD_KEY,
                        _default_priority(resource_class),
                    )
                    try:
                        priority = int(raw_priority)
                    except (TypeError, ValueError):
                        priority = _default_priority(resource_class)
                    target_key = str(payload.pop(_TARGET_KEY_PAYLOAD_KEY, "") or "")
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
                            priority=priority,
                            resource_class=resource_class,
                            target_key=target_key,
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

        recovered.sort(key=self._sort_key)
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
            self._wake_workers.set()

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
        while any(work_queue.unfinished_tasks for work_queue in self._queues.values()):
            time.sleep(0.01)

    @staticmethod
    def _sort_key(job: Job) -> tuple[int, str, str]:
        return (job.priority, job.created_at, job.job_id)

    @staticmethod
    def _job_identity(job: Job) -> tuple[str, str, str]:
        return (job.job_type, job.entity_type, job.target_key)

    def _worker_assignments(self) -> list[tuple[str, ...]]:
        if self._max_workers <= 0:
            return []
        if self._max_workers == 1:
            return [(_RESOURCE_CRITICAL, _RESOURCE_DEFAULT, _RESOURCE_NETWORK)]
        if self._max_workers == 2:
            return [
                (_RESOURCE_CRITICAL,),
                (_RESOURCE_DEFAULT, _RESOURCE_NETWORK),
            ]
        return [
            (_RESOURCE_CRITICAL,),
            (_RESOURCE_NETWORK,),
            *[(_RESOURCE_DEFAULT,) for _ in range(self._max_workers - 2)],
        ]

    def _put_job(self, job: Job) -> None:
        lane = job.resource_class
        if lane not in self._queues:
            lane = _RESOURCE_DEFAULT
        self._queues[lane].put((*self._sort_key(job), job))
        self._wake_workers.set()

    # ── Enqueue ────────────────────────────────────────────────────────

    def enqueue(self, job: Job) -> str:
        """Submit a job and return its ID. Non-blocking."""
        self._insert_db_job(job)
        with self._lock:
            self._active_targets.add(self._job_identity(job))
            if self._prepared and not self._running:
                self._startup_jobs.append(job)
            else:
                self._put_job(job)
        logger.debug("Job %s (%s) enqueued.", job.job_id, job.job_type)
        return job.job_id

    def enqueue_if_not_pending(self, job: Job) -> str | None:
        """Atomically enqueue one pending/running job for an exact target."""
        identity = self._job_identity(job)
        with self._lock:
            if identity in self._active_targets:
                return None
            if not self._insert_db_job_if_target_available(job):
                return None
            self._active_targets.add(identity)
            if self._prepared and not self._running:
                self._startup_jobs.append(job)
            else:
                self._put_job(job)
        logger.debug("Job %s (%s) enqueued.", job.job_id, job.job_type)
        return job.job_id

    def _has_pending_job(self, job_type: str, entity_type: str, entity_id: str) -> bool:
        """Check if a job for this entity+type is already pending or running."""
        if not self._db_path:
            return False
        try:
            conn = connect_sqlite_path(self._db_path, timeout=5)
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

    @staticmethod
    def _persisted_target_key(entity_id: str, payload_json: str | None) -> str:
        try:
            payload = json.loads(payload_json or "{}")
        except (TypeError, json.JSONDecodeError):
            return entity_id
        if not isinstance(payload, dict):
            return entity_id
        return str(payload.get(_TARGET_KEY_PAYLOAD_KEY) or _target_key(entity_id, payload))

    def _insert_db_job_if_target_available(self, job: Job) -> bool:
        """Claim a target and insert its job in one SQLite write transaction."""
        if not self._db_path:
            return True
        conn: sqlite3.Connection | None = None
        try:
            conn = connect_sqlite_path(self._db_path, timeout=5)
            conn.row_factory = sqlite3.Row
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                """SELECT entity_id, payload_json FROM background_jobs
                   WHERE job_type=? AND entity_type=?
                     AND status IN ('pending','running')""",
                (job.job_type, job.entity_type),
            ).fetchall()
            if any(
                self._persisted_target_key(str(row["entity_id"] or ""), row["payload_json"])
                == job.target_key
                for row in rows
            ):
                conn.rollback()
                return False
            row = job.to_row()
            cursor = conn.execute(
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
            return cursor.rowcount == 1
        except sqlite3.OperationalError:
            if conn is not None:
                conn.rollback()
            logger.debug("background_jobs table unavailable; job will run in-memory only.")
            return True
        finally:
            if conn is not None:
                conn.close()

    # ── Worker ─────────────────────────────────────────────────────────

    def _worker_loop(self, lanes: tuple[str, ...]):
        lane_offset = 0
        while self._running:
            selected_queue: queue.PriorityQueue[tuple[int, str, str, Job]] | None = None
            item: tuple[int, str, str, Job] | None = None
            for index in range(len(lanes)):
                lane = lanes[(lane_offset + index) % len(lanes)]
                work_queue = self._queues[lane]
                try:
                    item = work_queue.get_nowait()
                    selected_queue = work_queue
                    lane_offset = (lane_offset + index + 1) % len(lanes)
                    break
                except queue.Empty:
                    continue
            if item is None or selected_queue is None:
                self._wake_workers.clear()
                self._wake_workers.wait(0.05)
                continue
            job = item[3]
            try:
                self._process_job(job)
            finally:
                selected_queue.task_done()

    def _drain_queue(self):
        """Drop queued jobs after workers have stopped."""
        for work_queue in self._queues.values():
            while True:
                try:
                    work_queue.get_nowait()
                except queue.Empty:
                    break
                work_queue.task_done()

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
            self._put_job(job)
            return
        self._schedule_delayed(job, delay)

    def _schedule_delayed(self, job: Job, delay: float) -> None:
        """Wake a pending retry later without occupying a worker thread."""

        def release() -> None:
            with self._lock:
                self._retry_timers.pop(job.job_id, None)
                running = self._running
            if running:
                self._put_job(job)

        timer = _DelayedCall(
            max(0.0, delay),
            release,
            name=f"job-retry-{job.job_id}",
        )
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

    def _release_target(self, job: Job) -> None:
        with self._lock:
            self._active_targets.discard(self._job_identity(job))

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
            self._release_target(job)
            return False
        job.attempts += 1
        self._update_db_status(job.job_id, "running", attempts=job.attempts)
        try:
            cpu_heavy = job.job_type in {
                "artist_identity_rebuild",
                "track_credit_rebuild",
                "playback_import_maintenance",
                "music_search_snapshot_rebuild",
                "billboard_snapshot_rebuild",
                "analysis_snapshot_rebuild",
                "community_snapshot_rebuild",
                "account_archive_snapshot_rebuild",
                "governance_snapshot_rebuild",
            }
            with self._cpu_heavy_gate if cpu_heavy else nullcontext():
                handler(job)
            self._update_db_status(job.job_id, "done")
            if job.job_type in {
                "playback_import_maintenance",
                "artist_identity_rebuild",
                "track_credit_rebuild",
            }:
                from backend.services.analysis_snapshot_service import enqueue_defaults

                try:
                    enqueue_defaults(job.job_type, queue=self)
                except Exception:
                    logger.exception(
                        "Analysis maintenance scheduling failed after %s", job.job_type
                    )
            if job.job_type in {
                "playback_import_maintenance",
                "artist_identity_rebuild",
                "track_credit_rebuild",
                "billboard_snapshot_rebuild",
            }:
                from backend.services.community_snapshot_service import (
                    enqueue_defaults as enqueue_community,
                )

                try:
                    enqueue_community(job.job_type, queue=self)
                except Exception:
                    logger.exception(
                        "Community maintenance scheduling failed after %s", job.job_type
                    )
            if job.job_type in {
                "playback_import_maintenance",
                "artist_identity_rebuild",
                "track_credit_rebuild",
            }:
                from backend.services.account_archive_snapshot_service import (
                    enqueue_defaults as enqueue_archive,
                )

                try:
                    enqueue_archive(job.job_type, queue=self)
                except Exception:
                    logger.exception("Archive maintenance scheduling failed after %s", job.job_type)
            if job.job_type in {
                "playback_import_maintenance",
                "artist_identity_rebuild",
                "track_credit_rebuild",
                "billboard_snapshot_rebuild",
            }:
                from backend.services.governance_snapshot_service import (
                    enqueue_defaults as enqueue_governance,
                )

                try:
                    enqueue_governance(job.job_type, queue=self)
                except Exception:
                    logger.exception("Governance scheduling failed after %s", job.job_type)
            self._release_target(job)
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
                self._release_target(job)
                return False

    def _persist_pending_retry(self, job: Job, error: str) -> None:
        if not self._db_path:
            return
        try:
            conn = connect_sqlite_path(self._db_path, timeout=5)
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
            conn = connect_sqlite_path(self._db_path, timeout=5)
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
            conn = connect_sqlite_path(self._db_path, timeout=5)
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
