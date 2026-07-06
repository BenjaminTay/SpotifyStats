# AI Observable Agent Orchestrator Design

Date: 2026-06-28

Status: Implemented as V2 on 2026-06-29. Reports, chat, artist enrichment, and album enrichment now share the AI task/event model. Chat uses a backend-defined read-only Agent tool registry, supports thinking mode, stores tool traces, passes compact evidence plus coverage into the final answer, and retries once when the answer contradicts coverage.

## Context

SpotifyStats already has three AI-facing surfaces:

- AI Insights reports: weekly digest, monthly personality, yearly story.
- AI Insights chat: natural-language Q&A over listening history.
- Music detail enrichment: track, album, and artist pages fetch Wikipedia, Genius, and optional LLM-structured summaries.

The current implementation is useful but opaque. Users wait behind generic loading states and cannot tell whether the app is gathering local data, fetching Wikipedia, calling the LLM, parsing output, or saving cache. The chat also works from preselected local payloads rather than an agent that can inspect available backend data as needed.

The long-term target is a unified AI Orchestrator. To reduce risk, V2 should be implemented as a minimum vertical slice of the V3 architecture, not as a temporary throwaway feature.

## Goals

V2 must prove two product capabilities:

1. AI work is observable. Users can see meaningful progress stages for reports, chat answers, and one detail-page enrichment path.
2. AI chat behaves like a read-only analysis agent. It can choose from a backend-defined tool registry, call safe analytics APIs, and explain which data it used.

V3 expands the same architecture to all AI workflows: report generation, chat, detail enrichment, task history, retries, cancellation, streaming output, and richer tool coverage.

## Non-Goals

- No write tools in the first agent version.
- No arbitrary SQL execution.
- No arbitrary URL fetches chosen by the model.
- No settings mutation, import jobs, cache clearing, playlist creation, or database writes triggered by the agent.
- No direct exposure of secrets, raw API keys, internal stack traces, or unrestricted backend routes to the model.

## Recommended Route

Build V2 as a V3-compatible minimum vertical slice:

- A shared AI task/event model on the backend.
- A shared frontend progress and tool trace UI.
- A read-only tool registry for agent chat.
- Initial integration into AI reports, AI chat, and one music detail enrichment path.

This lets the product validate the experience while keeping the future V3 migration incremental.

## V2 Scope

V2 includes these paths:

- AI report generation for weekly, monthly, and yearly reports.
- AI chat with read-only tool calls.
- Two detail-page enrichment sample paths:
  - Artist career enrichment, because it combines Wikipedia fetch, optional translation, structured LLM parsing, and user-visible narrative content.
  - Album era enrichment, because it is central to music storytelling and validates album-specific Wikipedia parsing, single/release metadata, and structured LLM output.

Track detail enrichment can keep its existing loading behavior in V2, but it should not receive an incompatible bespoke implementation.

## V3 Scope

V3 expands the same primitives to:

- Track, album, and artist enrichment.
- Report regeneration history.
- Task replay and task detail drawers.
- Tool trace persistence.
- Streaming final answers.
- Cancellation and retry for all long-running AI jobs.
- More read-only tools.
- Cross-page AI assistant entry points.

## User Experience

### Progress Display

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

### Tool Trace

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

### Trust Markers

AI answers should show:

- Data range used.
- Whether cached data was used.
- Which read-only tools were called.
- A compact evidence summary for important tool results.
- A short disclaimer that the answer is generated from local listening data and may need human review.

## Backend Design

### AI Task Model

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

### AI Task Events

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

### API Shape

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

### Read-Only Tool Registry

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

### Agent Loop

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

### Progress Instrumentation

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

## Frontend Design

### Shared Components

Add shared AI UI primitives:

- `AITaskProgress`: shows stage list, current status, retry/cancel controls.
- `AIToolTrace`: shows read-only tool calls in a compact readable form.
- `AIResultShell`: wraps generated report or answer with progress, trace, cache status, and disclaimer.

These components should live in a shared AI feature area rather than inside only AI Insights.

### AI Reports

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

### AI Chat

The chat panel should:

- Start an `ai_chat_agent` task per question.
- Append user message immediately.
- Show progress while the agent plans and calls tools.
- Show tool trace above or below the final answer.
- Persist final user and assistant messages as today.

V2 can persist the tool trace in assistant message metadata.

### Detail Page Enrichment

Artist career and album era enrichment should:

- Use task endpoints when the career or era tab becomes active.
- Show enrichment stage progress inside the relevant section.
- Render existing structured view after completion.
- Preserve nullable fallback if Wikipedia or LLM enrichment fails.

This proves the task model outside the AI Insights page for both artist and album storytelling paths.

## Data Flow

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

## Error Handling

Errors should be stage-aware:

- Network or provider failures map to recoverable AI task errors.
- LLM not configured maps to configuration guidance.
- Unsupported tool request maps to a controlled tool error.
- Tool timeout maps to a partial answer if enough data exists, or a clear retry state.
- Cache write failure should not discard a successfully generated result.

The frontend should avoid generic "生成失败" where a more precise stage is known.

## Security And Safety

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

## Testing Plan

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

## Migration Plan

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

## Acceptance Criteria

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

## Implementation Notes

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

## Design Review

This design intentionally treats V2 as a stable subset of V3. The main architectural objects in V2, especially task runs, events, progress UI, and read-only tool registry, are the same objects V3 will extend. That keeps the first implementation useful immediately while avoiding a future rewrite.

## Implementation Status

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
