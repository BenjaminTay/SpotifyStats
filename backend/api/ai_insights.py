"""AI Insights API endpoints."""

# ruff: noqa: UP045

from __future__ import annotations

from sqlite3 import Connection
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.dependencies import PlayFilters, get_conn
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
    cached: bool = False
    cached_at: Optional[str] = None
    entities: Optional[ReportEntities] = None
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

    if "LLM 调用失败" in error or "LLM 返回为空" in error:
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
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    """Generate a narrative story from full Wrapped data."""
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
