# 早期AI可观测编排设计与实施提纲

2026-10-26按主题合并。历史设计保留决策及合同，实施部分只保留目标、分工和验收要求；旧操作步骤不作为当前任务，计划中的Expected不等于实际通过。

## 阅读顺序

- [AI Observable Agent Orchestrator Design](#ai-observable-agent-orchestrator-design)
- [AI Observable Agent Orchestrator Implementation Plan](#ai-observable-agent-orchestrator-implementation-plan)

## AI Observable Agent Orchestrator Design

原记录：`2026-06-28-ai-observable-agent-orchestrator-design.md`。

Date: 2026-06-28

Status: Implemented as V2 on 2026-06-29. Reports, chat, artist enrichment, and album enrichment now share the AI task/event model. Chat uses a backend-defined read-only Agent tool registry, supports thinking mode, stores tool traces, passes compact evidence plus coverage into the final answer, and retries once when the answer contradicts coverage.

### Context

SpotifyStats already has three AI-facing surfaces:

- AI Insights reports: weekly digest, monthly personality, yearly story.
- AI Insights chat: natural-language Q&A over listening history.
- Music detail enrichment: track, album, and artist pages fetch Wikipedia, Genius, and optional LLM-structured summaries.

The current implementation is useful but opaque. Users wait behind generic loading states and cannot tell whether the app is gathering local data, fetching Wikipedia, calling the LLM, parsing output, or saving cache. The chat also works from preselected local payloads rather than an agent that can inspect available backend data as needed.

The long-term target is a unified AI Orchestrator. To reduce risk, V2 should be implemented as a minimum vertical slice of the V3 architecture, not as a temporary throwaway feature.

### Goals

V2 must prove two product capabilities:

1. AI work is observable. Users can see meaningful progress stages for reports, chat answers, and one detail-page enrichment path.
2. AI chat behaves like a read-only analysis agent. It can choose from a backend-defined tool registry, call safe analytics APIs, and explain which data it used.

V3 expands the same architecture to all AI workflows: report generation, chat, detail enrichment, task history, retries, cancellation, streaming output, and richer tool coverage.

### Non-Goals

- No write tools in the first agent version.
- No arbitrary SQL execution.
- No arbitrary URL fetches chosen by the model.
- No settings mutation, import jobs, cache clearing, playlist creation, or database writes triggered by the agent.
- No direct exposure of secrets, raw API keys, internal stack traces, or unrestricted backend routes to the model.

### Recommended Route

Build V2 as a V3-compatible minimum vertical slice:

- A shared AI task/event model on the backend.
- A shared frontend progress and tool trace UI.
- A read-only tool registry for agent chat.
- Initial integration into AI reports, AI chat, and one music detail enrichment path.

This lets the product validate the experience while keeping the future V3 migration incremental.

### V2 Scope

V2 includes these paths:

- AI report generation for weekly, monthly, and yearly reports.
- AI chat with read-only tool calls.
- Two detail-page enrichment sample paths:
  - Artist career enrichment, because it combines Wikipedia fetch, optional translation, structured LLM parsing, and user-visible narrative content.
  - Album era enrichment, because it is central to music storytelling and validates album-specific Wikipedia parsing, single/release metadata, and structured LLM output.

Track detail enrichment can keep its existing loading behavior in V2, but it should not receive an incompatible bespoke implementation.

### V3 Scope

V3 expands the same primitives to:

- Track, album, and artist enrichment.
- Report regeneration history.
- Task replay and task detail drawers.
- Tool trace persistence.
- Streaming final answers.
- Cancellation and retry for all long-running AI jobs.
- More read-only tools.
- Cross-page AI assistant entry points.

### User Experience

#### Progress Display

AI progress should feel specific but not overly technical. The UI should show:

- Current stage label.
- Short detail message.
- Completed stages.
- Error stage with retry guidance.
- Cache hit state when no generation was needed.
- Manual generation state when no cached report exists.
- Tool call trace for agent answers.

Example report progress:

1. Preparing listening data.
2. Summarized 2026-06-17 to 2026-06-23 playback data.
3. Sending data to AI.
4. AI is writing the report.
5. Saving report cache.
6. Done.

Example enrichment progress:

1. Checking local cache.
2. Searching Wikipedia.
3. Fetching article content.
4. Translating and structuring article.
5. Merging local chart data.
6. Done.

Example agent progress:

1. Understanding the question.
2. Planning data queries.
3. Querying yearly summary.
4. Querying top artists.
5. Querying listening time distribution.
6. Writing answer.
7. Done.

#### Tool Trace

Agent answers should include a compact trace such as:

- Queried yearly summary for 2026.
- Queried top artists for 2026.
- Queried hourly listening distribution.

The trace should be understandable to users. Technical route names can stay hidden by default, with an optional expanded developer detail only if needed later.

Each tool trace item should include a user-readable evidence summary:

- `label`: what was queried.
- `params_summary`: the period, entity, metric, or filters used.
- `result_summary`: a compact statement of the returned data.
- `source_range`: the data range or entity scope that bounded the result.

#### Trust Markers

AI answers should show:

- Data range used.
- Whether cached data was used.
- Which read-only tools were called.
- A compact evidence summary for important tool results.
- A short disclaimer that the answer is generated from local listening data and may need human review.

### Backend Design

#### AI Task Model

Introduce a shared task run abstraction:

- `task_id`
- `task_type`
- `status`
- `stage`
- `progress_pct`
- `message`
- `created_at`
- `updated_at`
- `result_json`
- `error`

V2 should introduce SQLite-backed task tables from the start:

- `ai_task_runs`
- `ai_task_events`
- `ai_tool_calls`

In-memory state is allowed only for runtime scheduling and cancellation bookkeeping. The durable source of truth for completed tasks, event history, and tool traces should be SQLite. This keeps V2 compatible with V3 task history, replay, and audit views.

Task types for V2:

- `ai_report_weekly`
- `ai_report_monthly`
- `ai_report_yearly`
- `ai_chat_agent`
- `artist_enrichment`
- `album_enrichment`

Statuses:

- `queued`
- `running`
- `done`
- `error`
- `cancelled`

Stages:

- `checking_cache`
- `gathering_local_data`
- `fetching_external_data`
- `planning_tools`
- `calling_tool`
- `calling_llm`
- `postprocessing`
- `saving_cache`
- `done`
- `error`

The existing import job pattern and background job table can inform the shape, but AI tasks should have richer event history than the current generic background job status.

#### AI Task Events

Each task emits events:

- `event_id`
- `task_id`
- `event_type`
- `stage`
- `message`
- `payload_json`
- `created_at`

Event types:

- `stage_started`
- `stage_completed`
- `cache_hit`
- `tool_call_started`
- `tool_call_completed`
- `llm_started`
- `llm_completed`
- `result_ready`
- `error`

V2 uses polling through `GET /api/ai/tasks/{task_id}` and `GET /api/ai/tasks/{task_id}/events`. The response models should remain compatible with future SSE streaming, but SSE and token streaming are V3 work.

#### API Shape

Add task-oriented endpoints:

- `POST /api/ai/tasks/report`
- `POST /api/ai/tasks/chat`
- `POST /api/ai/tasks/enrichment/artist`
- `POST /api/ai/tasks/enrichment/album`
- `GET /api/ai/tasks/{task_id}`
- `GET /api/ai/tasks/{task_id}/events`
- `POST /api/ai/tasks/{task_id}/cancel`

`cancel` should only affect long-running local tasks and should not imply a write-capable agent. It changes task state only.

Existing synchronous endpoints can remain for compatibility during V2:

- `/api/ai-insights/weekly-digest`
- `/api/ai-insights/monthly-personality`
- `/api/ai-insights/yearly-story`
- `/api/ai-insights/ask`
- `/api/billboard/enrichment/artist/{artist_name}`
- `/api/billboard/enrichment/album/{album_name}`

The new task endpoints should become the preferred UI path.

#### Read-Only Tool Registry

The agent should call only backend-defined tools. Each tool has:

- Stable tool name.
- User-readable label.
- JSON schema for parameters.
- Python handler.
- Timeout.
- Result size cap.
- Redaction policy.
- Permission class, initially always `read_only`.

Tool execution should persist one `ai_tool_calls` row per call:

- `tool_call_id`
- `task_id`
- `tool_name`
- `status`
- `params_summary`
- `result_summary`
- `source_range`
- `started_at`
- `completed_at`
- `error`

Initial V2 tool candidates:

- `analysis_stats`: overall stats for a period.
- `analysis_charts`: top tracks, artists, or albums for a period.
- `playback_records`: notable listening records.
- `wrapped_yearly`: yearly review payload.
- `entity_stats`: stats for a track, album, or artist.
- `billboard_entity_detail`: chart history for a track, album, or artist.
- `listening_hours`: hourly or weekday listening patterns.

The model receives tool descriptions and schemas, not raw backend routes. The backend validates arguments before execution.

Agent tools may not write business data. The product may still persist normal application artifacts created by the chat workflow itself: task runs, task events, user messages, assistant messages, and tool trace metadata.

#### Agent Loop

V2 should use a bounded loop:

1. Parse user question and conversation context.
2. Ask the model to choose read-only tools.
3. Validate tool names and parameters.
4. Execute tools server-side.
5. Feed compact tool results back to the model.
6. Generate final answer.

Limits:

- Maximum 5 tool calls per user question in V2.
- Maximum 2 planning rounds in V2.
- Per-tool timeout.
- Total task timeout.
- Result payload trimming and summarization for large responses.

If the model asks for an unsupported tool, the backend should return a controlled tool error and continue or fail gracefully.

#### Progress Instrumentation

Report generation should not automatically call the LLM merely because the page opened or the user switched report type. It should emit events around:

- Cache check.
- Local data gathering.
- LLM call.
- Cache write.
- Result serialization.

Enrichment should emit events around:

- Cache check.
- Wikipedia search.
- Wikipedia fetch.
- Translation.
- Structured LLM extraction.
- Merge with local metadata.

Agent chat should emit events around:

- Intent or plan generation.
- Each tool call.
- Final answer generation.

### Frontend Design

#### Shared Components

Add shared AI UI primitives:

- `AITaskProgress`: shows stage list, current status, retry/cancel controls.
- `AIToolTrace`: shows read-only tool calls in a compact readable form.
- `AIResultShell`: wraps generated report or answer with progress, trace, cache status, and disclaimer.

These components should live in a shared AI feature area rather than inside only AI Insights.

#### AI Reports

The report tab should switch from a single loading skeleton to task-aware state:

- Check for a cached report when report type and date range are selected.
- If a cached report exists, render it automatically with cache status.
- If no cached report exists, show an explicit "Generate report" action instead of automatically calling the LLM.
- Start a report task only when the user clicks "Generate report" or "Refresh report".
- Poll task status/events until done or error.
- Render partial progress while waiting.
- Render final report in the existing `ReportCard` layout.
- Preserve copy, refresh, cancel, and follow-up actions.

Refresh should create a task with `force=true`.

#### AI Chat

The chat panel should:

- Start an `ai_chat_agent` task per question.
- Append user message immediately.
- Show progress while the agent plans and calls tools.
- Show tool trace above or below the final answer.
- Persist final user and assistant messages as today.

V2 can persist the tool trace in assistant message metadata.

#### Detail Page Enrichment

Artist career and album era enrichment should:

- Use task endpoints when the career or era tab becomes active.
- Show enrichment stage progress inside the relevant section.
- Render existing structured view after completion.
- Preserve nullable fallback if Wikipedia or LLM enrichment fails.

This proves the task model outside the AI Insights page for both artist and album storytelling paths.

### Data Flow

Report flow:

```text
UI selects report period
  -> POST /api/ai/tasks/report
  -> if cache hit, render cached report without LLM generation
  -> if cache miss, wait for explicit Generate report click
  -> backend emits checking_cache
  -> backend gathers local data
  -> backend calls LLM
  -> backend saves cache
  -> UI polls events/status
  -> UI renders ReportCard
```

Agent flow:

```text
User asks question
  -> POST /api/ai/tasks/chat
  -> backend emits planning_tools
  -> LLM returns tool plan
  -> backend executes validated read-only tools
  -> backend emits tool trace
  -> LLM writes final answer
  -> UI renders answer + trace
```

Enrichment flow:

```text
User opens artist career tab
  -> POST /api/ai/tasks/enrichment/artist
  -> backend checks cache
  -> backend searches/fetches Wikipedia
  -> backend optionally calls LLM for translation/structure
  -> backend merges result
  -> UI renders existing career section
```

Album enrichment flow:

```text
User opens album era tab
  -> POST /api/ai/tasks/enrichment/album
  -> backend checks cache
  -> backend searches/fetches Wikipedia
  -> backend optionally calls LLM for translation/structure
  -> backend merges result
  -> UI renders existing album era section
```

### Error Handling

Errors should be stage-aware:

- Network or provider failures map to recoverable AI task errors.
- LLM not configured maps to configuration guidance.
- Unsupported tool request maps to a controlled tool error.
- Tool timeout maps to a partial answer if enough data exists, or a clear retry state.
- Cache write failure should not discard a successfully generated result.

The frontend should avoid generic "生成失败" where a more precise stage is known.

### Security And Safety

Agent tools are read-only and backend-defined.

Guardrails:

- No arbitrary SQL.
- No arbitrary URL fetch.
- No write endpoints.
- No settings mutation.
- No import or cache mutation.
- No raw secret exposure.
- Parameter schema validation for every tool.
- Strict result size caps.
- Request ID propagation.
- Tool call logging without sensitive payloads.
- Chat/task persistence is allowed, but only for task state, user-visible conversation records, generated answers, and trace metadata.

### Testing Plan

Backend tests:

- Task lifecycle contract tests.
- Event ordering tests.
- Report task success, cache hit, and provider failure tests.
- Agent tool registry validation tests.
- Agent unsupported-tool and timeout tests.
- Read-only enforcement tests.
- Artist and album enrichment task fallback tests.

Frontend tests:

- `AITaskProgress` stage rendering.
- `AIToolTrace` rendering and accessible names.
- Report task hook states: queued, running, done, error, cancelled.
- Chat task flow with mocked tool trace.
- Artist enrichment progress display.
- Album enrichment progress display.

Smoke tests:

- AI report page shows progress stages.
- AI chat shows tool trace.
- Artist detail career tab shows enrichment progress or cached completion.
- Album detail era tab shows enrichment progress or cached completion.
- Existing AI unavailable branch remains intact.

### Migration Plan

V2 should keep current synchronous APIs while the new task APIs are introduced. Frontend AI surfaces can move one by one:

1. Add shared task/event backend primitives.
2. Add report task wrapper around existing report service.
3. Add frontend report task progress.
4. Add read-only agent tool registry.
5. Move chat to agent task path.
6. Add artist enrichment task path.
7. Add album enrichment task path.
8. Add tests and smoke coverage.

V3 then migrates all remaining enrichment and AI generation paths to the same task model.

### Acceptance Criteria

V2 is acceptable when:

- AI reports no longer show only an indeterminate wait state.
- Chat can answer using at least five backend read-only tools.
- Chat answers show which data tools were used.
- Tool traces include `params_summary`, `result_summary`, and `source_range`.
- Artist and album detail enrichment paths show meaningful stage progress.
- The old LLM-not-configured state still works.
- Agent cannot call write tools or arbitrary backend routes.
- Existing report, chat, and enrichment tests still pass.
- New task/event and tool registry tests pass.

### Implementation Notes

Prefer small bounded modules:

- Backend task models and event helpers.
- Backend task runner service.
- Backend tool registry service.
- Report task adapters.
- Chat agent adapter.
- Enrichment task adapter.
- Frontend AI task hooks.
- Shared progress and tool trace UI.

Avoid burying the orchestrator inside existing large service files. Existing report/enrichment services should be reused as handlers where possible, with event callbacks added around major stages.

### Design Review

This design intentionally treats V2 as a stable subset of V3. The main architectural objects in V2, especially task runs, events, progress UI, and read-only tool registry, are the same objects V3 will extend. That keeps the first implementation useful immediately while avoiding a future rewrite.

### Implementation Status

Implemented modules:

- `backend/models/ai_tasks.py`
- `backend/api/ai_tasks.py`
- `backend/domains/ai_tasks/`
- `backend/domains/ai_agent/`
- `backend/services/ai_task_service.py`
- `backend/services/ai_agent_service.py`
- `frontend/src/features/ai-tasks/`
- `frontend/src/hooks/useAiTasks.ts`
- AI Insights reports/chat and artist/album detail enrichment integrations

Current V2 limitations kept intentionally for V3:

- Final answer streaming is not implemented yet.
- Tool planning is single-pass with bounded retries only around final answer contradictions.
- Tool coverage is still small and analytic-service-oriented.
- Task history has backend persistence, but no full task-history drawer or replay UI yet.

## AI Observable Agent Orchestrator Implementation Plan

原记录：`2026-06-28-ai-observable-agent-orchestrator.md`。

> 历史实施提纲：已省略大段实现／测试代码草稿、重复命令及红绿测试步骤，保留设计要求、分工、接口示例与原验收事实。正文中的任务和Expected属于当时计划；当前行为见[文档地图](../../README.md)。

**Goal:** Build the V2 minimum vertical slice of the future AI Orchestrator: observable AI task progress, manual report generation when no cache exists, read-only Agent chat tools, and artist plus album enrichment progress.

**Architecture:** Add SQLite-backed AI task runs, events, and tool calls as durable orchestration primitives. Keep existing synchronous AI/report/enrichment endpoints for compatibility while the frontend moves to task-based polling. Implement read-only Agent tools through a backend registry so the model can inspect data without write access or arbitrary backend routing.

**Tech Stack:** FastAPI, SQLite migrations, Pydantic response models, existing SpotifyStats service layer, TanStack React Query, React/TypeScript, Vitest, pytest.

---

### Execution Constraints

- Do not create a git commit unless the user explicitly asks for one.
- Keep all Agent tools read-only. Chat/task persistence is allowed only for task state, visible chat records, generated answers, and tool trace metadata.
- Keep existing synchronous endpoints working throughout V2.
- Prefer targeted tests after each task; run broader checks only after the relevant vertical slice is complete.

### Scope Check

The approved spec covers two connected subsystems: observable task progress and read-only Agent tools. They share the same durable task/event/tool-call model, so this plan keeps them in one V2 vertical-slice plan rather than splitting them into unrelated projects.

### Execution Summary

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

### File Structure

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

#### Task 1: Add SQLite AI Task Tables And Repository

涉及文件：`backend/core/migrations.py`、`backend/domains/ai_tasks/repository.py`、`backend/tests/unit/test_ai_task_repository.py`。

- Add migration 22
- Implement repository

---

#### Task 2: Add Task API Models, Service, And Status Endpoints

涉及文件：`backend/models/ai_tasks.py`、`backend/services/ai_task_service.py`、`backend/api/ai_tasks.py`、`backend/api/router.py`、`backend/tests/contract/test_ai_task_api.py`。

- Add Pydantic models
- Add task service skeleton
- Add task API router

---

- 历史验收要求：If it fails because new endpoints are not accounted for, bind response models exactly as shown above before proceeding.

#### Task 3: Add Report Task Backend With Cache-Only And Manual Generate Modes

涉及文件：`backend/services/ai_insights_service.py`、`backend/services/ai_task_service.py`、`backend/api/ai_tasks.py`、`backend/tests/unit/test_ai_report_tasks.py`、`backend/tests/contract/test_ai_task_api.py`。

- Add report cache peek helper
- Add report task service functions

Then add these functions:

- Add report endpoint
- Add contract test for cache-only mode

---

#### Task 4: Add Shared Frontend AI Task Types, Hooks, And UI Primitives

涉及文件：`frontend/src/types/ai-tasks.ts`、`frontend/src/hooks/useAiTasks.ts`、`frontend/src/features/ai-tasks/AITaskProgress.tsx`、`frontend/src/features/ai-tasks/AIToolTrace.tsx`、`frontend/src/features/ai-tasks/AIResultShell.tsx`、`frontend/src/api/query-keys.ts`、`frontend/src/tests/ai-task-components.test.tsx`、`frontend/src/tests/ai-task-hooks.test.tsx`。

- Add frontend types
- Add query keys and hook
- Add UI primitives

---

#### Task 5: Move AI Reports To Cache-First Manual Generation Flow

涉及文件：`frontend/src/hooks/useAiTasks.ts`、`frontend/src/features/ai-insights/AiInsightsExperience.tsx`、`frontend/src/features/ai-insights/ReportCard.tsx`、`frontend/src/tests/ai-insights-task-flow.test.tsx`。

- Add report task hook
- Update report UI flow
- Import `useStartReportTask` and `useAiTask`.
- Replace automatic `useWeeklyDigest`, `useMonthlyPersonality`, and `useYearlyStory` calls with:
  - cache-only task on period/report type changes;
  - local `activeReportTaskId`;
  - generate button when result has `needs_generation: true`;
  - `useAiTask(activeReportTaskId)` while generating.

The report card should receive `task.result.report` when the task completes.

- Preserve existing ReportCard actions

Modify `frontend/src/features/ai-insights/ReportCard.tsx` so `onRetry` label remains `刷新报告`, and the parent passes a generate callback with `force: true`.

---

- 历史验收要求：If `query-hooks.test.tsx` still asserts old `useWeeklyDigest` behavior, keep those hooks available for compatibility and add new task-flow tests without deleting old hooks.

#### Task 6: Add Read-Only Agent Tool Registry

涉及文件：`backend/domains/ai_agent/tool_registry.py`、`backend/domains/ai_agent/tools.py`、`backend/tests/unit/test_ai_agent_tools.py`。

- Implement registry
- Implement initial tools

This starts with two tools. Add the remaining V2 tools in Task 7 while testing the Agent loop:

- `playback_records`
- `wrapped_yearly`
- `entity_stats`
- `billboard_entity_detail`
- `listening_hours`

---

#### Task 7: Add Read-Only Agent Chat Task Backend

涉及文件：`backend/domains/ai_agent/tools.py`、`backend/services/ai_agent_service.py`、`backend/services/ai_task_service.py`、`backend/api/ai_tasks.py`、`backend/tests/contract/test_ai_agent_task_contract.py`。

- Add remaining read-only tools

Extend `backend/domains/ai_agent/tools.py` with handlers for:

- `playback_records`: wraps `backend.services.analysis_records_service`.
- `wrapped_yearly`: wraps `backend.services.wrapped_service.get_wrapped_full`.
- `entity_stats`: wraps `backend.services.entity_stats_service`.
- `billboard_entity_detail`: wraps existing Billboard detail services or API-level service functions.
- `listening_hours`: wraps `backend.services.analysis_stats_service` helpers or `backend.api.listening_hours` service functions.

Register all five tools in `build_default_registry()` with `permission="read_only"`.

- Implement Agent service
- Add chat task starter
- Add chat endpoint

- Check read-only enforcement

---

#### Task 8: Move AI Chat UI To Agent Task Flow

涉及文件：`frontend/src/hooks/useAiTasks.ts`、`frontend/src/features/ai-insights/ChatInterface.tsx`、`frontend/src/features/ai-insights/ChatMessageList.tsx`、`frontend/src/tests/ai-insights-task-flow.test.tsx`。

- Add failing chat task frontend test
- Add chat task starter hook
- Update ChatInterface
- Replace `useAskQuestion()` for new sends with `useStartChatAgentTask()` and `useAiTask(taskId)`.
- Keep `useAskQuestion()` import only if old paths remain for compatibility; otherwise remove unused import.
-
- Save assistant metadata through existing `saveMessage`.
- Update ChatMessageList to render trace
- Import `AIToolTrace`.
-

---

#### Task 9: Add Artist And Album Enrichment Task Backend With Progress Events

涉及文件：`backend/services/wikipedia_service.py`、`backend/services/ai_task_service.py`、`backend/api/ai_tasks.py`、`backend/tests/unit/test_wikipedia_progress.py`、`backend/tests/contract/test_ai_enrichment_tasks.py`。

- Add progress callback to Wikipedia service

Before `_cache_set(cache_key, result)`:

- Add enrichment task service functions
- Add enrichment endpoints

---

#### Task 10: Move Artist And Album Detail Enrichment To Task Progress UI

涉及文件：`frontend/src/hooks/useAiTasks.ts`、`frontend/src/features/music/details/ArtistDetailExperience.tsx`、`frontend/src/features/music/details/ArtistCareerSection.tsx`、`frontend/src/features/music/details/AlbumDetailExperience.tsx`、`frontend/src/features/music/details/AlbumEraSection.tsx`、`frontend/src/tests/music-enrichment-task-flow.test.tsx`。

- Add enrichment task hooks
- Update ArtistDetailExperience
- Replace direct `useQuery` for `/billboard/enrichment/artist/...` with a task start when `activeTab === 'career'`.
- Store `artistEnrichmentTaskId`.
- Use `useAiTask(artistEnrichmentTaskId)`.
- Pass `enrichmentTask`, `enrichmentEvents`, and final `enrichment` result to `ArtistCareerSection`.

Task result shape should remain compatible with the existing section:

- Update ArtistCareerSection
- Import `AITaskProgress`.
- Render progress when task exists and `status` is `queued` or `running`.
- Render existing view after completion.
- Preserve “未找到 Wikipedia 信息” when task completes with `wiki: null`.
- Update AlbumDetailExperience
- Replace direct `useQuery` for `/billboard/enrichment/album/...` with a task start when `activeTab === 'era'`.
- Store `albumEnrichmentTaskId`.
- Use `useAiTask(albumEnrichmentTaskId)`.
- Pass task state and final enrichment result to `AlbumEraSection`.
- Update AlbumEraSection
- Import `AITaskProgress`.
- Render progress while album enrichment task is queued/running.
- Continue rendering release cycle content independently if it is already available.
- Render existing album enrichment view after completion.

---

#### Task 11: Refresh OpenAPI, Smoke Coverage, And Final Verification

涉及文件：`frontend/src/api/generated/openapi.json`、`frontend/src/api/generated/api-types.ts`、`scripts/frontend_interaction_smoke.mjs`、`scripts/openapi_operation_audit.py`、`scripts/openapi_parameter_boundary_audit.py`、`backend/tests/unit/`。

- Start backend for OpenAPI generation

- Refresh frontend generated API types

In another terminal, run:

- Extend interaction smoke
- Keep the existing LLM configured/unconfigured branch.
- When LLM is configured, verify one of these texts appears after opening reports:
  - `生成报告`
  - `缓存检查完成`
  - `AI 任务进度`
  - existing report text if cache is present.

Do not make the smoke call a live LLM generation. It should only verify cache/manual-generation affordances and tab navigation.

- Update smoke script unit test if needed

With backend 8000 and frontend 5173 running, run:

- Final status check

---

- 历史验收要求：If it fails because expected source markers changed, update the assertion to include `生成报告` and `AI 任务进度`.
- 历史验收要求：PASS with `0 unaccounted`. If a new AI task operation or parameter is unaccounted, update the corresponding audit script with targeted evidence from the new contract tests.
- 历史验收要求：It should not require clicking `生成报告`.

### Final Review Checklist

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
