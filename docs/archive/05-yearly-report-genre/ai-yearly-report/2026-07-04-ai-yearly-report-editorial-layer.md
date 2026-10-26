# AI Yearly Report Editorial Layer Implementation Plan

> 历史实施提纲：已省略大段实现／测试代码草稿、重复命令及红绿测试步骤，保留设计要求、分工、接口示例与原验收事实。正文中的任务和Expected属于当时计划；当前行为见[文档地图](../../../README.md)。

**Goal:** Add a deterministic editorial layer for AI visual yearly reports so generated reports assign each fact to one section, reduce template language, connect chart evidence to interpretation, and read like a personal music-year article instead of a data recap.

**Architecture:** Keep the existing `visual_yearly_artifact` contract, Report Agent research flow, chart data builder, and frontend renderer. Add `editorial_plan.py` between `story_insight_builder` and section composition; pass that plan into the composer and critic; replace exact chart-observation matching with interpreted chart evidence checks. The implementation is intentionally incremental: first build the plan, then consume it, then harden critic/probe/browser acceptance.

**Tech Stack:** FastAPI service layer, `backend/domains/ai_reports`, pytest unit/contract tests, `scripts/probe_visual_yearly_report_artifact.py`, React/Vitest smoke for renderer regressions, in-app browser QA on `/ai-insights`.

**Execution Status (2026-07-04):** Implemented via Subagent-Driven rollout. The backend now emits `yearly_editorial_v1` metadata, fact ownership, section roles, and language budgets; critic/probe checks now require interpreted chart evidence instead of raw observation echo; prose generation was tightened to reduce repeated facts and template words. Verified with focused backend tests, frontend renderer tests/build, changed/full real API probes for 2022-2026, and in-app browser refresh QA on `/ai-insights`.

---

## Source Spec

- `docs/superpowers/specs/2026-07-04-ai-yearly-report-editorial-layer-design.md`

## Current State

Already implemented and should be reused:

- `backend/domains/ai_reports/story_insight_builder.py`
  - Builds album relation, second-thread classification, highlight-day interpretation, discovery mode, and closing guidance.
- `backend/domains/ai_reports/dynamic_outline.py`
  - Selects section roles from chart signals.
- `backend/domains/ai_reports/narrative_quality.py`
  - Checks repeated core facts, missing chart observation usage, and generic phrase density.
- `backend/domains/ai_reports/visual_yearly_critic.py`
  - Checks length, chart count, internal guidance leakage, repeated meta prose, same-album false contrast, unsupported Olivia claims, and calls narrative quality.
- `scripts/probe_visual_yearly_report_artifact.py`
  - Runs real task API probes and validates visual artifact shape.

Known gap to fix:

- Current quality gates still expect prose to contain chart observation strings exactly. The editorial-layer spec requires the opposite: chart observations should be interpreted, not repeated verbatim. This plan updates quality/probe logic to detect concrete chart usage without forcing exact sentence echo.

### Backend Create

- `backend/domains/ai_reports/editorial_plan.py`
  - Defines `EditorialFact`, `SectionPlan`, and `EditorialPlan`.
  - Builds fact ownership from context, chart observations, story insights, and dynamic outline roles.
  - Stores language budgets, inference boundaries, and role contracts.

- `backend/tests/unit/test_editorial_plan.py`
  - Locks fact ownership, section roles, language budget, chart fact assignment, and metadata payload shape.

### Backend Modify

- `backend/domains/ai_reports/visual_yearly_artifact_service.py`
  - Build editorial plan after story insights and before section composition.
  - Use editorial roles as the section order source.
  - Attach owned fact ids to section `evidence_refs`.
  - Add editorial metadata to `artifact.metadata`.
  - Reduce repeated/generic prose in `_long_opening`, `_long_companionship`, `_long_discovery`, and `_long_closing`.

- `backend/domains/ai_reports/narrative_quality.py`
  - Accept optional `editorial_plan`.
  - Replace exact chart observation matching with token/entity/month/number based chart-reading checks.
  - Add duplicate fact, chart-prose echo, language budget, data-listing, and unsupported life-claim checks.

- `backend/domains/ai_reports/visual_yearly_critic.py`
  - Pass `editorial_plan` into narrative quality.
  - Convert new narrative quality issue codes into repair instructions.
  - Treat editorial hard blockers as cache-blocking errors.

- `scripts/probe_visual_yearly_report_artifact.py`
  - Validate editorial metadata.
  - Add `--mode changed|full` for broader quality sampling.
  - Replace exact chart-observation checks with interpreted chart-reading checks.
  - Check language budget and repeated fact ownership.

### Frontend Modify

- `frontend/src/features/ai-insights/yearly-artifact/YearlyReportArtifact.tsx` or the current artifact renderer entry file
  - Keep existing visual layout.
  - Ensure shortened chart captions still render accessibly.
  - Do not display full `editorial_plan`; only tolerate new metadata fields.

### Docs Modify

- `docs/CHANGELOG.md`
  - Add a short implementation and verification note after execution.

## Task 1: Add Editorial Plan Builder

涉及文件：`backend/domains/ai_reports/editorial_plan.py`、`backend/tests/unit/test_editorial_plan.py`。

- Implement editorial plan models and builder

Implementation requirements for private helpers:

- `_outline_roles(visual)` returns `visual["outline_sections"][*]["role"]` when present; otherwise returns `("opening", "main_artist", "turning_point", "album_story", "highlight_day", "discovery", "closing")`.
- `_build_facts(context, insights, roles)` creates at least these ids when data exists:
  - `yearly_overview_density` -> `opening`
  - `top_artist_primary` -> `main_artist`
  - `artist_monthly_trend_primary_observation` -> `turning_point` if that role exists, otherwise `second_thread`
  - `album_relation_primary` -> `album_story` or `billboard_divergence`
  - `playback_billboard_matrix_primary_observation` -> `album_story` or `billboard_divergence`
  - `highlight_day_density` -> `highlight_day`
  - `discovery_primary` -> `discovery`
- `_build_sections(roles, facts)` fills each section with owned facts whose `home_section_role` matches the role and referenced facts whose `allowed_reuse` is not `"none"`.
- `_build_sections` keeps only roles listed in `SECTION_CONTRACTS`, and appends missing `opening` and `closing` if absent.

Suggested checkpoint message if the user later asks for commits:

```text
feat: add AI yearly editorial plan builder
```

Do not run `git commit` unless the user explicitly asks for commits.

## Task 2: Route Editorial Plan Through Visual Yearly Artifact Service

涉及文件：`backend/domains/ai_reports/visual_yearly_artifact_service.py`、`backend/tests/unit/test_visual_yearly_artifact_service.py`。

- Add service tests for editorial metadata and evidence refs
- Add wrapper imports and build the plan

Merge final metadata:

- Let section composition use editorial roles and fact refs

Suggested checkpoint message if the user later asks for commits:

```text
feat: route AI yearly reports through editorial plans
```

Do not run `git commit` unless the user explicitly asks for commits.

## Task 3: Replace Exact Chart Echo With Interpreted Chart Reading

涉及文件：`backend/domains/ai_reports/narrative_quality.py`、`backend/domains/ai_reports/visual_yearly_critic.py`、`backend/tests/unit/test_narrative_quality.py`、`backend/tests/unit/test_visual_yearly_critic.py`。

- Update narrative quality tests for interpreted chart usage

- Implement interpreted chart reading helpers

Add helpers:

- Add editorial plan aware checks

Add simple guards:

- Pass editorial plan from visual critic

Suggested checkpoint message if the user later asks for commits:

```text
test: enforce editorial quality gates for yearly reports
```

Do not run `git commit` unless the user explicitly asks for commits.

## Task 4: Make Section Prose Consume Editorial Intent

涉及文件：`backend/domains/ai_reports/visual_yearly_artifact_service.py`、`backend/tests/unit/test_visual_yearly_artifact_service.py`。

- Add tests for reduced generic language and no repeated overview
- Expose language budget in metadata

Keep this in artifact metadata only. It is acceptable for frontend to ignore it.

- Tighten opening prose

In `_long_opening`, keep the first sentence with active days, plays, and hours. Replace the rest of the paragraph with a shorter interpretation that does not reuse `坐标`, `纹理`, or `私人路径`.

Use this replacement return body:

- Tighten companionship and discovery prose

Replace “听歌地图” with “听歌结构” and “开了一扇门” with “增加了一个新方向” in the same function.

- Tighten closing prose

In `_long_closing`, replace the first half with a shorter synthesis. Keep later paragraph about playback vs personal Billboard if it does not duplicate the album section claim.

Then remove these phrases from closing:

- `私人地图`
- `坐标`
- `入口`
- `叙事地图`
- `缝隙`

Keep one explanation of:

```text
播放量告诉我们你在哪些名字上花了最多时间，个人 Billboard 则把周与周之间的延续性保留下来。
```

Suggested checkpoint message if the user later asks for commits:

```text
fix: tighten AI yearly report editorial prose
```

Do not run `git commit` unless the user explicitly asks for commits.

## Task 5: Extend Probe For Editorial Acceptance

涉及文件：`scripts/probe_visual_yearly_report_artifact.py`。

- Add CLI mode argument

Then the `single` branch writes that one summary.

- Replace exact chart observation probe with interpreted check
- Add editorial metadata validation

When collecting chart observation issues, also add:

- Syntax check the probe

Suggested checkpoint message if the user later asks for commits:

```text
test: extend yearly report editorial probe
```

Do not run `git commit` unless the user explicitly asks for commits.

- 历史实施约束：If `args.mode != "single"`, run multiple years.

## Task 6: Frontend Metadata Tolerance And Caption Regression

涉及文件：`frontend/src/features/ai-insights/yearly-artifact/`、`frontend/src/tests/visual-yearly-report.test.tsx`。

- Inspect renderer entry file

历史验收预期： identify the renderer component that renders chart observations/captions.

- Add renderer test for extra metadata tolerance

Suggested checkpoint message if the user later asks for commits:

```text
test: tolerate yearly editorial metadata in renderer
```

Do not run `git commit` unless the user explicitly asks for commits.

- 历史验收要求：If it fails because metadata is rendered raw, hide debug metadata from user-facing UI.

## Task 7: Full Verification And Browser Acceptance

涉及文件：`docs/CHANGELOG.md`。

历史验收预期： production build succeeds.

Ensure backend is running on `127.0.0.1:8000`, then run:

- Exit code 0.
- JSON `ok: true`.
- Summaries for 2025 and 2026.
- Each summary includes `artifact_metadata.editorial_plan_version == "yearly_editorial_v1"`.
- Exit code 0, or only years with genuinely insufficient historical data fail with explicit sparse-data issue.
- If any year fails, inspect JSON and classify whether it is a product bug or a sparse-data acceptance update.
- Browser acceptance on `/ai-insights`

Use the in-app browser or Playwright browser control:

1. Open `http://localhost:5173/ai-insights`.
2. Go to the yearly report tab.
3. Select 2026.
4. Click refresh/generate.
5. Wait for task status done.
6. Confirm timestamp updates.
7. Confirm report body changed when force refresh is used.
8. Confirm visible report includes:
   - `截至 2026-06-23`
   - `Taylor Swift`
   - `Olivia Rodrigo`
   - `The Life of a Showgirl`
   - At least one explanation of playback vs personal Billboard.
9. Confirm report does not overuse:
   - `入口`
   - `坐标`
   - `地图`
   - `声音线`
10. Confirm no console errors and no horizontal overflow.

- Update changelog

```markdown
- AI Visual Yearly Report Editorial Layer：年度图文报告新增确定性 Editorial Plan，给核心事实分配唯一章节主场，记录 section roles/fact count/language budget，并将 critic/probe 从“原样复述图表 observation”升级为“解释性使用图表证据”。这减少了报告中的模板词、重复事实和播放分析页面复述感，同时继续保留个人 Billboard 与本地播放数据的事实边界。
```

- Final checkpoint
- No whitespace errors.
- Changed files match this plan scope.

Suggested final checkpoint message if the user later asks for commits:

```text
feat: add editorial layer for AI yearly reports
```

Do not run `git commit` unless the user explicitly asks for commits.

## Implementation Order

Run tasks in order:

1. Task 1 builds a standalone editorial plan and tests it in isolation.
2. Task 2 wires the plan into the yearly artifact service without changing frontend behavior.
3. Task 3 updates quality gates so the new editorial contract is enforceable.
4. Task 4 tightens prose generation to satisfy the new gates.
5. Task 5 upgrades the real API probe.
6. Task 6 confirms the frontend tolerates new metadata.
7. Task 7 performs real data and browser acceptance.

## Acceptance Criteria

The implementation is complete when:

- `generate_visual_yearly_artifact()` returns metadata with:
  - `editorial_plan_version = "yearly_editorial_v1"`
  - `fact_count >= 5`
  - non-empty `section_roles`
  - `language_budget`
- 2025 and 2026 changed-mode probes pass.
- The report no longer requires exact chart observation echo in prose.
- Repeated core facts, repeated generic language, unsupported life-event claims, and same-album false contrast are rejected before cache.
- Browser refresh on `/ai-insights` shows an updated, readable report with no console errors or horizontal overflow.

## Self-Review

- Spec coverage: covered Fact Ledger, Section Role Contract, Language Budget, Chart-Prose Bridge, Narrative Inference Calibrator, Editorial Critic, metadata, probes, and browser acceptance.
- Scope check: this is one subsystem, AI visual yearly reports. It does not rewrite Report Agent tools, frontend layout, PDF/export, or general chat.
- Type consistency: public names are `EditorialFact`, `SectionPlan`, `EditorialPlan`, `build_editorial_plan`, `yearly_editorial_v1`, and are referenced consistently across service, critic, and probe tasks.
