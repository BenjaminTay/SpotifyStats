"""Import API — async import jobs for streaming and account data."""

from __future__ import annotations

import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query

from backend.core.auth import require_auth
from backend.core.cache_manager import invalidate_all
from backend.core.db import get_db
from backend.core.import_account_data import ACCOUNT_DATA_DIR, import_all
from backend.core.import_data import DATA_DIR, import_data
from backend.dependencies import get_conn
from backend.domains.imports.change_set import (
    PlaybackChangeSet,
    build_playback_change_set,
    publish_year_partition_state,
)
from backend.domains.imports.database_snapshot import (
    create_database_snapshot,
    discard_database_created_by_failed_import,
    restore_database_snapshot,
)
from backend.domains.imports.execution import (
    ImportExecutionAction,
    ImportExecutionDecision,
    resolve_import_execution,
)
from backend.domains.imports.incremental import FingerprintRecord, dataset_digest
from backend.domains.imports.state import (
    publish_playback_import_state,
    record_playback_import_run,
    summarise_current_playback_dataset,
)
from backend.domains.metadata.import_health import build_import_health_report
from backend.models.common import ImportJobCreateResponse, ImportJobStatus
from backend.models.imports import ImportHealthResponse, ImportPreflightResponse
from backend.services.import_maintenance_service import run_post_streaming_import_maintenance
from backend.services.import_plan_service import (
    StreamingImportAssessment,
    assess_streaming_import,
    build_streaming_import_preflight,
)

router = APIRouter(prefix="/import", tags=["Import"])

# In-memory job store (single-user local app, no persistence needed)
_jobs = {}
_import_lock = threading.Lock()


@router.get("/preflight", response_model=ImportPreflightResponse)
def get_import_preflight(
    mode: Literal["auto", "append", "replace"] = Query("auto"),
) -> dict:
    """Inspect local Spotify export files without changing the database."""
    return build_streaming_import_preflight(
        DATA_DIR,
        ACCOUNT_DATA_DIR,
        requested_mode=mode,
    )


@router.get("/health", response_model=ImportHealthResponse)
def get_import_health(conn=Depends(get_conn)) -> dict:
    """Return raw, relationship, metadata, and derived-data health."""
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        **build_import_health_report(conn),
    }


def _make_job():
    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {
        "job_id": job_id,
        "status": "running",
        "progress_pct": 0.0,
        "message": "初始化...",
        "result": None,
    }
    return job_id


def _progress_cb(job_id):
    def cb(message: str, pct: float):
        _jobs[job_id]["message"] = message
        _jobs[job_id]["progress_pct"] = max(0.0, min(1.0, float(pct)))

    return cb


def _restore_after_import_failure(snapshot: dict | None) -> dict | None:
    """Restore the pre-import database and clear derived runtime caches."""
    if not snapshot:
        return None
    if snapshot.get("status") == "skipped" and snapshot.get("reason") == "database_not_found":
        invalidate_all()
        rollback = discard_database_created_by_failed_import(snapshot["source_db"])
        invalidate_all()
        return rollback
    if snapshot.get("status") != "created" or not snapshot.get("path"):
        return None
    invalidate_all()
    rollback = restore_database_snapshot(snapshot["path"])
    invalidate_all()
    return rollback


def _failure_result(
    snapshot: dict | None,
    rollback: dict | None,
    rollback_error: Exception | None = None,
) -> dict | None:
    if not snapshot:
        return None
    rollback_result = rollback
    if rollback_error:
        rollback_result = {"status": "failed", "message": str(rollback_error)}
    return {
        "database_snapshot": snapshot,
        "rollback": rollback_result or {"status": "not_needed"},
    }


def _run_with_import_slot(job_id: str, run) -> None:
    """Allow only one database-mutating import job at a time."""
    if not _import_lock.acquire(blocking=False):
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["message"] = "已有导入任务正在运行，本次导入未开始"
        return
    try:
        run()
    finally:
        _import_lock.release()


def _record_plan_outcome(
    job_id: str,
    assessment: StreamingImportAssessment,
    *,
    requested_mode: str,
    status: Literal["success", "noop", "needs_confirmation"],
    change_set: PlaybackChangeSet | None = None,
) -> None:
    conn = get_db(readonly=False)
    try:
        record_playback_import_run(
            conn,
            run_id=job_id,
            requested_mode=requested_mode,
            status=status,
            plan=assessment.plan,
            change_set=change_set,
        )
        conn.commit()
    finally:
        conn.close()


def _streaming_execution_gate(
    job_id: str,
    *,
    confirm_warnings: bool,
    requested_mode: Literal["auto", "append", "replace"],
    confirm_plan: bool,
    confirmation_token: str | None,
) -> tuple[StreamingImportAssessment, ImportExecutionDecision] | None:
    """Resolve source and relationship evidence before any playback write."""
    assessment = assess_streaming_import(
        DATA_DIR,
        ACCOUNT_DATA_DIR,
        requested_mode=requested_mode,
    )
    preflight = assessment.report
    if preflight["blockers"]:
        _jobs[job_id].update(
            status="blocked",
            progress_pct=0.0,
            message="导入已阻断：导入前检查发现硬性问题，数据库未修改",
            result={"preflight": preflight, "import_started": False},
        )
        return None
    confirmation_required = confirm_warnings or confirm_plan
    confirmation_is_stale = confirmation_token is not None and (
        confirmation_token != preflight.get("confirmation_token")
    )
    if (confirmation_required and confirmation_token is None) or confirmation_is_stale:
        _record_plan_outcome(
            job_id,
            assessment,
            requested_mode=requested_mode,
            status="needs_confirmation",
        )
        _jobs[job_id].update(
            status="needs_confirmation",
            progress_pct=0.0,
            message="输入文件或当前数据已变化，请重新核对最新导入计划",
            result={
                "preflight": preflight,
                "import_started": False,
                "confirmation_reason": "stale_plan",
            },
        )
        return None
    if preflight["warnings"] and not confirm_warnings:
        _record_plan_outcome(
            job_id,
            assessment,
            requested_mode=requested_mode,
            status="needs_confirmation",
        )
        _jobs[job_id].update(
            status="needs_confirmation",
            progress_pct=0.0,
            message="导入需要确认：发现文件警告，播放事实尚未修改",
            result={"preflight": preflight, "import_started": False},
        )
        return None

    decision = resolve_import_execution(
        assessment.plan,
        requested_mode=requested_mode,
        confirm_plan=confirm_plan,
    )
    if decision.action is ImportExecutionAction.NEEDS_CONFIRMATION:
        _record_plan_outcome(
            job_id,
            assessment,
            requested_mode=requested_mode,
            status="needs_confirmation",
        )
        _jobs[job_id].update(
            status="needs_confirmation",
            progress_pct=0.0,
            message=decision.message,
            result={"preflight": preflight, "import_started": False},
        )
        return None
    if decision.action is ImportExecutionAction.BLOCKED:
        _jobs[job_id].update(
            status="blocked",
            progress_pct=0.0,
            message=decision.message,
            result={"preflight": preflight, "import_started": False},
        )
        return None
    return assessment, decision


def _complete_noop_import(
    job_id: str,
    assessment: StreamingImportAssessment,
    *,
    requested_mode: str,
) -> dict:
    """Persist an auditable noop without changing playback or derived revisions."""
    conn = get_db(readonly=False)
    try:
        state = conn.execute(
            """SELECT active_generation_id, record_count
               FROM playback_import_state WHERE state_id=1"""
        ).fetchone()
        generation_id = str(state[0]) if state and state[0] else ""
        if not generation_id:
            raise RuntimeError("identical import requires an active playback generation")
        conn.execute(
            """UPDATE playback_import_state
               SET account_identity_hash=?, last_relation=?, last_strategy='noop',
                   updated_at=?
               WHERE state_id=1""",
            (
                assessment.incoming_account_identity_hash
                or assessment.existing_account_identity_hash,
                assessment.plan.relation.value,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        record_playback_import_run(
            conn,
            run_id=job_id,
            requested_mode=requested_mode,
            status="noop",
            plan=assessment.plan,
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "detected_relation": assessment.plan.relation.value,
        "executed_strategy": "noop",
        "noop": True,
        "records": int(state[1] or 0),
        "inserted_records": 0,
        "unchanged_records": assessment.plan.unchanged_count,
        "database_snapshot": {"status": "skipped", "reason": "identical_dataset"},
    }


def _publish_import_state(
    assessment: StreamingImportAssessment,
    import_result: dict,
    *,
    executed_strategy: Literal["incremental", "full"],
    conn: sqlite3.Connection | None = None,
) -> None:
    """Verify facts and publish the active generation before derived maintenance."""
    inserted = int(import_result.get("inserted_records", -1))
    expected_inserted = (
        assessment.plan.incoming_count
        if executed_strategy == "full"
        else assessment.plan.added_count
    )
    if inserted != expected_inserted:
        raise RuntimeError(
            "import ChangeSet mismatch: "
            f"expected {expected_inserted} inserted records, got {inserted}"
        )

    if import_result.get("input_dataset_digest") != assessment.plan.incoming_digest:
        raise RuntimeError("source files changed after the import plan was confirmed")
    if executed_strategy == "incremental" and (
        import_result.get("previous_dataset_digest") != assessment.plan.previous_digest
    ):
        raise RuntimeError("active playback baseline changed after import planning")
    expected_inserted_digest = (
        assessment.plan.incoming_digest
        if executed_strategy == "full"
        else dataset_digest(
            FingerprintRecord(
                source_type=identity.source_type,
                fingerprint=identity.fingerprint,
            )
            for identity in assessment.plan.added
        )
    )
    if import_result.get("inserted_dataset_digest") != expected_inserted_digest:
        raise RuntimeError("inserted playback identities do not match the import plan")

    owns_connection = conn is None
    active_conn = conn or get_db(readonly=False)
    try:
        summary = summarise_current_playback_dataset(active_conn)
        expected_count = assessment.plan.incoming_count
        if executed_strategy == "incremental" and assessment.plan.removed_count == 0:
            expected_count = assessment.plan.existing_count + assessment.plan.added_count
        if summary.record_count != expected_count:
            raise RuntimeError(
                "active playback count mismatch: "
                f"expected {expected_count}, got {summary.record_count}"
            )
        if import_result.get("dataset_digest") != summary.dataset_digest:
            raise RuntimeError("import result digest does not match the active facts")
        if assessment.plan.relation.value != "delta_tail" and (
            summary.dataset_digest != assessment.plan.incoming_digest
        ):
            raise RuntimeError("active playback digest does not match the import plan")
        generation_id = str(import_result.get("generation_id") or "")
        account_identity_hash = (
            assessment.incoming_account_identity_hash
            if executed_strategy == "full"
            else (
                assessment.incoming_account_identity_hash
                or assessment.existing_account_identity_hash
            )
        )
        publish_playback_import_state(
            active_conn,
            generation_id=generation_id,
            account_identity_hash=account_identity_hash,
            relation=assessment.plan.relation.value,
            strategy=executed_strategy,
            summary=summary,
        )
        if owns_connection:
            active_conn.commit()
    finally:
        if owns_connection:
            active_conn.close()


def _post_streaming_health_summary() -> dict:
    """Run the small set of hard checks that can invalidate an import."""
    conn = get_db(readonly=True)
    try:
        report = build_import_health_report(conn)
    finally:
        conn.close()

    database = report["database"]
    relationships = report["relationships"]
    return {
        "status": report["status"],
        "blockers": list(report["blockers"]),
        "warnings": list(report["warnings"]),
        "play_count": database["play_count"],
        "sqlite_integrity": database["sqlite_integrity"],
        "orphan_play_track_count": relationships["orphan_play_track_count"],
        "orphan_play_album_count": relationships["orphan_play_album_count"],
    }


class PostImportHealthError(RuntimeError):
    """Raised when a streaming import violates a core data invariant."""


@router.post("/streaming", response_model=ImportJobCreateResponse)
def start_streaming_import(
    auth: None = Depends(require_auth),
    confirm_warnings: bool = Query(False, description="确认导入前警告后继续"),
    mode: Literal["auto", "append", "replace"] = Query(
        "auto", description="自动判定、只追加或完整替换"
    ),
    confirm_plan: bool = Query(False, description="确认高风险关系后执行完整替换"),
    confirmation_token: str | None = Query(
        None,
        description="绑定本次警告或覆盖确认的只读计划标识",
    ),
):
    """Trigger streaming data import in the background."""
    job_id = _make_job()
    cb = _progress_cb(job_id)

    def _run():
        snapshot = None
        try:
            gated = _streaming_execution_gate(
                job_id,
                confirm_warnings=confirm_warnings,
                requested_mode=mode,
                confirm_plan=confirm_plan,
                confirmation_token=confirmation_token,
            )
            if gated is None:
                return
            assessment, decision = gated
            if decision.action is ImportExecutionAction.NOOP:
                _jobs[job_id]["message"] = "输入数据未变化，跳过导入"
                _jobs[job_id]["result"] = _complete_noop_import(
                    job_id,
                    assessment,
                    requested_mode=mode,
                )
                _jobs[job_id]["status"] = "done"
                _jobs[job_id]["progress_pct"] = 1.0
                return

            snapshot = create_database_snapshot(job_id=job_id)
            import_mode: Literal["append", "replace"] = (
                "append" if decision.action is ImportExecutionAction.APPEND else "replace"
            )
            executed_strategy: Literal["incremental", "full"] = (
                "incremental" if import_mode == "append" else "full"
            )

            def publish_before_commit(conn: sqlite3.Connection, import_result: dict) -> None:
                _publish_import_state(
                    assessment,
                    import_result,
                    executed_strategy=executed_strategy,
                    conn=conn,
                )
                import_result["change_set"] = build_playback_change_set(
                    conn,
                    generation_id=str(import_result.get("generation_id") or ""),
                    strategy=executed_strategy,
                    plan=assessment.plan,
                )
                publish_year_partition_state(conn, import_result["change_set"])
                record_playback_import_run(
                    conn,
                    run_id=job_id,
                    requested_mode=mode,
                    status="maintenance_pending",
                    plan=assessment.plan,
                    change_set=import_result["change_set"],
                )

            result = import_data(
                progress_callback=cb,
                build_preaggregations=False,
                mode=import_mode,
                generation_id=uuid.uuid4().hex,
                expected_previous_digest=(
                    assessment.plan.previous_digest if import_mode == "append" else None
                ),
                before_final_commit=publish_before_commit,
            )
            # Compatibility for test doubles and legacy wrappers that do not
            # invoke the transactional finalizer. The production importer sets
            # this flag only after facts and active state share one commit.
            if not result.get("finalized_in_transaction"):
                _publish_import_state(
                    assessment,
                    result,
                    executed_strategy=executed_strategy,
                )
            change_set = result.get("change_set")
            if isinstance(change_set, PlaybackChangeSet):
                maintenance = run_post_streaming_import_maintenance(
                    progress_callback=cb,
                    defer_music_search_snapshots=True,
                    change_set=change_set,
                )
            else:
                maintenance = run_post_streaming_import_maintenance(
                    progress_callback=cb,
                    defer_music_search_snapshots=True,
                )
            post_import_health = _post_streaming_health_summary()
            if post_import_health["blockers"]:
                raise PostImportHealthError(
                    "导入后健康检查未通过：" + "；".join(post_import_health["blockers"])
                )
            _record_plan_outcome(
                job_id,
                assessment,
                requested_mode=mode,
                status="success",
                change_set=(change_set if isinstance(change_set, PlaybackChangeSet) else None),
            )
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["progress_pct"] = 1.0
            _jobs[job_id]["message"] = "导入完成"
            _jobs[job_id]["result"] = {
                "files": result.get("files_imported", result.get("files", 0)),
                "records": result.get("total_records", result.get("records", 0)),
                "artists": result.get("unique_artists", result.get("artists", 0)),
                "albums": result.get("unique_albums", result.get("albums", 0)),
                "tracks": result.get("unique_tracks", result.get("tracks", 0)),
                "duplicate_records_skipped": result.get("duplicate_records_skipped", 0),
                "unchanged_records": result.get("unchanged_records", 0),
                "inserted_records": result.get("inserted_records", 0),
                "active_records": result.get("active_records", 0),
                "detected_relation": assessment.plan.relation.value,
                "executed_strategy": executed_strategy,
                "noop": False,
                "database_snapshot": snapshot,
                "post_import_health": post_import_health,
                **maintenance,
            }
        except Exception as e:
            rollback = None
            rollback_error = None
            try:
                rollback = _restore_after_import_failure(snapshot)
            except Exception as restore_error:
                rollback_error = restore_error
            _jobs[job_id]["status"] = "error"
            message = str(e)
            if rollback_error:
                message = f"{message}（数据库回滚失败：{rollback_error}）"
            _jobs[job_id]["message"] = message
            _jobs[job_id]["result"] = _failure_result(snapshot, rollback, rollback_error)

    threading.Thread(target=lambda: _run_with_import_slot(job_id, _run), daemon=True).start()
    return {"job_id": job_id}


@router.post("/account", response_model=ImportJobCreateResponse)
def start_account_import(auth: None = Depends(require_auth)):
    """Trigger account data import in the background."""
    job_id = _make_job()
    cb = _progress_cb(job_id)

    def _run():
        snapshot = None
        try:
            snapshot = create_database_snapshot(job_id=job_id)
            result = import_all(progress_callback=cb)
            invalidate_all()
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["progress_pct"] = 1.0
            _jobs[job_id]["message"] = "导入完成"
            # Simplify results: only keep summary keys, skip nested dicts
            summary = {}
            for k, v in result.items():
                if isinstance(v, dict):
                    for sk, sv in v.items():
                        if isinstance(sv, int) or isinstance(sv, str):
                            summary[f"{k}.{sk}"] = sv
                else:
                    summary[k] = str(v)
            summary["database_snapshot"] = snapshot
            _jobs[job_id]["result"] = summary
        except Exception as e:
            rollback = None
            rollback_error = None
            try:
                rollback = _restore_after_import_failure(snapshot)
            except Exception as restore_error:
                rollback_error = restore_error
            _jobs[job_id]["status"] = "error"
            message = str(e)
            if rollback_error:
                message = f"{message}（数据库回滚失败：{rollback_error}）"
            _jobs[job_id]["message"] = message
            _jobs[job_id]["result"] = _failure_result(snapshot, rollback, rollback_error)

    threading.Thread(target=lambda: _run_with_import_slot(job_id, _run), daemon=True).start()
    return {"job_id": job_id}


@router.get("/status/{job_id}", response_model=ImportJobStatus)
def get_import_status(job_id: str):
    """Query the status of an import job."""
    job = _jobs.get(job_id)
    if not job:
        return {
            "job_id": job_id,
            "status": "not_found",
            "progress_pct": 0,
            "message": "Job not found",
        }
    return job
