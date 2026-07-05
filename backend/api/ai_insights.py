"""AI Insights API endpoints."""

# ruff: noqa: UP045

from __future__ import annotations

import json
from sqlite3 import Connection
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.dependencies import PlayFilters, get_conn
from backend.services import ai_insights_service
from backend.services.ai_insights_service import (
    answer_question,
    generate_monthly_personality,
    generate_weekly_digest,
    generate_yearly_story,
    get_suggested_questions,
)

router = APIRouter(prefix="/ai-insights", tags=["AI Insights"])


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=2000)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    conversation_history: Optional[list[ChatMessage]] = None


# ── Response models ──────────────────────────────────────────────────────────


class ReportEntities(BaseModel):
    artists: list[str] = []
    tracks: list[str] = []


class DigestResponse(BaseModel):
    success: bool
    report: Optional[str] = None
    artifact: Optional[dict[str, Any]] = None
    cached: bool = False
    cached_at: Optional[str] = None
    entities: Optional[ReportEntities] = None
    metadata: Optional[dict[str, Any]] = None
    critic: Optional[dict[str, Any]] = None
    fact_validation: Optional[dict[str, Any]] = None
    insight_synthesis: Optional[dict[str, Any]] = None
    dynamic_outline: Optional[dict[str, Any]] = None
    evidence_ledger: Optional[list[dict[str, Any]]] = None
    error: Optional[str] = None


class AskResponseBody(BaseModel):
    success: bool
    answer: str = ""
    period_info: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    error: Optional[str] = None


class SuggestedQuestionsResponse(BaseModel):
    questions: list[str]


def _raise_for_error(result: dict) -> None:
    """Map service-layer error messages to appropriate HTTP status codes."""
    error = result.get("error", "生成失败")

    if "LLM 未配置" in error:
        raise HTTPException(status_code=503, detail=error)

    if "暂无听歌数据" in error:
        return  # 200 OK — valid business result, not an error

    if "LLM 调用失败" in error or "LLM 返回为空" in error or "报告质量校验未通过" in error:
        raise HTTPException(status_code=502, detail=error)

    if "数据获取失败" in error or "数据查询失败" in error:
        raise HTTPException(status_code=500, detail=error)

    # Unknown errors — 500
    raise HTTPException(status_code=500, detail=error)


@router.get("/weekly-digest", response_model=DigestResponse)
def weekly_digest(
    week_start: str = Query(..., description="YYYY-MM-DD"),
    week_end: str = Query(..., description="YYYY-MM-DD"),
    force: bool = Query(False, description="Bypass server-side cache"),
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    """Generate a natural-language weekly listening digest."""
    result = generate_weekly_digest(
        conn,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        week_start,
        week_end,
        force=force,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
    )
    if not result["success"]:
        _raise_for_error(result)
    return result


@router.get("/monthly-personality", response_model=DigestResponse)
def monthly_personality(
    month: str = Query(..., description="YYYY-MM"),
    year: int = Query(..., description="e.g. 2026"),
    force: bool = Query(False, description="Bypass server-side cache"),
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    """Generate a monthly personality report."""
    result = generate_monthly_personality(
        conn,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        month,
        year,
        force=force,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
    )
    if not result["success"]:
        _raise_for_error(result)
    return result


@router.get("/yearly-story", response_model=DigestResponse)
def yearly_story(
    year: int = Query(...),
    force: bool = Query(False, description="Bypass server-side cache"),
    report_mode: Literal["visual_yearly_artifact", "agentic_longform", "basic_summary"] = Query(
        "visual_yearly_artifact",
        description="Use visual artifact, agentic longform, or legacy basic summary yearly flow",
    ),
    writer_pipeline: Literal[
        "agent_synthesis_v2", "editorial_agent_v1", "deterministic_visual_v1"
    ] = Query(
        "agent_synthesis_v2",
        description="Writer pipeline for visual yearly artifacts",
    ),
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    """Generate a narrative story from full Wrapped data."""
    if report_mode == "visual_yearly_artifact" and not force:
        cached = ai_insights_service.peek_report_cache(
            conn,
            "yearly",
            min_ms=filters.min_ms,
            music_only=filters.music_only,
            merge_enabled=filters.merge_enabled,
            dynamic_threshold=filters.dynamic_threshold,
            max_merge_gap_minutes=filters.max_merge_gap_minutes,
            report_mode="visual_yearly_artifact",
            writer_pipeline=writer_pipeline,
            year=year,
        )
        return _visual_yearly_cache_response(cached)

    if report_mode == "visual_yearly_artifact" and force:
        from backend.domains.ai_reports.visual_yearly_artifact_service import (
            generate_visual_yearly_artifact,
        )

        result = generate_visual_yearly_artifact(
            {
                "report_type": "yearly",
                "report_mode": report_mode,
                "writer_pipeline": writer_pipeline,
                "year": year,
                "min_ms": filters.min_ms,
                "music_only": filters.music_only,
                "merge_enabled": filters.merge_enabled,
                "dynamic_threshold": filters.dynamic_threshold,
                "max_merge_gap_minutes": filters.max_merge_gap_minutes,
                "force": force,
            }
        )
        if not result["success"]:
            _raise_for_error(result)
        return result

    if report_mode == "agentic_longform" and force:
        from backend.services.yearly_report_agent_service import generate_agentic_yearly_report

        result = generate_agentic_yearly_report(
            {
                "report_type": "yearly",
                "report_mode": report_mode,
                "year": year,
                "min_ms": filters.min_ms,
                "music_only": filters.music_only,
                "merge_enabled": filters.merge_enabled,
                "dynamic_threshold": filters.dynamic_threshold,
                "max_merge_gap_minutes": filters.max_merge_gap_minutes,
                "force": force,
            }
        )
        if not result["success"]:
            _raise_for_error(result)
        return result

    result = generate_yearly_story(
        conn,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        year,
        force=force,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
    )
    if not result["success"]:
        _raise_for_error(result)
    return result


def _visual_yearly_cache_response(cached: dict[str, Any]) -> dict[str, Any]:
    if not cached.get("cached") or not isinstance(cached.get("report"), str):
        return {
            "success": True,
            "report": None,
            "artifact": None,
            "cached": False,
            "cached_at": None,
            "entities": None,
            "metadata": {
                "report_mode": "visual_yearly_artifact",
                "needs_generation": True,
            },
            "error": None,
        }
    try:
        payload = json.loads(cached["report"])
    except (TypeError, json.JSONDecodeError):
        return {
            "success": True,
            "report": cached["report"],
            "artifact": None,
            "cached": True,
            "cached_at": cached.get("cached_at"),
            "entities": None,
            "metadata": {
                "report_mode": "visual_yearly_artifact",
                "cache_parse_error": True,
            },
            "error": None,
        }
    if not isinstance(payload, dict):
        payload = {}
    return {
        "success": bool(payload.get("success", True)),
        "report": payload.get("report"),
        "artifact": payload.get("artifact") if isinstance(payload.get("artifact"), dict) else None,
        "cached": True,
        "cached_at": cached.get("cached_at"),
        "entities": payload.get("entities") if isinstance(payload.get("entities"), dict) else None,
        "metadata": payload.get("metadata") if isinstance(payload.get("metadata"), dict) else None,
        "critic": payload.get("critic") if isinstance(payload.get("critic"), dict) else None,
        "fact_validation": payload.get("fact_validation")
        if isinstance(payload.get("fact_validation"), dict)
        else None,
        "insight_synthesis": payload.get("insight_synthesis")
        if isinstance(payload.get("insight_synthesis"), dict)
        else None,
        "dynamic_outline": payload.get("dynamic_outline")
        if isinstance(payload.get("dynamic_outline"), dict)
        else None,
        "evidence_ledger": payload.get("evidence_ledger")
        if isinstance(payload.get("evidence_ledger"), list)
        else None,
        "error": payload.get("error"),
    }


# ── Phase 2 endpoints ───────────────────────────────────────────────────────


@router.post("/ask", response_model=AskResponseBody)
def ask(
    body: AskRequest,
    filters: PlayFilters = Depends(),
    merge_level: int = Query(default=1, ge=1, le=3),
    conn: Connection = Depends(get_conn),
):
    """Answer a natural-language question about listening history."""
    history = None
    if body.conversation_history:
        history = [m.model_dump() for m in body.conversation_history]

    result = answer_question(
        conn,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        body.question,
        history,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
        merge_level=merge_level,
    )
    if not result["success"]:
        _raise_for_error(result)
    return result


@router.get("/suggested-questions", response_model=SuggestedQuestionsResponse)
def suggested_questions(
    context: Optional[str] = Query(
        None, description="Report type context: weekly, monthly, yearly, chat"
    ),
):
    """Return a list of suggested starter questions."""
    return {"questions": get_suggested_questions(context)}
