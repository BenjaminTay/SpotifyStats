"""Fixed, generation-fenced post-import stage runner.

The existing maintenance implementation remains the deterministic core stage;
the runner adds durable attempts, a hard fact fence, health publication and
targeted retry without ever re-entering playback ETL.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import traceback
from collections.abc import Iterable
from typing import Any

from backend.core.db import get_db
from backend.domains.imports.change_set import PlaybackChangeSet
from backend.domains.imports.control_store import (
    finish_stage_attempt,
    get_run,
    latest_stage_attempts,
    pending_stage_runs,
    start_stage_attempt,
    supersede_other_runs,
    update_run,
    utc_now,
)
from backend.domains.imports.state import summarise_current_playback_dataset
from backend.services.import_maintenance_service import run_import_maintenance_stage

IMPORT_STAGES = (
    "metadata",
    "identity_merge",
    "album_project_l3",
    "billboard_aggregates",
    "candidate_index",
    "critical_prewarm",
    "cover_supplemental",
    "exact_snapshots",
)
_watchers: set[str] = set()
_watchers_lock = threading.Lock()


class ImportStageFenceError(RuntimeError):
    error_code = "stage_generation_drift"


_STAGE_DEPENDENCY_TABLES = {
    "metadata": (),
    "identity_merge": ("analysis_source_revisions",),
    "album_project_l3": (
        "track_identity_state",
        "analysis_source_revisions",
    ),
    "billboard_aggregates": (
        "track_identity_state",
        "album_project_revision_state",
        "l3_album_attribution_revision_state",
        "settings",
    ),
    "candidate_index": (
        "track_identity_state",
        "album_project_revision_state",
        "l3_album_attribution_revision_state",
        "music_search_revision_state",
        "settings",
    ),
    "critical_prewarm": (
        "track_identity_state",
        "album_project_revision_state",
        "l3_album_attribution_revision_state",
        "music_search_revision_state",
        "governance_source_revisions",
        "settings",
    ),
    "cover_supplemental": ("analysis_source_revisions",),
    "exact_snapshots": (
        "music_search_revision_state",
        "music_search_snapshot_variant_state",
        "music_search_year_end_projection_state",
        "settings",
    ),
}

_NON_SEMANTIC_DEPENDENCY_COLUMNS = {
    "updated_at",
}
_TABLE_NON_SEMANTIC_DEPENDENCY_COLUMNS = {
    "playback_import_state": {
        "active_publication_id",
        "active_source_version_id",
        "last_relation",
        "last_strategy",
        "publication_state",
    },
    "music_search_snapshot_variant_state": {
        "job_id",
        "last_error",
    },
    "music_search_year_end_projection_state": {
        "built_at",
        "last_error",
    },
}


def _stage_dependency_revision(stage: str) -> dict[str, Any]:
    """Return the declared, compact semantic dependency vector for a stage."""

    conn = get_db(readonly=True)
    try:
        tables = {
            str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        payload: dict[str, Any] = {"schema_version": 1, "stage": stage, "tables": {}}
        selected = ("playback_import_state", *_STAGE_DEPENDENCY_TABLES[stage])
        for table in selected:
            if table not in tables:
                payload["tables"][table] = None
                continue
            excluded = _NON_SEMANTIC_DEPENDENCY_COLUMNS | set(
                _TABLE_NON_SEMANTIC_DEPENDENCY_COLUMNS.get(table, ())
            )
            columns = [
                str(row[1])
                for row in conn.execute(f'PRAGMA table_info("{table}")')
                if str(row[1]) not in excluded
            ]
            if not columns:
                payload["tables"][table] = []
                continue
            quoted = ",".join(f'"{column}"' for column in columns)
            rows = [
                list(row)
                for row in conn.execute(
                    f'SELECT {quoted} FROM "{table}" ORDER BY {quoted}'
                ).fetchall()
            ]
            payload["tables"][table] = {"columns": columns, "rows": rows}
        canonical = json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        ).encode("utf-8")
        return {"schema_version": 1, "sha256": hashlib.sha256(canonical).hexdigest()}
    finally:
        conn.close()


def _background_job_status(conn: sqlite3.Connection, job_id: str | None) -> str | None:
    if not job_id:
        return None
    if (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='background_jobs'"
        ).fetchone()
        is None
    ):
        return None
    row = conn.execute("SELECT status FROM background_jobs WHERE job_id=?", (job_id,)).fetchone()
    return str(row[0]) if row is not None else None


def _classify_readiness(
    *,
    search_ready: bool,
    search_failed: bool,
    search_warming: bool,
    year_end_ready: bool,
    year_end_failed: bool,
    year_end_warming: bool,
    billboard_ready: bool,
    billboard_failed: bool,
    billboard_warming: bool,
) -> str:
    if search_failed or year_end_failed or billboard_failed:
        return "failed"
    if search_ready and year_end_ready and billboard_ready:
        return "ready"
    if (
        (not search_ready and not search_warming)
        or (not year_end_ready and not year_end_warming)
        or (not billboard_ready and not billboard_warming)
    ):
        return "unavailable"
    return "warming"


def _retryable_stage_error(exc: Exception) -> bool:
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    if isinstance(exc, sqlite3.OperationalError) and any(
        marker in str(exc).lower() for marker in ("locked", "busy")
    ):
        return True
    code = str(getattr(exc, "error_code", "")).lower()
    return any(
        marker in code
        for marker in (
            "timeout",
            "temporarily_unavailable",
            "provider_unavailable",
            "rate_limit",
            "resource_busy",
        )
    )


def _fact_fence(generation_id: str, dataset_digest: str) -> None:
    conn = get_db(readonly=True)
    try:
        row = conn.execute(
            """SELECT active_generation_id,dataset_digest
               FROM playback_import_state WHERE state_id=1"""
        ).fetchone()
        summary = summarise_current_playback_dataset(conn)
        if (
            row is None
            or str(row[0] or "") != generation_id
            or str(row[1] or "") != dataset_digest
            or summary.dataset_digest != dataset_digest
        ):
            raise ImportStageFenceError("active playback facts changed")
    finally:
        conn.close()


def _publish_main_state(generation_id: str, dataset_digest: str, state: str) -> None:
    conn = get_db(readonly=False)
    try:
        cursor = conn.execute(
            """UPDATE playback_import_state SET publication_state=?, updated_at=?
               WHERE state_id=1 AND active_generation_id=? AND dataset_digest=?""",
            (state, utc_now(), generation_id, dataset_digest),
        )
        if cursor.rowcount != 1:
            raise ImportStageFenceError("active playback facts changed")
        if state in {"core_ready", "ready"}:
            conn.execute(
                """UPDATE playback_import_runs
                   SET status='success', completed_at=COALESCE(completed_at, ?)
                   WHERE publication_id=(
                       SELECT active_publication_id
                       FROM playback_import_state WHERE state_id=1
                   ) AND status='maintenance_pending'""",
                (utc_now(),),
            )
        conn.commit()
    finally:
        conn.close()


def _run_stage(
    stage: str,
    *,
    run_id: str,
    change_set: PlaybackChangeSet,
    prior_outputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if stage == "exact_snapshots":
        return inspect_import_readiness(run_id)
    return run_import_maintenance_stage(stage, change_set, prior_outputs)


def _normalise_stage_evidence(
    stage: str,
    output: dict[str, Any],
    *,
    change_set: PlaybackChangeSet,
    active_record_count: int | None,
) -> dict[str, Any]:
    result = dict(output)
    problem_count = len(result.get("errors") or [])
    problem_count += int(result.get("blocker_count") or 0)
    scope = {
        "strategy": result.get("strategy") or change_set.strategy,
        "changed_records": change_set.added_count + change_set.removed_count,
        "changed_entities": change_set.entity_count,
        "affected_weeks": len(change_set.billboard_weeks),
        "affected_years": len(change_set.years),
    }
    result["evidence_contract"] = {
        "schema_version": 1,
        "stage": stage,
        "scope": scope,
        "denominator": {
            "active_record_count": active_record_count,
            "changed_record_count": change_set.added_count + change_set.removed_count,
        },
        "problem_count": problem_count,
        "affected_play_count": change_set.added_count + change_set.removed_count,
        "affected_ms": None,
    }
    return result


def inspect_import_readiness(run_id: str | None = None) -> dict[str, Any]:
    """Read exact Search, Year-End and Billboard publication state only."""

    from backend.domains.music_search.variants import build_music_search_variant_contexts
    from backend.domains.music_search.year_end_projection import year_end_projection_set_status
    from backend.services.billboard_snapshot_service import (
        billboard_default_snapshots_have_lkg,
        billboard_default_snapshots_ready,
    )
    from backend.services.music_search_maintenance_service import (
        _current_filter_values,
        _revalidated_snapshot_set_report,
    )

    conn = get_db(readonly=True)
    try:
        contexts = build_music_search_variant_contexts(conn, _current_filter_values(conn))
        search = _revalidated_snapshot_set_report(conn, contexts)
        year_end = year_end_projection_set_status(conn, contexts)
        variant_rows = (
            conn.execute(
                """SELECT maintenance_status,active_snapshot_key
                   FROM music_search_snapshot_variant_state"""
            ).fetchall()
            if conn.execute(
                """SELECT 1 FROM sqlite_master
                   WHERE type='table' AND name='music_search_snapshot_variant_state'"""
            ).fetchone()
            else []
        )
        candidate = (
            next(
                (
                    item.get("output_evidence") or {}
                    for item in latest_stage_attempts(run_id)
                    if item["stage"] == "candidate_index"
                ),
                {},
            )
            if run_id
            else {}
        )
        search_job_status = _background_job_status(conn, candidate.get("search_job_id"))
        billboard_job_status = _background_job_status(conn, candidate.get("billboard_job_id"))
    finally:
        conn.close()
    billboard_ready = billboard_default_snapshots_ready()
    billboard_lkg = billboard_default_snapshots_have_lkg()
    search_ready = search is not None and int(search.get("ready_count") or 0) == 4
    year_end_ready = (
        year_end.get("status") == "ready" and int(year_end.get("ready_count") or 0) == 4
    )
    search_failed = any(str(row[0]) == "failed" for row in variant_rows)
    search_lkg = len(variant_rows) == 4 and all(row[1] for row in variant_rows)
    search_warming = search_job_status in {"pending", "running"} and search_lkg
    billboard_failed = billboard_job_status == "failed"
    billboard_warming = billboard_job_status in {"pending", "running"} and billboard_lkg
    year_end_failed = any(
        variant.get("status") == "failed" for variant in year_end.get("variants", [])
    )
    year_end_warming = year_end.get("status") == "warming"
    build_in_progress = (
        search_job_status in {"pending", "running"}
        or billboard_job_status in {"pending", "running"}
        or any(
            variant.get("status") in {"pending", "running"}
            for variant in year_end.get("variants", [])
        )
    )
    status = _classify_readiness(
        search_ready=search_ready,
        search_failed=search_failed,
        search_warming=search_warming,
        year_end_ready=year_end_ready,
        year_end_failed=year_end_failed,
        year_end_warming=year_end_warming,
        billboard_ready=billboard_ready,
        billboard_failed=billboard_failed,
        billboard_warming=billboard_warming,
    )
    return {
        "status": status,
        "search_ready_count": int(search.get("ready_count") or 0) if search else 0,
        "search_expected_count": 4,
        "year_end_ready_count": int(year_end.get("ready_count") or 0),
        "year_end_expected_count": 4,
        "billboard_ready": billboard_ready,
        "billboard_job_status": billboard_job_status,
        "search_job_status": search_job_status,
        "build_in_progress": build_in_progress,
        "year_end": year_end,
    }


def reconcile_import_readiness(run_id: str) -> dict[str, Any]:
    run = get_run(run_id)
    if run is None:
        raise KeyError(run_id)
    generation_id = str(run.get("new_generation_id") or "")
    dataset_digest = str(run.get("new_dataset_digest") or "")
    _fact_fence(generation_id, dataset_digest)
    readiness = inspect_import_readiness(run_id)
    if readiness["status"] == "ready":
        dependency_revision = _stage_dependency_revision("exact_snapshots")
        attempt = start_stage_attempt(
            run_id,
            "exact_snapshots",
            generation_id,
            dataset_digest,
            dependency_revision=dependency_revision,
        )
        readiness["input_dependency_revision"] = dependency_revision
        readiness["validation_dependency_revision"] = _stage_dependency_revision("exact_snapshots")
        finish_stage_attempt(
            run_id,
            "exact_snapshots",
            attempt,
            status="succeeded",
            output=readiness,
            strategy="revalidated",
        )
        _publish_main_state(generation_id, dataset_digest, "ready")
        pending_retry = next(
            (
                item
                for item in latest_stage_attempts(run_id)
                if item["stage"] != "exact_snapshots"
                and item["status"] == "retryable_failed"
                and item.get("retryable")
            ),
            None,
        )
        update_run(
            run_id,
            status="retryable_failed" if pending_retry else "succeeded",
            publication_state="ready",
            progress_pct=1.0,
            completed_at=utc_now(),
            error_code=(str(pending_retry.get("error_code")) if pending_retry else None),
            error_detail=(
                "核心数据与精确快照已发布，但补充阶段仍可重试" if pending_retry else None
            ),
            retryable=int(pending_retry is not None),
            message=(
                "数据已发布，补充阶段仍可定点重试"
                if pending_retry
                else "导入完成，全部精确快照已发布"
            ),
        )
    elif readiness["status"] == "failed" or (
        readiness["status"] == "unavailable" and not readiness.get("build_in_progress")
    ):
        dependency_revision = _stage_dependency_revision("exact_snapshots")
        attempt = start_stage_attempt(
            run_id,
            "exact_snapshots",
            generation_id,
            dataset_digest,
            dependency_revision=dependency_revision,
        )
        readiness["input_dependency_revision"] = dependency_revision
        readiness["validation_dependency_revision"] = _stage_dependency_revision("exact_snapshots")
        finish_stage_attempt(
            run_id,
            "exact_snapshots",
            attempt,
            status="failed",
            output=readiness,
            strategy="revalidated",
            error_code=(
                "exact_snapshot_unavailable"
                if readiness["status"] == "unavailable"
                else "exact_snapshot_failed"
            ),
            retryable=True,
        )
        update_run(
            run_id,
            status="retryable_failed",
            publication_state="core_ready",
            error_code=(
                "exact_snapshot_unavailable"
                if readiness["status"] == "unavailable"
                else "exact_snapshot_failed"
            ),
            error_detail="Search、Year-End 或 Billboard 精确快照未能进入可恢复构建态",
            retryable=1,
            completed_at=utc_now(),
            message="核心数据可用，但精确快照构建失败",
        )
    else:
        update_run(
            run_id,
            status="running",
            publication_state="core_ready",
            progress_pct=0.95,
            completed_at=None,
            message="核心数据可用，精确快照正在后台构建",
        )
    return readiness


def _watch_readiness(run_id: str) -> None:
    try:
        while True:
            run = get_run(run_id)
            if run is None or run.get("status") in {"succeeded", "superseded", "blocked"}:
                return
            try:
                result = reconcile_import_readiness(run_id)
            except ImportStageFenceError:
                update_run(
                    run_id,
                    status="superseded",
                    publication_state="superseded",
                    error_code="stage_generation_drift",
                    completed_at=utc_now(),
                    message="运行目标已被新一代播放事实取代",
                )
                return
            if result["status"] in {"ready", "failed"} or (
                result["status"] == "unavailable" and not result.get("build_in_progress")
            ):
                return
            time.sleep(2)
    finally:
        with _watchers_lock:
            _watchers.discard(run_id)


def start_import_readiness_watcher(run_id: str) -> None:
    with _watchers_lock:
        if run_id in _watchers:
            return
        _watchers.add(run_id)
    threading.Thread(target=_watch_readiness, args=(run_id,), daemon=True).start()


def run_import_stages(
    run_id: str,
    change_set: PlaybackChangeSet,
    *,
    stages: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Run or retry fixed stages behind generation/digest fences."""

    run = get_run(run_id)
    if run is None:
        raise KeyError(run_id)
    generation_id = str(run.get("new_generation_id") or change_set.generation_id)
    dataset_digest = str(run.get("new_dataset_digest") or "")
    if not dataset_digest:
        raise ImportStageFenceError("stage dataset digest is missing")
    requested = tuple(stages or IMPORT_STAGES)
    force = stages is not None
    if any(stage not in IMPORT_STAGES for stage in requested):
        raise ValueError("unsupported import stage retry")
    attempts = latest_stage_attempts(run_id)
    prior_outputs: dict[str, dict[str, Any]] = {}
    for item in attempts:
        evidence = item.get("output_evidence")
        if item["status"] != "succeeded" or not isinstance(evidence, dict):
            continue
        if evidence.get("validation_dependency_revision") == _stage_dependency_revision(
            str(item["stage"])
        ):
            prior_outputs[str(item["stage"])] = evidence
    degraded: dict[str, dict[str, Any]] = {}
    supersede_other_runs(run_id, generation_id)
    update_run(run_id, status="running", message="正在恢复导入后处理")
    for stage in requested:
        _fact_fence(generation_id, dataset_digest)
        if not force and stage in prior_outputs:
            continue
        input_dependency_revision = _stage_dependency_revision(stage)
        attempt = start_stage_attempt(
            run_id,
            stage,
            generation_id,
            dataset_digest,
            dependency_revision=input_dependency_revision,
        )
        try:
            output = _run_stage(
                stage,
                run_id=run_id,
                change_set=change_set,
                prior_outputs=prior_outputs,
            )
            _fact_fence(generation_id, dataset_digest)
            output = _normalise_stage_evidence(
                stage,
                output,
                change_set=change_set,
                active_record_count=(run.get("result") or {}).get("active_records"),
            )
            output["input_dependency_revision"] = input_dependency_revision
            output["validation_dependency_revision"] = _stage_dependency_revision(stage)
        except Exception as exc:
            retryable = _retryable_stage_error(exc)
            status = (
                "superseded"
                if isinstance(exc, ImportStageFenceError)
                else "retryable_failed"
                if retryable
                else "failed"
            )
            error_code = getattr(
                exc,
                "error_code",
                "stage_resource_busy" if retryable else f"{stage}_failed",
            )
            finish_stage_attempt(
                run_id,
                stage,
                attempt,
                status=status,
                error_code=str(error_code),
                error_detail=traceback.format_exc(limit=20),
                retryable=retryable,
            )
            if stage == "cover_supplemental":
                prior_outputs[stage] = {
                    "status": "failed",
                    "error_code": str(error_code),
                    "supplemental": True,
                }
                continue
            update_run(
                run_id,
                status=status,
                publication_state=(
                    "superseded"
                    if status == "superseded"
                    else str(run.get("publication_state") or "sources_published")
                ),
                error_code=str(error_code),
                error_detail=str(exc),
                retryable=int(retryable),
                completed_at=utc_now(),
                message=f"阶段 {stage} 失败",
            )
            return {"status": status, "stage": stage, "error_code": str(error_code)}
        active_unavailable_build = (
            stage == "exact_snapshots"
            and output.get("status") == "unavailable"
            and bool(output.get("build_in_progress"))
        )
        if output.get("status") == "failed" or (
            output.get("status") == "unavailable" and not active_unavailable_build
        ):
            error_code = str(output.get("error_code") or f"{stage}_failed")
            finish_stage_attempt(
                run_id,
                stage,
                attempt,
                status="retryable_failed",
                output=output,
                strategy=str(output.get("strategy") or "revalidated"),
                fallback_reason=output.get("fallback_reason"),
                error_code=error_code,
                error_detail=str(output.get("message") or "阶段输出明确标记为失败"),
                retryable=True,
            )
            publication_state = (
                "core_ready"
                if "critical_prewarm" in prior_outputs
                else str(run.get("publication_state") or "sources_published")
            )
            update_run(
                run_id,
                status="retryable_failed",
                publication_state=publication_state,
                error_code=error_code,
                error_detail=str(output.get("message") or "阶段输出明确标记为失败"),
                retryable=1,
                completed_at=utc_now(),
                message=f"阶段 {stage} 失败，可定点重试",
            )
            return {"status": "retryable_failed", "stage": stage, "error_code": error_code}
        if output.get("status") == "partial":
            error_code = "metadata_provider_unavailable"
            finish_stage_attempt(
                run_id,
                stage,
                attempt,
                status="retryable_failed",
                output=output,
                strategy=str(output.get("strategy") or "targeted"),
                error_code=error_code,
                error_detail="外部元数据仅部分完成，可定点重试",
                retryable=True,
            )
            degraded[stage] = output
            prior_outputs[stage] = output
            continue
        attempt_status = (
            "warming"
            if output.get("status") == "warming" or active_unavailable_build
            else "succeeded"
        )
        finish_stage_attempt(
            run_id,
            stage,
            attempt,
            status=attempt_status,
            output=output,
            strategy=str(output.get("strategy") or "verified"),
            fallback_reason=output.get("fallback_reason"),
        )
        if attempt_status == "succeeded":
            prior_outputs[stage] = output
        if stage == "critical_prewarm":
            _publish_main_state(generation_id, dataset_digest, "core_ready")
            update_run(
                run_id,
                publication_state="core_ready",
                progress_pct=0.9,
                message="核心播放统计已可用",
            )
    exact = prior_outputs.get("exact_snapshots") or (
        output if requested and requested[-1] == "exact_snapshots" else {}
    )
    ready = exact.get("status") == "ready"
    core_ready = "critical_prewarm" in prior_outputs
    publication_state = "ready" if ready else "core_ready" if core_ready else "sources_published"
    if ready:
        _publish_main_state(generation_id, dataset_digest, "ready")
    task_status = "retryable_failed" if degraded else "succeeded" if ready else "running"
    update_run(
        run_id,
        status=task_status,
        publication_state=publication_state,
        progress_pct=1.0 if ready else 0.95 if core_ready else 0.7,
        completed_at=utc_now() if ready else None,
        error_code="metadata_provider_unavailable" if degraded else None,
        error_detail="外部元数据仅部分完成，可定点重试" if degraded else None,
        retryable=int(bool(degraded)),
        message=(
            "导入完成"
            if ready
            else "数据已更新，精确快照正在后台构建"
            if core_ready
            else "阶段已重试，后续核心阶段仍待恢复"
        ),
        result_json={
            **(run.get("result") or {}),
            "maintenance": {**prior_outputs, "exact_snapshots": exact},
        },
    )
    if core_ready and not ready:
        start_import_readiness_watcher(run_id)
    return {"status": task_status, "stages": prior_outputs, "degraded": degraded}


def resume_pending_import_stages() -> dict[str, int]:
    """Resume source-published runs before generic background writers start."""

    report = {"resumed": 0, "blocked": 0}
    for run in pending_stage_runs():
        payload = run.get("change_set")
        if not isinstance(payload, dict):
            update_run(
                str(run["run_id"]),
                status="blocked",
                publication_state="recovery_blocked",
                error_code="recovery_change_set_missing",
                completed_at=utc_now(),
            )
            report["blocked"] += 1
            continue
        try:
            change_set = PlaybackChangeSet.from_dict(payload)
            run_import_stages(str(run["run_id"]), change_set)
            if run.get("publication_state") == "core_ready":
                start_import_readiness_watcher(str(run["run_id"]))
            report["resumed"] += 1
        except Exception as exc:
            update_run(
                str(run["run_id"]),
                status="blocked",
                publication_state="recovery_blocked",
                error_code=getattr(exc, "error_code", "stage_recovery_failed"),
                error_detail=str(exc),
                completed_at=utc_now(),
            )
            report["blocked"] += 1
    return report
