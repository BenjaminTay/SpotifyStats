# AI Visual Yearly Report Artifact Implementation Plan

> 历史实施提纲：已省略大段实现／测试代码草稿、重复命令及红绿测试步骤，保留设计要求、分工、接口示例与原验收事实。正文中的任务和Expected属于当时计划；当前行为见[文档地图](../../../README.md)。

**Goal:** Upgrade yearly AI reports from text-only analysis into a structured visual music-year artifact with narrative sections, insight cards, chart blocks, real chart data, and style/fact validation.

**Architecture:** Keep the existing read-only Report Agent, evidence ledger, yearly contract, and fact validator. Add a `visual_yearly_artifact` pipeline after evidence gathering: deterministic Narrative Brief, Visual Brief, Chart Data Builder, Artifact Composer, Visual Critic, and frontend artifact renderer. Preserve `agentic_longform` and `basic_summary` as explicit fallback modes.

**Tech Stack:** FastAPI service layer, SQLite-backed AI task runs/events/tool calls, existing `backend/domains/ai_reports` package, pytest unit/contract tests, React 19 + TypeScript, TanStack Query, ECharts via existing `LazyEChart`, Vitest, Playwright/browser smoke probes.

---

## Implementation Status

Status: implemented and self-verified on 2026-07-04.

Delivered:

- Backend `visual_yearly_artifact` mode with `visual_yearly_v1` artifact schema, narrative brief, visual brief, deterministic chart data builder, visual critic, fact validation, cache isolation, AI task routing, and direct forced API support.
- Frontend artifact renderer for `/ai-insights` yearly reports, including hero, insight cards, sections, and 7 concrete chart blocks.
- Probe script `scripts/probe_visual_yearly_report_artifact.py` and targeted backend/frontend tests.
- Documentation updates in README, AGENTS, CLAUDE, backend CLAUDE, docs README, CHANGELOG, and this plan.

Acceptance evidence:

- Backend targeted pytest: 36 passed.
- Frontend targeted Vitest: 7 passed.
- `npm run build`: pass.
- Ruff targeted check and `git diff --check`: pass.
- Live artifact probes for 2025 and 2026: pass, each with 7 sections, 7 chart data blocks, and 3 insight cards.
- Browser acceptance via Chrome CDP: `/ai-insights` -> `年度叙事`, desktop 1440px and mobile 390px, 8 figures, 0 console warning/error, 0 horizontal overflow, no chart empty-state fallback, no `[object Object]`.
- Browser screenshots: `/tmp/spotify_visual_yearly_desktop.png`, `/tmp/spotify_visual_yearly_mobile.png`.

Not done:

- No commit was created in this execution; commit remains a separate explicit user action.

---

## Source Spec

- Design spec: `docs/superpowers/specs/2026-07-03-ai-visual-yearly-report-artifact-design.md`
- Existing agentic yearly report plan: `docs/superpowers/plans/2026-07-03-agentic-longform-yearly-report.md`
- Existing implementation entry points:
  - `backend/services/yearly_report_agent_service.py`
  - `backend/domains/ai_reports/agentic_tools.py`
  - `backend/domains/ai_reports/yearly_contract.py`
  - `backend/domains/ai_reports/yearly_validator.py`
  - `backend/services/ai_task_service.py`
  - `frontend/src/features/ai-insights/ReportCard.tsx`
  - `frontend/src/features/ai-tasks/AITaskProgress.tsx`

## Scope

This plan implements one complete vertical slice:

- `visual_yearly_artifact` report mode for yearly reports.
- Structured backend artifact result with narrative brief, visual brief, sections, insight cards, chart specs, chart data, critic, and fact validation.
- Frontend renderer for yearly artifact on the existing `/ai-insights` report surface.
- Chart data generated only by deterministic backend code.
- HTTP probe and browser acceptance checks for 2025 full-year and 2026 partial-year reports.

This plan does not implement PDF export, social sharing, custom themes, generated images, or weekly/monthly artifact rendering.

### Backend Create

- `backend/domains/ai_reports/visual_artifact_models.py`
  - Dataclasses and constants for `visual_yearly_v1`, sections, insight cards, chart specs, chart data, artifact metadata, and artifact result serialization.

- `backend/domains/ai_reports/narrative_brief.py`
  - Deterministic story-material builder that converts report context into companionship, second thread, discovery, life rhythm, tensions, and safe speculation rules.

- `backend/domains/ai_reports/visual_brief.py`
  - Deterministic visual-planning builder that selects chart specs from available evidence and chart-data coverage.

- `backend/domains/ai_reports/visual_chart_data.py`
  - Read-only chart-data builder for listening calendar, artist monthly trend, album duality, highlight day timeline, genre mix, discovery timeline, and playback/Billboard matrix.

- `backend/domains/ai_reports/visual_yearly_prompts.py`
  - Prompt text for artifact prose composition and repair, focused on personal music-year writing rather than business analysis.

- `backend/domains/ai_reports/visual_yearly_critic.py`
  - Critic for artifact completeness, chart refs, business-report terms, internal terminology leakage, story obligations, and prose length.

- `backend/domains/ai_reports/visual_yearly_artifact_service.py`
  - Orchestrates narrative brief, visual brief, chart data, prose sections, deterministic fallback, critic, fact validation, and result metadata.

- `backend/tests/unit/test_visual_yearly_artifact_models.py`
- `backend/tests/unit/test_narrative_brief.py`
- `backend/tests/unit/test_visual_brief.py`
- `backend/tests/unit/test_visual_chart_data.py`
- `backend/tests/unit/test_visual_yearly_critic.py`
- `backend/tests/unit/test_visual_yearly_artifact_service.py`
- `backend/tests/contract/test_visual_yearly_report_contract.py`
- `scripts/probe_visual_yearly_report_artifact.py`
  - Forces a visual yearly report through the real task API and validates artifact shape, chart refs, forbidden terms, critic, fact validation, and key 2025/2026 golden signals.

### Backend Modify

- `backend/models/ai_tasks.py`
  - Extend `ReportTaskRequest.report_mode` to include `visual_yearly_artifact`; default yearly UI should eventually send this mode explicitly.

- `backend/api/ai_insights.py`
  - Allow direct forced `/api/ai-insights/yearly-story` calls with `report_mode=visual_yearly_artifact` to return artifact metadata for debugging and probes.

- `backend/services/ai_task_service.py`
  - Route yearly `visual_yearly_artifact` tasks to the new service.
  - Persist artifact evidence/tool calls using the existing repository.
  - Add stage progress mapping for narrative/visual/chart/artifact review stages.

- `backend/services/yearly_report_agent_service.py`
  - Keep `agentic_longform` unchanged.
  - Expose reusable research-plan helpers or context construction only when the visual service needs them.
  - Do not move visual artifact code into this file.

### Frontend Create

- `frontend/src/features/ai-insights/yearly-artifact/yearlyArtifactTypes.ts`
- `frontend/src/features/ai-insights/yearly-artifact/VisualYearlyReport.tsx`
- `frontend/src/features/ai-insights/yearly-artifact/YearlyHero.tsx`
- `frontend/src/features/ai-insights/yearly-artifact/YearlySection.tsx`
- `frontend/src/features/ai-insights/yearly-artifact/YearlyInsightCards.tsx`
- `frontend/src/features/ai-insights/yearly-artifact/YearlyChartBlock.tsx`
- `frontend/src/features/ai-insights/yearly-artifact/charts/ListeningCalendarChart.tsx`
- `frontend/src/features/ai-insights/yearly-artifact/charts/ArtistMonthlyTrendChart.tsx`
- `frontend/src/features/ai-insights/yearly-artifact/charts/AlbumDualityCompare.tsx`
- `frontend/src/features/ai-insights/yearly-artifact/charts/HighlightDayTimeline.tsx`
- `frontend/src/features/ai-insights/yearly-artifact/charts/GenreLanguageMixChart.tsx`
- `frontend/src/features/ai-insights/yearly-artifact/charts/DiscoveryTimeline.tsx`
- `frontend/src/features/ai-insights/yearly-artifact/charts/PlaybackBillboardMatrix.tsx`
- `frontend/src/tests/visual-yearly-report.test.tsx`

### Frontend Modify

- `frontend/src/features/ai-insights/AiReportsPanel.tsx`
  - Parse `artifact` from task result.
  - Send `report_mode: "visual_yearly_artifact"` for yearly cache/generate payloads.

- `frontend/src/features/ai-insights/ReportCard.tsx`
  - Render `VisualYearlyReport` when a valid artifact exists.
  - Keep Markdown fallback for old reports and non-yearly reports.

- `frontend/src/features/ai-tasks/AITaskProgress.tsx`
  - Add readable stage labels for narrative, visual, chart data, artifact composition, and artifact review.

- `frontend/src/hooks/useAiTasks.ts`
  - Extend `ReportTaskRequest.report_mode` union.

### Docs Modify

- `docs/README.md`
- `docs/CHANGELOG.md`
- `AGENTS.md`
- `CLAUDE.md`
- `backend/CLAUDE.md`
- `README.md`

## Acceptance Criteria

- 2025 generated yearly result has `metadata.report_mode == "visual_yearly_artifact"` and `metadata.contract_version == "visual_yearly_v1"`.
- 2025 artifact contains at least 6 sections, 4 chart specs, 4 resolved chart data entries, and 3 insight cards.
- 2025 artifact prose length is at least 2800 Chinese characters.
- 2025 artifact includes Taylor Swift, Michael Wong, JOLIN, The Life of a Showgirl, 光良「回憶裡的瘋狂」巡迴演唱會, and 2025-02-14.
- 2025 artifact explains the difference between playback-leading album and personal-chart-leading album.
- Final user prose does not contain forbidden internal/business terms: `稳定中心`, `三榜联动`, `第二层证据`, `evidence ledger`, `dynamic outline`, `综合来看`, `后续观察`.
- 2026 artifact is explicitly partial-year and includes `截至 2026-06-23`.
- Chart data is generated by backend code, not by LLM.
- Visual critic and yearly fact validator both pass for normal 2025/2026 data.
- Frontend renders the artifact instead of plain Markdown and shows at least four chart blocks.
- 390px mobile viewport has no horizontal overflow and browser console has no errors or warnings.

---

## Task 1: Add Visual Artifact Models

涉及文件：`backend/domains/ai_reports/visual_artifact_models.py`、`backend/tests/unit/test_visual_yearly_artifact_models.py`。

- Write serialization and ref-integrity tests
- Implement visual artifact models

## Task 2: Build Narrative Brief

涉及文件：`backend/domains/ai_reports/narrative_brief.py`、`backend/tests/unit/test_narrative_brief.py`。

- Write 2025 narrative brief tests
- Implement deterministic narrative brief

## Task 3: Build Visual Brief And Chart Specs

涉及文件：`backend/domains/ai_reports/visual_brief.py`、`backend/tests/unit/test_visual_brief.py`。

- Write visual brief tests
- Implement visual brief builder

## Task 4: Build Deterministic Chart Data

涉及文件：`backend/domains/ai_reports/visual_chart_data.py`、`backend/tests/unit/test_visual_chart_data.py`。

- Write chart data tests with compact context
- Implement chart data builder

## Task 5: Add Visual Yearly Critic

涉及文件：`backend/domains/ai_reports/visual_yearly_critic.py`、`backend/tests/unit/test_visual_yearly_critic.py`。

- Write critic tests
- Implement visual critic

## Task 6: Compose Visual Yearly Artifact

涉及文件：`backend/domains/ai_reports/visual_yearly_prompts.py`、`backend/domains/ai_reports/visual_yearly_artifact_service.py`、`backend/tests/unit/test_visual_yearly_artifact_service.py`。

- Write artifact service test with monkeypatched research
- Add prompt constants
- Implement deterministic artifact composer first

Add helper prose functions that each return at least 350 Chinese characters for full-year reports. Use no forbidden business-report terms. Keep exact entity names from context.

## Task 7: Route Visual Artifact Through API And AI Tasks

涉及文件：`backend/models/ai_tasks.py`、`backend/services/ai_task_service.py`、`backend/api/ai_insights.py`、`backend/tests/contract/test_visual_yearly_report_contract.py`、`backend/tests/unit/test_ai_report_tasks.py`。

- Add contract tests for task and direct API routes
- Extend report mode models and response shape
- Route visual report in API
- Route visual report in task service

- Add unit test for visual task dispatch

## Task 8: Add Frontend Artifact Types And Renderer Shell

涉及文件：`frontend/src/features/ai-insights/yearly-artifact/yearlyArtifactTypes.ts`、`frontend/src/features/ai-insights/yearly-artifact/VisualYearlyReport.tsx`、`frontend/src/features/ai-insights/yearly-artifact/YearlyHero.tsx`、`frontend/src/features/ai-insights/yearly-artifact/YearlySection.tsx`、`frontend/src/features/ai-insights/yearly-artifact/YearlyInsightCards.tsx`、`frontend/src/features/ai-insights/yearly-artifact/YearlyChartBlock.tsx`、`frontend/src/tests/visual-yearly-report.test.tsx`。

- Write frontend renderer tests
- Add frontend artifact types
- Add renderer shell components

## Task 9: Add Concrete Chart Components

- Create files under `frontend/src/features/ai-insights/yearly-artifact/charts/`
- Modify: `frontend/src/features/ai-insights/yearly-artifact/YearlyChartBlock.tsx`
- Modify: `frontend/src/tests/visual-yearly-report.test.tsx`
- Add chart dispatch test

Extend `frontend/src/tests/visual-yearly-report.test.tsx`:

- Implement first chart components
- Implement remaining chart components as readable first-pass views

Create the remaining files with simple, data-driven, non-ECharts implementations:

- `ArtistMonthlyTrendChart.tsx`: table-like monthly rows for entities.
- `HighlightDayTimeline.tsx`: hourly bars and top tracks.
- `GenreLanguageMixChart.tsx`: horizontal percentage bars.
- `DiscoveryTimeline.tsx`: first-seen artist list.
- `PlaybackBillboardMatrix.tsx`: compact grid of items with plays/weeks.

Each component must:

- Accept `data: unknown`.
- Validate shape locally.
- Render a clear empty state.
- Avoid fixed widths wider than parent.
- Dispatch concrete chart components

## Task 10: Integrate Artifact Into Existing AI Reports UI

涉及文件：`frontend/src/features/ai-insights/AiReportsPanel.tsx`、`frontend/src/features/ai-insights/ReportCard.tsx`、`frontend/src/features/ai-tasks/AITaskProgress.tsx`、`frontend/src/hooks/useAiTasks.ts`、`frontend/src/tests/ai-task-components.test.tsx`、`frontend/src/tests/visual-yearly-report.test.tsx`。

- Extend ReportCard test for artifact branch
- Extend frontend request/result types

Use `isVisualYearlyArtifact(value.artifact)` in `reportResultFromPayload()`.

- Send visual mode for yearly reports

Do the same for generate payloads.

- Render visual artifact from ReportCard

Before Markdown content:

- Add stage labels

## Task 11: Add HTTP Probe And Golden Checks

涉及文件：`scripts/probe_visual_yearly_report_artifact.py`。

- Create/Modify: `backend/tests/contract/test_visual_yearly_report_contract.py`
- Create probe script

## Task 12: Browser Acceptance And Documentation

涉及文件：`README.md`、`AGENTS.md`、`CLAUDE.md`、`backend/CLAUDE.md`、`docs/README.md`、`docs/CHANGELOG.md`、`docs/superpowers/plans/2026-07-04-ai-visual-yearly-report-artifact.md`。

Use the in-app browser or Playwright to verify:

1. Navigate to `/ai-insights`.
2. Click `年度叙事`.
3. Select `2025`.
4. Click `刷新报告`.
5. Confirm progress includes:
   - `提炼年度故事线`
   - `选择年报图表`
   - `准备图表数据`
   - `生成图文年报`
   - `检查文风与事实口径`
6. Confirm final page renders artifact, not only Markdown.
7. Confirm at least 4 chart blocks appear.
8. Set viewport width to 390px and confirm no horizontal overflow.
9. Confirm console error/warning count is 0.

- Update docs

```text
年度叙事默认生成图文音乐年报 artifact，包含故事章节、重点卡片、真实图表数据、个人榜单关系分析和文风/事实校验。
```

```text
AI Visual Yearly Report Artifact（2026-07-04）：年度报告默认 `report_mode=visual_yearly_artifact`，保留只读 Report Agent 和 fact validator，新增 Narrative Brief、Visual Brief、Chart Data Builder、Visual Critic 与前端 artifact renderer。LLM 只写故事表达，不得生成图表数据；图表数据必须由 deterministic backend builder 生成。
```

```markdown
| [`superpowers/plans/2026-07-04-ai-visual-yearly-report-artifact.md`](superpowers/plans/2026-07-04-ai-visual-yearly-report-artifact.md) | AI Visual Yearly Report Artifact 实施计划：Narrative Brief、Visual Brief、真实图表数据、图文年报渲染器、critic、probe 与浏览器验收 |
```

Update `docs/CHANGELOG.md` with implementation summary and actual verification commands.

- Final checkpoint

Not completed in this execution because no commit was requested.

## Self-Review

- Spec coverage: every spec section is mapped to tasks:
  - Artifact schema: Task 1.
  - Narrative Brief: Task 2.
  - Visual Brief: Task 3.
  - Chart Data Builder: Task 4.
  - Visual/Narrative Critic: Task 5.
  - Artifact Composer and fact validation: Task 6.
  - API/task result integration: Task 7.
  - Frontend renderer and chart blocks: Tasks 8-10.
  - Probe/browser/docs: Tasks 11-12.
- 占位扫描：this plan contains no vague task, no open-ended “add tests” step, and no unassigned implementation area.
- Type consistency:
  - Report mode is consistently `visual_yearly_artifact`.
  - Contract version is consistently `visual_yearly_v1`.
  - Frontend `VisualYearlyArtifact` mirrors backend `VisualYearlyArtifact.to_dict()`.
  - Chart `id` and `data_key` use the same key in first implementation.
- Scope control:
  - Weekly/monthly reports stay on current renderer.
  - PDF export, sharing, custom themes, and generated images are not part of this plan.
  - `agentic_longform` and `basic_summary` remain available fallback modes.
