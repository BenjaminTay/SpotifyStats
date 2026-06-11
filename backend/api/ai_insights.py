"""AI Insights API endpoints."""

from __future__ import annotations

from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.dependencies import PlayFilters, get_conn
from backend.services.ai_insights_service import (
    answer_question,
    generate_monthly_personality,
    generate_weekly_digest,
    generate_yearly_story,
    get_suggested_questions,
)

router = APIRouter(prefix="/ai-insights", tags=["AI Insights"])


class AskRequest(BaseModel):
    question: str
    conversation_history: list[dict[str, str]] | None = None


@router.get("/weekly-digest")
def weekly_digest(
    week_start: str = Query(..., description="YYYY-MM-DD"),
    week_end: str = Query(..., description="YYYY-MM-DD"),
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
    )
    if not result["success"]:
        raise HTTPException(status_code=503, detail=result.get("error", "生成失败"))
    return result


@router.get("/monthly-personality")
def monthly_personality(
    month: str = Query(..., description="YYYY-MM"),
    year: int = Query(..., description="e.g. 2026"),
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
    )
    if not result["success"]:
        raise HTTPException(status_code=503, detail=result.get("error", "生成失败"))
    return result


@router.get("/yearly-story")
def yearly_story(
    year: int = Query(...),
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
    )
    if not result["success"]:
        raise HTTPException(status_code=503, detail=result.get("error", "生成失败"))
    return result


# ── Phase 2 endpoints ───────────────────────────────────────────────────────


@router.post("/ask")
def ask(
    body: AskRequest,
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    """Answer a natural-language question about listening history."""
    if not body.question or not body.question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")
    if len(body.question) > 500:
        raise HTTPException(status_code=400, detail="问题长度不能超过 500 字符")

    result = answer_question(
        conn,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        body.question,
        body.conversation_history,
    )
    if not result["success"]:
        raise HTTPException(status_code=503, detail=result.get("error", "回答失败"))
    return result


@router.get("/suggested-questions")
def suggested_questions():
    """Return a list of suggested starter questions."""
    return {"questions": get_suggested_questions()}
