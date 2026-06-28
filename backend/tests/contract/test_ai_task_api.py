from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

import backend.api.ai_tasks as ai_tasks_api
from backend.core.db import get_db
from backend.domains.ai_tasks.repository import AiTaskRepository
from backend.main import app

pytestmark = pytest.mark.contract


def _repo() -> AiTaskRepository:
    conn = get_db(readonly=False)
    return AiTaskRepository(conn)


def _close_repo(repo: AiTaskRepository) -> None:
    repo.conn.close()


def _create_task(
    task_id: str,
    *,
    status: str = "queued",
    stage: str = "checking_cache",
    message: str = "正在检查缓存",
) -> None:
    repo = _repo()
    try:
        repo.create_run(
            task_id=task_id,
            task_type="ai_report_weekly",
            status=status,
            stage=stage,
            message=message,
            request={"report_type": "weekly", "action": "cache_only"},
        )
    finally:
        _close_repo(repo)


def _find_route(method: str, path: str) -> APIRoute:
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route
    raise AssertionError(f"Route not found: {method} {path}")


def test_missing_ai_task_returns_found_false(client):
    response = client.get("/api/ai/tasks/not-real")

    assert response.status_code == 200
    assert response.headers["x-request-id"]
    assert response.json() == {"found": False}


def test_existing_ai_task_returns_status_payload(client):
    _create_task(
        "task-status",
        status="running",
        stage="gathering_local_data",
        message="正在汇总播放记录",
    )

    response = client.get("/api/ai/tasks/task-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["found"] is True
    assert payload["task_id"] == "task-status"
    assert payload["task_type"] == "ai_report_weekly"
    assert payload["status"] == "running"
    assert payload["stage"] == "gathering_local_data"
    assert payload["progress_pct"] == 0.0
    assert payload["message"] == "正在汇总播放记录"
    assert payload["request"] == {"report_type": "weekly", "action": "cache_only"}
    assert payload["created_at"]
    assert payload["updated_at"]


def test_task_events_for_missing_task_returns_found_false(client):
    response = client.get("/api/ai/tasks/not-real/events")

    assert response.status_code == 200
    assert response.headers["x-request-id"]
    assert response.json() == {"found": False, "events": [], "tool_calls": []}


def test_task_events_include_events_and_tool_calls(client):
    _create_task("task-events", status="running", stage="planning_tools")
    repo = _repo()
    try:
        repo.add_event(
            task_id="task-events",
            event_type="stage_started",
            stage="planning_tools",
            message="正在规划数据查询",
            payload={"round": 1},
        )
        repo.add_tool_call(
            task_id="task-events",
            tool_name="analysis_charts",
            status="done",
            params_summary="2026 artist plays top 10",
            result_summary="Top artist is Artist A with 12 plays",
            source_range="2026-01-01 to 2026-12-31",
        )
    finally:
        _close_repo(repo)

    response = client.get("/api/ai/tasks/task-events/events")

    assert response.status_code == 200
    payload = response.json()
    assert payload["found"] is True
    assert payload["events"][0]["task_id"] == "task-events"
    assert payload["events"][0]["event_type"] == "stage_started"
    assert payload["events"][0]["payload"] == {"round": 1}
    assert payload["tool_calls"][0]["tool_name"] == "analysis_charts"
    assert payload["tool_calls"][0]["params_summary"] == "2026 artist plays top 10"
    assert payload["tool_calls"][0]["source_range"] == "2026-01-01 to 2026-12-31"


def test_cancel_queued_task_marks_it_cancelled(client):
    _create_task("task-cancel", status="queued", stage="checking_cache")

    response = client.post("/api/ai/tasks/task-cancel/cancel")

    assert response.status_code == 200
    payload = response.json()
    assert payload["found"] is True
    assert payload["task_id"] == "task-cancel"
    assert payload["status"] == "cancelled"
    assert payload["stage"] == "cancelled"
    assert payload["message"] == "任务已取消"


def test_cancel_missing_task_returns_found_false(client):
    response = client.post("/api/ai/tasks/not-real/cancel")

    assert response.status_code == 200
    assert response.headers["x-request-id"]
    assert response.json() == {"found": False}


def test_cancel_task_writes_cancel_event(client):
    _create_task("task-cancel-event", status="queued", stage="checking_cache")

    response = client.post("/api/ai/tasks/task-cancel-event/cancel")
    events_response = client.get("/api/ai/tasks/task-cancel-event/events")

    assert response.status_code == 200
    assert events_response.status_code == 200
    payload = events_response.json()
    assert payload["found"] is True
    assert [event["event_type"] for event in payload["events"]] == ["stage_completed"]
    assert payload["events"][0]["stage"] == "cancelled"
    assert payload["events"][0]["message"] == "任务已取消"


def test_cancel_done_task_keeps_existing_state(client):
    _create_task("task-done", status="done", stage="done", message="已完成")

    response = client.post("/api/ai/tasks/task-done/cancel")

    assert response.status_code == 200
    payload = response.json()
    assert payload["found"] is True
    assert payload["status"] == "done"
    assert payload["stage"] == "done"
    assert payload["message"] == "已完成"


def test_report_cache_only_returns_done_and_needs_generation(client, monkeypatch):
    import backend.services.ai_task_service as task_service

    monkeypatch.setattr(
        task_service,
        "peek_report_cache",
        lambda request: {
            "cached": False,
            "report": None,
            "cached_at": None,
            "entities": None,
            "needs_generation": True,
        },
    )

    response = client.post(
        "/api/ai/tasks/report",
        json={
            "report_type": "weekly",
            "action": "cache_only",
            "week_start": "2026-06-17",
            "week_end": "2026-06-23",
        },
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"]
    body = response.json()
    assert body["status"] == "done"
    assert body["stage"] == "done"
    assert body["result"]["needs_generation"] is True
    assert body["result"]["cached"] is False


def test_report_task_request_preserves_filter_parameters(client, monkeypatch):
    observed = {}

    def fake_start_report_task(request):
        observed.update(request)
        return {
            "task_id": "task-filter",
            "status": "done",
            "stage": "done",
            "progress_pct": 1.0,
            "message": "缓存检查完成",
            "result": {
                "needs_generation": True,
                "request": request,
            },
        }

    monkeypatch.setattr(ai_tasks_api, "start_report_task", fake_start_report_task)

    response = client.post(
        "/api/ai/tasks/report",
        json={
            "report_type": "monthly",
            "action": "cache_only",
            "month": "2026-06",
            "year": 2026,
            "min_ms": 45000,
            "music_only": False,
            "merge_enabled": False,
            "dynamic_threshold": False,
            "max_merge_gap_minutes": 45,
        },
    )

    assert response.status_code == 200
    assert observed["min_ms"] == 45000
    assert observed["music_only"] is False
    assert observed["merge_enabled"] is False
    assert observed["dynamic_threshold"] is False
    assert observed["max_merge_gap_minutes"] == 45
    assert response.json()["result"]["request"]["month"] == "2026-06"


@pytest.mark.parametrize(
    "payload",
    [
        {"report_type": "weekly", "action": "cache_only"},
        {"report_type": "monthly", "action": "cache_only", "month": "2026-06"},
        {"report_type": "yearly", "action": "cache_only"},
    ],
)
def test_report_task_request_rejects_missing_period_fields(client, monkeypatch, payload):
    monkeypatch.setattr(
        ai_tasks_api,
        "start_report_task",
        lambda request: pytest.fail("invalid report request must not start a task"),
    )

    response = client.post("/api/ai/tasks/report", json=payload)

    assert response.status_code == 422
    assert response.headers["x-request-id"]


def test_ai_task_routes_declare_response_models():
    expected = {
        ("POST", "/api/ai/tasks/report"),
        ("POST", "/api/ai/tasks/chat"),
        ("POST", "/api/ai/tasks/enrichment/artist"),
        ("POST", "/api/ai/tasks/enrichment/album"),
        ("GET", "/api/ai/tasks/{task_id}"),
        ("GET", "/api/ai/tasks/{task_id}/events"),
        ("POST", "/api/ai/tasks/{task_id}/cancel"),
    }

    for method, path in expected:
        route = _find_route(method, path)
        assert route.response_model is not None, f"{method} {path} missing response_model"

    schema = app.openapi()
    for method, path in expected:
        response = schema["paths"][path][method.lower()]["responses"]["200"]
        assert "schema" in response["content"]["application/json"]

    status_required = set(schema["components"]["schemas"]["AiTaskStatusResponse"]["required"])
    events_required = set(schema["components"]["schemas"]["AiTaskEventsResponse"]["required"])
    create_required = set(schema["components"]["schemas"]["AiTaskCreateResponse"]["required"])
    assert "found" in status_required
    assert {"found", "events", "tool_calls"}.issubset(events_required)
    assert {"task_id", "status", "stage"}.issubset(create_required)
