"""Recover post-import maintenance from durable, generation-bound evidence."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from backend.core.db import get_db
from backend.core.job_queue import Job, JobQueue, get_job_queue
from backend.domains.imports.change_set import PlaybackChangeSet
from backend.domains.imports.state import (
    compare_and_set_playback_import_run_status,
    summarise_current_playback_dataset,
)
from backend.domains.metadata.import_health import build_import_health_report
from backend.services.import_maintenance_service import run_post_streaming_import_maintenance

PLAYBACK_IMPORT_MAINTENANCE_JOB_TYPE = "playback_import_maintenance"
PLAYBACK_IMPORT_MAINTENANCE_ENTITY_TYPE = "playback_import_run"


class ImportMaintenanceRecoveryEvidenceError(RuntimeError):
    """Fail-closed recovery evidence error with a non-sensitive stable code."""

    def __init__(self, error_code: str):
        super().__init__(error_code)
        self.error_code = error_code


class ImportMaintenanceAlreadyTerminalError(RuntimeError):
    """The persisted retry raced with an already completed or blocked run."""


@dataclass(frozen=True)
class PendingImportMaintenance:
    run_id: str
    change_set: PlaybackChangeSet


def _load_and_fence_pending_run(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    expected_generation_id: str | None = None,
) -> PendingImportMaintenance:
    row = conn.execute(
        """SELECT status, change_set_json
           FROM playback_import_runs WHERE run_id=?""",
        (run_id,),
    ).fetchone()
    if row is None:
        raise ImportMaintenanceRecoveryEvidenceError("recovery_run_missing")
    status = str(row["status"])
    if status in {"success", "recovery_blocked"}:
        raise ImportMaintenanceAlreadyTerminalError(status)
    if status != "maintenance_pending":
        raise ImportMaintenanceRecoveryEvidenceError("recovery_run_not_pending")
    encoded = row["change_set_json"]
    if not isinstance(encoded, str) or not encoded:
        raise ImportMaintenanceRecoveryEvidenceError("recovery_change_set_missing")
    try:
        payload = json.loads(encoded)
        change_set = PlaybackChangeSet.from_dict(payload)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ImportMaintenanceRecoveryEvidenceError("recovery_change_set_invalid") from exc
    if expected_generation_id is not None and change_set.generation_id != expected_generation_id:
        raise ImportMaintenanceRecoveryEvidenceError("recovery_job_generation_drift")

    state = conn.execute(
        """SELECT active_generation_id, fingerprint_version,
                  dataset_digest, record_count
           FROM playback_import_state WHERE state_id=1"""
    ).fetchone()
    if state is None or not state["active_generation_id"]:
        raise ImportMaintenanceRecoveryEvidenceError("recovery_active_state_missing")
    if str(state["active_generation_id"]) != change_set.generation_id:
        raise ImportMaintenanceRecoveryEvidenceError("recovery_active_generation_drift")
    try:
        summary = summarise_current_playback_dataset(conn)
    except (TypeError, ValueError, sqlite3.DatabaseError) as exc:
        raise ImportMaintenanceRecoveryEvidenceError("recovery_active_facts_invalid") from exc
    if int(state["fingerprint_version"] or 0) != summary.fingerprint_version:
        raise ImportMaintenanceRecoveryEvidenceError("recovery_fingerprint_version_drift")
    if int(state["record_count"] or 0) != summary.record_count:
        raise ImportMaintenanceRecoveryEvidenceError("recovery_active_count_drift")
    if str(state["dataset_digest"] or "") != summary.dataset_digest:
        raise ImportMaintenanceRecoveryEvidenceError("recovery_active_digest_drift")
    generation_count = int(
        conn.execute(
            "SELECT COUNT(*) FROM plays WHERE import_generation_id=?",
            (change_set.generation_id,),
        ).fetchone()[0]
    )
    if generation_count != change_set.added_count:
        raise ImportMaintenanceRecoveryEvidenceError("recovery_generation_count_drift")
    return PendingImportMaintenance(run_id=run_id, change_set=change_set)


def _mark_recovery_blocked(conn: sqlite3.Connection, run_id: str, error_code: str) -> None:
    compare_and_set_playback_import_run_status(
        conn,
        run_id=run_id,
        expected_status="maintenance_pending",
        status="recovery_blocked",
        error_code=error_code,
    )
    conn.commit()


def enqueue_pending_import_maintenance(
    queue: JobQueue | None = None,
) -> dict[str, int]:
    """Validate every pending run and idempotently enqueue recoverable work."""

    target_queue = queue or get_job_queue()
    conn = get_db(readonly=False)
    enqueued = 0
    already_pending = 0
    blocked = 0
    try:
        run_ids = [
            str(row[0])
            for row in conn.execute(
                """SELECT run_id FROM playback_import_runs
                   WHERE status='maintenance_pending'
                   ORDER BY started_at, run_id"""
            ).fetchall()
        ]
        for run_id in run_ids:
            try:
                pending = _load_and_fence_pending_run(conn, run_id)
            except ImportMaintenanceAlreadyTerminalError:
                continue
            except ImportMaintenanceRecoveryEvidenceError as exc:
                _mark_recovery_blocked(conn, run_id, exc.error_code)
                blocked += 1
                continue
            job = Job.create(
                PLAYBACK_IMPORT_MAINTENANCE_JOB_TYPE,
                PLAYBACK_IMPORT_MAINTENANCE_ENTITY_TYPE,
                run_id,
                generation_id=pending.change_set.generation_id,
            )
            if target_queue.enqueue_if_not_pending(job) is None:
                already_pending += 1
            else:
                enqueued += 1
    finally:
        conn.close()
    return {
        "pending_runs": len(run_ids),
        "enqueued": enqueued,
        "already_pending": already_pending,
        "blocked": blocked,
    }


def handle_import_maintenance_recovery(job: Job) -> None:
    """Replay maintenance and promote the run only behind a final fact fence."""

    run_id = str(job.entity_id or "")
    expected_generation_id = job.payload.get("generation_id")
    if not run_id or not isinstance(expected_generation_id, str):
        raise RuntimeError("invalid playback import maintenance job")
    conn = get_db(readonly=False)
    try:
        try:
            pending = _load_and_fence_pending_run(
                conn,
                run_id,
                expected_generation_id=expected_generation_id,
            )
        except ImportMaintenanceAlreadyTerminalError:
            return
        except ImportMaintenanceRecoveryEvidenceError as exc:
            _mark_recovery_blocked(conn, run_id, exc.error_code)
            return
    finally:
        conn.close()

    run_post_streaming_import_maintenance(
        defer_music_search_snapshots=True,
        change_set=pending.change_set,
    )

    conn = get_db(readonly=False)
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            _load_and_fence_pending_run(
                conn,
                run_id,
                expected_generation_id=expected_generation_id,
            )
            health = build_import_health_report(conn)
            if health["blockers"]:
                raise RuntimeError("post-recovery import health is blocked")
            transitioned = compare_and_set_playback_import_run_status(
                conn,
                run_id=run_id,
                expected_status="maintenance_pending",
                status="success",
            )
            if not transitioned:
                raise RuntimeError("playback import maintenance success CAS failed")
            conn.commit()
        except ImportMaintenanceAlreadyTerminalError:
            conn.rollback()
        except ImportMaintenanceRecoveryEvidenceError as exc:
            conn.rollback()
            _mark_recovery_blocked(conn, run_id, exc.error_code)
    finally:
        conn.close()
