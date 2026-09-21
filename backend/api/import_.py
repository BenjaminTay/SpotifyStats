"""Import API — async import jobs for streaming and account data."""

from __future__ import annotations

import hashlib
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from backend.core.auth import require_auth
from backend.core.cache_manager import invalidate_all
from backend.core.db import get_db
from backend.core.import_account_data import ACCOUNT_DATA_DIR, import_all
from backend.core.import_data import (
    DATA_DIR,
    ImportBaselineDriftError,
    ImportBaselineFence,
    import_data,
)
from backend.dependencies import get_conn
from backend.domains.imports.change_set import (
    PlaybackChangeSet,
    build_playback_change_set,
    publish_year_partition_state,
)
from backend.domains.imports.control_store import (
    active_source_state,
    clear_import_write_quarantine,
    import_write_gate_state,
    latest_stage_attempts,
    pending_publications,
    quarantine_import_writes,
    record_report_result,
)
from backend.domains.imports.control_store import (
    create_run as create_control_run,
)
from backend.domains.imports.control_store import (
    get_batch as get_control_batch,
)
from backend.domains.imports.control_store import (
    get_run as get_control_run,
)
from backend.domains.imports.control_store import (
    list_runs as list_control_runs,
)
from backend.domains.imports.control_store import (
    update_run as update_control_run,
)
from backend.domains.imports.control_store import (
    utc_now as control_utc_now,
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
from backend.domains.imports.incremental import (
    FINGERPRINT_VERSION,
    FingerprintRecord,
    dataset_digest,
)
from backend.domains.imports.source_registry import (
    ImportSourceError,
    create_receiving_batch,
    finalize_receiving_batch,
    freeze_local_batch,
    receive_batch_file,
    resolve_batch_directory,
    source_dataset_summary,
    validate_batch_lineage,
)
from backend.domains.imports.state import (
    publish_playback_import_state,
    record_playback_import_run,
    summarise_current_playback_dataset,
)
from backend.domains.imports.streaming_staging import take_cached_staging
from backend.domains.imports.write_coordinator import (
    ImportWriteBusyError,
    exclusive_publication,
)
from backend.domains.metadata.import_health import (
    build_import_cleanup_preview,
    build_import_health_report,
)
from backend.models.common import ImportJobCreateResponse, ImportJobStatus
from backend.models.imports import (
    ImportBatchCreateRequest,
    ImportBatchResponse,
    ImportBatchUploadResponse,
    ImportCleanupPreviewResponse,
    ImportHealthResponse,
    ImportPreflightResponse,
    ImportRunCreateRequest,
    ImportRunCreateResponse,
    ImportRunDetailResponse,
    ImportRunHistoryResponse,
    ImportStageRetryRequest,
)
from backend.services.import_plan_service import (
    StreamingImportAssessment,
    assess_streaming_import,
    build_streaming_import_preflight,
)
from backend.services.import_publication_service import (
    mark_facts_committed,
    mark_prepared,
    publish_sources,
)
from backend.services.import_run_report_service import (
    build_import_run_report,
    render_import_run_markdown,
    write_import_run_reports,
)
from backend.services.import_stage_service import reconcile_import_readiness, run_import_stages

router = APIRouter(prefix="/import", tags=["Import"])

# In-memory job store (single-user local app, no persistence needed)
_jobs: dict[str, dict] = {}
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
        retain_staging_for_confirmation=True,
    )


@router.get("/health", response_model=ImportHealthResponse)
def get_import_health(conn=Depends(get_conn)) -> dict:
    """Return raw, relationship, metadata, and derived-data health."""
    from backend.services.governance_snapshot_service import read

    report = read(conn, "import_health")
    latest = next(reversed(_jobs.values()), None) if _jobs else None
    if latest is not None:
        report["runtime"]["import_job"] = {
            key: latest.get(key) for key in ("job_id", "status", "message", "progress_pct")
        }
        if latest.get("status") in {"error", "blocked"}:
            report["runtime"]["errors"].append(latest.get("message") or "导入任务失败")
            report["status"] = "failed"
            report["summary"] = {
                **report["summary"],
                "safe_to_use": False,
                "headline": "当前导入任务失败，请检查任务错误",
            }
    return report


@router.post(
    "/governance/cleanup-preview",
    response_model=ImportCleanupPreviewResponse,
)
def preview_import_cleanup(
    sample_limit: int = Query(default=20, ge=1, le=100),
    conn=Depends(get_conn),
    auth: None = Depends(require_auth),
) -> dict:
    """Preview historical relationship cleanup without writing to the database."""
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **build_import_cleanup_preview(conn, sample_limit=sample_limit),
    }


def _plan_payload(assessment: StreamingImportAssessment) -> dict:
    plan = assessment.plan
    return {
        "detected_relation": plan.relation.value,
        "estimated_strategy": plan.estimated_strategy.value,
        "existing_count": plan.existing_count,
        "incoming_count": plan.incoming_count,
        "unchanged_count": plan.unchanged_count,
        "added_count": plan.added_count,
        "removed_count": plan.removed_count,
        "incoming_digest": plan.incoming_digest,
        "previous_digest": plan.previous_digest,
    }


def _control_run_detail(run: dict) -> dict:
    stages = []
    for stage in latest_stage_attempts(str(run["run_id"])):
        output = stage.get("output_evidence") or {}
        stages.append(
            {
                "stage": stage["stage"],
                "attempt": stage["attempt"],
                "status": stage["status"],
                "freshness": output.get("status"),
                "message": output.get("message"),
                "error_code": stage.get("error_code"),
                "retryable": bool(stage.get("retryable")),
                "queued_at": stage.get("queued_at"),
                "started_at": stage.get("started_at"),
                "completed_at": stage.get("completed_at"),
                "result": _public_result(output),
            }
        )
    return {
        "run_id": run["run_id"],
        "batch_id": run["batch_id"],
        "status": run["status"],
        "publication_state": run["publication_state"],
        "progress_pct": float(run.get("progress_pct") or 0),
        "message": str(run.get("message") or ""),
        "error_code": run.get("error_code"),
        "retryable": bool(run.get("retryable")),
        "report_status": str(run.get("report_status") or "pending"),
        "report_error_code": run.get("report_error_code"),
        "result": _public_result(run.get("result")),
        "plan": run.get("plan"),
        "stages": stages,
        "started_at": run["started_at"],
        "completed_at": run.get("completed_at"),
    }


def _public_result(value):
    """Remove private recovery paths and internal target identifiers from the UI payload."""

    if isinstance(value, list):
        return [_public_result(item) for item in value]
    if not isinstance(value, dict):
        return value
    hidden_markers = ("path", "job_id", "generation_id", "dataset_digest", "revision")
    return {
        key: _public_result(item)
        for key, item in value.items()
        if not any(marker in key.lower() for marker in hidden_markers)
        and key != "database_snapshot"
    }


class ConfirmedImportPlanDriftError(RuntimeError):
    error_code = "confirmed_plan_drift"


def _batch_confirmation_token(
    batch_id: str,
    base_token: str,
    *,
    mode: str,
) -> str:
    batch = get_control_batch(batch_id)
    if batch is None or batch.get("status") not in {"frozen", "published"}:
        raise ImportSourceError("batch_not_frozen")
    payload = (
        "streaming-import-confirmation-v2\0"
        f"batch={batch_id}\0manifest={batch.get('manifest_digest') or ''}\0"
        f"mode={mode}\0base={base_token}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


SourceAlignment = Literal["empty", "legacy_unregistered", "published"]


def _assert_confirmed_source_alignment(
    assessment: StreamingImportAssessment,
) -> SourceAlignment:
    """Classify a fenced baseline without mistaking valid legacy state for drift."""

    conn = get_db(readonly=True)
    try:
        state = conn.execute(
            """SELECT active_generation_id,dataset_digest,record_count,
                      fingerprint_version,active_source_version_id,
                      active_publication_id,publication_state
               FROM playback_import_state WHERE state_id=1"""
        ).fetchone()
        fact_count = int(conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0])
    finally:
        conn.close()
    if state is None:
        raise ConfirmedImportPlanDriftError("主库导入状态缺失；请先恢复导入状态")

    generation_id = str(state[0]) if state[0] else None
    digest = str(state[1]) if state[1] else None
    state_count = int(state[2] or 0)
    fingerprint_version = int(state[3]) if state[3] is not None else None
    source_version_id = str(state[4]) if state[4] else None
    publication_id = str(state[5]) if state[5] else None
    publication_state = str(state[6] or "")
    expected_main = (
        assessment.existing_generation_id,
        assessment.existing_dataset_digest,
        assessment.existing_state_record_count,
        assessment.existing_fingerprint_version,
        assessment.existing_source_version_id,
        assessment.existing_record_count,
    )
    actual_main = (
        generation_id,
        digest,
        state_count,
        fingerprint_version,
        source_version_id,
        fact_count,
    )
    if actual_main != expected_main:
        raise ConfirmedImportPlanDriftError("主库事实或导入状态已变化；请重新预检后再导入")

    source = active_source_state()
    control_source = str(source.get("active_source_version_id") or "") or None
    control_generation = str(source.get("active_generation_id") or "") or None
    control_digest = str(source.get("active_dataset_digest") or "") or None
    pending = pending_publications()
    gate = import_write_gate_state()
    has_recovery_evidence = bool(pending) or bool(gate.get("blocked"))

    if (
        fact_count == 0
        and generation_id is None
        and digest is None
        and source_version_id is None
        and publication_id is None
        and control_source is None
        and control_generation is None
        and control_digest is None
        and not has_recovery_evidence
    ):
        return "empty"

    if (
        fact_count > 0
        and assessment.baseline_status == "ready"
        and generation_id is not None
        and digest is not None
        and state_count == fact_count
        and fingerprint_version == FINGERPRINT_VERSION
        and source_version_id is None
        and publication_id is None
        and publication_state == "legacy"
        and control_source is None
        and control_generation is None
        and control_digest is None
        and not has_recovery_evidence
    ):
        return "legacy_unregistered"

    if (
        source_version_id is not None
        and publication_id is not None
        and publication_state in {"sources_published", "core_ready", "ready"}
        and (control_source, control_generation, control_digest)
        == (source_version_id, generation_id, digest)
        and not has_recovery_evidence
    ):
        return "published"

    raise ConfirmedImportPlanDriftError(
        "主库事实、活动原始来源或恢复状态不一致；请先完成来源恢复后再导入"
    )


def _active_fact_source_target(
    assessment: StreamingImportAssessment,
) -> tuple[int, str]:
    conn = get_db(readonly=True)
    try:
        rows = conn.execute(
            """SELECT content_type,source_fingerprint
               FROM plays
               WHERE source_fingerprint IS NOT NULL
               ORDER BY content_type,source_fingerprint"""
        ).fetchall()
    finally:
        conn.close()
    records = [FingerprintRecord(source_type=str(row[0]), fingerprint=str(row[1])) for row in rows]
    records.extend(
        FingerprintRecord(source_type=item.source_type, fingerprint=item.fingerprint)
        for item in assessment.plan.added
    )
    identities = {record.identity for record in records}
    return len(identities), dataset_digest(records)


def _prepare_publication_source(
    batch_id: str,
    assessment: StreamingImportAssessment,
    *,
    strategy: Literal["incremental", "reconcile", "full"],
    source_alignment: SourceAlignment,
) -> str:
    """Bind the immutable intake packet to an exact replayable source version."""

    batch = get_control_batch(batch_id)
    if batch is None:
        raise ImportSourceError("batch_unavailable")
    if strategy == "incremental":
        expected_count, expected_digest = _active_fact_source_target(assessment)
        candidate_summary = source_dataset_summary(batch_id)
        if (
            int(candidate_summary["record_count"]) == expected_count
            and str(candidate_summary["dataset_digest"]) == expected_digest
        ):
            return batch_id
        parent_id = assessment.existing_source_version_id
        if assessment.existing_record_count and not parent_id:
            if source_alignment == "legacy_unregistered":
                raise ImportSourceError(
                    "legacy_source_baseline_requires_full_snapshot",
                    "当前旧版基线尚未登记活动来源；请提供覆盖全部历史的完整导出并选择完整替换",
                )
            raise ImportSourceError("active_source_baseline_missing")
        if parent_id:
            parent_summary = source_dataset_summary(parent_id)
            if int(parent_summary["record_count"]) != assessment.existing_record_count or str(
                parent_summary["dataset_digest"]
            ) != str(assessment.existing_dataset_digest or ""):
                raise ImportSourceError("active_source_semantic_drift")
        if not parent_id:
            raise ImportSourceError("delta_parent_missing")
        publication = freeze_local_batch(
            resolve_batch_directory(batch_id),
            kind="delta",
            parent_source_version_id=parent_id,
        )
    else:
        expected_count = assessment.plan.incoming_count
        expected_digest = assessment.plan.incoming_digest
        if batch.get("kind") in {"snapshot", "legacy"}:
            publication = batch
        else:
            publication = freeze_local_batch(resolve_batch_directory(batch_id), kind="snapshot")

    publication_id = str(publication["batch_id"])
    summary = source_dataset_summary(publication_id)
    if (
        int(summary["record_count"]) != expected_count
        or str(summary["dataset_digest"]) != expected_digest
    ):
        raise ImportSourceError("publication_source_semantic_mismatch")
    return publication_id


@router.post("/batches", response_model=ImportBatchResponse)
def create_import_batch(
    request: ImportBatchCreateRequest,
    auth: None = Depends(require_auth),
) -> dict:
    """Create a server-owned receiving batch for browser uploads."""
    del auth
    try:
        return create_receiving_batch(
            kind=request.kind,
            parent_source_version_id=request.parent_source_version_id,
        )
    except ImportSourceError as exc:
        raise HTTPException(status_code=409, detail=exc.error_code) from exc


@router.put(
    "/batches/{batch_id}/files/{file_name}",
    response_model=ImportBatchUploadResponse,
)
async def upload_import_batch_file(
    batch_id: str,
    file_name: str,
    request: Request,
    source_type: Literal["audio", "video"] = Query(...),
    auth: None = Depends(require_auth),
) -> dict:
    del auth
    try:
        return await receive_batch_file(
            batch_id,
            file_name,
            source_type,
            request.stream(),
        )
    except ImportSourceError as exc:
        status = 413 if exc.error_code == "upload_size_limit_exceeded" else 409
        raise HTTPException(status_code=status, detail=exc.error_code) from exc


@router.post("/batches/{batch_id}/finalize", response_model=ImportBatchResponse)
def finalize_import_batch(
    batch_id: str,
    auth: None = Depends(require_auth),
) -> dict:
    del auth
    try:
        return finalize_receiving_batch(batch_id)
    except ImportSourceError as exc:
        raise HTTPException(status_code=409, detail=exc.error_code) from exc


@router.get("/batches/{batch_id}/preflight", response_model=ImportPreflightResponse)
def get_batch_preflight(
    batch_id: str,
    mode: Literal["auto", "append", "replace"] = Query("auto"),
) -> dict:
    try:
        validate_batch_lineage(batch_id)
    except ImportSourceError as exc:
        raise HTTPException(status_code=409, detail=exc.error_code) from exc
    packet_dir = resolve_batch_directory(batch_id)
    report = dict(
        build_streaming_import_preflight(
            packet_dir,
            ACCOUNT_DATA_DIR,
            requested_mode=mode,
            retain_staging_for_confirmation=False,
        )
    )
    report["confirmation_token"] = _batch_confirmation_token(
        batch_id,
        str(report.get("confirmation_token") or ""),
        mode=mode,
    )
    return report


def _execute_control_run(
    run_id: str,
    batch_id: str,
    *,
    mode: Literal["auto", "append", "replace"],
    confirm_plan: bool,
    confirmation_digest: str,
) -> None:
    validate_batch_lineage(batch_id)
    packet_dir = resolve_batch_directory(batch_id)
    assessment: StreamingImportAssessment | None = None
    snapshot = None
    facts_committed = False
    sources_published = False
    rollback = None
    rollback_error: Exception | None = None

    def is_pre_dml_source_block(exc: BaseException) -> bool:
        return isinstance(exc, ImportSourceError) and exc.error_code in {
            "legacy_source_baseline_requires_full_snapshot",
        }

    def restore_before_publication_unlock(_exc: BaseException) -> None:
        nonlocal rollback, rollback_error
        if facts_committed:
            return
        if isinstance(_exc, (ConfirmedImportPlanDriftError, ImportBaselineDriftError)) or (
            is_pre_dml_source_block(_exc)
        ):
            rollback = {"status": "skipped", "reason": "confirmed_plan_drift_before_dml"}
            clear_import_write_quarantine(run_id)
            return
        try:
            rollback = _restore_after_import_failure(snapshot)
            clear_import_write_quarantine(run_id)
        except Exception as restore_exc:
            rollback_error = restore_exc
            quarantine_import_writes(run_id, "database_restore_failed")

    try:
        update_control_run(
            run_id,
            status="running",
            progress_pct=0.05,
            message="正在核验冻结输入与活动基线",
        )
        assessment = assess_streaming_import(
            packet_dir,
            ACCOUNT_DATA_DIR,
            requested_mode=mode,
            retain_staging=True,
        )
        current_confirmation = _batch_confirmation_token(
            batch_id,
            str(assessment.report.get("confirmation_token") or ""),
            mode=mode,
        )
        if current_confirmation != confirmation_digest:
            raise ConfirmedImportPlanDriftError("输入或活动数据已变化；本次执行未开始，请重新预检")
        decision = resolve_import_execution(
            assessment.plan,
            requested_mode=mode,
            confirm_plan=confirm_plan,
        )
        if decision.action in {
            ImportExecutionAction.BLOCKED,
            ImportExecutionAction.NEEDS_CONFIRMATION,
        }:
            raise RuntimeError(decision.message)
        with exclusive_publication(
            on_error=restore_before_publication_unlock,
            owner_run_id=run_id,
        ):
            validate_batch_lineage(batch_id)
            fresh_assessment = assess_streaming_import(
                packet_dir,
                ACCOUNT_DATA_DIR,
                requested_mode=mode,
                staging=assessment.staging,
                retain_staging=True,
            )
            locked_confirmation = _batch_confirmation_token(
                batch_id,
                str(fresh_assessment.report.get("confirmation_token") or ""),
                mode=mode,
            )
            if locked_confirmation != confirmation_digest:
                raise ConfirmedImportPlanDriftError(
                    "活动基线或来源谱系已变化；本次执行未开始，请重新预检"
                )
            assessment = fresh_assessment
            decision = resolve_import_execution(
                assessment.plan,
                requested_mode=mode,
                confirm_plan=confirm_plan,
            )
            if decision.action in {
                ImportExecutionAction.BLOCKED,
                ImportExecutionAction.NEEDS_CONFIRMATION,
            }:
                raise ConfirmedImportPlanDriftError(decision.message)
            source_alignment = _assert_confirmed_source_alignment(assessment)
            if decision.action is ImportExecutionAction.NOOP:
                if source_alignment == "legacy_unregistered":
                    update_control_run(
                        run_id,
                        status="succeeded",
                        publication_state="legacy_source_unregistered",
                        progress_pct=1.0,
                        message=(
                            "输入数据未变化，播放事实保持不变；活动原始来源尚未登记，"
                            "请提供覆盖全部历史的完整导出并选择完整替换"
                        ),
                        result_json={
                            "noop": True,
                            "executed_strategy": "noop",
                            "source_registration_status": "not_registered",
                            "next_action": "replace_with_complete_snapshot",
                        },
                        completed_at=control_utc_now(),
                    )
                    return
                update_control_run(
                    run_id,
                    status="succeeded",
                    publication_state="ready",
                    progress_pct=1.0,
                    message="输入数据未变化，跳过导入",
                    result_json={"noop": True, "executed_strategy": "noop"},
                    completed_at=control_utc_now(),
                )
                return

            import_mode: Literal["append", "reconcile", "replace"]
            strategy: Literal["incremental", "reconcile", "full"]
            if decision.action is ImportExecutionAction.APPEND:
                import_mode, strategy = "append", "incremental"
            elif decision.action is ImportExecutionAction.RECONCILE:
                import_mode, strategy = "reconcile", "reconcile"
            else:
                import_mode, strategy = "replace", "full"

            source_version_id = _prepare_publication_source(
                batch_id,
                assessment,
                strategy=strategy,
                source_alignment=source_alignment,
            )
            update_control_run(run_id, source_version_id=source_version_id)
            state_conn = get_db(readonly=True)
            try:
                state = state_conn.execute(
                    """SELECT active_generation_id,dataset_digest,
                              active_source_version_id
                       FROM playback_import_state WHERE state_id=1"""
                ).fetchone()
            finally:
                state_conn.close()
            snapshot = create_database_snapshot(job_id=run_id)
            mark_prepared(
                run_id,
                old_generation_id=(str(state[0]) if state and state[0] else None),
                old_dataset_digest=(str(state[1]) if state and state[1] else None),
                old_source_version_id=(str(state[2]) if state and state[2] else None),
                database_snapshot_path=(snapshot.get("path") if snapshot else None),
            )

            def finalize(conn: sqlite3.Connection, import_result: dict) -> None:
                _publish_import_state(
                    assessment,
                    import_result,
                    executed_strategy=strategy,
                    conn=conn,
                    publication_id=run_id,
                    source_version_id=source_version_id,
                )
                change_set = build_playback_change_set(
                    conn,
                    generation_id=str(import_result.get("generation_id") or ""),
                    strategy=strategy,
                    plan=assessment.plan,
                    removed_rows=import_result.get("_removed_impact_rows"),
                )
                import_result["change_set"] = change_set
                publish_year_partition_state(conn, change_set)
                record_playback_import_run(
                    conn,
                    run_id=run_id,
                    requested_mode=mode,
                    status="maintenance_pending",
                    plan=assessment.plan,
                    change_set=change_set,
                    batch_id=batch_id,
                    source_version_id=source_version_id,
                    publication_id=run_id,
                    baseline_reason_code=assessment.baseline_reason_code,
                )

            update_control_run(
                run_id,
                progress_pct=0.2,
                message="正在提交播放事实",
            )

            def progress(message: str, pct: float) -> None:
                bounded = max(0.0, min(1.0, float(pct)))
                update_control_run(
                    run_id,
                    progress_pct=0.2 + 0.38 * bounded,
                    message=message,
                )

            result = import_data(
                data_dir=str(packet_dir),
                build_preaggregations=False,
                mode=import_mode,
                generation_id=uuid.uuid4().hex,
                expected_previous_digest=(
                    assessment.plan.previous_digest
                    if import_mode in {"append", "reconcile"}
                    else None
                ),
                expected_baseline=ImportBaselineFence(
                    generation_id=assessment.existing_generation_id,
                    dataset_digest=assessment.existing_dataset_digest,
                    source_version_id=assessment.existing_source_version_id,
                    state_record_count=assessment.existing_state_record_count,
                    play_count=assessment.existing_record_count,
                    fingerprint_version=assessment.existing_fingerprint_version,
                ),
                removed_identities=(
                    assessment.plan.removed if import_mode == "reconcile" else None
                ),
                before_final_commit=finalize,
                staging=assessment.staging,
                progress_callback=progress,
            )
            facts_committed = True
            change_set = result.get("change_set")
            if not isinstance(change_set, PlaybackChangeSet):
                raise RuntimeError("transactional import ChangeSet is missing")
            mark_facts_committed(
                run_id,
                generation_id=str(result["generation_id"]),
                dataset_digest=str(result["dataset_digest"]),
                change_set=change_set.to_dict(),
            )
            quarantine_import_writes(run_id, "facts_committed_source_pending")
            update_control_run(
                run_id,
                result_json={
                    "detected_relation": assessment.plan.relation.value,
                    "executed_strategy": strategy,
                    "noop": False,
                    "inserted_records": int(result.get("inserted_records") or 0),
                    "unchanged_records": int(result.get("unchanged_records") or 0),
                    "active_records": int(result.get("active_records") or 0),
                    "duplicate_records_skipped": int(result.get("duplicate_records_skipped") or 0),
                },
            )
            publish_sources(
                run_id,
                generation_id=str(result["generation_id"]),
                dataset_digest=str(result["dataset_digest"]),
            )
            sources_published = True
        run_import_stages(run_id, change_set)
    except Exception as exc:
        current = get_control_run(run_id) or {}
        before_facts_retryable = not facts_committed and (
            isinstance(exc, ImportWriteBusyError)
            or (
                isinstance(exc, sqlite3.OperationalError)
                and any(marker in str(exc).lower() for marker in ("locked", "busy"))
            )
        )
        before_facts_blocked = not facts_committed and (
            isinstance(exc, ConfirmedImportPlanDriftError) or is_pre_dml_source_block(exc)
        )
        update_control_run(
            run_id,
            status=(
                "blocked"
                if (facts_committed and not sources_published) or before_facts_blocked
                else "retryable_failed"
                if before_facts_retryable
                else "failed"
            ),
            publication_state=(
                str(current.get("publication_state") or "sources_published")
                if sources_published
                else "facts_committed"
                if facts_committed
                else "failed_before_facts"
            ),
            message=(
                "播放事实已提交，来源发布需要恢复"
                if facts_committed and not sources_published
                else "播放事实与来源已发布，后处理失败"
                if sources_published
                else str(exc)
            ),
            error_code=(
                getattr(exc, "error_code", None)
                or ("source_publish_failed" if facts_committed else "facts_import_failed")
            ),
            error_detail=str(exc),
            result_json={
                **(current.get("result") or {}),
                "database_snapshot": snapshot,
                "rollback": rollback,
            },
            retryable=int(before_facts_retryable),
            completed_at=control_utc_now(),
        )
        if rollback_error is not None:
            update_control_run(
                run_id,
                publication_state="recovery_blocked",
                error_code="database_restore_failed",
                error_detail=str(rollback_error),
            )
    finally:
        if assessment is not None and assessment.staging is not None:
            assessment.staging.close()


def _execute_control_run_with_slot(
    run_id: str,
    batch_id: str,
    *,
    mode: Literal["auto", "append", "replace"],
    confirm_plan: bool,
    confirmation_digest: str,
) -> None:
    if not _import_lock.acquire(blocking=False):
        update_control_run(
            run_id,
            status="retryable_failed",
            publication_state="planned",
            message="已有导入任务正在运行，本次导入未开始",
            error_code="import_slot_busy",
            retryable=1,
            completed_at=control_utc_now(),
        )
        return
    try:
        _execute_control_run(
            run_id,
            batch_id,
            mode=mode,
            confirm_plan=confirm_plan,
            confirmation_digest=confirmation_digest,
        )
    finally:
        _import_lock.release()


@router.post(
    "/batches/{batch_id}/runs",
    response_model=ImportRunCreateResponse,
)
def create_import_run(
    batch_id: str,
    request: ImportRunCreateRequest,
    auth: None = Depends(require_auth),
) -> dict:
    del auth
    try:
        validate_batch_lineage(batch_id)
    except ImportSourceError as exc:
        raise HTTPException(status_code=409, detail=exc.error_code) from exc
    packet_dir = resolve_batch_directory(batch_id)
    assessment = assess_streaming_import(
        packet_dir,
        ACCOUNT_DATA_DIR,
        requested_mode=request.mode,
        retain_staging=False,
    )
    expected_token = _batch_confirmation_token(
        batch_id,
        str(assessment.report.get("confirmation_token") or ""),
        mode=request.mode,
    )
    if request.confirmation_token != expected_token:
        raise HTTPException(status_code=409, detail="输入或活动数据已变化，请重新预检")
    if assessment.report["blockers"]:
        raise HTTPException(status_code=409, detail="导入前检查存在阻断项")
    if assessment.report["warnings"] and not request.confirm_warnings:
        raise HTTPException(status_code=409, detail="导入警告尚未确认")
    decision = resolve_import_execution(
        assessment.plan,
        requested_mode=request.mode,
        confirm_plan=request.confirm_plan,
    )
    if decision.action in {ImportExecutionAction.BLOCKED, ImportExecutionAction.NEEDS_CONFIRMATION}:
        raise HTTPException(status_code=409, detail=decision.message)
    execution_key = hashlib.sha256(
        f"{batch_id}\0{expected_token}\0{request.mode}".encode()
    ).hexdigest()
    proposed_run_id = uuid.uuid4().hex[:12]
    run_id, created = create_control_run(
        run_id=proposed_run_id,
        execution_key=execution_key,
        batch_id=batch_id,
        confirmation_digest=expected_token,
        requested_mode=request.mode,
        detected_relation=assessment.plan.relation.value,
        strategy=decision.action.value,
        baseline_reason_code=assessment.baseline_reason_code,
        plan=_plan_payload(assessment),
    )
    if created:
        threading.Thread(
            target=lambda: _execute_control_run_with_slot(
                run_id,
                batch_id,
                mode=request.mode,
                confirm_plan=request.confirm_plan,
                confirmation_digest=expected_token,
            ),
            daemon=True,
        ).start()
    return {"run_id": run_id, "created": created}


@router.get("/runs", response_model=ImportRunHistoryResponse)
def get_import_run_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    rows = list_control_runs(limit=limit + 1, offset=offset)
    has_more = len(rows) > limit
    visible = rows[:limit]
    return {
        "runs": [_control_run_detail(run) for run in visible],
        "has_more": has_more,
        "next_offset": offset + limit if has_more else None,
    }


@router.get(
    "/runs/latest",
    response_model=Optional[ImportRunDetailResponse],  # noqa: UP045 - evaluated on Python 3.9
)
def get_latest_import_run() -> dict | None:
    rows = list_control_runs(limit=1)
    if not rows:
        return None
    return _control_run_detail(rows[0])


@router.get("/runs/{run_id}", response_model=ImportRunDetailResponse)
def get_import_run_detail(run_id: str) -> dict:
    run = get_control_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Import run not found")
    return _control_run_detail(run)


@router.get("/runs/{run_id}/report")
def get_import_run_report(
    run_id: str,
    format: Literal["json", "markdown"] = Query("json"),
    auth: None = Depends(require_auth),
):
    """Return the private local report; ordinary run payloads omit paths and traces."""
    del auth
    if get_control_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Import run not found")
    write_import_run_reports(run_id)
    record_report_result(run_id, status="ready", error_code=None)
    report = build_import_run_report(run_id)
    if format == "json":
        return report
    return Response(
        content=render_import_run_markdown(report),
        media_type="text/markdown; charset=utf-8",
    )


@router.post("/runs/{run_id}/recheck", response_model=ImportRunDetailResponse)
def recheck_import_run(
    run_id: str,
    auth: None = Depends(require_auth),
) -> dict:
    del auth
    try:
        reconcile_import_readiness(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Import run not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    run = get_control_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Import run not found")
    return _control_run_detail(run)


@router.post("/runs/{run_id}/retry", response_model=ImportRunCreateResponse)
def retry_import_stage(
    run_id: str,
    request: ImportStageRetryRequest,
    auth: None = Depends(require_auth),
) -> dict:
    del auth
    run = get_control_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Import run not found")
    if request.stage == "facts":
        if (
            run.get("publication_state") not in {"planned", "failed_before_facts"}
            or run.get("status") != "retryable_failed"
            or not run.get("retryable")
        ):
            raise HTTPException(status_code=409, detail="播放事实阶段不是可重试失败")
        threading.Thread(
            target=lambda: _execute_control_run_with_slot(
                run_id,
                str(run["batch_id"]),
                mode=run["requested_mode"],
                confirm_plan=str(run.get("strategy") or "") in {"reconcile", "replace"},
                confirmation_digest=str(run["confirmation_digest"]),
            ),
            daemon=True,
        ).start()
        return {"run_id": run_id, "created": False}
    attempts = {item["stage"]: item for item in latest_stage_attempts(run_id)}
    selected = attempts.get(request.stage)
    if selected is None:
        raise HTTPException(status_code=409, detail="该阶段没有可重试记录")
    if selected["status"] not in {"failed", "retryable_failed"} or not selected.get("retryable"):
        raise HTTPException(status_code=409, detail="该阶段不是可重试失败")
    payload = run.get("change_set")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=409, detail="该运行没有可恢复的 ChangeSet")
    try:
        change_set = PlaybackChangeSet.from_dict(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="恢复证据无效") from exc

    def retry_and_resume() -> None:
        if not _import_lock.acquire(blocking=False):
            return
        try:
            retried = run_import_stages(run_id, change_set, stages=(request.stage,))
            if retried.get("status") not in {
                "failed",
                "blocked",
                "superseded",
                "retryable_failed",
            }:
                run_import_stages(run_id, change_set)
        finally:
            _import_lock.release()

    threading.Thread(target=retry_and_resume, daemon=True).start()
    return {"run_id": run_id, "created": False}


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
    staging = take_cached_staging(confirmation_token)
    source_drift = False
    if staging is not None:
        try:
            staging.verify_source_manifest()
        except RuntimeError:
            source_drift = True
            staging.close()
            staging = None
    try:
        assessment = assess_streaming_import(
            DATA_DIR,
            ACCOUNT_DATA_DIR,
            requested_mode=requested_mode,
            staging=staging,
            retain_staging=True,
        )
    except Exception:
        if staging is not None:
            staging.close()
        raise
    preflight = assessment.report
    if preflight["blockers"]:
        _jobs[job_id].update(
            status="blocked",
            progress_pct=0.0,
            message="导入已阻断：导入前检查发现硬性问题，数据库未修改",
            result={"preflight": preflight, "import_started": False},
        )
        if assessment.staging is not None:
            assessment.staging.close()
        return None
    confirmation_required = confirm_warnings or confirm_plan
    confirmation_is_stale = source_drift or (
        confirmation_token is not None and confirmation_token != preflight.get("confirmation_token")
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
        if assessment.staging is not None:
            assessment.staging.close()
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
        if assessment.staging is not None:
            assessment.staging.close()
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
        if assessment.staging is not None:
            assessment.staging.close()
        return None
    if decision.action is ImportExecutionAction.BLOCKED:
        _jobs[job_id].update(
            status="blocked",
            progress_pct=0.0,
            message=decision.message,
            result={"preflight": preflight, "import_started": False},
        )
        if assessment.staging is not None:
            assessment.staging.close()
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
    executed_strategy: Literal["incremental", "reconcile", "full"],
    conn: sqlite3.Connection | None = None,
    publication_id: str | None = None,
    source_version_id: str | None = None,
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
    if executed_strategy in {"incremental", "reconcile"} and (
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
            if executed_strategy in {"full", "reconcile"}
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
            source_version_id=source_version_id,
            publication_id=publication_id,
            publication_state="facts_committed" if publication_id else "legacy",
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
    """Compatibility adapter onto immutable batches and durable executions."""
    del auth
    try:
        batch = freeze_local_batch(
            DATA_DIR,
            # The legacy directory contract is a complete export packet even
            # when the caller asks the planner to execute only its append tail.
            kind="snapshot",
        )
        batch_id = str(batch["batch_id"])
        assessment = assess_streaming_import(
            resolve_batch_directory(batch_id),
            ACCOUNT_DATA_DIR,
            requested_mode=mode,
            retain_staging=False,
        )
        expected_token = str(assessment.report.get("confirmation_token") or "")
        durable_confirmation = _batch_confirmation_token(
            batch_id,
            expected_token,
            mode=mode,
        )
        decision = resolve_import_execution(
            assessment.plan,
            requested_mode=mode,
            confirm_plan=confirm_plan,
        )
        execution_key = hashlib.sha256(
            f"{batch_id}\0{expected_token}\0{mode}\0{int(confirm_warnings)}\0"
            f"{int(confirm_plan)}\0{confirmation_token or ''}".encode()
        ).hexdigest()
        run_id, created = create_control_run(
            run_id=uuid.uuid4().hex[:12],
            execution_key=execution_key,
            batch_id=batch_id,
            confirmation_digest=durable_confirmation,
            requested_mode=mode,
            detected_relation=assessment.plan.relation.value,
            strategy=decision.action.value,
            baseline_reason_code=assessment.baseline_reason_code,
            plan=_plan_payload(assessment),
        )
        if not created:
            return {"job_id": run_id}
        stale = confirmation_token is not None and confirmation_token != expected_token
        needs_confirmation = (
            stale
            or ((confirm_warnings or confirm_plan) and confirmation_token is None)
            or bool(assessment.report["warnings"] and not confirm_warnings)
            or decision.action is ImportExecutionAction.NEEDS_CONFIRMATION
        )
        if assessment.report["blockers"]:
            update_control_run(
                run_id,
                status="blocked",
                publication_state="planned",
                message=decision.message or "导入前检查存在阻断项",
                error_code="preflight_blocked",
                result_json={"preflight": assessment.report, "import_started": False},
                completed_at=control_utc_now(),
            )
        elif needs_confirmation:
            update_control_run(
                run_id,
                status="needs_confirmation",
                publication_state="planned",
                message=(
                    "输入文件或当前数据已变化，请重新核对最新导入计划"
                    if stale
                    else "输入数据或导入计划需要重新确认"
                ),
                error_code="confirmation_required",
                result_json={
                    "preflight": assessment.report,
                    "import_started": False,
                    **({"confirmation_reason": "stale_plan"} if stale else {}),
                },
                completed_at=control_utc_now(),
            )
        elif decision.action is ImportExecutionAction.BLOCKED:
            update_control_run(
                run_id,
                status="blocked",
                publication_state="planned",
                message=decision.message,
                error_code="plan_blocked",
                result_json={"preflight": assessment.report, "import_started": False},
                completed_at=control_utc_now(),
            )
        else:
            threading.Thread(
                target=lambda: _execute_control_run_with_slot(
                    run_id,
                    batch_id,
                    mode=mode,
                    confirm_plan=confirm_plan,
                    confirmation_digest=durable_confirmation,
                ),
                daemon=True,
            ).start()
        return {"job_id": run_id}
    except ImportSourceError as exc:
        raise HTTPException(status_code=409, detail=exc.error_code) from exc


@router.post("/account", response_model=ImportJobCreateResponse)
def start_account_import(auth: None = Depends(require_auth)):
    """Trigger account data import in the background."""
    job_id = _make_job()
    cb = _progress_cb(job_id)

    def _run():
        snapshot = None
        publication_guard = None
        try:
            guard = exclusive_publication()
            guard.__enter__()
            publication_guard = guard
            snapshot = create_database_snapshot(job_id=job_id)
            result = import_all(progress_callback=cb)
            failed = [value for value in result.values() if str(value).startswith("error:")]
            if failed:
                raise RuntimeError("账号数据导入包含失败阶段：" + "；".join(failed))
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
        finally:
            if publication_guard is not None:
                publication_guard.__exit__(None, None, None)

    threading.Thread(target=lambda: _run_with_import_slot(job_id, _run), daemon=True).start()
    return {"job_id": job_id}


@router.get("/status/{job_id}", response_model=ImportJobStatus)
def get_import_status(job_id: str):
    """Query the status of an import job."""
    job = _jobs.get(job_id)
    if not job:
        durable = get_control_run(job_id)
        if durable is not None:
            status = str(durable["status"])
            legacy_status = (
                "done"
                if status == "succeeded"
                else "running"
                if status in {"pending", "running"}
                else "needs_confirmation"
                if status == "needs_confirmation"
                else "blocked"
                if status == "blocked"
                else "error"
            )
            return {
                "job_id": job_id,
                "status": legacy_status,
                "progress_pct": float(durable.get("progress_pct") or 0),
                "message": str(durable.get("message") or ""),
                "result": _public_result(durable.get("result")),
            }
        return {
            "job_id": job_id,
            "status": "not_found",
            "progress_pct": 0,
            "message": "Job not found",
        }
    return job
