# AI Visual Yearly Report Quality Polish Implementation Plan

> 历史实施提纲：已省略大段实现／测试代码草稿、重复命令及红绿测试步骤，保留设计要求、分工、接口示例与原验收事实。正文中的任务和Expected属于当时计划；当前行为见[文档地图](../../../README.md)。

**Goal:** Upgrade the AI visual yearly report from a readable data article into a more insightful, less repetitive, data-adaptive personal music-year narrative.

**Architecture:** Keep the current `visual_yearly_artifact` contract and frontend renderer. Add deterministic narrative-quality gates, richer chart-reading signals, and a dynamic outline planner before prose composition so the report can read the actual year instead of filling a fixed template. The LLM/prompt layer should receive stronger obligations, while backend validators reject repeated facts, shallow chart integration, weak Billboard usage, and generic section prose.

**Tech Stack:** FastAPI service layer, `backend/domains/ai_reports`, pytest unit/contract tests, React/Vitest renderer smoke, `scripts/probe_visual_yearly_report_artifact.py`, in-app browser QA for `/ai-insights`.

**Execution status (2026-07-04):** Implemented via Subagent-Driven rollout. The backend now emits chart-derived observations, dynamic outline roles, narrative quality gates, partial-year-safe visible labels, and stricter visual artifact probes. The frontend renderer now shows matrix item type labels and chart observations. Verified with targeted backend tests, frontend visual report tests/build, 2025 and 2026 real API probes, and in-app browser refresh QA on `/ai-insights`.

---

## Current Evidence

Latest generated 2026 report status:

- `ai_report_yearly` task completed successfully.
- Article length: 3,259 Chinese characters.
- Artifact shape: 7 sections, 4 insight cards, 7 chart specs.
- Browser render: report visible, all 7 chart titles visible, no horizontal overflow, no console errors.

Quality problems still visible:

- Repetition: opening repeats `174 个活跃日、7860 次播放、约 498 小时` in adjacent sentences; closing repeats the album-duality sentence.
- Shallow trend reading: monthly artist trend shows Taylor Swift high in January, Olivia Rodrigo rising strongly in April-June, but prose only says “另一条情绪线”.
- Weak Billboard analysis: report mentions The Life of a Showgirl staying 24 weeks, but does not compare playback rank vs personal Billboard rank across tracks/albums/artists.
- Template structure: sections are still nearly fixed as opening -> Taylor -> Olivia -> album -> highlight day -> discovery -> closing.
- Chart integration gap: chart titles and data render, but prose rarely extracts concrete turning points from the chart data.
- Data typing issue: `playback_billboard_matrix.items[*].type` is `unknown`, which limits frontend labels and narrative grouping.
- Emotional specificity is conservative: avoids hallucinated life events, but overuses safe generic phrases like “陪伴”“声音线”“入口”.

### Backend Create

- `backend/domains/ai_reports/narrative_quality.py`
  - Pure quality checks for repeated fact phrases, duplicated long sentences, generic prose density, chart-reference obligations, and Billboard-analysis obligations.

- `backend/domains/ai_reports/dynamic_outline.py`
  - Selects report sections from detected yearly signals instead of always using the same seven-section order.

- `backend/tests/unit/test_narrative_quality.py`
  - Locks quality gates with small prose fixtures.

- `backend/tests/unit/test_dynamic_outline.py`
  - Locks section selection for 2026-like, discovery-heavy, chart-divergent, and low-data years.

### Backend Modify

- `backend/domains/ai_reports/visual_chart_data.py`
  - Add chart-derived observations:
    - artist monthly turning points
    - album playback/chart relation
    - Billboard matrix item type
    - short-burst vs long-stay classification
    - highlight-day concentration summary

- `backend/domains/ai_reports/story_insight_builder.py`
  - Consume chart observations and produce section-level `analysis_points`.
  - Replace generic “second thread” prose inputs with concrete month/change evidence.

- `backend/domains/ai_reports/visual_brief.py`
  - Include `outline_sections`, `chart_obligations`, and `billboard_obligations`.

- `backend/domains/ai_reports/visual_yearly_artifact_service.py`
  - Use dynamic outline sections.
  - Pass `analysis_points` into each section composer.
  - Deduplicate facts across sections before final artifact output.

- `backend/domains/ai_reports/visual_yearly_critic.py`
  - Call `narrative_quality.evaluate_visual_yearly_quality()`.
  - Reject reports with repeated facts, missing chart reading, weak Billboard analysis, or too many generic filler phrases.

- `scripts/probe_visual_yearly_report_artifact.py`
  - Add acceptance checks for repetition, chart-derived observations, typed Billboard matrix items, and dynamic section evidence.

### Frontend Modify

- `frontend/src/features/ai-insights/yearly-artifact/*`
  - No structural redesign is planned.
  - Add visible type labels for playback/Billboard matrix items so `track`, `album`, and `artist` are not only backend-only fields.

---

## Task 1: Add Narrative Quality Gates

涉及文件：`backend/domains/ai_reports/narrative_quality.py`、`backend/tests/unit/test_narrative_quality.py`、`backend/domains/ai_reports/visual_yearly_critic.py`。

- Implement quality evaluator
- Wire evaluator into visual critic

---

## Task 2: Enrich Chart Data With Readable Observations

涉及文件：`backend/domains/ai_reports/visual_chart_data.py`、`backend/tests/unit/test_visual_chart_data.py`。

- Add chart observation helpers
- Attach observations to chart data

---

## Task 3: Add Dynamic Outline Planner

涉及文件：`backend/domains/ai_reports/dynamic_outline.py`、`backend/tests/unit/test_dynamic_outline.py`、`backend/domains/ai_reports/visual_brief.py`。

- Implement outline planner
- Attach outline to visual brief

---

## Task 4: Make Section Prose Consume Analysis Points

涉及文件：`backend/domains/ai_reports/story_insight_builder.py`、`backend/domains/ai_reports/visual_yearly_artifact_service.py`、`backend/tests/unit/test_story_insight_builder.py`、`backend/tests/unit/test_visual_yearly_artifact_service.py`。

Use the existing fixture/helper name in the file. If `_sample_visual_context()` does not exist, create a local helper in the test file with the same minimal context currently used by existing visual artifact service tests.

- Add analysis points in story insight builder

The exact names may include additional existing keys, but `analysis_points` must be present for every section that references a chart.

- Update section composer

Keep existing section schema unchanged.

- Add dedupe pass before returning artifact

---

## Task 5: Strengthen Critic and Probe Acceptance

涉及文件：`backend/domains/ai_reports/visual_yearly_critic.py`、`backend/tests/unit/test_visual_yearly_critic.py`、`scripts/probe_visual_yearly_report_artifact.py`。

- Write critic tests for weak Billboard usage
- Add Billboard obligation check

Then inside critic:

- Add probe checks
- pytest passes.
- probe JSON has `"ok": true`.

---

## Task 6: Frontend Matrix Labels and Browser QA

涉及文件：`frontend/src/features/ai-insights/yearly-artifact/VisualYearlyReport.tsx`、`frontend/src/tests/visual-yearly-report.test.tsx`。

- Implement label mapping

Use this exact rendering in each matrix item:

- Browser acceptance

Use the in-app browser on:

```text
http://localhost:5173/ai-insights
```

Interaction path:

1. Open `/ai-insights`.
2. Click `年度叙事`.
3. Click `刷新报告`.
4. Wait for report to finish.
5. Verify:
   - Report title contains `你的 2026 音乐年记`.
   - No stale `AI 任务进度` after completion.
   - No `undefined`, `null`, `NaN`, or visible `unknown`.
   - Text includes the artist monthly turning point, such as `Olivia Rodrigo 在 2026-06`.
   - Text includes a Billboard longevity interpretation, such as `在榜` or `长留`.
   - All chart titles render.
   - Horizontal overflow is `0`.
   - Console error/warn count is `0`.

---

## Task 7: Final Quality Matrix

涉及文件：`docs/CHANGELOG.md`。

- Review: `AGENTS.md`, `CLAUDE.md`, `README.md`, `docs/README.md`

```json
{"ok": true}
```

in both JSON files.

- Update docs and prompt indexes

```markdown
- AI 图文年报质量打磨：新增叙事质量门禁、动态图文大纲、图表读图观察、播放/Billboard 对照义务和浏览器刷新验收，减少重复事实与模板化段落。
```

Review these files for stale AI yearly-report descriptions:

- `AGENTS.md`
- `CLAUDE.md`
- `README.md`
- `docs/README.md`

When any reviewed file still describes the old fixed-template or markdown-only yearly report behavior, replace that wording with:

```markdown
AI 图文年报使用动态大纲、图表读图观察、播放/Billboard 对照和叙事质量门禁生成；报告保留可视化 artifact 结构，并通过浏览器刷新验收防止旧任务进度残留。
```

- Final diff check
- `git diff --check` has no output.
- `git status --short` only contains intentional files from this plan and existing uncommitted visual-report work.

---

## Acceptance Criteria

The repair is acceptable only if all of these are true:

- The generated 2026 report does not repeat the same core fact in adjacent or near-adjacent sentences.
- At least one section reads a concrete monthly trend observation from `artist_monthly_trend`.
- The report explicitly compares playback heat with personal Billboard longevity or rank behavior.
- `playback_billboard_matrix.items[*].type` is one of `track`, `album`, or `artist`, not `unknown`.
- The outline can change when chart signals change; tests prove at least one non-default outline path.
- Browser QA confirms no stale completion progress after refresh.
- Browser QA confirms no visible `undefined`, `null`, `NaN`, or `unknown`.
- Target backend tests, frontend tests, live probes, build, and `git diff --check` pass.

## Execution Notes

- Keep the existing visual artifact schema backward compatible.
- Prefer deterministic backend analysis over asking the LLM to infer everything from raw data.
- Do not add new chart types unless an existing chart cannot express the needed observation.
- Do not make the prose more dramatic by inventing life events. Use bounded inference language when connecting music to life rhythm.
- Keep each task small enough for one subagent to implement and for the main agent to review before continuing.
