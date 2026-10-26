# Agentic Longform Yearly Report Implementation Plan

> 历史实施提纲：已省略大段实现／测试代码草稿、重复命令及红绿测试步骤，保留设计要求、分工、接口示例与原验收事实。正文中的任务和Expected属于当时计划；当前行为见[文档地图](../../../README.md)。

**Goal:** Build an agentic longform yearly report workflow that lets a read-only Report Agent query SpotifyStats data, synthesize insights, create a dynamic outline, write a long article, and pass an editorial quality critic before caching the result.

**Implementation status (2026-07-03):** Implemented. The yearly AI report now defaults to `report_mode=agentic_longform`, runs through read-only research tools, evidence ledger, insight synthesis, dynamic outline, longform drafting, editorial critic, and yearly fact validation before caching. The legacy deterministic yearly summary remains available as `report_mode=basic_summary` and as the marked `fallback_level=basic_summary` safety path.

**Validation evidence (2026-07-03):**

- Backend targeted set: `55 passed` for agentic yearly report service/tools/critic, AI report task dispatch, API contracts, and task API contracts.
- Frontend regression set: Vitest `233 passed`; production build succeeded.
- HTTP probe: `scripts/probe_agentic_yearly_report.py --year 2026` returned `report_mode=agentic_longform`, `contract_version=agentic_yearly_v14`, `fallback_level=null`, 9 read-only tool calls, `critic.ok=true`, `fact_validation.ok=true`, and 1,846-character report.
- Browser acceptance: `/ai-insights` -> “年度叙事” -> “刷新报告” showed tool queries, insight synthesis, outline, draft, critic/fact-check progress, then rendered `Agentic 长文` / `已通过编辑审稿` / `1,846 字`.

**Architecture:** Keep the existing AI task/event/tool-call infrastructure and the V12 yearly report validator as the safety layer. Add a report-specific read-only tool registry, evidence ledger, insight synthesis, dynamic outline, longform draft prompt, and editorial critic, then route yearly report generation through this agentic workflow behind the existing AI Insights entry point. Treat the current deterministic yearly report as `basic_summary` fallback rather than the official AI longform report.

**Tech Stack:** FastAPI service layer, SQLite task/event persistence, existing `backend/domains/ai_agent` read-only tool registry patterns, existing `backend/domains/ai_reports` yearly contract/validator, pytest unit/contract tests, HTTP probes, React AI Insights task progress UI.

---

## Source Spec

- Design spec: `docs/superpowers/specs/2026-07-03-agentic-longform-yearly-report-design.md`
- Existing related plans:
  - `docs/superpowers/plans/2026-06-28-ai-observable-agent-orchestrator.md`
  - `docs/superpowers/plans/2026-06-29-ai-agent-universal-analytical-harness.md`
  - `docs/superpowers/plans/2026-07-03-ai-yearly-report-editorial-quality.md`

## Scope

This plan implements a V14 agentic yearly report vertical slice. It is intentionally narrower than a full AI platform rewrite:

- Reuse the existing `/ai-insights` user entry and AI task progress system.
- Add report-oriented tools rather than exposing arbitrary backend routes.
- Keep all tools read-only and allowlisted.
- Generate the official yearly report through research, evidence, insight, outline, draft, and critic stages.
- Keep V12 deterministic report generation as a marked `basic_summary` fallback.
- Do not implement token streaming in this iteration.
- Do not redesign the AI Insights page beyond progress/tool-trace labels and metadata display needed for this workflow.

### Backend Create

- `backend/domains/ai_reports/agentic_models.py`
  Typed dataclasses and helpers for `EvidenceLedgerEntry`, `InsightSynthesis`, `DynamicOutline`, `EditorialCritique`, `AgenticYearlyMetadata`, and final report result shape.

- `backend/domains/ai_reports/agentic_tools.py`
  Report-oriented read-only tools wrapping existing services and AI Agent tools: period context, overview, top entities, same-period comparison, personal Billboard year-end, Billboard diagnostics, entity stats, genre distribution, discovery/returns, highlight day detail.

- `backend/domains/ai_reports/agentic_prompts.py`
  Mission prompt, insight synthesis prompt, dynamic outline prompt, longform draft prompt, and repair prompt.

- `backend/domains/ai_reports/editorial_critic.py`
  Deterministic heuristics plus optional LLM critic wrapper for longform quality checks.

- `backend/services/yearly_report_agent_service.py`
  Orchestrates the report agent workflow, task events, tool calls, LLM calls, fallback, cache, and metadata.

- `backend/tests/unit/test_agentic_yearly_report_tools.py`
- `backend/tests/unit/test_agentic_yearly_report_critic.py`
- `backend/tests/unit/test_agentic_yearly_report_service.py`
- `backend/tests/contract/test_agentic_yearly_report_contract.py`
- `scripts/probe_agentic_yearly_report.py`
  HTTP probe that forces a 2026 report, validates metadata, critic status, length, forbidden dashboard-restatement patterns, and tool traces.

### Backend Modify

- `backend/services/ai_task_service.py`
  Route yearly report tasks to `yearly_report_agent_service` when `report_mode=agentic_longform` or default V14 is enabled.

- `backend/api/ai_insights.py`
  Accept and return report mode metadata while preserving existing response compatibility.

- `backend/services/ai_insights_service.py`
  Keep V12 generation and `_build_yearly_report_fallback()` available as fallback/basic summary. Do not add new agent logic here beyond a thin compatibility function if needed.

- `backend/domains/ai_reports/yearly_validator.py`
  Reuse for fact safety. Add any missing helper entry points only if the new critic needs validator issue normalization.

- `backend/domains/ai_agent/tool_registry.py` and `backend/domains/ai_agent/tools.py` only if a report tool should reuse an existing general tool. Prefer keeping report-specific wrappers in `agentic_tools.py`.

### Frontend Modify

- `frontend/src/features/ai-insights/`
  Display `report_mode`, `fallback_level`, article length, and user-readable report research stages if already exposed through task events.

- `frontend/src/features/ai-tasks/`
  Ensure new stages such as `researching`, `synthesizing_insights`, `outlining`, `drafting`, and `critic_review` render with readable labels.

### Docs Modify

- `docs/README.md`
- `docs/CHANGELOG.md`
- `AGENTS.md`
- `CLAUDE.md`
- `backend/CLAUDE.md`
- `README.md` if user-facing AI feature summary needs an update.

## Acceptance Criteria

- A forced 2026 yearly report returns `report_mode="agentic_longform"`, `contract_version="agentic_yearly_v14"`, `fallback_level=null`, `critic_passed=true`, and `article_length >= 1400`.
- The report uses at least 6 read-only tool calls and at least 2 personal Billboard-related tool calls.
- Tool calls are persisted to `ai_tool_calls` and visible through existing task events/tool trace retrieval.
- The report contains a clear thesis and develops it across at least 3 sections.
- The report explains at least one relationship between playback data and personal Billboard data.
- The report includes at least one Billboard analysis dimension: dominance, stability, breakout, long-tail, cross-chart alignment, or playback/Billboard tension.
- The editorial critic rejects the current V12 fallback-style data listing report.
- If the agent fails, the response marks `fallback_level="basic_summary"` and does not present that text as the official longform report.
- No arbitrary SQL, arbitrary URL, write operation, settings mutation, import job, playlist write, or external official Billboard lookup is exposed to the model.

## Execution Notes

- Keep commits optional during execution unless the user explicitly requests git commits. If execution mode includes commits, use the checkpoint messages suggested at the end of each task.
- Preserve existing dirty worktree changes; do not revert files unrelated to this plan.
- Use `apply_patch` for manual edits.

---

## Task 1: Add Agentic Yearly Report Data Models

涉及文件：`backend/domains/ai_reports/agentic_models.py`、`backend/tests/unit/test_agentic_yearly_report_service.py`。

- Write model serialization tests
- Implement the model module

---

## Task 2: Add Report-Oriented Read-Only Tools

涉及文件：`backend/domains/ai_reports/agentic_tools.py`、`backend/tests/unit/test_agentic_yearly_report_tools.py`。

- Write tests for report tool allowlist and static execution
- Implement initial report tool registry

---

## Task 3: Implement Live Yearly Report Tool Wrappers

涉及文件：`backend/domains/ai_reports/agentic_tools.py`、`backend/tests/unit/test_agentic_yearly_report_tools.py`。

- Add tests for live yearly data wrappers with monkeypatches
- Implement `_gather_yearly_data_for_tool()` and wrappers

---

## Task 4: Add Billboard Yearly Diagnostics

涉及文件：`backend/domains/ai_reports/agentic_tools.py`、`backend/tests/unit/test_agentic_yearly_report_tools.py`。

- Add diagnostics test

- Implement diagnostics

---

## Task 5: Add Editorial Critic

涉及文件：`backend/domains/ai_reports/editorial_critic.py`、`backend/tests/unit/test_agentic_yearly_report_critic.py`。

- Write critic tests
- Implement deterministic critic

---

## Task 6: Add Agentic Prompts

涉及文件：`backend/domains/ai_reports/agentic_prompts.py`、`backend/tests/unit/test_agentic_yearly_report_service.py`。

- Add prompt content tests
- Implement prompt module

---

## Task 7: Implement Agentic Yearly Report Service Skeleton

涉及文件：`backend/services/yearly_report_agent_service.py`、`backend/tests/unit/test_agentic_yearly_report_service.py`。

- Add service skeleton tests

- Implement service skeleton

---

## Task 8: Add Fallback Metadata And Basic Summary Path

涉及文件：`backend/services/yearly_report_agent_service.py`、`backend/tests/unit/test_agentic_yearly_report_service.py`。

- Add fallback test

- Implement fallback path

Import `BASIC_SUMMARY_FALLBACK_LEVEL` from `agentic_models`.

---

## Task 9: Persist Agentic Task Events And Tool Calls

涉及文件：`backend/services/yearly_report_agent_service.py`、`backend/services/ai_task_service.py`、`backend/tests/unit/test_ai_report_tasks.py`。

- Add task event expectations

If `run_report_task_inline_for_tests()` does not exist, add it in this task as a small test-only helper that calls `run_report_generation_task(task_id, request)` synchronously with the stored request.

- Route yearly agent tasks

Import `json` at the top of `backend/services/ai_task_service.py`.

- Add inline test helper if needed

---

## Task 10: Preserve API Compatibility And Expose Metadata

涉及文件：`backend/api/ai_insights.py`、`backend/services/ai_insights_service.py`、`backend/tests/contract/test_agentic_yearly_report_contract.py`。

- Update API route

Preserve existing response fields (`success`, `report`, `error`, `cached`) for frontend compatibility. Add `metadata`, `critic`, and `evidence_ledger` as optional fields.

---

## Task 11: Add HTTP Probe For Agentic Yearly Report Quality

涉及文件：`scripts/probe_agentic_yearly_report.py`。

- Test manually with running backend.
- Create probe script

---

- 历史验收要求：PASS and JSON `ok: true`.

## Task 12: Add Frontend Stage Labels And Metadata Display

涉及文件：`frontend/src/features/ai-tasks/`、`frontend/src/features/ai-insights/`。

- Locate current stage label mapping

历史验收预期： identify the component that maps backend task stages to user-facing labels.

- Add stage labels

Keep existing labels unchanged.

- Display report metadata if present

Use existing design primitives/classes in the file rather than introducing a new visual system.

---

- 历史验收要求：PASS, 0 console errors/warnings, 0 horizontal overflow.

## Task 13: Update Documentation

涉及文件：`README.md`、`AGENTS.md`、`CLAUDE.md`、`backend/CLAUDE.md`、`docs/README.md`、`docs/CHANGELOG.md`。

- Update docs index

```markdown
| [`superpowers/plans/2026-07-03-agentic-longform-yearly-report.md`](superpowers/plans/2026-07-03-agentic-longform-yearly-report.md) | Agentic Longform Yearly Report 实施计划：只读 Report Agent、自主查询、Evidence Ledger、动态大纲、个人 Billboard 深度分析、长文 critic 与验收探针 |
```

- Update changelog

```markdown
### 计划与设计

- 新增 Agentic Longform Yearly Report V14 实施计划，目标是把年度报告从播放分析页面复述升级为只读 Report Agent 自主查询、分析、审稿后生成的长篇个人音乐分析文章。
- 计划保留 V12 年度报告事实安全 validator 和 basic summary fallback，同时新增 Evidence Ledger、Insight Synthesis、Dynamic Outline、Billboard diagnostics 与 Editorial Critic。
- 年度报告验收标准提升为：长文长度、明确 thesis、播放与个人 Billboard 关系解释、动态结构、工具轨迹可见和反数据罗列 critic。
```

- Update AI context docs after implementation

After code lands, update these docs with the actual final behavior:

- `README.md`: user-facing AI Insights description.
- `AGENTS.md`: AI report agent architecture and read-only boundary.
- `CLAUDE.md`: quick developer status.
- `backend/CLAUDE.md`: backend service/module table.

Use concrete implemented names: `yearly_report_agent_service.py`, `agentic_tools.py`, `editorial_critic.py`, and `agentic_yearly_v14`.

- Check docs for stale version references

历史验收预期： V12 appears only as safety/fallback context; V14 appears as the new agentic report workflow.

---

## Task 14: Final Validation Matrix

- No new files unless a validation failure requires a focused fix.

With backend running:

- `ok: true`
- `metadata.report_mode: agentic_longform`
- `metadata.contract_version: agentic_yearly_v14`
- `metadata.fallback_level: null`
- `metadata.critic_passed: true`
- `metadata.article_length >= 1400`
- `metadata.tool_calls >= 6`
- Manual browser acceptance

In the in-app browser:

1. Open `http://localhost:5173/ai-insights`.
2. Navigate to yearly report.
3. Click the manual generate/refresh button for 2026.
4. Confirm progress stages include data research, Billboard query, insight synthesis, outline, draft, and critic review.
5. Confirm final report is article-length and not a dashboard restatement.
6. Confirm report mentions local personal Billboard boundary.
7. Confirm report explains at least one relationship between playback behavior and personal Billboard evidence.

- Final workspace and docs check
- No accidental runtime files staged.
- No unresolved planning markers in new plan/code.
- Old contract versions do not appear in new V14 files except historical docs.

---

- 历史验收要求：If this probe still validates through the V12 validator only, inspect output manually and use `probe_agentic_yearly_report.py` as the stronger V14 gate.
- 历史验收要求：PASS with 0 console errors, 0 warnings, 0 page errors, 0px scroll overflow.

## Self-Review Checklist

- Spec goal is covered: report generation is agentic, tool-driven, and longform.
- Read-only boundary is covered: report tools are allowlisted and reject unknown tool names.
- Evidence Ledger is covered: every tool call becomes an `EvidenceLedgerEntry`.
- Insight Synthesis is covered: service builds structured synthesis before drafting.
- Dynamic Outline is covered: service builds outline before drafting.
- Billboard analysis is covered: diagnostics include dominance, stability, breakout, and cross-chart alignment.
- Critic is covered: deterministic critic rejects data listing, Billboard underuse, and partial-year annual labels.
- Fallback distinction is covered: critic failure returns `fallback_level=basic_summary`.
- Frontend is covered: progress labels and metadata display are planned.
- Verification is covered: backend tests, lint, HTTP probe, frontend smoke, manual browser acceptance.
