"""Service layer for durable AI task status, events, and cancellation."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from backend.core.db import get_db
from backend.domains.ai_reports.visual_artifact_models import VISUAL_YEARLY_REPORT_MODE
from backend.domains.ai_tasks.repository import AiTaskRepository
from backend.services import ai_insights_service, wikipedia_service

logger = logging.getLogger(__name__)

TaskHandler = Callable[[str, dict[str, Any]], None]
TERMINAL_STATUSES = {"done", "error", "cancelled"}
ENRICHMENT_PROGRESS_BY_STAGE = {
    "checking_cache": 0.1,
    "fetching_external_data": 0.4,
    "calling_llm": 0.75,
    "saving_cache": 0.9,
}
_AGENTIC_STAGE_PROGRESS = {
    "researching": 0.25,
    "synthesizing_insights": 0.45,
    "outlining": 0.6,
    "drafting": 0.75,
    "critic_review": 0.85,
    "building_narrative_brief": 0.48,
    "planning_visuals": 0.58,
    "building_chart_data": 0.68,
    "composing_artifact": 0.78,
    "reviewing_visual_artifact": 0.88,
}


def new_task_id() -> str:
    return uuid.uuid4().hex[:12]


def get_task(task_id: str) -> dict[str, Any] | None:
    conn = get_db(readonly=True)
    try:
        return AiTaskRepository(conn).get_run(task_id)
    finally:
        conn.close()


def get_task_events(
    task_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    conn = get_db(readonly=True)
    try:
        repo = AiTaskRepository(conn)
        if repo.get_run(task_id) is None:
            return None
        return repo.list_events(task_id), repo.list_tool_calls(task_id)
    finally:
        conn.close()


def create_task(
    *,
    task_type: str,
    stage: str,
    message: str,
    request: dict[str, Any],
    handler: TaskHandler | None = None,
) -> dict[str, Any]:
    task_id = new_task_id()
    conn = get_db(readonly=False)
    try:
        repo = AiTaskRepository(conn)
        repo.create_run(
            task_id=task_id,
            task_type=task_type,
            status="queued",
            stage=stage,
            message=message,
            request=request,
        )
        repo.add_event(
            task_id=task_id,
            event_type="stage_started",
            stage=stage,
            message=message,
            payload=None,
        )
    finally:
        conn.close()

    if handler is not None:
        thread = threading.Thread(
            target=_run_handler_safely,
            args=(task_id, request, handler),
            daemon=True,
        )
        thread.start()

    return {
        "task_id": task_id,
        "task_type": task_type,
        "status": "queued",
        "stage": stage,
        "progress_pct": 0.0,
        "message": message,
        "result": None,
    }


def _run_handler_safely(
    task_id: str,
    request: dict[str, Any],
    handler: TaskHandler,
) -> None:
    try:
        handler(task_id, request)
    except Exception as exc:
        mark_task_error(task_id, exc)


def mark_task_done(
    task_id: str,
    *,
    stage: str = "done",
    message: str = "任务已完成",
    result: dict[str, Any] | None = None,
) -> None:
    payload = result or {}
    conn = get_db(readonly=False)
    try:
        repo = AiTaskRepository(conn)
        updated = repo.update_run_if_not_terminal(
            task_id=task_id,
            status="done",
            stage=stage,
            progress_pct=1.0,
            message=message,
            result=payload,
        )
        if not updated:
            return
        repo.add_event(
            task_id=task_id,
            event_type="result_ready",
            stage=stage,
            message=message,
            payload=payload,
        )
    finally:
        conn.close()


def mark_task_error(task_id: str, exc: Exception) -> None:
    error_message = str(exc) or exc.__class__.__name__
    message = f"任务执行失败：{error_message}"
    conn = get_db(readonly=False)
    try:
        repo = AiTaskRepository(conn)
        updated = repo.update_run_if_not_terminal(
            task_id=task_id,
            status="error",
            stage="error",
            progress_pct=1.0,
            message=message,
            result=None,
            error=error_message,
        )
        if not updated:
            return
        repo.add_event(
            task_id=task_id,
            event_type="stage_failed",
            stage="error",
            message=message,
            payload={"error": error_message},
        )
    finally:
        conn.close()


def _task_type_for_report(report_type: str) -> str:
    return {
        "weekly": "ai_report_weekly",
        "monthly": "ai_report_monthly",
        "yearly": "ai_report_yearly",
    }[report_type]


def _should_use_agentic_yearly_report(request: dict[str, Any]) -> bool:
    return (
        request.get("report_type") == "yearly"
        and request.get("report_mode", "agentic_longform") == "agentic_longform"
    )


def _should_use_visual_yearly_artifact(request: dict[str, Any]) -> bool:
    return (
        request.get("report_type") == "yearly"
        and request.get("report_mode", "visual_yearly_artifact") == "visual_yearly_artifact"
    )


def peek_report_cache(request: dict[str, Any]) -> dict[str, Any]:
    conn = get_db(readonly=True)
    try:
        cached = ai_insights_service.peek_report_cache(
            conn,
            request["report_type"],
            min_ms=request.get("min_ms", 30000),
            music_only=request.get("music_only", True),
            merge_enabled=request.get("merge_enabled", True),
            dynamic_threshold=request.get("dynamic_threshold", True),
            max_merge_gap_minutes=request.get("max_merge_gap_minutes"),
            report_mode=VISUAL_YEARLY_REPORT_MODE
            if _should_use_visual_yearly_artifact(request)
            else None,
            week_start=request.get("week_start"),
            week_end=request.get("week_end"),
            month=request.get("month"),
            year=request.get("year"),
        )
        if _should_use_visual_yearly_artifact(request):
            return _visual_yearly_cache_result(cached)
        return {**cached, "needs_generation": not cached["cached"]}
    finally:
        conn.close()


def start_report_task(request: dict[str, Any]) -> dict[str, Any]:
    report_type = request["report_type"]
    action = request.get("action", "cache_only")
    if action == "cache_only":
        result = peek_report_cache(request)
        task_id = new_task_id()
        conn = get_db(readonly=False)
        try:
            repo = AiTaskRepository(conn)
            repo.create_run(
                task_id=task_id,
                task_type=_task_type_for_report(report_type),
                status="done",
                stage="done",
                message="缓存检查完成",
                request=request,
            )
            repo.add_event(
                task_id=task_id,
                event_type="cache_hit" if result["cached"] else "stage_completed",
                stage="checking_cache",
                message="命中报告缓存" if result["cached"] else "未找到报告缓存",
                payload={"cached": result["cached"]},
            )
            repo.update_run(
                task_id=task_id,
                status="done",
                stage="done",
                progress_pct=1.0,
                message="缓存检查完成",
                result=result,
            )
            repo.add_event(
                task_id=task_id,
                event_type="result_ready",
                stage="done",
                message="缓存检查完成",
                payload={"cached": result["cached"]},
            )
        finally:
            conn.close()
        return {
            "task_id": task_id,
            "task_type": _task_type_for_report(report_type),
            "status": "done",
            "stage": "done",
            "progress_pct": 1.0,
            "message": "缓存检查完成",
            "result": result,
        }

    return create_task(
        task_type=_task_type_for_report(report_type),
        stage="checking_cache",
        message="准备生成 AI 报告",
        request=request,
        handler=run_report_generation_task,
    )


def start_chat_agent_task(request: dict[str, Any]) -> dict[str, Any]:
    from backend.services.ai_agent_service import run_chat_agent_task

    return create_task(
        task_type="ai_chat_agent",
        stage="queued",
        message="准备启动 Agent Chat",
        request=request,
        handler=run_chat_agent_task,
    )


def start_artist_enrichment_task(request: dict[str, Any]) -> dict[str, Any]:
    return create_task(
        task_type="ai_enrichment_artist",
        stage="checking_cache",
        message="准备获取艺人百科资料",
        request=request,
        handler=run_artist_enrichment_task,
    )


def start_album_enrichment_task(request: dict[str, Any]) -> dict[str, Any]:
    return create_task(
        task_type="ai_enrichment_album",
        stage="checking_cache",
        message="准备获取专辑百科资料",
        request=request,
        handler=run_album_enrichment_task,
    )


def _set_task_stage(
    repo: AiTaskRepository,
    *,
    task_id: str,
    stage: str,
    progress_pct: float,
    message: str,
    event_type: str = "stage_started",
    payload: dict[str, Any] | None = None,
) -> bool:
    updated = repo.update_run_if_not_terminal(
        task_id=task_id,
        status="running",
        stage=stage,
        progress_pct=progress_pct,
        message=message,
    )
    if not updated:
        return False
    repo.add_event(
        task_id=task_id,
        event_type=event_type,
        stage=stage,
        message=message,
        payload=payload,
    )
    return True


def _mark_report_task_error(
    repo: AiTaskRepository,
    *,
    task_id: str,
    message: str,
    result: dict[str, Any] | None = None,
) -> None:
    updated = repo.update_run_if_not_terminal(
        task_id=task_id,
        status="error",
        stage="error",
        progress_pct=1.0,
        message=message,
        result=result,
        error=message,
    )
    if not updated:
        return
    repo.add_event(
        task_id=task_id,
        event_type="stage_failed",
        stage="error",
        message=message,
        payload=result or {"error": message},
    )


def _event_type_for_enrichment_progress(stage: str, message: str) -> str:
    if stage == "checking_cache" and ("命中" in message or "cache hit" in message.lower()):
        return "cache_hit"
    if stage == "saving_cache":
        return "stage_completed"
    return "stage_started"


def _set_enrichment_progress(
    repo: AiTaskRepository,
    *,
    task_id: str,
    stage: str,
    message: str,
) -> bool:
    return _set_task_stage(
        repo,
        task_id=task_id,
        stage=stage,
        progress_pct=ENRICHMENT_PROGRESS_BY_STAGE.get(stage, 0.5),
        message=message,
        event_type=_event_type_for_enrichment_progress(stage, message),
    )


def _mark_task_error_with_repo(
    repo: AiTaskRepository,
    *,
    task_id: str,
    message: str,
) -> None:
    updated = repo.update_run_if_not_terminal(
        task_id=task_id,
        status="error",
        stage="error",
        progress_pct=1.0,
        message=f"任务执行失败：{message}",
        result=None,
        error=message,
    )
    if not updated:
        return
    repo.add_event(
        task_id=task_id,
        event_type="stage_failed",
        stage="error",
        message=f"任务执行失败：{message}",
        payload={"error": message},
    )


def _complete_enrichment_task(
    repo: AiTaskRepository,
    *,
    task_id: str,
    message: str,
    wiki: dict[str, Any] | None,
) -> None:
    result = {"wiki": wiki, "genius": None}
    updated = repo.update_run_if_not_terminal(
        task_id=task_id,
        status="done",
        stage="done",
        progress_pct=1.0,
        message=message,
        result=result,
    )
    if not updated:
        return
    repo.add_event(
        task_id=task_id,
        event_type="result_ready",
        stage="done",
        message=message,
        payload=result,
    )


def run_artist_enrichment_task(task_id: str, request: dict[str, Any]) -> None:
    conn = get_db(readonly=False)
    try:
        repo = AiTaskRepository(conn)

        def progress_callback(stage: str, message: str) -> None:
            _set_enrichment_progress(repo, task_id=task_id, stage=stage, message=message)

        def should_continue() -> bool:
            task = repo.get_run(task_id)
            return task is not None and task.get("status") not in TERMINAL_STATUSES

        try:
            wiki = wikipedia_service.get_artist_wiki(
                request["artist_name"],
                progress_callback=progress_callback,
                should_continue=should_continue,
            )
        except Exception as exc:
            _mark_task_error_with_repo(
                repo,
                task_id=task_id,
                message=str(exc) or exc.__class__.__name__,
            )
            return

        _complete_enrichment_task(
            repo,
            task_id=task_id,
            message="艺人百科资料获取完成",
            wiki=wiki,
        )
    finally:
        conn.close()


def run_album_enrichment_task(task_id: str, request: dict[str, Any]) -> None:
    conn = get_db(readonly=False)
    try:
        repo = AiTaskRepository(conn)

        def progress_callback(stage: str, message: str) -> None:
            _set_enrichment_progress(repo, task_id=task_id, stage=stage, message=message)

        def should_continue() -> bool:
            task = repo.get_run(task_id)
            return task is not None and task.get("status") not in TERMINAL_STATUSES

        try:
            wiki = wikipedia_service.get_album_wiki(
                request["album_name"],
                request["artist_name"],
                progress_callback=progress_callback,
                should_continue=should_continue,
            )
        except Exception as exc:
            _mark_task_error_with_repo(
                repo,
                task_id=task_id,
                message=str(exc) or exc.__class__.__name__,
            )
            return

        _complete_enrichment_task(
            repo,
            task_id=task_id,
            message="专辑百科资料获取完成",
            wiki=wiki,
        )
    finally:
        conn.close()


def _run_report_generator(
    conn: sqlite3.Connection,
    request: dict[str, Any],
    *,
    progress_callback: Callable[[str, float, str], bool] | None = None,
    should_continue: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    report_type = request["report_type"]
    min_ms = request.get("min_ms", 30000)
    music_only = request.get("music_only", True)
    merge_enabled = request.get("merge_enabled", True)
    force = request.get("force", False)
    dynamic_threshold = request.get("dynamic_threshold", True)
    max_merge_gap_minutes = request.get("max_merge_gap_minutes")

    if report_type == "weekly":
        return ai_insights_service.generate_weekly_digest(
            conn,
            min_ms,
            music_only,
            merge_enabled,
            request.get("week_start") or "",
            request.get("week_end") or "",
            force=force,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
            cache_result=False,
            progress_callback=progress_callback,
            should_continue=should_continue,
        )
    if report_type == "monthly":
        return ai_insights_service.generate_monthly_personality(
            conn,
            min_ms,
            music_only,
            merge_enabled,
            request.get("month") or "",
            request.get("year") or 0,
            force=force,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
            cache_result=False,
            progress_callback=progress_callback,
            should_continue=should_continue,
        )
    if _should_use_visual_yearly_artifact(request):
        from backend.domains.ai_reports.visual_yearly_artifact_service import (
            generate_visual_yearly_artifact,
        )

        def emit_event(
            event_type: str,
            message: str,
            payload: dict[str, Any] | None = None,
        ) -> None:
            del event_type
            event_payload = payload or {}
            stage = str(event_payload.get("stage") or "building_narrative_brief")
            progress = float(
                event_payload.get("progress_pct") or _AGENTIC_STAGE_PROGRESS.get(stage, 0.5)
            )
            if progress_callback is not None:
                progress_callback(stage, progress, message)

        return generate_visual_yearly_artifact(request, emit_event=emit_event)
    if _should_use_agentic_yearly_report(request):
        from backend.services.yearly_report_agent_service import generate_agentic_yearly_report

        def emit_event(
            event_type: str,
            message: str,
            payload: dict[str, Any] | None = None,
        ) -> None:
            del event_type
            event_payload = payload or {}
            stage = str(event_payload.get("stage") or "researching")
            progress = float(
                event_payload.get("progress_pct") or _AGENTIC_STAGE_PROGRESS.get(stage, 0.5)
            )
            if progress_callback is not None:
                progress_callback(stage, progress, message)

        return generate_agentic_yearly_report(request, emit_event=emit_event)
    return ai_insights_service.generate_yearly_story(
        conn,
        min_ms,
        music_only,
        merge_enabled,
        request.get("year") or 0,
        force=force,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        cache_result=False,
        progress_callback=progress_callback,
        should_continue=should_continue,
    )


def _write_report_cache_from_task_result(
    conn: sqlite3.Connection,
    request: dict[str, Any],
    result: dict[str, Any],
    *,
    fetched_at: str | None = None,
) -> None:
    if result.get("cached") or (not result.get("report") and not result.get("artifact")):
        return
    try:
        if _should_use_visual_yearly_artifact(request):
            if not result.get("artifact"):
                return
            payload = json.dumps(
                _visual_yearly_cache_payload(result, cached_at=fetched_at),
                ensure_ascii=False,
            )
            ai_insights_service.store_report_cache(
                conn,
                request["report_type"],
                payload,
                min_ms=request.get("min_ms", 30000),
                music_only=request.get("music_only", True),
                merge_enabled=request.get("merge_enabled", True),
                dynamic_threshold=request.get("dynamic_threshold", True),
                max_merge_gap_minutes=request.get("max_merge_gap_minutes"),
                report_mode=VISUAL_YEARLY_REPORT_MODE,
                week_start=request.get("week_start"),
                week_end=request.get("week_end"),
                month=request.get("month"),
                year=request.get("year"),
                commit=False,
                fetched_at=fetched_at,
            )
            return
        ai_insights_service.store_report_cache(
            conn,
            request["report_type"],
            result["report"],
            min_ms=request.get("min_ms", 30000),
            music_only=request.get("music_only", True),
            merge_enabled=request.get("merge_enabled", True),
            dynamic_threshold=request.get("dynamic_threshold", True),
            max_merge_gap_minutes=request.get("max_merge_gap_minutes"),
            week_start=request.get("week_start"),
            week_end=request.get("week_end"),
            month=request.get("month"),
            year=request.get("year"),
            commit=False,
            fetched_at=fetched_at,
        )
    except sqlite3.Error:
        logger.warning("AI report task cache write failed", exc_info=True)


def _visual_yearly_cache_payload(
    result: dict[str, Any],
    *,
    cached_at: str | None = None,
) -> dict[str, Any]:
    return {
        "success": bool(result.get("success", True)),
        "report": result.get("report"),
        "artifact": result.get("artifact"),
        "cached": False,
        "cached_at": cached_at,
        "entities": result.get("entities"),
        "metadata": result.get("metadata"),
        "critic": result.get("critic"),
        "fact_validation": result.get("fact_validation"),
        "evidence_ledger": result.get("evidence_ledger"),
        "error": result.get("error"),
    }


def _report_result_is_cacheable(result: dict[str, Any]) -> bool:
    return bool((not result.get("cached")) and (result.get("report") or result.get("artifact")))


def _report_cache_write_timestamp() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0).isoformat(sep=" ")


def _report_task_result_with_cached_at(
    result: dict[str, Any],
    cached_at: str | None,
) -> dict[str, Any]:
    if not cached_at:
        return result
    return {**result, "cached_at": cached_at}


def _visual_yearly_cache_result(cached: dict[str, Any]) -> dict[str, Any]:
    if not cached.get("cached"):
        return {
            "success": True,
            "report": None,
            "artifact": None,
            "cached": False,
            "cached_at": None,
            "entities": None,
            "metadata": None,
            "error": None,
            "needs_generation": True,
        }
    try:
        payload = json.loads(str(cached.get("report") or ""))
    except json.JSONDecodeError:
        logger.warning("Invalid visual yearly report cache payload")
        return {
            "success": True,
            "report": None,
            "artifact": None,
            "cached": False,
            "cached_at": None,
            "entities": None,
            "metadata": None,
            "error": None,
            "needs_generation": True,
        }
    if not isinstance(payload, dict) or not isinstance(payload.get("artifact"), dict):
        return {
            "success": True,
            "report": None,
            "artifact": None,
            "cached": False,
            "cached_at": None,
            "entities": None,
            "metadata": None,
            "error": None,
            "needs_generation": True,
        }
    return {
        **payload,
        "cached": True,
        "cached_at": cached.get("cached_at"),
        "needs_generation": False,
    }


def _persist_report_tool_calls(
    repo: AiTaskRepository,
    *,
    task_id: str,
    result: dict[str, Any],
) -> None:
    metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
    source_range = str(metadata.get("data_range") or "")
    for entry in result.get("evidence_ledger") or []:
        if not isinstance(entry, dict):
            continue
        repo.add_tool_call(
            task_id=task_id,
            tool_name=str(entry.get("tool_name") or ""),
            status="done",
            params_summary=json.dumps(entry.get("params") or {}, ensure_ascii=False),
            result_summary=str(entry.get("result_summary") or ""),
            source_range=source_range,
        )


def run_report_generation_task(task_id: str, request: dict[str, Any]) -> None:
    conn = get_db(readonly=False)
    try:
        repo = AiTaskRepository(conn)
        if not _set_task_stage(
            repo,
            task_id=task_id,
            stage="checking_cache",
            progress_pct=0.1,
            message="正在检查报告缓存",
            event_type="stage_completed",
        ):
            return
        if not _set_task_stage(
            repo,
            task_id=task_id,
            stage="gathering_local_data",
            progress_pct=0.35,
            message="正在汇总本地播放数据",
        ):
            return

        def report_progress(stage: str, progress_pct: float, message: str) -> bool:
            return _set_task_stage(
                repo,
                task_id=task_id,
                stage=stage,
                progress_pct=progress_pct,
                message=message,
            )

        def should_continue() -> bool:
            task = repo.get_run(task_id)
            return task is not None and task.get("status") not in TERMINAL_STATUSES

        try:
            result = _run_report_generator(
                conn,
                request,
                progress_callback=report_progress,
                should_continue=should_continue,
            )
        except Exception as exc:
            _mark_report_task_error(
                repo,
                task_id=task_id,
                message=str(exc) or exc.__class__.__name__,
            )
            return

        metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
        if metadata.get("report_mode") in {"agentic_longform", "visual_yearly_artifact"}:
            _persist_report_tool_calls(repo, task_id=task_id, result=result)

        if result.get("success"):
            cache_written_at = (
                _report_cache_write_timestamp() if _report_result_is_cacheable(result) else None
            )
            task_result = _report_task_result_with_cached_at(result, cache_written_at)
            if not result.get("cached"):
                if not _set_task_stage(
                    repo,
                    task_id=task_id,
                    stage="saving_cache",
                    progress_pct=0.9,
                    message="正在保存报告缓存",
                ):
                    return

            updated = repo.update_run_if_not_terminal_with_write(
                task_id=task_id,
                status="done",
                stage="done",
                progress_pct=1.0,
                message="报告生成完成",
                result=task_result,
                write=lambda active_conn: _write_report_cache_from_task_result(
                    active_conn,
                    request,
                    task_result,
                    fetched_at=cache_written_at,
                ),
            )
            if not updated:
                return
            repo.add_event(
                task_id=task_id,
                event_type="result_ready",
                stage="done",
                message="报告生成完成",
                payload={
                    "cached": task_result.get("cached", False),
                    "cached_at": task_result.get("cached_at"),
                },
            )
            return

        error_message = result.get("error") or "报告生成失败"
        _mark_report_task_error(
            repo,
            task_id=task_id,
            message=error_message,
            result=result,
        )
    finally:
        conn.close()


def cancel_task(task_id: str) -> dict[str, Any] | None:
    conn = get_db(readonly=False)
    try:
        repo = AiTaskRepository(conn)
        task = repo.get_run(task_id)
        if task is None:
            return None
        if task["status"] in TERMINAL_STATUSES:
            return task

        updated = repo.update_run_if_not_terminal(
            task_id=task_id,
            status="cancelled",
            stage="cancelled",
            progress_pct=float(task.get("progress_pct") or 0.0),
            message="任务已取消",
            result=None,
            error=None,
        )
        if not updated:
            return repo.get_run(task_id)
        repo.add_event(
            task_id=task_id,
            event_type="stage_completed",
            stage="cancelled",
            message="任务已取消",
            payload=None,
        )
        return repo.get_run(task_id)
    finally:
        conn.close()
