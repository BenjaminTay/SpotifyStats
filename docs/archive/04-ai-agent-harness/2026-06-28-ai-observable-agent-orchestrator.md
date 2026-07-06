# AI Observable Agent Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the V2 minimum vertical slice of the future AI Orchestrator: observable AI task progress, manual report generation when no cache exists, read-only Agent chat tools, and artist plus album enrichment progress.

**Architecture:** Add SQLite-backed AI task runs, events, and tool calls as durable orchestration primitives. Keep existing synchronous AI/report/enrichment endpoints for compatibility while the frontend moves to task-based polling. Implement read-only Agent tools through a backend registry so the model can inspect data without write access or arbitrary backend routing.

**Tech Stack:** FastAPI, SQLite migrations, Pydantic response models, existing SpotifyStats service layer, TanStack React Query, React/TypeScript, Vitest, pytest.

---

## Execution Constraints

- Do not create a git commit unless the user explicitly asks for one.
- Keep all Agent tools read-only. Chat/task persistence is allowed only for task state, visible chat records, generated answers, and tool trace metadata.
- Keep existing synchronous endpoints working throughout V2.
- Prefer targeted tests after each task; run broader checks only after the relevant vertical slice is complete.

## Scope Check

The approved spec covers two connected subsystems: observable task progress and read-only Agent tools. They share the same durable task/event/tool-call model, so this plan keeps them in one V2 vertical-slice plan rather than splitting them into unrelated projects.

## Execution Summary

Implement in this order:

1. Add durable AI task tables and repository.
2. Add task API models, service shell, status endpoints, and router registration.
3. Add report task backend with cache-only check and manual generation action.
4. Add shared frontend task polling hooks and progress/trace components.
5. Move AI Reports to cache-first, manual-generate UI.
6. Add backend-defined read-only Agent tool registry.
7. Add Agent chat task backend with bounded tool planning and persisted traces.
8. Move AI Chat to task-based Agent flow.
9. Add artist and album enrichment task wrappers with progress events.
10. Move artist career and album era sections to task-progress UI.
11. Refresh generated OpenAPI types, smoke coverage, audits, and final targeted verification.

## File Structure

Backend files to create:

- `backend/models/ai_tasks.py`: Pydantic request/response models for AI task endpoints.
- `backend/domains/ai_tasks/repository.py`: SQLite CRUD for `ai_task_runs`, `ai_task_events`, and `ai_tool_calls`.
- `backend/services/ai_task_service.py`: task creation, event emission, background execution, status/result assembly.
- `backend/api/ai_tasks.py`: task endpoint router under `/ai/tasks`.
- `backend/domains/ai_agent/tool_registry.py`: read-only tool metadata, schema validation, and dispatch.
- `backend/domains/ai_agent/tools.py`: tool handlers that wrap existing analytics services.
- `backend/services/ai_agent_service.py`: bounded planning/tool execution/final-answer loop.

Backend files to modify:

- `backend/core/migrations.py`: add migration 22 for AI task tables.
- `backend/api/router.py`: include `ai_tasks_router`.
- `backend/services/ai_insights_service.py`: add report cache peek helpers and event-aware report wrappers without removing current public functions.
- `backend/services/wikipedia_service.py`: add optional progress callback for artist and album wiki flows.
- `backend/api/billboard/enrichment.py`: preserve existing endpoints while allowing task wrappers to reuse response shaping.
- `backend/tests/fixtures/build_seed_db.py`: ensure new AI task tables exist in seed DB if the fixture rebuild script validates full schema.
- `scripts/openapi_operation_audit.py`: account for new task operations if the audit reports them as unaccounted.
- `scripts/openapi_parameter_boundary_audit.py`: account for new task path/body boundary obligations if the audit reports them as unaccounted.

Frontend files to create:

- `frontend/src/types/ai-tasks.ts`: task status, event, tool trace, and request/response types.
- `frontend/src/hooks/useAiTasks.ts`: generic polling hooks and task start helpers.
- `frontend/src/features/ai-tasks/AITaskProgress.tsx`: shared stage/status display.
- `frontend/src/features/ai-tasks/AIToolTrace.tsx`: compact user-readable tool trace.
- `frontend/src/features/ai-tasks/AIResultShell.tsx`: wrapper for generated output, cache status, trace, and disclaimer.

Frontend files to modify:

- `frontend/src/api/query-keys.ts`: add `aiTasks` keys.
- `frontend/src/features/ai-insights/AiInsightsExperience.tsx`: use task-based report flow.
- `frontend/src/features/ai-insights/ReportCard.tsx`: accept cached/manual/task state from task result.
- `frontend/src/features/ai-insights/ChatInterface.tsx`: start chat agent task and render progress/trace.
- `frontend/src/features/ai-insights/ChatMessageList.tsx`: render assistant metadata tool trace.
- `frontend/src/features/music/details/ArtistDetailExperience.tsx`: use artist enrichment task on career tab.
- `frontend/src/features/music/details/ArtistCareerSection.tsx`: render progress before existing enrichment view.
- `frontend/src/features/music/details/AlbumDetailExperience.tsx`: use album enrichment task on era tab.
- `frontend/src/features/music/details/AlbumEraSection.tsx`: render progress before existing enrichment view.
- `scripts/frontend_interaction_smoke.mjs`: extend AI scenario to verify task-progress affordances without live LLM dependency.
- `scripts/frontend_route_smoke.mjs`: keep route markers stable if task UI changes visible text.
- `frontend/src/api/generated/openapi.json` and `frontend/src/api/generated/api-types.ts`: refresh after backend task endpoints are stable.

Test files to create or modify:

- `backend/tests/unit/test_ai_task_repository.py`
- `backend/tests/contract/test_ai_task_api.py`
- `backend/tests/unit/test_ai_report_tasks.py`
- `backend/tests/unit/test_ai_agent_tools.py`
- `backend/tests/contract/test_ai_agent_task_contract.py`
- `backend/tests/unit/test_wikipedia_progress.py`
- `backend/tests/contract/test_ai_enrichment_tasks.py`
- `frontend/src/tests/ai-task-components.test.tsx`
- `frontend/src/tests/ai-task-hooks.test.tsx`
- `frontend/src/tests/ai-insights-task-flow.test.tsx`
- `frontend/src/tests/music-enrichment-task-flow.test.tsx`

---

### Task 1: Add SQLite AI Task Tables And Repository

**Files:**
- Modify: `backend/core/migrations.py`
- Create: `backend/domains/ai_tasks/repository.py`
- Test: `backend/tests/unit/test_ai_task_repository.py`

- [ ] **Step 1: Write failing repository tests**

Create `backend/tests/unit/test_ai_task_repository.py`:

```python
from __future__ import annotations

import sqlite3

import pytest

pytestmark = pytest.mark.unit


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE ai_task_runs (
            task_id TEXT PRIMARY KEY,
            task_type TEXT NOT NULL,
            status TEXT NOT NULL,
            stage TEXT NOT NULL,
            progress_pct REAL NOT NULL DEFAULT 0,
            message TEXT NOT NULL DEFAULT '',
            request_json TEXT,
            result_json TEXT,
            error TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE ai_task_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            stage TEXT NOT NULL,
            message TEXT NOT NULL DEFAULT '',
            payload_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE ai_tool_calls (
            tool_call_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            status TEXT NOT NULL,
            params_summary TEXT NOT NULL DEFAULT '',
            result_summary TEXT NOT NULL DEFAULT '',
            source_range TEXT NOT NULL DEFAULT '',
            error TEXT,
            started_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT
        );
        """
    )
    return conn


def test_repository_creates_run_event_and_tool_call():
    from backend.domains.ai_tasks.repository import AiTaskRepository

    conn = make_conn()
    repo = AiTaskRepository(conn)

    repo.create_run(
        task_id="task-1",
        task_type="ai_chat_agent",
        status="queued",
        stage="planning_tools",
        message="准备分析问题",
        request={"question": "今年我听得最多的艺人是谁？"},
    )
    repo.add_event(
        task_id="task-1",
        event_type="stage_started",
        stage="planning_tools",
        message="正在规划数据查询",
        payload={"round": 1},
    )
    repo.add_tool_call(
        task_id="task-1",
        tool_name="analysis_charts",
        status="done",
        params_summary="2026 artist plays top 10",
        result_summary="Top artist is Artist A with 12 plays",
        source_range="2026-01-01 to 2026-12-31",
    )
    repo.update_run(
        task_id="task-1",
        status="done",
        stage="done",
        progress_pct=1.0,
        message="分析完成",
        result={"answer": "Artist A"},
    )

    run = repo.get_run("task-1")
    events = repo.list_events("task-1")
    tools = repo.list_tool_calls("task-1")

    assert run is not None
    assert run["status"] == "done"
    assert run["result"]["answer"] == "Artist A"
    assert events[0]["payload"] == {"round": 1}
    assert tools[0]["tool_name"] == "analysis_charts"
    assert tools[0]["source_range"] == "2026-01-01 to 2026-12-31"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_task_repository.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.domains.ai_tasks'`.

- [ ] **Step 3: Add migration 22**

Append this migration before the runner section in `backend/core/migrations.py`:

```python
@migration(22, "ai_task_runs_events_tool_calls")
def migrate_022(conn: sqlite3.Connection):
    """Persist AI task progress, event history, and read-only tool traces."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS ai_task_runs (
            task_id TEXT PRIMARY KEY,
            task_type TEXT NOT NULL,
            status TEXT NOT NULL,
            stage TEXT NOT NULL,
            progress_pct REAL NOT NULL DEFAULT 0,
            message TEXT NOT NULL DEFAULT '',
            request_json TEXT,
            result_json TEXT,
            error TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_task_runs_status ON ai_task_runs(status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_task_runs_type_created ON ai_task_runs(task_type, created_at)"
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS ai_task_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL REFERENCES ai_task_runs(task_id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            stage TEXT NOT NULL,
            message TEXT NOT NULL DEFAULT '',
            payload_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_task_events_task ON ai_task_events(task_id, event_id)"
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS ai_tool_calls (
            tool_call_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL REFERENCES ai_task_runs(task_id) ON DELETE CASCADE,
            tool_name TEXT NOT NULL,
            status TEXT NOT NULL,
            params_summary TEXT NOT NULL DEFAULT '',
            result_summary TEXT NOT NULL DEFAULT '',
            source_range TEXT NOT NULL DEFAULT '',
            error TEXT,
            started_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT
        )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_tool_calls_task ON ai_tool_calls(task_id, tool_call_id)"
    )
```

- [ ] **Step 4: Implement repository**

Create `backend/domains/ai_tasks/repository.py`:

```python
"""Repository for durable AI task runs, events, and read-only tool traces."""

from __future__ import annotations

import json
import sqlite3
from typing import Any


def _json_dump(value: dict[str, Any] | list[Any] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _json_load(value: str | None):
    if not value:
        return None
    return json.loads(value)


class AiTaskRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create_run(
        self,
        *,
        task_id: str,
        task_type: str,
        status: str,
        stage: str,
        message: str = "",
        request: dict[str, Any] | None = None,
    ) -> None:
        self.conn.execute(
            """INSERT INTO ai_task_runs
               (task_id, task_type, status, stage, progress_pct, message, request_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (task_id, task_type, status, stage, 0.0, message, _json_dump(request)),
        )
        self.conn.commit()

    def update_run(
        self,
        *,
        task_id: str,
        status: str,
        stage: str,
        progress_pct: float,
        message: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        self.conn.execute(
            """UPDATE ai_task_runs
               SET status = ?, stage = ?, progress_pct = ?, message = ?,
                   result_json = COALESCE(?, result_json),
                   error = ?,
                   updated_at = datetime('now')
               WHERE task_id = ?""",
            (
                status,
                stage,
                max(0.0, min(1.0, float(progress_pct))),
                message,
                _json_dump(result),
                error,
                task_id,
            ),
        )
        self.conn.commit()

    def add_event(
        self,
        *,
        task_id: str,
        event_type: str,
        stage: str,
        message: str = "",
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.conn.execute(
            """INSERT INTO ai_task_events
               (task_id, event_type, stage, message, payload_json)
               VALUES (?, ?, ?, ?, ?)""",
            (task_id, event_type, stage, message, _json_dump(payload)),
        )
        self.conn.commit()

    def add_tool_call(
        self,
        *,
        task_id: str,
        tool_name: str,
        status: str,
        params_summary: str,
        result_summary: str = "",
        source_range: str = "",
        error: str | None = None,
        completed: bool = True,
    ) -> None:
        completed_at_expr = "datetime('now')" if completed else "NULL"
        self.conn.execute(
            f"""INSERT INTO ai_tool_calls
                (task_id, tool_name, status, params_summary, result_summary,
                 source_range, error, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, {completed_at_expr})""",
            (
                task_id,
                tool_name,
                status,
                params_summary,
                result_summary,
                source_range,
                error,
            ),
        )
        self.conn.commit()

    def get_run(self, task_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM ai_task_runs WHERE task_id = ?", (task_id,)
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["request"] = _json_load(result.pop("request_json", None))
        result["result"] = _json_load(result.pop("result_json", None))
        return result

    def list_events(self, task_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM ai_task_events WHERE task_id = ? ORDER BY event_id ASC",
            (task_id,),
        ).fetchall()
        events = []
        for row in rows:
            item = dict(row)
            item["payload"] = _json_load(item.pop("payload_json", None))
            events.append(item)
        return events

    def list_tool_calls(self, task_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM ai_tool_calls WHERE task_id = ? ORDER BY tool_call_id ASC",
            (task_id,),
        ).fetchall()
        return [dict(row) for row in rows]
```

- [ ] **Step 5: Run repository test**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_task_repository.py -q
```

Expected: PASS.

- [ ] **Step 6: Run migration test suite**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_migrations.py -q
```

Expected: PASS.

- [ ] **Step 7: Checkpoint**

Run:

```bash
git status --short
```

Expected: modified `backend/core/migrations.py` plus new repository/test files. Do not commit unless the user explicitly asks.

---

### Task 2: Add Task API Models, Service, And Status Endpoints

**Files:**
- Create: `backend/models/ai_tasks.py`
- Create: `backend/services/ai_task_service.py`
- Create: `backend/api/ai_tasks.py`
- Modify: `backend/api/router.py`
- Test: `backend/tests/contract/test_ai_task_api.py`

- [ ] **Step 1: Write failing contract tests**

Create `backend/tests/contract/test_ai_task_api.py`:

```python
from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


def test_missing_ai_task_returns_found_false(client):
    response = client.get("/api/ai/tasks/not-real")

    assert response.status_code == 200
    assert response.headers["x-request-id"]
    assert response.json() == {"found": False}


def test_task_events_for_missing_task_returns_found_false(client):
    response = client.get("/api/ai/tasks/not-real/events")

    assert response.status_code == 200
    assert response.headers["x-request-id"]
    assert response.json() == {"found": False, "events": [], "tool_calls": []}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/pytest backend/tests/contract/test_ai_task_api.py -q
```

Expected: FAIL with 404 for `/api/ai/tasks/not-real`.

- [ ] **Step 3: Add Pydantic models**

Create `backend/models/ai_tasks.py`:

```python
"""Pydantic models for AI task orchestration endpoints."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

AiTaskStatus = Literal["queued", "running", "done", "error", "cancelled"]


class AiTaskRunResponse(BaseModel):
    found: bool = True
    task_id: str | None = None
    task_type: str | None = None
    status: str | None = None
    stage: str | None = None
    progress_pct: float = 0.0
    message: str = ""
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AiTaskEventResponse(BaseModel):
    event_id: int
    task_id: str
    event_type: str
    stage: str
    message: str = ""
    payload: dict[str, Any] | None = None
    created_at: str


class AiToolCallResponse(BaseModel):
    tool_call_id: int
    task_id: str
    tool_name: str
    status: str
    params_summary: str = ""
    result_summary: str = ""
    source_range: str = ""
    error: str | None = None
    started_at: str
    completed_at: str | None = None


class AiTaskEventsResponse(BaseModel):
    found: bool = True
    events: list[AiTaskEventResponse] = []
    tool_calls: list[AiToolCallResponse] = []


class AiTaskCreateResponse(BaseModel):
    task_id: str
    status: str
    stage: str
    progress_pct: float = 0.0
    message: str = ""
    result: dict[str, Any] | None = None


class ReportTaskRequest(BaseModel):
    report_type: Literal["weekly", "monthly", "yearly"]
    action: Literal["cache_only", "generate"] = "cache_only"
    force: bool = False
    week_start: str | None = None
    week_end: str | None = None
    month: str | None = None
    year: int | None = None
    min_ms: int = Field(default=30000, ge=0)
    music_only: bool = True
    merge_enabled: bool = True
    dynamic_threshold: bool = True
    max_merge_gap_minutes: int | None = Field(default=None, ge=1, le=240)


class ChatAgentTaskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    conversation_history: list[dict[str, str]] | None = None
    min_ms: int = Field(default=30000, ge=0)
    music_only: bool = True
    merge_enabled: bool = True
    dynamic_threshold: bool = True
    max_merge_gap_minutes: int | None = Field(default=None, ge=1, le=240)
    merge_level: int = Field(default=1, ge=1, le=3)


class ArtistEnrichmentTaskRequest(BaseModel):
    artist_name: str = Field(..., min_length=1, max_length=300)


class AlbumEnrichmentTaskRequest(BaseModel):
    album_name: str = Field(..., min_length=1, max_length=300)
    artist_name: str = Field(..., min_length=1, max_length=300)
```

- [ ] **Step 4: Add task service skeleton**

Create `backend/services/ai_task_service.py`:

```python
"""AI task orchestration service with durable status and event history."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from typing import Any

from backend.core.db import get_db
from backend.domains.ai_tasks.repository import AiTaskRepository


TaskHandler = Callable[[str, dict[str, Any]], None]


def new_task_id() -> str:
    return uuid.uuid4().hex[:12]


def get_task(task_id: str) -> dict[str, Any] | None:
    conn = get_db(readonly=True)
    try:
        return AiTaskRepository(conn).get_run(task_id)
    finally:
        conn.close()


def get_task_events(task_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
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
        thread = threading.Thread(target=handler, args=(task_id, request), daemon=True)
        thread.start()

    return {
        "task_id": task_id,
        "status": "queued",
        "stage": stage,
        "progress_pct": 0.0,
        "message": message,
        "result": None,
    }


def mark_task_done(task_id: str, stage: str, message: str, result: dict[str, Any]) -> None:
    conn = get_db(readonly=False)
    try:
        repo = AiTaskRepository(conn)
        repo.update_run(
            task_id=task_id,
            status="done",
            stage=stage,
            progress_pct=1.0,
            message=message,
            result=result,
        )
        repo.add_event(
            task_id=task_id,
            event_type="result_ready",
            stage=stage,
            message=message,
            payload=result,
        )
    finally:
        conn.close()
```

- [ ] **Step 5: Add task API router**

Create `backend/api/ai_tasks.py`:

```python
"""AI task endpoints for observable reports, Agent chat, and enrichment."""

from __future__ import annotations

from fastapi import APIRouter

from backend.models.ai_tasks import AiTaskEventsResponse, AiTaskRunResponse
from backend.services.ai_task_service import get_task, get_task_events

router = APIRouter(prefix="/ai/tasks", tags=["AI Tasks"])


@router.get("/{task_id}", response_model=AiTaskRunResponse)
def get_ai_task(task_id: str):
    task = get_task(task_id)
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
        "result": task["result"],
        "error": task["error"],
        "created_at": task["created_at"],
        "updated_at": task["updated_at"],
    }


@router.get("/{task_id}/events", response_model=AiTaskEventsResponse)
def get_ai_task_events(task_id: str):
    payload = get_task_events(task_id)
    if payload is None:
        return {"found": False, "events": [], "tool_calls": []}
    events, tool_calls = payload
    return {"found": True, "events": events, "tool_calls": tool_calls}
```

Modify `backend/api/router.py`:

```python
from backend.api.ai_tasks import router as ai_tasks_router
```

Add near the existing AI routers:

```python
api_router.include_router(ai_tasks_router)
```

- [ ] **Step 6: Run contract tests**

Run:

```bash
.venv/bin/pytest backend/tests/contract/test_ai_task_api.py -q
```

Expected: PASS.

- [ ] **Step 7: Run response model audit target**

Run:

```bash
.venv/bin/pytest backend/tests/contract/test_remaining_json_response_models.py -q
```

Expected: PASS. If it fails because new endpoints are not accounted for, bind response models exactly as shown above before proceeding.

- [ ] **Step 8: Checkpoint**

Run:

```bash
git status --short
```

Expected: backend task API/model/service files are new, router modified. Do not commit unless the user explicitly asks.

---

### Task 3: Add Report Task Backend With Cache-Only And Manual Generate Modes

**Files:**
- Modify: `backend/services/ai_insights_service.py`
- Modify: `backend/services/ai_task_service.py`
- Modify: `backend/api/ai_tasks.py`
- Test: `backend/tests/unit/test_ai_report_tasks.py`
- Test: `backend/tests/contract/test_ai_task_api.py`

- [ ] **Step 1: Write failing report task tests**

Create `backend/tests/unit/test_ai_report_tasks.py`:

```python
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_cache_only_weekly_report_does_not_call_llm(monkeypatch):
    from backend.services import ai_task_service

    called = {"llm": False}

    monkeypatch.setattr(
        ai_task_service,
        "peek_report_cache",
        lambda request: {
            "cached": False,
            "report": None,
            "cached_at": None,
            "entities": None,
            "needs_generation": True,
        },
        raising=False,
    )
    monkeypatch.setattr(
        ai_task_service,
        "run_report_generation_task",
        lambda task_id, request: called.__setitem__("llm", True),
        raising=False,
    )

    result = ai_task_service.start_report_task(
        {
            "report_type": "weekly",
            "action": "cache_only",
            "week_start": "2026-06-17",
            "week_end": "2026-06-23",
            "min_ms": 30000,
            "music_only": True,
            "merge_enabled": True,
            "dynamic_threshold": True,
            "max_merge_gap_minutes": None,
        }
    )

    assert result["status"] == "done"
    assert result["result"]["needs_generation"] is True
    assert called["llm"] is False


def test_generate_weekly_report_starts_background_task(monkeypatch):
    from backend.services import ai_task_service

    observed = {}

    def fake_create_task(*, task_type, stage, message, request, handler):
        observed.update(
            {
                "task_type": task_type,
                "stage": stage,
                "message": message,
                "request": request,
                "handler": handler,
            }
        )
        return {
            "task_id": "task-123",
            "status": "queued",
            "stage": stage,
            "progress_pct": 0.0,
            "message": message,
            "result": None,
        }

    monkeypatch.setattr(ai_task_service, "create_task", fake_create_task)

    result = ai_task_service.start_report_task(
        {
            "report_type": "weekly",
            "action": "generate",
            "week_start": "2026-06-17",
            "week_end": "2026-06-23",
            "min_ms": 30000,
            "music_only": True,
            "merge_enabled": True,
            "dynamic_threshold": True,
            "max_merge_gap_minutes": None,
        }
    )

    assert result["task_id"] == "task-123"
    assert observed["task_type"] == "ai_report_weekly"
    assert observed["stage"] == "checking_cache"
    assert observed["handler"] == ai_task_service.run_report_generation_task
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_report_tasks.py -q
```

Expected: FAIL with `AttributeError` for `start_report_task`.

- [ ] **Step 3: Add report cache peek helper**

In `backend/services/ai_insights_service.py`, add a public helper after `_safe_extract_entities`:

```python
def peek_report_cache(
    conn: sqlite3.Connection,
    report_type: str,
    *,
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    dynamic_threshold: bool,
    max_merge_gap_minutes: Optional[int],
    week_start: str | None = None,
    week_end: str | None = None,
    month: str | None = None,
    year: int | None = None,
) -> dict:
    """Return cached AI report metadata without calling the LLM."""
    filter_part = _filter_cache_part(
        min_ms, music_only, merge_enabled, dynamic_threshold, max_merge_gap_minutes
    )
    if report_type == "weekly":
        key = _cache_key("weekly", week_start or "", week_end or "", filter_part)
        ttl = _CACHE_TTL["weekly"]
    elif report_type == "monthly":
        key = _cache_key("monthly", month or "", str(year or ""), filter_part)
        ttl = _CACHE_TTL["monthly"]
    elif report_type == "yearly":
        key = _cache_key("yearly", str(year or ""), filter_part)
        ttl = _CACHE_TTL["yearly"]
    else:
        return {"cached": False, "report": None, "cached_at": None, "entities": None}

    cached = _get_cached(conn, key, ttl)
    if not cached:
        return {"cached": False, "report": None, "cached_at": None, "entities": None}

    return {
        "cached": True,
        "report": cached[0],
        "cached_at": cached[1],
        "entities": {"artists": [], "tracks": []},
    }
```

- [ ] **Step 4: Add report task service functions**

In `backend/services/ai_task_service.py`, add imports:

```python
from backend.services import ai_insights_service
```

Then add these functions:

```python
def _task_type_for_report(report_type: str) -> str:
    return {
        "weekly": "ai_report_weekly",
        "monthly": "ai_report_monthly",
        "yearly": "ai_report_yearly",
    }[report_type]


def peek_report_cache(request: dict[str, Any]) -> dict[str, Any]:
    conn = get_db(readonly=True)
    try:
        cached = ai_insights_service.peek_report_cache(
            conn,
            request["report_type"],
            min_ms=request["min_ms"],
            music_only=request["music_only"],
            merge_enabled=request["merge_enabled"],
            dynamic_threshold=request["dynamic_threshold"],
            max_merge_gap_minutes=request.get("max_merge_gap_minutes"),
            week_start=request.get("week_start"),
            week_end=request.get("week_end"),
            month=request.get("month"),
            year=request.get("year"),
        )
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
                message="已检查报告缓存",
                request=request,
            )
            repo.add_event(
                task_id=task_id,
                event_type="cache_hit" if result["cached"] else "stage_completed",
                stage="checking_cache",
                message="命中缓存" if result["cached"] else "未找到缓存",
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
        finally:
            conn.close()
        return {
            "task_id": task_id,
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


def run_report_generation_task(task_id: str, request: dict[str, Any]) -> None:
    conn = get_db(readonly=False)
    try:
        repo = AiTaskRepository(conn)
        repo.update_run(
            task_id=task_id,
            status="running",
            stage="gathering_local_data",
            progress_pct=0.25,
            message="正在汇总本地播放数据",
        )
        repo.add_event(
            task_id=task_id,
            event_type="stage_started",
            stage="gathering_local_data",
            message="正在汇总本地播放数据",
        )

        report_type = request["report_type"]
        if report_type == "weekly":
            result = ai_insights_service.generate_weekly_digest(
                conn,
                request["min_ms"],
                request["music_only"],
                request["merge_enabled"],
                request["week_start"],
                request["week_end"],
                force=request.get("force", False),
                dynamic_threshold=request["dynamic_threshold"],
                max_merge_gap_minutes=request.get("max_merge_gap_minutes"),
            )
        elif report_type == "monthly":
            result = ai_insights_service.generate_monthly_personality(
                conn,
                request["min_ms"],
                request["music_only"],
                request["merge_enabled"],
                request["month"],
                request["year"],
                force=request.get("force", False),
                dynamic_threshold=request["dynamic_threshold"],
                max_merge_gap_minutes=request.get("max_merge_gap_minutes"),
            )
        else:
            result = ai_insights_service.generate_yearly_story(
                conn,
                request["min_ms"],
                request["music_only"],
                request["merge_enabled"],
                request["year"],
                force=request.get("force", False),
                dynamic_threshold=request["dynamic_threshold"],
                max_merge_gap_minutes=request.get("max_merge_gap_minutes"),
            )

        if result.get("success"):
            repo.update_run(
                task_id=task_id,
                status="done",
                stage="done",
                progress_pct=1.0,
                message="报告生成完成",
                result=result,
            )
            repo.add_event(
                task_id=task_id,
                event_type="result_ready",
                stage="done",
                message="报告生成完成",
                payload={"cached": result.get("cached", False)},
            )
            return

        repo.update_run(
            task_id=task_id,
            status="error",
            stage="error",
            progress_pct=1.0,
            message=result.get("error") or "报告生成失败",
            error=result.get("error") or "报告生成失败",
            result=result,
        )
        repo.add_event(
            task_id=task_id,
            event_type="error",
            stage="error",
            message=result.get("error") or "报告生成失败",
            payload=result,
        )
    except Exception as exc:
        repo = AiTaskRepository(conn)
        repo.update_run(
            task_id=task_id,
            status="error",
            stage="error",
            progress_pct=1.0,
            message="报告任务异常",
            error=str(exc)[:500],
        )
        repo.add_event(
            task_id=task_id,
            event_type="error",
            stage="error",
            message="报告任务异常",
            payload={"error": str(exc)[:500]},
        )
    finally:
        conn.close()
```

- [ ] **Step 5: Add report endpoint**

In `backend/api/ai_tasks.py`, add imports:

```python
from backend.models.ai_tasks import AiTaskCreateResponse, ReportTaskRequest
from backend.services.ai_task_service import start_report_task
```

Add endpoint before `GET /{task_id}`:

```python
@router.post("/report", response_model=AiTaskCreateResponse)
def create_report_task(body: ReportTaskRequest):
    return start_report_task(body.model_dump())
```

- [ ] **Step 6: Add contract test for cache-only mode**

Append to `backend/tests/contract/test_ai_task_api.py`:

```python
def test_report_cache_only_does_not_require_llm(client, monkeypatch):
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
    body = response.json()
    assert body["status"] == "done"
    assert body["result"]["needs_generation"] is True
```

- [ ] **Step 7: Run report tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_report_tasks.py backend/tests/contract/test_ai_task_api.py -q
```

Expected: PASS.

- [ ] **Step 8: Checkpoint**

Run:

```bash
git status --short
```

Expected: report task backend files modified. Do not commit unless the user explicitly asks.

---

### Task 4: Add Shared Frontend AI Task Types, Hooks, And UI Primitives

**Files:**
- Create: `frontend/src/types/ai-tasks.ts`
- Create: `frontend/src/hooks/useAiTasks.ts`
- Create: `frontend/src/features/ai-tasks/AITaskProgress.tsx`
- Create: `frontend/src/features/ai-tasks/AIToolTrace.tsx`
- Create: `frontend/src/features/ai-tasks/AIResultShell.tsx`
- Modify: `frontend/src/api/query-keys.ts`
- Test: `frontend/src/tests/ai-task-components.test.tsx`
- Test: `frontend/src/tests/ai-task-hooks.test.tsx`

- [ ] **Step 1: Write failing component tests**

Create `frontend/src/tests/ai-task-components.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { AITaskProgress } from '@/features/ai-tasks/AITaskProgress'
import { AIToolTrace } from '@/features/ai-tasks/AIToolTrace'

describe('AITaskProgress', () => {
  it('renders current stage and completed events', () => {
    render(
      <AITaskProgress
        task={{
          found: true,
          task_id: 'task-1',
          task_type: 'ai_report_weekly',
          status: 'running',
          stage: 'calling_llm',
          progress_pct: 0.6,
          message: 'AI 正在生成周报',
          result: null,
          error: null,
          created_at: '2026-06-28T00:00:00',
          updated_at: '2026-06-28T00:00:01',
        }}
        events={[
          {
            event_id: 1,
            task_id: 'task-1',
            event_type: 'stage_completed',
            stage: 'gathering_local_data',
            message: '已汇总播放数据',
            payload: null,
            created_at: '2026-06-28T00:00:00',
          },
        ]}
      />,
    )

    expect(screen.getByText('AI 正在生成周报')).toBeInTheDocument()
    expect(screen.getByText('已汇总播放数据')).toBeInTheDocument()
  })
})

describe('AIToolTrace', () => {
  it('renders readable tool evidence', () => {
    render(
      <AIToolTrace
        toolCalls={[
          {
            tool_call_id: 1,
            task_id: 'task-1',
            tool_name: 'analysis_charts',
            status: 'done',
            params_summary: '2026 artist plays top 10',
            result_summary: 'Artist A ranked #1',
            source_range: '2026-01-01 to 2026-12-31',
            error: null,
            started_at: '2026-06-28T00:00:00',
            completed_at: '2026-06-28T00:00:01',
          },
        ]}
      />,
    )

    expect(screen.getByText('analysis_charts')).toBeInTheDocument()
    expect(screen.getByText('Artist A ranked #1')).toBeInTheDocument()
    expect(screen.getByText('2026-01-01 to 2026-12-31')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Write failing hook test**

Create `frontend/src/tests/ai-task-hooks.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { api } from '@/lib/api'
import { useAiTask } from '@/hooks/useAiTasks'

function wrapper(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
}

describe('useAiTask', () => {
  it('loads task and events', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    vi.spyOn(api, 'get').mockImplementation((path: string) => {
      if (path === '/ai/tasks/task-1') {
        return Promise.resolve({
          found: true,
          task_id: 'task-1',
          status: 'done',
          stage: 'done',
          progress_pct: 1,
          message: '完成',
          result: { report: 'hello' },
          error: null,
        })
      }
      return Promise.resolve({ found: true, events: [], tool_calls: [] })
    })

    const { result } = renderHook(() => useAiTask('task-1'), {
      wrapper: wrapper(client),
    })

    await waitFor(() => expect(result.current.task?.status).toBe('done'))
    expect(result.current.events).toEqual([])
    expect(result.current.toolCalls).toEqual([])
  })
})
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
cd frontend && npm test -- ai-task-components.test.tsx ai-task-hooks.test.tsx --run
```

Expected: FAIL with unresolved imports for `@/features/ai-tasks/*` and `@/hooks/useAiTasks`.

- [ ] **Step 4: Add frontend types**

Create `frontend/src/types/ai-tasks.ts`:

```ts
export type AiTaskStatus = 'queued' | 'running' | 'done' | 'error' | 'cancelled'

export interface AiTaskRun {
  found: boolean
  task_id: string | null
  task_type: string | null
  status: AiTaskStatus | string | null
  stage: string | null
  progress_pct: number
  message: string
  result: Record<string, unknown> | null
  error: string | null
  created_at: string | null
  updated_at: string | null
}

export interface AiTaskEvent {
  event_id: number
  task_id: string
  event_type: string
  stage: string
  message: string
  payload: Record<string, unknown> | null
  created_at: string
}

export interface AiToolCall {
  tool_call_id: number
  task_id: string
  tool_name: string
  status: string
  params_summary: string
  result_summary: string
  source_range: string
  error: string | null
  started_at: string
  completed_at: string | null
}

export interface AiTaskEventsPayload {
  found: boolean
  events: AiTaskEvent[]
  tool_calls: AiToolCall[]
}

export interface AiTaskCreatePayload {
  task_id: string
  status: string
  stage: string
  progress_pct: number
  message: string
  result: Record<string, unknown> | null
}
```

- [ ] **Step 5: Add query keys and hook**

Modify `frontend/src/api/query-keys.ts`, add:

```ts
  aiTasks: {
    all: ['ai-tasks'] as const,
    task: (taskId: string) => ['ai-tasks', 'task', taskId] as const,
    events: (taskId: string) => ['ai-tasks', 'events', taskId] as const,
  },
```

Create `frontend/src/hooks/useAiTasks.ts`:

```ts
import { useQuery } from '@tanstack/react-query'

import { queryKeys } from '@/api/query-keys'
import { api } from '@/lib/api'
import type { AiTaskEventsPayload, AiTaskRun } from '@/types/ai-tasks'

function shouldPoll(task: AiTaskRun | null): boolean {
  return task?.status === 'queued' || task?.status === 'running'
}

export function useAiTask(taskId: string | null) {
  const taskQuery = useQuery({
    queryKey: taskId ? queryKeys.aiTasks.task(taskId) : [...queryKeys.aiTasks.all, 'none'],
    queryFn: () => api.get<AiTaskRun>(`/ai/tasks/${taskId}`),
    enabled: !!taskId,
    refetchInterval: (query) => shouldPoll((query.state.data as AiTaskRun | undefined) ?? null) ? 1000 : false,
  })

  const eventsQuery = useQuery({
    queryKey: taskId ? queryKeys.aiTasks.events(taskId) : [...queryKeys.aiTasks.all, 'events', 'none'],
    queryFn: () => api.get<AiTaskEventsPayload>(`/ai/tasks/${taskId}/events`),
    enabled: !!taskId,
    refetchInterval: shouldPoll(taskQuery.data ?? null) ? 1000 : false,
  })

  return {
    task: taskQuery.data ?? null,
    events: eventsQuery.data?.events ?? [],
    toolCalls: eventsQuery.data?.tool_calls ?? [],
    loading: taskQuery.isLoading,
    error: taskQuery.error instanceof Error ? taskQuery.error.message : null,
    refetch: () => {
      void taskQuery.refetch()
      void eventsQuery.refetch()
    },
  }
}
```

- [ ] **Step 6: Add UI primitives**

Create `frontend/src/features/ai-tasks/AITaskProgress.tsx`:

```tsx
import type { AiTaskEvent, AiTaskRun } from '@/types/ai-tasks'

interface Props {
  task: AiTaskRun | null
  events: AiTaskEvent[]
}

export function AITaskProgress({ task, events }: Props) {
  if (!task) return null

  const pct = Math.round((task.progress_pct ?? 0) * 100)
  return (
    <div className="rounded-xl border border-border bg-card/40 p-4 backdrop-blur-[12px]">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[1.2px] text-muted-foreground">
            AI 任务进度
          </p>
          <p className="mt-1 text-[13px] text-foreground">{task.message || task.stage}</p>
        </div>
        <span className="text-[12px] text-muted-foreground">{pct}%</span>
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted/30">
        <div
          className="h-full rounded-full bg-accent-foreground transition-[width]"
          style={{ width: `${pct}%` }}
        />
      </div>
      {events.length > 0 && (
        <ol className="mt-3 space-y-1.5">
          {events.map((event) => (
            <li key={event.event_id} className="text-[12px] text-muted-foreground">
              {event.message || event.stage}
            </li>
          ))}
        </ol>
      )}
      {task.status === 'error' && task.error && (
        <p className="mt-3 text-[12px] text-destructive">{task.error}</p>
      )}
    </div>
  )
}
```

Create `frontend/src/features/ai-tasks/AIToolTrace.tsx`:

```tsx
import type { AiToolCall } from '@/types/ai-tasks'

interface Props {
  toolCalls: AiToolCall[]
}

export function AIToolTrace({ toolCalls }: Props) {
  if (toolCalls.length === 0) return null

  return (
    <div className="rounded-xl border border-border bg-card/30 p-4">
      <p className="text-[11px] font-semibold uppercase tracking-[1.2px] text-muted-foreground">
        数据查询轨迹
      </p>
      <div className="mt-3 space-y-2">
        {toolCalls.map((call) => (
          <div key={call.tool_call_id} className="rounded-lg bg-muted/25 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-[12px] text-foreground">{call.tool_name}</span>
              <span className="text-[11px] text-muted-foreground">{call.status}</span>
            </div>
            {call.params_summary && (
              <p className="mt-1 text-[12px] text-muted-foreground">{call.params_summary}</p>
            )}
            {call.result_summary && (
              <p className="mt-1 text-[12px] text-foreground/80">{call.result_summary}</p>
            )}
            {call.source_range && (
              <p className="mt-1 text-[11px] text-muted-foreground/70">{call.source_range}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
```

Create `frontend/src/features/ai-tasks/AIResultShell.tsx`:

```tsx
import type { ReactNode } from 'react'

import { AITaskProgress } from './AITaskProgress'
import { AIToolTrace } from './AIToolTrace'
import type { AiTaskEvent, AiTaskRun, AiToolCall } from '@/types/ai-tasks'

interface Props {
  task: AiTaskRun | null
  events: AiTaskEvent[]
  toolCalls?: AiToolCall[]
  children: ReactNode
}

export function AIResultShell({ task, events, toolCalls = [], children }: Props) {
  return (
    <div className="space-y-4">
      <AITaskProgress task={task} events={events} />
      <AIToolTrace toolCalls={toolCalls} />
      {children}
      <p className="text-center text-[11px] text-muted-foreground/60">
        由 AI 基于本地听歌数据生成，仅供参考。
      </p>
    </div>
  )
}
```

- [ ] **Step 7: Run frontend tests**

Run:

```bash
cd frontend && npm test -- ai-task-components.test.tsx ai-task-hooks.test.tsx --run
```

Expected: PASS.

- [ ] **Step 8: Checkpoint**

Run:

```bash
git status --short
```

Expected: frontend shared task files are new, query keys modified. Do not commit unless the user explicitly asks.

---

### Task 5: Move AI Reports To Cache-First Manual Generation Flow

**Files:**
- Modify: `frontend/src/hooks/useAiTasks.ts`
- Modify: `frontend/src/features/ai-insights/AiInsightsExperience.tsx`
- Modify: `frontend/src/features/ai-insights/ReportCard.tsx`
- Test: `frontend/src/tests/ai-insights-task-flow.test.tsx`

- [ ] **Step 1: Write failing report flow test**

Create `frontend/src/tests/ai-insights-task-flow.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { AiInsightsExperience } from '@/features/ai-insights/AiInsightsExperience'
import { api } from '@/lib/api'

vi.mock('@/hooks/useSettings', () => ({
  useSettings: () => ({
    settings: {
      llm_enabled: true,
      has_llm_key: true,
      min_ms: 30000,
      music_only: true,
      merge_enabled: true,
    },
  }),
}))

function wrapper(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
}

describe('AiInsightsExperience report tasks', () => {
  it('shows generate action when cache is missing and starts generation only after click', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const getSpy = vi.spyOn(api, 'get').mockImplementation((path: string) => {
      if (path === '/analysis/stats') {
        return Promise.resolve({ period: { start_date: '2026-01-01', end_date: '2026-06-23' } })
      }
      if (path === '/ai/tasks/task-generate') {
        return Promise.resolve({
          found: true,
          task_id: 'task-generate',
          status: 'done',
          stage: 'done',
          progress_pct: 1,
          message: '报告生成完成',
          result: { success: true, report: '生成后的周报', cached: false },
          error: null,
        })
      }
      if (path === '/ai/tasks/task-generate/events') {
        return Promise.resolve({ found: true, events: [], tool_calls: [] })
      }
      return Promise.resolve({})
    })
    const postSpy = vi.spyOn(api, 'post').mockResolvedValueOnce({
      task_id: 'task-cache',
      status: 'done',
      stage: 'done',
      progress_pct: 1,
      message: '缓存检查完成',
      result: { cached: false, report: null, needs_generation: true },
    }).mockResolvedValueOnce({
      task_id: 'task-generate',
      status: 'queued',
      stage: 'checking_cache',
      progress_pct: 0,
      message: '准备生成 AI 报告',
      result: null,
    })

    render(<AiInsightsExperience />, { wrapper: wrapper(client) })

    await screen.findByText('生成报告')
    expect(postSpy).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByText('生成报告'))

    await waitFor(() => expect(postSpy).toHaveBeenCalledTimes(2))
    expect(getSpy).toHaveBeenCalledWith('/ai/tasks/task-generate')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd frontend && npm test -- ai-insights-task-flow.test.tsx --run
```

Expected: FAIL because `AiInsightsExperience` does not call `/ai/tasks/report`.

- [ ] **Step 3: Add report task hook**

In `frontend/src/hooks/useAiTasks.ts`, add:

```ts
import { useMutation } from '@tanstack/react-query'
import type { AiTaskCreatePayload } from '@/types/ai-tasks'

export interface ReportTaskRequest {
  report_type: 'weekly' | 'monthly' | 'yearly'
  action: 'cache_only' | 'generate'
  force?: boolean
  week_start?: string
  week_end?: string
  month?: string
  year?: number
  min_ms?: number
  music_only?: boolean
  merge_enabled?: boolean
  dynamic_threshold?: boolean
  max_merge_gap_minutes?: number | null
}

export function useStartReportTask() {
  return useMutation({
    mutationFn: (payload: ReportTaskRequest) =>
      api.post<AiTaskCreatePayload>('/ai/tasks/report', payload),
  })
}
```

- [ ] **Step 4: Update report UI flow**

Modify `frontend/src/features/ai-insights/AiInsightsExperience.tsx`:

- Import `useStartReportTask` and `useAiTask`.
- Replace automatic `useWeeklyDigest`, `useMonthlyPersonality`, and `useYearlyStory` calls with:
  - cache-only task on period/report type changes;
  - local `activeReportTaskId`;
  - generate button when result has `needs_generation: true`;
  - `useAiTask(activeReportTaskId)` while generating.

Use this helper inside the component:

```tsx
const baseReportPayload = {
  min_ms: settings?.min_ms ?? 30000,
  music_only: settings?.music_only ?? true,
  merge_enabled: settings?.merge_enabled ?? true,
  dynamic_threshold: true,
  max_merge_gap_minutes: null,
}
```

Use this button text for cache miss:

```tsx
生成报告
```

The report card should receive `task.result.report` when the task completes.

- [ ] **Step 5: Preserve existing ReportCard actions**

Modify `frontend/src/features/ai-insights/ReportCard.tsx` so `onRetry` label remains `刷新报告`, and the parent passes a generate callback with `force: true`.

- [ ] **Step 6: Run report flow test**

Run:

```bash
cd frontend && npm test -- ai-insights-task-flow.test.tsx --run
```

Expected: PASS.

- [ ] **Step 7: Run existing AI hook/component tests**

Run:

```bash
cd frontend && npm test -- ai-insights-components.test.tsx query-hooks.test.tsx --run
```

Expected: PASS. If `query-hooks.test.tsx` still asserts old `useWeeklyDigest` behavior, keep those hooks available for compatibility and add new task-flow tests without deleting old hooks.

- [ ] **Step 8: Checkpoint**

Run:

```bash
git status --short
```

Expected: AI Insights frontend files modified. Do not commit unless the user explicitly asks.

---

### Task 6: Add Read-Only Agent Tool Registry

**Files:**
- Create: `backend/domains/ai_agent/tool_registry.py`
- Create: `backend/domains/ai_agent/tools.py`
- Test: `backend/tests/unit/test_ai_agent_tools.py`

- [ ] **Step 1: Write failing tool registry tests**

Create `backend/tests/unit/test_ai_agent_tools.py`:

```python
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_registry_rejects_unknown_tool():
    from backend.domains.ai_agent.tool_registry import get_tool_registry

    registry = get_tool_registry()

    with pytest.raises(KeyError):
        registry.execute("settings_update", {})


def test_registry_returns_evidence_summary(monkeypatch):
    from backend.domains.ai_agent.tool_registry import get_tool_registry

    registry = get_tool_registry()

    def fake_handler(params):
        return {
            "data": {"total_plays": 10},
            "params_summary": "2026 lifetime stats",
            "result_summary": "10 plays",
            "source_range": "2026-01-01 to 2026-12-31",
        }

    registry.register_for_test(
        name="test_read_only",
        label="Test Read Only",
        schema={"type": "object", "properties": {}},
        handler=fake_handler,
    )

    result = registry.execute("test_read_only", {})

    assert result["result_summary"] == "10 plays"
    assert result["source_range"] == "2026-01-01 to 2026-12-31"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_tools.py -q
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement registry**

Create `backend/domains/ai_agent/tool_registry.py`:

```python
"""Read-only Agent tool registry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class AgentTool:
    name: str
    label: str
    schema: dict[str, Any]
    handler: ToolHandler
    permission: str = "read_only"


class AgentToolRegistry:
    def __init__(self):
        self._tools: dict[str, AgentTool] = {}

    def register(self, tool: AgentTool) -> None:
        if tool.permission != "read_only":
            raise ValueError("Agent tools must be read_only")
        self._tools[tool.name] = tool

    def register_for_test(
        self,
        *,
        name: str,
        label: str,
        schema: dict[str, Any],
        handler: ToolHandler,
    ) -> None:
        self.register(AgentTool(name=name, label=label, schema=schema, handler=handler))

    def describe_for_model(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "label": tool.label,
                "schema": tool.schema,
                "permission": tool.permission,
            }
            for tool in self._tools.values()
        ]

    def execute(self, name: str, params: dict[str, Any]) -> dict[str, Any]:
        if name not in self._tools:
            raise KeyError(f"Unsupported read-only tool: {name}")
        result = self._tools[name].handler(params)
        return {
            "tool_name": name,
            "data": result.get("data"),
            "params_summary": result.get("params_summary", ""),
            "result_summary": result.get("result_summary", ""),
            "source_range": result.get("source_range", ""),
        }


_registry: AgentToolRegistry | None = None


def get_tool_registry() -> AgentToolRegistry:
    global _registry
    if _registry is None:
        from backend.domains.ai_agent.tools import build_default_registry

        _registry = build_default_registry()
    return _registry
```

- [ ] **Step 4: Implement initial tools**

Create `backend/domains/ai_agent/tools.py`:

```python
"""Read-only Agent tool handlers backed by existing SpotifyStats services."""

from __future__ import annotations

from typing import Any

from backend.core.db import get_db
from backend.domains.ai_agent.tool_registry import AgentTool, AgentToolRegistry


def _period_summary(params: dict[str, Any]) -> tuple[str, str | None, str | None]:
    period = str(params.get("period") or "lifetime")
    start_date = params.get("start_date")
    end_date = params.get("end_date")
    if start_date or end_date:
        return "custom", start_date, end_date
    return period, None, None


def analysis_stats_tool(params: dict[str, Any]) -> dict[str, Any]:
    from backend.services.analysis_stats_service import get_analysis_stats

    period, start_date, end_date = _period_summary(params)
    conn = get_db(readonly=True)
    try:
        data = get_analysis_stats(
            conn,
            min_ms=int(params.get("min_ms", 30000)),
            music_only=bool(params.get("music_only", True)),
            merge_enabled=bool(params.get("merge_enabled", True)),
            period=period,
            start_date=start_date,
            end_date=end_date,
            dynamic_threshold=bool(params.get("dynamic_threshold", True)),
            max_merge_gap_minutes=params.get("max_merge_gap_minutes"),
        )
    finally:
        conn.close()
    total_plays = data.get("summary", {}).get("total_plays", 0)
    return {
        "data": data,
        "params_summary": f"{period} overall listening stats",
        "result_summary": f"{total_plays} total plays",
        "source_range": f"{start_date or data.get('period', {}).get('start_date') or 'start'} to {end_date or data.get('period', {}).get('end_date') or 'end'}",
    }


def analysis_charts_tool(params: dict[str, Any]) -> dict[str, Any]:
    from backend.services.analysis_stats_service import get_analysis_charts

    period, start_date, end_date = _period_summary(params)
    entity = str(params.get("entity") or "artist")
    conn = get_db(readonly=True)
    try:
        data = get_analysis_charts(
            conn,
            min_ms=int(params.get("min_ms", 30000)),
            music_only=bool(params.get("music_only", True)),
            merge_enabled=bool(params.get("merge_enabled", True)),
            period=period,
            start_date=start_date,
            end_date=end_date,
            entity=entity,
            metric=str(params.get("metric") or "plays"),
            limit=int(params.get("limit", 10)),
            offset=0,
            include_compilations=bool(params.get("include_compilations", False)),
            dynamic_threshold=bool(params.get("dynamic_threshold", True)),
            max_merge_gap_minutes=params.get("max_merge_gap_minutes"),
            merge_level=int(params.get("merge_level", 1)),
        )
    finally:
        conn.close()
    rows = data.get("items") or data.get("rows") or []
    first_name = rows[0].get("name") if rows and isinstance(rows[0], dict) else "no result"
    return {
        "data": data,
        "params_summary": f"{period} top {entity}",
        "result_summary": f"Top {entity}: {first_name}",
        "source_range": f"{start_date or 'period start'} to {end_date or 'period end'}",
    }


def build_default_registry() -> AgentToolRegistry:
    registry = AgentToolRegistry()
    common_schema = {
        "type": "object",
        "properties": {
            "period": {"type": "string"},
            "start_date": {"type": "string"},
            "end_date": {"type": "string"},
            "min_ms": {"type": "integer"},
            "music_only": {"type": "boolean"},
            "merge_enabled": {"type": "boolean"},
            "dynamic_threshold": {"type": "boolean"},
            "max_merge_gap_minutes": {"type": ["integer", "null"]},
        },
    }
    registry.register(
        AgentTool(
            name="analysis_stats",
            label="Overall listening statistics",
            schema=common_schema,
            handler=analysis_stats_tool,
        )
    )
    chart_schema = {
        **common_schema,
        "properties": {
            **common_schema["properties"],
            "entity": {"type": "string", "enum": ["track", "artist", "album"]},
            "metric": {"type": "string", "enum": ["plays", "hours"]},
            "limit": {"type": "integer"},
            "merge_level": {"type": "integer"},
        },
    }
    registry.register(
        AgentTool(
            name="analysis_charts",
            label="Top tracks, artists, or albums",
            schema=chart_schema,
            handler=analysis_charts_tool,
        )
    )
    return registry
```

This starts with two tools. Add the remaining V2 tools in Task 7 while testing the Agent loop:

- `playback_records`
- `wrapped_yearly`
- `entity_stats`
- `billboard_entity_detail`
- `listening_hours`

- [ ] **Step 5: Run tool tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_tools.py -q
```

Expected: PASS.

- [ ] **Step 6: Checkpoint**

Run:

```bash
git status --short
```

Expected: AI Agent tool registry files are new. Do not commit unless the user explicitly asks.

---

### Task 7: Add Read-Only Agent Chat Task Backend

**Files:**
- Modify: `backend/domains/ai_agent/tools.py`
- Create: `backend/services/ai_agent_service.py`
- Modify: `backend/services/ai_task_service.py`
- Modify: `backend/api/ai_tasks.py`
- Test: `backend/tests/contract/test_ai_agent_task_contract.py`

- [ ] **Step 1: Write failing Agent task contract test**

Create `backend/tests/contract/test_ai_agent_task_contract.py`:

```python
from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


def test_chat_agent_task_persists_tool_trace(client, monkeypatch):
    import backend.services.ai_agent_service as agent_service

    def fake_run(task_id, request):
        from backend.core.db import get_db
        from backend.domains.ai_tasks.repository import AiTaskRepository

        conn = get_db(readonly=False)
        try:
            repo = AiTaskRepository(conn)
            repo.add_tool_call(
                task_id=task_id,
                tool_name="analysis_stats",
                status="done",
                params_summary="2026 stats",
                result_summary="10 plays",
                source_range="2026-01-01 to 2026-12-31",
            )
            repo.update_run(
                task_id=task_id,
                status="done",
                stage="done",
                progress_pct=1.0,
                message="回答生成完成",
                result={"answer": "你在 2026 年共有 10 次有效播放。"},
            )
        finally:
            conn.close()

    monkeypatch.setattr(agent_service, "run_chat_agent_task", fake_run)

    response = client.post(
        "/api/ai/tasks/chat",
        json={"question": "我今年听了多少次？"},
    )

    assert response.status_code == 200
    task_id = response.json()["task_id"]

    detail = client.get(f"/api/ai/tasks/{task_id}").json()
    events = client.get(f"/api/ai/tasks/{task_id}/events").json()

    assert detail["status"] == "done"
    assert detail["result"]["answer"].startswith("你在 2026 年")
    assert events["tool_calls"][0]["tool_name"] == "analysis_stats"
    assert events["tool_calls"][0]["source_range"] == "2026-01-01 to 2026-12-31"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/pytest backend/tests/contract/test_ai_agent_task_contract.py -q
```

Expected: FAIL with 404 for `/api/ai/tasks/chat`.

- [ ] **Step 3: Add remaining read-only tools**

Extend `backend/domains/ai_agent/tools.py` with handlers for:

- `playback_records`: wraps `backend.services.analysis_records_service`.
- `wrapped_yearly`: wraps `backend.services.wrapped_service.get_wrapped_full`.
- `entity_stats`: wraps `backend.services.entity_stats_service`.
- `billboard_entity_detail`: wraps existing Billboard detail services or API-level service functions.
- `listening_hours`: wraps `backend.services.analysis_stats_service` helpers or `backend.api.listening_hours` service functions.

Each handler must return:

```python
{
    "data": data,
    "params_summary": "...",
    "result_summary": "...",
    "source_range": "...",
}
```

Register all five tools in `build_default_registry()` with `permission="read_only"`.

- [ ] **Step 4: Implement Agent service**

Create `backend/services/ai_agent_service.py`:

```python
"""Read-only AI Agent task runner."""

from __future__ import annotations

import json
from typing import Any

from backend.core.db import get_db
from backend.domains.ai_agent.tool_registry import get_tool_registry
from backend.domains.ai_tasks.repository import AiTaskRepository
from backend.services.ai_insights_service import _llm_chat

AGENT_PLAN_SYSTEM = """你是 SpotifyStats 的只读数据分析规划器。
只能从给定 tools 中选择工具。返回 JSON:
{"tool_calls":[{"tool_name":"analysis_stats","params":{}}]}
最多选择 5 个工具。不要要求写入、导入、清缓存、访问 URL 或执行 SQL。"""

AGENT_ANSWER_SYSTEM = """你是 SpotifyStats 的音乐数据分析助手。
只能基于 TOOL_RESULTS 中的数据回答。用中文，简洁，引用关键数字，并说明数据范围。"""


def _parse_tool_plan(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return [{"tool_name": "analysis_stats", "params": {"period": "lifetime"}}]
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        parsed = json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        return [{"tool_name": "analysis_stats", "params": {"period": "lifetime"}}]
    calls = parsed.get("tool_calls") or []
    return [
        {
            "tool_name": str(item.get("tool_name", "")),
            "params": item.get("params") if isinstance(item.get("params"), dict) else {},
        }
        for item in calls[:5]
        if item.get("tool_name")
    ]


def run_chat_agent_task(task_id: str, request: dict[str, Any]) -> None:
    conn = get_db(readonly=False)
    try:
        repo = AiTaskRepository(conn)
        repo.update_run(
            task_id=task_id,
            status="running",
            stage="planning_tools",
            progress_pct=0.15,
            message="正在规划数据查询",
        )
        repo.add_event(
            task_id=task_id,
            event_type="stage_started",
            stage="planning_tools",
            message="正在规划数据查询",
        )

        registry = get_tool_registry()
        plan_prompt = json.dumps(
            {
                "question": request["question"],
                "tools": registry.describe_for_model(),
            },
            ensure_ascii=False,
        )
        raw_plan = _llm_chat(AGENT_PLAN_SYSTEM, plan_prompt, temperature=0.1)
        tool_plan = _parse_tool_plan(raw_plan)
        tool_results = []

        for index, call in enumerate(tool_plan, start=1):
            tool_name = call["tool_name"]
            params = {
                **call.get("params", {}),
                "min_ms": request.get("min_ms", 30000),
                "music_only": request.get("music_only", True),
                "merge_enabled": request.get("merge_enabled", True),
                "dynamic_threshold": request.get("dynamic_threshold", True),
                "max_merge_gap_minutes": request.get("max_merge_gap_minutes"),
                "merge_level": request.get("merge_level", 1),
            }
            repo.update_run(
                task_id=task_id,
                status="running",
                stage="calling_tool",
                progress_pct=min(0.75, 0.2 + index * 0.1),
                message=f"正在查询 {tool_name}",
            )
            try:
                result = registry.execute(tool_name, params)
                tool_results.append(result)
                repo.add_tool_call(
                    task_id=task_id,
                    tool_name=tool_name,
                    status="done",
                    params_summary=result["params_summary"],
                    result_summary=result["result_summary"],
                    source_range=result["source_range"],
                )
            except Exception as exc:
                repo.add_tool_call(
                    task_id=task_id,
                    tool_name=tool_name,
                    status="error",
                    params_summary=json.dumps(params, ensure_ascii=False)[:300],
                    error=str(exc)[:300],
                )

        repo.update_run(
            task_id=task_id,
            status="running",
            stage="calling_llm",
            progress_pct=0.85,
            message="AI 正在生成回答",
        )
        answer_prompt = json.dumps(
            {
                "question": request["question"],
                "tool_results": tool_results,
                "conversation_history": request.get("conversation_history") or [],
            },
            ensure_ascii=False,
        )
        answer = _llm_chat(AGENT_ANSWER_SYSTEM, answer_prompt, temperature=0.4)
        if not answer:
            answer = "我没能生成可靠回答，请稍后重试。"

        repo.update_run(
            task_id=task_id,
            status="done",
            stage="done",
            progress_pct=1.0,
            message="回答生成完成",
            result={"answer": answer, "tool_results": tool_results},
        )
        repo.add_event(
            task_id=task_id,
            event_type="result_ready",
            stage="done",
            message="回答生成完成",
            payload={"tool_call_count": len(tool_results)},
        )
    except Exception as exc:
        repo = AiTaskRepository(conn)
        repo.update_run(
            task_id=task_id,
            status="error",
            stage="error",
            progress_pct=1.0,
            message="Agent 任务异常",
            error=str(exc)[:500],
        )
    finally:
        conn.close()
```

- [ ] **Step 5: Add chat task starter**

In `backend/services/ai_task_service.py`, add:

```python
def start_chat_agent_task(request: dict[str, Any]) -> dict[str, Any]:
    from backend.services.ai_agent_service import run_chat_agent_task

    return create_task(
        task_type="ai_chat_agent",
        stage="planning_tools",
        message="准备分析问题",
        request=request,
        handler=run_chat_agent_task,
    )
```

- [ ] **Step 6: Add chat endpoint**

In `backend/api/ai_tasks.py`, import:

```python
from backend.models.ai_tasks import ChatAgentTaskRequest
from backend.services.ai_task_service import start_chat_agent_task
```

Add:

```python
@router.post("/chat", response_model=AiTaskCreateResponse)
def create_chat_agent_task(body: ChatAgentTaskRequest):
    return start_chat_agent_task(body.model_dump())
```

- [ ] **Step 7: Run Agent backend tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_tools.py backend/tests/contract/test_ai_agent_task_contract.py -q
```

Expected: PASS.

- [ ] **Step 8: Check read-only enforcement**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_agent_tools.py::test_registry_rejects_unknown_tool -q
```

Expected: PASS.

- [ ] **Step 9: Checkpoint**

Run:

```bash
git status --short
```

Expected: Agent backend files modified or created. Do not commit unless the user explicitly asks.

---

### Task 8: Move AI Chat UI To Agent Task Flow

**Files:**
- Modify: `frontend/src/hooks/useAiTasks.ts`
- Modify: `frontend/src/features/ai-insights/ChatInterface.tsx`
- Modify: `frontend/src/features/ai-insights/ChatMessageList.tsx`
- Test: `frontend/src/tests/ai-insights-task-flow.test.tsx`

- [ ] **Step 1: Add failing chat task frontend test**

Append to `frontend/src/tests/ai-insights-task-flow.test.tsx`:

```tsx
import { ChatInterface } from '@/features/ai-insights/ChatInterface'

describe('ChatInterface agent tasks', () => {
  it('starts chat task and renders tool trace after answer', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    vi.spyOn(api, 'post').mockResolvedValue({
      task_id: 'chat-task',
      status: 'queued',
      stage: 'planning_tools',
      progress_pct: 0,
      message: '准备分析问题',
      result: null,
    })
    vi.spyOn(api, 'get').mockImplementation((path: string) => {
      if (path === '/ai/tasks/chat-task') {
        return Promise.resolve({
          found: true,
          task_id: 'chat-task',
          task_type: 'ai_chat_agent',
          status: 'done',
          stage: 'done',
          progress_pct: 1,
          message: '回答生成完成',
          result: { answer: '你今年听了 10 次。' },
          error: null,
        })
      }
      if (path === '/ai/tasks/chat-task/events') {
        return Promise.resolve({
          found: true,
          events: [],
          tool_calls: [
            {
              tool_call_id: 1,
              task_id: 'chat-task',
              tool_name: 'analysis_stats',
              status: 'done',
              params_summary: '2026 stats',
              result_summary: '10 plays',
              source_range: '2026',
              error: null,
              started_at: '2026-06-28T00:00:00',
              completed_at: '2026-06-28T00:00:01',
            },
          ],
        })
      }
      return Promise.resolve({})
    })

    render(
      <ChatInterface sessionId={null} onSessionCreated={() => {}} />,
      { wrapper: wrapper(client) },
    )

    fireEvent.change(screen.getByPlaceholderText('输入问题，如「我今年听最多的艺人是谁？」'), {
      target: { value: '我今年听了多少次？' },
    })
    fireEvent.click(screen.getByRole('button', { name: '发送问题' }))

    await screen.findByText('你今年听了 10 次。')
    expect(screen.getByText('analysis_stats')).toBeInTheDocument()
    expect(screen.getByText('10 plays')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd frontend && npm test -- ai-insights-task-flow.test.tsx --run
```

Expected: FAIL because chat still calls `/ai-insights/ask`.

- [ ] **Step 3: Add chat task starter hook**

In `frontend/src/hooks/useAiTasks.ts`, add:

```ts
export interface ChatAgentTaskRequest {
  question: string
  conversation_history?: { role: string; content: string }[]
  min_ms?: number
  music_only?: boolean
  merge_enabled?: boolean
  dynamic_threshold?: boolean
  max_merge_gap_minutes?: number | null
  merge_level?: number
}

export function useStartChatAgentTask() {
  return useMutation({
    mutationFn: (payload: ChatAgentTaskRequest) =>
      api.post<AiTaskCreatePayload>('/ai/tasks/chat', payload),
  })
}
```

- [ ] **Step 4: Update ChatInterface**

Modify `frontend/src/features/ai-insights/ChatInterface.tsx`:

- Replace `useAskQuestion()` for new sends with `useStartChatAgentTask()` and `useAiTask(taskId)`.
- Keep `useAskQuestion()` import only if old paths remain for compatibility; otherwise remove unused import.
- When task completes with `result.answer`, append assistant message with `meta` containing:

```ts
{
  success: true,
  answer,
  error: null,
  period_info: null,
  start_date: null,
  end_date: null,
  tool_calls: toolCalls,
}
```

- Save assistant metadata through existing `saveMessage`.

- [ ] **Step 5: Update ChatMessageList to render trace**

Modify `frontend/src/features/ai-insights/ChatMessageList.tsx`:

- Import `AIToolTrace`.
- When assistant `msg.meta?.tool_calls` exists, render:

```tsx
<div className="mt-3">
  <AIToolTrace toolCalls={msg.meta.tool_calls} />
</div>
```

Also update `frontend/src/types/ai-insights.ts` so `AskResponse` includes:

```ts
tool_calls?: import('@/types/ai-tasks').AiToolCall[]
```

- [ ] **Step 6: Run chat frontend test**

Run:

```bash
cd frontend && npm test -- ai-insights-task-flow.test.tsx --run
```

Expected: PASS.

- [ ] **Step 7: Run existing AI component tests**

Run:

```bash
cd frontend && npm test -- ai-insights-components.test.tsx --run
```

Expected: PASS.

- [ ] **Step 8: Checkpoint**

Run:

```bash
git status --short
```

Expected: chat frontend task flow files modified. Do not commit unless the user explicitly asks.

---

### Task 9: Add Artist And Album Enrichment Task Backend With Progress Events

**Files:**
- Modify: `backend/services/wikipedia_service.py`
- Modify: `backend/services/ai_task_service.py`
- Modify: `backend/api/ai_tasks.py`
- Test: `backend/tests/unit/test_wikipedia_progress.py`
- Test: `backend/tests/contract/test_ai_enrichment_tasks.py`

- [ ] **Step 1: Write failing progress tests**

Create `backend/tests/unit/test_wikipedia_progress.py`:

```python
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_artist_wiki_progress_callback_receives_cache_and_search(monkeypatch):
    from backend.services import wikipedia_service as wiki

    events = []

    monkeypatch.setattr(wiki, "_cache_get", lambda key: None)
    monkeypatch.setattr(wiki, "_cache_set", lambda key, data: None)
    monkeypatch.setattr(wiki, "find_artist_page", lambda artist: (None, None))

    result = wiki.get_artist_wiki("Missing Artist", progress_callback=lambda stage, message: events.append((stage, message)))

    assert result is None
    assert events[0][0] == "checking_cache"
    assert any(stage == "fetching_external_data" for stage, _message in events)
```

- [ ] **Step 2: Write failing enrichment task contract test**

Create `backend/tests/contract/test_ai_enrichment_tasks.py`:

```python
from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


def test_artist_enrichment_task_endpoint(client, monkeypatch):
    import backend.services.ai_task_service as task_service

    def fake_run(task_id, request):
        from backend.core.db import get_db
        from backend.domains.ai_tasks.repository import AiTaskRepository

        conn = get_db(readonly=False)
        try:
            repo = AiTaskRepository(conn)
            repo.update_run(
                task_id=task_id,
                status="done",
                stage="done",
                progress_pct=1.0,
                message="艺人增强完成",
                result={"wiki": {"summary": "Artist summary"}},
            )
        finally:
            conn.close()

    monkeypatch.setattr(task_service, "run_artist_enrichment_task", fake_run)

    response = client.post("/api/ai/tasks/enrichment/artist", json={"artist_name": "Artist A"})

    assert response.status_code == 200
    task_id = response.json()["task_id"]
    assert client.get(f"/api/ai/tasks/{task_id}").json()["result"]["wiki"]["summary"] == "Artist summary"


def test_album_enrichment_task_endpoint(client, monkeypatch):
    import backend.services.ai_task_service as task_service

    def fake_run(task_id, request):
        from backend.core.db import get_db
        from backend.domains.ai_tasks.repository import AiTaskRepository

        conn = get_db(readonly=False)
        try:
            repo = AiTaskRepository(conn)
            repo.update_run(
                task_id=task_id,
                status="done",
                stage="done",
                progress_pct=1.0,
                message="专辑增强完成",
                result={"wiki": {"summary": "Album summary"}},
            )
        finally:
            conn.close()

    monkeypatch.setattr(task_service, "run_album_enrichment_task", fake_run)

    response = client.post(
        "/api/ai/tasks/enrichment/album",
        json={"album_name": "Album A", "artist_name": "Artist A"},
    )

    assert response.status_code == 200
    task_id = response.json()["task_id"]
    assert client.get(f"/api/ai/tasks/{task_id}").json()["result"]["wiki"]["summary"] == "Album summary"
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_wikipedia_progress.py backend/tests/contract/test_ai_enrichment_tasks.py -q
```

Expected: FAIL because `progress_callback` and enrichment task endpoints do not exist.

- [ ] **Step 4: Add progress callback to Wikipedia service**

Modify signatures in `backend/services/wikipedia_service.py`:

```python
def get_album_wiki(album_name, artist_name, progress_callback=None):
def get_artist_wiki(artist_name, progress_callback=None):
```

Inside each function, emit:

```python
if progress_callback:
    progress_callback("checking_cache", "正在检查 Wikipedia 缓存")
```

Before page search:

```python
if progress_callback:
    progress_callback("fetching_external_data", "正在搜索 Wikipedia 页面")
```

Before parallel fetch:

```python
if progress_callback:
    progress_callback("fetching_external_data", "正在获取 Wikipedia 页面内容")
```

Before `_add_translations(result)`:

```python
if progress_callback:
    progress_callback("calling_llm", "正在翻译和结构化 Wikipedia 内容")
```

Before `_cache_set(cache_key, result)`:

```python
if progress_callback:
    progress_callback("saving_cache", "正在保存增强缓存")
```

- [ ] **Step 5: Add enrichment task service functions**

In `backend/services/ai_task_service.py`, add:

```python
def _emit_task_event(task_id: str, stage: str, message: str, progress_pct: float) -> None:
    conn = get_db(readonly=False)
    try:
        repo = AiTaskRepository(conn)
        repo.update_run(
            task_id=task_id,
            status="running",
            stage=stage,
            progress_pct=progress_pct,
            message=message,
        )
        repo.add_event(
            task_id=task_id,
            event_type="stage_started",
            stage=stage,
            message=message,
        )
    finally:
        conn.close()


def start_artist_enrichment_task(request: dict[str, Any]) -> dict[str, Any]:
    return create_task(
        task_type="artist_enrichment",
        stage="checking_cache",
        message="准备获取艺人增强信息",
        request=request,
        handler=run_artist_enrichment_task,
    )


def start_album_enrichment_task(request: dict[str, Any]) -> dict[str, Any]:
    return create_task(
        task_type="album_enrichment",
        stage="checking_cache",
        message="准备获取专辑增强信息",
        request=request,
        handler=run_album_enrichment_task,
    )


def run_artist_enrichment_task(task_id: str, request: dict[str, Any]) -> None:
    from backend.services.wikipedia_service import get_artist_wiki

    def progress(stage: str, message: str):
        progress_map = {
            "checking_cache": 0.15,
            "fetching_external_data": 0.45,
            "calling_llm": 0.75,
            "saving_cache": 0.9,
        }
        _emit_task_event(task_id, stage, message, progress_map.get(stage, 0.5))

    wiki = get_artist_wiki(request["artist_name"], progress_callback=progress)
    mark_task_done(task_id, "done", "艺人增强完成", {"wiki": wiki, "genius": None})


def run_album_enrichment_task(task_id: str, request: dict[str, Any]) -> None:
    from backend.services.wikipedia_service import get_album_wiki

    def progress(stage: str, message: str):
        progress_map = {
            "checking_cache": 0.15,
            "fetching_external_data": 0.45,
            "calling_llm": 0.75,
            "saving_cache": 0.9,
        }
        _emit_task_event(task_id, stage, message, progress_map.get(stage, 0.5))

    wiki = get_album_wiki(
        request["album_name"],
        request["artist_name"],
        progress_callback=progress,
    )
    mark_task_done(task_id, "done", "专辑增强完成", {"wiki": wiki, "genius": None})
```

- [ ] **Step 6: Add enrichment endpoints**

In `backend/api/ai_tasks.py`, import:

```python
from backend.models.ai_tasks import ArtistEnrichmentTaskRequest, AlbumEnrichmentTaskRequest
from backend.services.ai_task_service import start_artist_enrichment_task, start_album_enrichment_task
```

Add endpoints:

```python
@router.post("/enrichment/artist", response_model=AiTaskCreateResponse)
def create_artist_enrichment_task(body: ArtistEnrichmentTaskRequest):
    return start_artist_enrichment_task(body.model_dump())


@router.post("/enrichment/album", response_model=AiTaskCreateResponse)
def create_album_enrichment_task(body: AlbumEnrichmentTaskRequest):
    return start_album_enrichment_task(body.model_dump())
```

- [ ] **Step 7: Run enrichment tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_wikipedia_progress.py backend/tests/contract/test_ai_enrichment_tasks.py -q
```

Expected: PASS.

- [ ] **Step 8: Checkpoint**

Run:

```bash
git status --short
```

Expected: Wikipedia service, task service, API router, tests modified or new. Do not commit unless the user explicitly asks.

---

### Task 10: Move Artist And Album Detail Enrichment To Task Progress UI

**Files:**
- Modify: `frontend/src/hooks/useAiTasks.ts`
- Modify: `frontend/src/features/music/details/ArtistDetailExperience.tsx`
- Modify: `frontend/src/features/music/details/ArtistCareerSection.tsx`
- Modify: `frontend/src/features/music/details/AlbumDetailExperience.tsx`
- Modify: `frontend/src/features/music/details/AlbumEraSection.tsx`
- Test: `frontend/src/tests/music-enrichment-task-flow.test.tsx`

- [ ] **Step 1: Write failing enrichment UI test**

Create `frontend/src/tests/music-enrichment-task-flow.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { AITaskProgress } from '@/features/ai-tasks/AITaskProgress'

describe('music enrichment progress', () => {
  it('shows album or artist enrichment progress inside shared progress UI', () => {
    render(
      <AITaskProgress
        task={{
          found: true,
          task_id: 'artist-task',
          task_type: 'artist_enrichment',
          status: 'running',
          stage: 'fetching_external_data',
          progress_pct: 0.45,
          message: '正在获取 Wikipedia 页面内容',
          result: null,
          error: null,
          created_at: '2026-06-28T00:00:00',
          updated_at: '2026-06-28T00:00:01',
        }}
        events={[]}
      />,
    )

    expect(screen.getByText('正在获取 Wikipedia 页面内容')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify shared component still passes**

Run:

```bash
cd frontend && npm test -- music-enrichment-task-flow.test.tsx --run
```

Expected: PASS after Task 4. This test protects the visible text marker used by page integration.

- [ ] **Step 3: Add enrichment task hooks**

In `frontend/src/hooks/useAiTasks.ts`, add:

```ts
export function useStartArtistEnrichmentTask() {
  return useMutation({
    mutationFn: (payload: { artist_name: string }) =>
      api.post<AiTaskCreatePayload>('/ai/tasks/enrichment/artist', payload),
  })
}

export function useStartAlbumEnrichmentTask() {
  return useMutation({
    mutationFn: (payload: { album_name: string; artist_name: string }) =>
      api.post<AiTaskCreatePayload>('/ai/tasks/enrichment/album', payload),
  })
}
```

- [ ] **Step 4: Update ArtistDetailExperience**

Modify `frontend/src/features/music/details/ArtistDetailExperience.tsx`:

- Replace direct `useQuery` for `/billboard/enrichment/artist/...` with a task start when `activeTab === 'career'`.
- Store `artistEnrichmentTaskId`.
- Use `useAiTask(artistEnrichmentTaskId)`.
- Pass `enrichmentTask`, `enrichmentEvents`, and final `enrichment` result to `ArtistCareerSection`.

Task result shape should remain compatible with the existing section:

```ts
const enrichment = artistTask?.result as ArtistEnrichmentResponse | null
```

- [ ] **Step 5: Update ArtistCareerSection**

Modify `frontend/src/features/music/details/ArtistCareerSection.tsx`:

- Import `AITaskProgress`.
- Render progress when task exists and `status` is `queued` or `running`.
- Render existing view after completion.
- Preserve “未找到 Wikipedia 信息” when task completes with `wiki: null`.

- [ ] **Step 6: Update AlbumDetailExperience**

Modify `frontend/src/features/music/details/AlbumDetailExperience.tsx`:

- Replace direct `useQuery` for `/billboard/enrichment/album/...` with a task start when `activeTab === 'era'`.
- Store `albumEnrichmentTaskId`.
- Use `useAiTask(albumEnrichmentTaskId)`.
- Pass task state and final enrichment result to `AlbumEraSection`.

- [ ] **Step 7: Update AlbumEraSection**

Modify `frontend/src/features/music/details/AlbumEraSection.tsx`:

- Import `AITaskProgress`.
- Render progress while album enrichment task is queued/running.
- Continue rendering release cycle content independently if it is already available.
- Render existing album enrichment view after completion.

- [ ] **Step 8: Run focused frontend tests**

Run:

```bash
cd frontend && npm test -- music-enrichment-task-flow.test.tsx ai-task-components.test.tsx --run
```

Expected: PASS.

- [ ] **Step 9: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 10: Checkpoint**

Run:

```bash
git status --short
```

Expected: music detail frontend files modified. Do not commit unless the user explicitly asks.

---

### Task 11: Refresh OpenAPI, Smoke Coverage, And Final Verification

**Files:**
- Modify: `frontend/src/api/generated/openapi.json`
- Modify: `frontend/src/api/generated/api-types.ts`
- Modify: `scripts/frontend_interaction_smoke.mjs`
- Modify if required by audits: `scripts/openapi_operation_audit.py`
- Modify if required by audits: `scripts/openapi_parameter_boundary_audit.py`
- Test: existing frontend smoke script unit tests under `backend/tests/unit/`

- [ ] **Step 1: Start backend for OpenAPI generation**

Run:

```bash
source .venv/bin/activate && SPOTIFY_STATS_WARMUP=0 uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Expected: backend starts and `/openapi.json` is reachable.

- [ ] **Step 2: Refresh frontend generated API types**

In another terminal, run:

```bash
cd frontend && npm run generate-types
```

Expected: `frontend/src/api/generated/openapi.json` and `frontend/src/api/generated/api-types.ts` update without errors.

- [ ] **Step 3: Extend interaction smoke**

Modify `scripts/frontend_interaction_smoke.mjs` in the `ai-insights-tabs` scenario:

- Keep the existing LLM configured/unconfigured branch.
- When LLM is configured, verify one of these texts appears after opening reports:
  - `生成报告`
  - `缓存检查完成`
  - `AI 任务进度`
  - existing report text if cache is present.

Do not make the smoke call a live LLM generation. It should only verify cache/manual-generation affordances and tab navigation.

- [ ] **Step 4: Update smoke script unit test if needed**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_frontend_interaction_smoke_script.py -q
```

Expected: PASS. If it fails because expected source markers changed, update the assertion to include `生成报告` and `AI 任务进度`.

- [ ] **Step 5: Run backend targeted tests**

Run:

```bash
.venv/bin/pytest backend/tests/unit/test_ai_task_repository.py backend/tests/unit/test_ai_report_tasks.py backend/tests/unit/test_ai_agent_tools.py backend/tests/unit/test_wikipedia_progress.py backend/tests/contract/test_ai_task_api.py backend/tests/contract/test_ai_agent_task_contract.py backend/tests/contract/test_ai_enrichment_tasks.py -q
```

Expected: PASS.

- [ ] **Step 6: Run frontend targeted tests**

Run:

```bash
cd frontend && npm test -- ai-task-components.test.tsx ai-task-hooks.test.tsx ai-insights-task-flow.test.tsx music-enrichment-task-flow.test.tsx --run
```

Expected: PASS.

- [ ] **Step 7: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 8: Run API contract checks**

Run:

```bash
.venv/bin/pytest backend/tests/contract/test_remaining_json_response_models.py backend/tests/contract/test_infrastructure_response_models.py -q
```

Expected: PASS.

- [ ] **Step 9: Run OpenAPI audits**

Run:

```bash
.venv/bin/python scripts/openapi_operation_audit.py --json-output /tmp/spotify_openapi_operation_audit.json
.venv/bin/python scripts/openapi_parameter_boundary_audit.py --json-output /tmp/spotify_openapi_parameter_boundary_audit.json
```

Expected: PASS with `0 unaccounted`. If a new AI task operation or parameter is unaccounted, update the corresponding audit script with targeted evidence from the new contract tests.

- [ ] **Step 10: Run AI interaction smoke without live generation**

With backend 8000 and frontend 5173 running, run:

```bash
node scripts/frontend_interaction_smoke.mjs --scenario ai-insights-tabs --base-url http://localhost:5173
```

Expected: PASS. It should not require clicking `生成报告`.

- [ ] **Step 11: Final status check**

Run:

```bash
git status --short
```

Expected: implementation files, generated API files, tests, and smoke script changes are visible. Do not commit unless the user explicitly asks.

---

## Final Review Checklist

Self-review result:

- Implementation status: implemented and ready to commit on 2026-06-29.
- Spec coverage: covered. The plan has tasks for manual cache-first reports, artist and album enrichment progress, read-only Agent tools, persisted task history, tool traces, old endpoint compatibility, OpenAPI refresh, and smoke/test verification.
- 占位词扫描：通过。没有未解决的占位标记。
- Type consistency: aligned. Task, event, and tool-call field names are consistently `task_id`, `status`, `stage`, `progress_pct`, `params_summary`, `result_summary`, and `source_range`.

- V2 report flow is cache-first and manual-generate on cache miss.
- AI report generation displays task stages while waiting.
- Agent chat uses backend-defined read-only tools only.
- Tool traces include `params_summary`, `result_summary`, and `source_range`.
- Artist career enrichment displays task progress.
- Album era enrichment displays task progress.
- Old synchronous endpoints still exist.
- LLM-not-configured UI still renders.
- No Agent tool writes settings, import jobs, caches, playlists, or arbitrary SQL/URL.
- Targeted backend tests pass.
- Targeted frontend tests pass.
- `npm run build` passes.
- OpenAPI audits pass or have explicit new evidence entries.
- Added follow-up hardening after real AI answer review: compact evidence now preserves album project, weekly rank, top-track and entity coverage details; final prompts now distinguish personal Billboard from external official Billboard and require coverage-consistent answers.
