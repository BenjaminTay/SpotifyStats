"""Bridge the main playback transaction and the immutable active source pointer."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from backend.core import db as db_module
from backend.core.db import get_db
from backend.domains.imports.control_store import (
    active_source_state,
    clear_import_write_quarantine,
    get_run,
    pending_publications,
    quarantine_import_writes,
    restore_active_source,
    set_active_source,
    update_run,
    utc_now,
)
from backend.domains.imports.source_registry import resolve_batch_directory


class PublicationRecoveryError(RuntimeError):
    def __init__(self, error_code: str):
        super().__init__(error_code)
        self.error_code = error_code


def mark_prepared(
    run_id: str,
    *,
    old_generation_id: str | None,
    old_dataset_digest: str | None,
    old_source_version_id: str | None,
    database_snapshot_path: str | None,
) -> None:
    update_run(
        run_id,
        status="running",
        publication_state="prepared",
        old_generation_id=old_generation_id,
        old_dataset_digest=old_dataset_digest,
        old_source_version_id=old_source_version_id,
        database_snapshot_path=database_snapshot_path,
        message="输入已冻结，准备发布播放事实",
    )


def mark_facts_committed(
    run_id: str,
    *,
    generation_id: str,
    dataset_digest: str,
    change_set: dict[str, Any] | None,
) -> None:
    update_run(
        run_id,
        status="running",
        publication_state="facts_committed",
        new_generation_id=generation_id,
        new_dataset_digest=dataset_digest,
        change_set_json=change_set,
        progress_pct=0.6,
        message="播放事实已提交，正在发布活动原始来源",
    )


def publish_sources(
    run_id: str,
    batch_id: str,
    *,
    generation_id: str,
    dataset_digest: str,
) -> None:
    """Publish an already-frozen source and mark the main provenance visible."""

    resolve_batch_directory(batch_id, active=True)
    run = get_run(run_id)
    if run is None:
        raise PublicationRecoveryError("publication_run_missing")
    conn = get_db(readonly=False)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """SELECT active_generation_id, dataset_digest, active_publication_id
               FROM playback_import_state WHERE state_id=1"""
        ).fetchone()
        if (
            row is None
            or str(row[0] or "") != generation_id
            or str(row[1] or "") != dataset_digest
            or str(row[2] or "") != run_id
        ):
            raise PublicationRecoveryError("publication_main_state_drift")
        conn.rollback()
    finally:
        conn.close()

    source_state = active_source_state()
    current_source = source_state.get("active_source_version_id")
    if str(current_source or "") == str(run.get("old_source_version_id") or ""):
        set_active_source(
            batch_id,
            generation_id,
            dataset_digest,
            expected_source_version_id=run.get("old_source_version_id"),
        )
    elif str(current_source or "") != batch_id:
        raise PublicationRecoveryError("publication_source_state_drift")
    conn = get_db(readonly=False)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """UPDATE playback_import_state
               SET active_source_version_id=?, publication_state='sources_published'
               WHERE state_id=1 AND active_publication_id=?""",
            (batch_id, run_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        restore_active_source(
            run.get("old_source_version_id"),
            run.get("old_generation_id"),
            run.get("old_dataset_digest"),
            expected_source_version_id=batch_id,
        )
        raise
    finally:
        conn.close()
    update_run(
        run_id,
        publication_state="sources_published",
        progress_pct=0.65,
        message="播放事实与活动原始来源已发布",
    )
    clear_import_write_quarantine(run_id)


def recover_interrupted_publications(*, db_path: str | None = None) -> dict[str, int]:
    from backend.domains.imports.write_coordinator import exclusive_publication

    with exclusive_publication(db_path=db_path, blocking=True):
        return _recover_interrupted_publications_locked(db_path=db_path)


def _recover_interrupted_publications_locked(*, db_path: str | None = None) -> dict[str, int]:
    """Resolve prepared/facts-committed crash windows before ordinary writers start."""

    database = Path(db_path or db_module.DB_PATH)
    report = {"completed": 0, "not_committed": 0, "blocked": 0}
    for run in pending_publications(db_path=str(database)):
        run_id = str(run["run_id"])
        if not database.is_file():
            update_run(
                run_id,
                db_path=str(database),
                status="blocked",
                publication_state="recovery_blocked",
                recovery_status="blocked",
                error_code="recovery_database_missing",
                completed_at=utc_now(),
            )
            report["blocked"] += 1
            continue
        conn = sqlite3.connect(database)
        conn.row_factory = sqlite3.Row
        try:
            columns = {
                str(row[1]) for row in conn.execute("PRAGMA table_info(playback_import_state)")
            }
            if "active_publication_id" not in columns:
                state = None
            else:
                state = conn.execute(
                    """SELECT active_generation_id,dataset_digest,active_publication_id
                       FROM playback_import_state WHERE state_id=1"""
                ).fetchone()
        finally:
            conn.close()
        if state is not None and str(state[2] or "") == run_id:
            try:
                publish_sources(
                    run_id,
                    str(run["batch_id"]),
                    generation_id=str(state[0]),
                    dataset_digest=str(state[1]),
                )
                update_run(run_id, db_path=str(database), recovery_status="completed_forward")
                report["completed"] += 1
            except Exception as exc:
                quarantine_import_writes(
                    run_id,
                    "source_publish_recovery_failed",
                    db_path=str(database),
                )
                update_run(
                    run_id,
                    db_path=str(database),
                    status="blocked",
                    publication_state="recovery_blocked",
                    recovery_status="blocked",
                    error_code=getattr(exc, "error_code", "source_publish_recovery_failed"),
                    error_detail=str(exc),
                    completed_at=utc_now(),
                )
                report["blocked"] += 1
            continue
        if run["publication_state"] == "prepared":
            update_run(
                run_id,
                db_path=str(database),
                status="failed",
                publication_state="failed_before_facts",
                recovery_status="not_committed",
                error_code="facts_not_committed",
                completed_at=utc_now(),
            )
            report["not_committed"] += 1
        else:
            quarantine_import_writes(
                run_id,
                "recovery_publication_drift",
                db_path=str(database),
            )
            update_run(
                run_id,
                db_path=str(database),
                status="blocked",
                publication_state="recovery_blocked",
                recovery_status="blocked",
                error_code="recovery_publication_drift",
                completed_at=utc_now(),
            )
            report["blocked"] += 1
    return report
