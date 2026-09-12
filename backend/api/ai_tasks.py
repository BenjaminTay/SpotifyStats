"""AI task status endpoints for observable orchestration."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.models.ai_tasks import (
    AiAgentInboxRequest,
    AiAgentInboxResponse,
    AiAgentTrajectoryResponse,
    AiTaskCreateResponse,
    AiTaskEventsResponse,
    AiTaskStatusResponse,
    AlbumEnrichmentTaskRequest,
    ArtistEnrichmentTaskRequest,
    ArtistGenreBackfillTaskRequest,
    ChatAgentTaskRequest,
    ReportTaskRequest,
)
from backend.services.ai_task_service import (
    cancel_task,
    enqueue_agent_input,
    get_agent_trajectory,
    get_task,
    get_task_events,
    start_album_enrichment_task,
    start_artist_enrichment_task,
    start_artist_genre_backfill_task,
    start_chat_agent_task,
    start_report_task,
)

router = APIRouter(prefix="/ai/tasks", tags=["AI Tasks"])

_STREAM_TERMINAL_STATUSES = {"done", "error", "cancelled"}
_SAFE_AGENT_STATE_EVENT_TYPES = {
    "session_state_initialized",
    "session_state_updated",
    "session_input_consumed",
}
_SAFE_AGENT_STATE_FIELDS = (
    "entities",
    "time_range",
    "metrics",
    "excluded_dimensions",
    "filters",
)


def _sse(event: str, data: dict[str, Any], *, event_id: str | None = None) -> str:
    lines = []
    if event_id:
        lines.append(f"id: {event_id}")
    lines.extend((f"event: {event}", f"data: {json.dumps(data, ensure_ascii=False)}", ""))
    return "\n".join(lines) + "\n"


_STREAM_CURSOR_RE = re.compile(r"^v1:p(?P<progress>\d+):t(?P<tool>\d+):a(?P<answer>\d+)$")


def _stream_cursor(progress: int, tool: int, answer: int) -> str:
    return f"v1:p{max(0, progress)}:t{max(0, tool)}:a{max(0, answer)}"


def _parse_stream_cursor(value: str | None) -> tuple[int, int, int]:
    """Parse current composite cursors and legacy single-channel event ids."""

    raw = (value or "").strip()
    match = _STREAM_CURSOR_RE.fullmatch(raw)
    if match:
        return (
            int(match.group("progress")),
            int(match.group("tool")),
            int(match.group("answer")),
        )
    for prefix, index in (("progress-", 0), ("tool-", 1), ("answer-", 2)):
        if raw.startswith(prefix) and raw[len(prefix) :].isdigit():
            cursor = [0, 0, 0]
            cursor[index] = int(raw[len(prefix) :])
            return cursor[0], cursor[1], cursor[2]
    return 0, 0, 0


def _stream_task_payload(task: dict[str, Any]) -> dict[str, Any]:
    """Public stream projection without the original prompt or hidden trace."""

    return {
        "found": True,
        "task_id": task["task_id"],
        "task_type": task["task_type"],
        "status": task["status"],
        "stage": task["stage"],
        "progress_pct": task["progress_pct"],
        "message": task["message"],
        "result": task["result"],
        "error": task["error"],
        "created_at": task["created_at"],
        "updated_at": task["updated_at"],
    }


def _answer_text(task: dict[str, Any]) -> str:
    result = task.get("result")
    if not isinstance(result, dict):
        return ""
    for key in ("answer", "report"):
        value = result.get(key)
        if isinstance(value, str):
            return value
    return ""


def _safe_agent_state_payload(item: dict[str, Any]) -> dict[str, Any] | None:
    if item.get("event_type") not in _SAFE_AGENT_STATE_EVENT_TYPES:
        return None
    raw = item.get("payload")
    if not isinstance(raw, dict):
        return None
    state = raw.get("state")
    if not isinstance(state, dict):
        return None
    payload: dict[str, Any] = {
        "state": {field: state.get(field) for field in _SAFE_AGENT_STATE_FIELDS},
    }
    for field in ("inbox_id", "input_type", "semantic_action"):
        value = raw.get(field)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            payload[field] = value
    return payload


async def _task_event_stream(task_id: str, request: Request):
    cursor_value = request.headers.get("last-event-id") or request.query_params.get("cursor")
    last_event_id, last_tool_call_id, last_answer_chunk = _parse_stream_cursor(cursor_value)
    last_snapshot = ""
    yield "retry: 1000\n\n"
    yield _sse(
        "stream.connected",
        {
            "task_id": task_id,
            "cursor": _stream_cursor(last_event_id, last_tool_call_id, last_answer_chunk),
        },
    )

    while not await request.is_disconnected():
        task = get_task(task_id)
        if task is None:
            yield _sse("stream.error", {"code": "task_not_found", "message": "AI 任务不存在"})
            return

        snapshot = _stream_task_payload(task)
        signature = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
        is_terminal = task["status"] in _STREAM_TERMINAL_STATUSES
        if signature != last_snapshot and not is_terminal:
            yield _sse("task.snapshot", snapshot)
            last_snapshot = signature

        trace = get_task_events(task_id)
        if trace is not None:
            events, tool_calls = trace
            for item in events:
                event_id = int(item["event_id"])
                if event_id <= last_event_id:
                    continue
                # Deliberately omit payload: it can contain runtime bookkeeping
                # and validation internals that are not user-facing progress.
                progress_payload = {
                    "event_id": event_id,
                    "task_id": task_id,
                    "event_type": item["event_type"],
                    "stage": item["stage"],
                    "message": item["message"],
                    "created_at": item["created_at"],
                }
                safe_state = _safe_agent_state_payload(item)
                if safe_state is not None:
                    progress_payload["payload"] = safe_state
                last_event_id = event_id
                yield _sse(
                    "task.progress",
                    progress_payload,
                    event_id=_stream_cursor(
                        last_event_id,
                        last_tool_call_id,
                        last_answer_chunk,
                    ),
                )
            for item in tool_calls:
                tool_call_id = int(item["tool_call_id"])
                if tool_call_id <= last_tool_call_id:
                    continue
                last_tool_call_id = tool_call_id
                yield _sse(
                    "task.tool",
                    {
                        "tool_call_id": tool_call_id,
                        "task_id": task_id,
                        "tool_name": item["tool_name"],
                        "status": item["status"],
                        "params_summary": item["params_summary"],
                        "result_summary": item["result_summary"],
                        "source_range": item["source_range"],
                        "error": item["error"],
                        "started_at": item["started_at"],
                        "completed_at": item["completed_at"],
                    },
                    event_id=_stream_cursor(
                        last_event_id,
                        last_tool_call_id,
                        last_answer_chunk,
                    ),
                )

        if is_terminal:
            # Only publish answer chunks after the validator has accepted and
            # persisted the final task result.  Intermediate model prose and
            # reasoning are never streamed.
            answer = _answer_text(task)
            for index in range(0, len(answer), 160):
                chunk_index = index // 160 + 1
                if chunk_index <= last_answer_chunk:
                    continue
                last_answer_chunk = chunk_index
                yield _sse(
                    "task.answer_delta",
                    {"task_id": task_id, "delta": answer[index : index + 160]},
                    event_id=_stream_cursor(
                        last_event_id,
                        last_tool_call_id,
                        last_answer_chunk,
                    ),
                )
            yield _sse(
                "task.completed",
                snapshot,
                event_id=_stream_cursor(
                    last_event_id,
                    last_tool_call_id,
                    last_answer_chunk,
                ),
            )
            return

        await asyncio.sleep(0.25)


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
    return start_chat_agent_task(body.model_dump(exclude_none=True))


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


@router.post(
    "/metadata/artist-genres",
    response_model=AiTaskCreateResponse,
    response_model_exclude_none=True,
)
def create_artist_genre_backfill_task(body: ArtistGenreBackfillTaskRequest):
    return start_artist_genre_backfill_task(body.model_dump())


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


@router.get(
    "/{task_id}/trajectory",
    response_model=AiAgentTrajectoryResponse,
    response_model_exclude_none=True,
)
def get_ai_agent_trajectory(task_id: str):
    events = get_agent_trajectory(task_id)
    if events is None:
        return {"found": False, "events": []}
    return {"found": True, "events": events}


@router.get(
    "/{task_id}/stream",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
def stream_ai_task(task_id: str, request: Request):
    """Stream a safe projection of durable task progress via SSE."""

    return StreamingResponse(
        _task_event_stream(task_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/{task_id}/inbox",
    response_model=AiAgentInboxResponse,
)
def post_ai_agent_input(task_id: str, body: AiAgentInboxRequest):
    payload = enqueue_agent_input(
        task_id,
        action=body.action,
        content=body.content,
    )
    if payload is None:
        return {
            "accepted": False,
            "task_id": task_id,
            "action": body.action,
            "status": "not_found",
        }
    return payload


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
