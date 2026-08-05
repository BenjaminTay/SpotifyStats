"""Import API — async import jobs for streaming and account data."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from backend.core.auth import require_auth
from backend.core.cache_manager import invalidate_all
from backend.core.db import get_db
from backend.core.import_account_data import ACCOUNT_DATA_DIR, import_all
from backend.core.import_data import DATA_DIR, import_data
from backend.dependencies import get_conn
from backend.domains.imports.database_snapshot import (
    create_database_snapshot,
    discard_database_created_by_failed_import,
    restore_database_snapshot,
)
from backend.domains.imports.source_inspector import inspect_data_sources
from backend.domains.metadata.import_health import build_import_health_report
from backend.models.common import ImportJobCreateResponse, ImportJobStatus
from backend.models.imports import ImportHealthResponse, ImportPreflightResponse
from backend.services.import_maintenance_service import run_post_streaming_import_maintenance

router = APIRouter(prefix="/import", tags=["Import"])

# In-memory job store (single-user local app, no persistence needed)
_jobs = {}
_import_lock = threading.Lock()


@router.get("/preflight", response_model=ImportPreflightResponse)
def get_import_preflight() -> dict:
    """Inspect local Spotify export files without changing the database."""
    return inspect_data_sources(DATA_DIR, ACCOUNT_DATA_DIR)


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


def _streaming_preflight_allows(job_id: str, confirm_warnings: bool) -> bool:
    """Apply the read-only source gate before the destructive import starts."""
    preflight = inspect_data_sources(DATA_DIR, ACCOUNT_DATA_DIR)
    if preflight["blockers"]:
        _jobs[job_id].update(
            status="blocked",
            progress_pct=0.0,
            message="导入已阻断：导入前检查发现硬性问题，数据库未修改",
            result={"preflight": preflight, "import_started": False},
        )
        return False
    if preflight["warnings"] and not confirm_warnings:
        _jobs[job_id].update(
            status="needs_confirmation",
            progress_pct=0.0,
            message="导入需要确认：发现导入前警告，数据库尚未修改",
            result={"preflight": preflight, "import_started": False},
        )
        return False
    return True


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
):
    """Trigger streaming data import in the background."""
    job_id = _make_job()
    cb = _progress_cb(job_id)

    def _run():
        snapshot = None
        try:
            if not _streaming_preflight_allows(job_id, confirm_warnings):
                return
            snapshot = create_database_snapshot(job_id=job_id)
            result = import_data(progress_callback=cb, build_preaggregations=False)
            maintenance = run_post_streaming_import_maintenance(progress_callback=cb)
            post_import_health = _post_streaming_health_summary()
            if post_import_health["blockers"]:
                raise PostImportHealthError(
                    "导入后健康检查未通过：" + "；".join(post_import_health["blockers"])
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
