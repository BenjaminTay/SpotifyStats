"""AI task status endpoints for observable orchestration."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from backend.models.ai_tasks import (
    AiTaskCreateResponse,
    AiTaskEventsResponse,
    AiTaskStatusResponse,
    AlbumEnrichmentTaskRequest,
    ArtistEnrichmentTaskRequest,
    ChatAgentTaskRequest,
    ReportTaskRequest,
)
from backend.services.ai_task_service import (
    cancel_task,
    get_task,
    get_task_events,
    start_album_enrichment_task,
    start_artist_enrichment_task,
    start_chat_agent_task,
    start_report_task,
)

router = APIRouter(prefix="/ai/tasks", tags=["AI Tasks"])


def _status_payload(task: dict[str, Any] | None) -> dict[str, Any]:
    if task is None:
        return {"found": False}
    return {
        "found": True,
        "task_id": task["task_id"],
        "task_type": task["task_type"],
        "status": task["status"],
        "stage": task["stage"],
        "progress_pct": task["progress_pct"],
        "message": task["message"],
        "request": task["request"],
        "result": task["result"],
        "error": task["error"],
        "created_at": task["created_at"],
        "updated_at": task["updated_at"],
    }


@router.post(
    "/report",
    response_model=AiTaskCreateResponse,
    response_model_exclude_none=True,
)
def create_report_task(body: ReportTaskRequest):
    return start_report_task(body.model_dump())


@router.post(
    "/chat",
    response_model=AiTaskCreateResponse,
    response_model_exclude_none=True,
)
def create_chat_agent_task(body: ChatAgentTaskRequest):
    return start_chat_agent_task(body.model_dump())


@router.post(
    "/enrichment/artist",
    response_model=AiTaskCreateResponse,
    response_model_exclude_none=True,
)
def create_artist_enrichment_task(body: ArtistEnrichmentTaskRequest):
    return start_artist_enrichment_task(body.model_dump())


@router.post(
    "/enrichment/album",
    response_model=AiTaskCreateResponse,
    response_model_exclude_none=True,
)
def create_album_enrichment_task(body: AlbumEnrichmentTaskRequest):
    return start_album_enrichment_task(body.model_dump())


@router.get(
    "/{task_id}/events",
    response_model=AiTaskEventsResponse,
    response_model_exclude_none=True,
)
def get_ai_task_events(task_id: str):
    payload = get_task_events(task_id)
    if payload is None:
        return {"found": False, "events": [], "tool_calls": []}
    events, tool_calls = payload
    return {"found": True, "events": events, "tool_calls": tool_calls}


@router.post(
    "/{task_id}/cancel",
    response_model=AiTaskStatusResponse,
    response_model_exclude_none=True,
)
def cancel_ai_task(task_id: str):
    return _status_payload(cancel_task(task_id))


@router.get(
    "/{task_id}",
    response_model=AiTaskStatusResponse,
    response_model_exclude_none=True,
)
def get_ai_task(task_id: str):
    return _status_payload(get_task(task_id))
