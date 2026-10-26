# AI Yearly Report Editorial Agent Pipeline Implementation Plan

> 历史实施提纲：已省略大段实现／测试代码草稿、重复命令及红绿测试步骤，保留设计要求、分工、接口示例与原验收事实。正文中的任务和Expected属于当时计划；当前行为见[文档地图](../../../README.md)。

**Goal:** Replace the yearly report prose path with a hybrid editorial agent pipeline that builds a research brief, lets the LLM plan/write/edit the article, validates claims deterministically, then renders the existing visual yearly artifact shape.

**Architecture:** Keep deterministic builders responsible for evidence, chart data, cache contracts, and safety checks. Add a focused `backend/domains/ai_reports/editorial_agent/` package for research brief models, storyline planning, LLM writing/editing, claim checking, orchestration, and taste scoring. Integrate behind `writer_pipeline=editorial_agent_v1`, prove quality with 2025/2026 probes and browser acceptance, then make the new pipeline the default only after the taste gate passes.

**Tech Stack:** FastAPI task orchestration, SQLite report cache, existing `LLMProvider` via `_llm_chat`, Python dataclasses + typed dicts, pytest unit/contract tests, existing visual yearly React artifact renderer, Vitest, Playwright/in-app browser smoke.

**Commit Policy:** Do not create per-task commits. The user explicitly requested keeping the spec and plan uncommitted until the repair is complete; stage and commit only after full implementation, verification, and documentation sync.

**Execution Status (2026-07-05):** Implemented. The final pipeline ships as `visual_yearly_artifact` + `writer_pipeline=editorial_agent_v1`; backend now has the `editorial_agent/` package, writer metadata, claim check, taste scoring, cache-key isolation, task progress stages, frontend badges, updated probe validation, artifact-level deterministic editorial fallback, browser refresh acceptance, and a fix for the partial-year post-processing bug that turned `表明年度` into `表之后度`.

---

## File Structure

Create:

- `backend/domains/ai_reports/editorial_agent/__init__.py` — package exports and version constants.
- `backend/domains/ai_reports/editorial_agent/models.py` — dataclasses for research brief, storyline plan, article draft, edited article, extracted claims, claim check result, and taste rubric.
- `backend/domains/ai_reports/editorial_agent/research_brief.py` — converts existing yearly context, chart data, and story insights into evidence-led story material.
- `backend/domains/ai_reports/editorial_agent/prompts.py` — planner/writer/editor/repair prompts.
- `backend/domains/ai_reports/editorial_agent/llm_steps.py` — JSON/text LLM helper functions with injectable chat function for tests.
- `backend/domains/ai_reports/editorial_agent/storyline_planner.py` — LLM planner plus deterministic fallback plan.
- `backend/domains/ai_reports/editorial_agent/writer.py` — LLM longform writer plus deterministic article fallback for explicit fallback levels.
- `backend/domains/ai_reports/editorial_agent/editor.py` — LLM editorial rewrite pass and deterministic cleanup helpers.
- `backend/domains/ai_reports/editorial_agent/claim_checker.py` — claim extraction and evidence matching.
- `backend/domains/ai_reports/editorial_agent/taste_rubric.py` — deterministic taste scoring used by probes and tests.
- `backend/domains/ai_reports/editorial_agent/pipeline.py` — orchestrates research, planning, writing, editing, claim checking, repair, and artifact section conversion.
- `backend/tests/unit/test_yearly_editorial_agent_models.py`
- `backend/tests/unit/test_yearly_research_brief.py`
- `backend/tests/unit/test_yearly_storyline_planner.py`
- `backend/tests/unit/test_yearly_writer_editor.py`
- `backend/tests/unit/test_yearly_claim_checker.py`
- `backend/tests/unit/test_yearly_taste_rubric.py`
- `backend/tests/unit/test_yearly_editorial_agent_pipeline.py`
- `backend/tests/contract/test_yearly_editorial_agent_contract.py`
- `scripts/evaluate_yearly_report_taste.py`

Modify:

- `backend/domains/ai_reports/visual_yearly_artifact_service.py` — route prose composition through the editorial agent when requested/defaulted.
- `backend/domains/ai_reports/visual_yearly_critic.py` — read editorial agent metadata and add new article-quality blockers.
- `backend/services/ai_task_service.py` — include `writer_pipeline` in report request/cache/payload, add progress stages, preserve fallback metadata.
- `backend/services/ai_insights_service.py` — include writer pipeline in visual yearly cache key or report mode cache part.
- `backend/models/ai_tasks.py` — allow `writer_pipeline` request field.
- `frontend/src/features/ai-tasks/AITaskProgress.tsx` — labels for new stages.
- `frontend/src/features/ai-insights/ReportCard.tsx` — optional badges for `writer_pipeline_version`, claim check, editorial review, and taste score.
- `frontend/src/tests/ai-task-components.test.tsx`
- `frontend/src/tests/visual-yearly-report.test.tsx`
- `scripts/probe_visual_yearly_report_artifact.py` — add `--writer-pipeline`, taste score checks, and metadata validation.
- `docs/README.md`
- `docs/CHANGELOG.md`
- `README.md`, `AGENTS.md`, `CLAUDE.md`, `backend/CLAUDE.md` only if the new pipeline becomes default.

Do not touch unrelated artist genre resolution files currently present in the worktree:

- `backend/core/db.py`
- `backend/core/migrations.py`
- `backend/tests/unit/test_migrations.py`
- `backend/tests/unit/test_artist_genre_resolution.py`
- `docs/superpowers/plans/2026-07-04-artist-genre-resolution.md`

---

## Task 1: Editorial Agent Models

涉及文件：`backend/domains/ai_reports/editorial_agent/__init__.py`、`backend/domains/ai_reports/editorial_agent/models.py`、`backend/tests/unit/test_yearly_editorial_agent_models.py`。

- Write model tests first
- Create package exports
- Implement dataclasses

---

## Task 2: Research Brief Builder

涉及文件：`backend/domains/ai_reports/editorial_agent/research_brief.py`、`backend/tests/unit/test_yearly_research_brief.py`。

- Write research brief tests
- Implement research brief extraction

---

## Task 3: LLM Step Helpers and Prompts

涉及文件：`backend/domains/ai_reports/editorial_agent/prompts.py`、`backend/domains/ai_reports/editorial_agent/llm_steps.py`、`backend/tests/unit/test_yearly_storyline_planner.py`。

- Write helper tests

"""

    assert extract_json_object(text) == {"title": "音乐年记", "sections": [1, 2]}

def test_extract_json_object_returns_empty_dict_for_invalid_json():
    assert extract_json_object("不是 json") == {}
```

- [ ] **Step 2: Run helper tests and confirm failure**

Run:

```bash
source .venv/bin/activate && pytest backend/tests/unit/test_yearly_storyline_planner.py::test_extract_json_object_reads_fenced_json -q
```

- Add prompts
- Add LLM helpers

---

## Task 4: Storyline Planner

涉及文件：`backend/domains/ai_reports/editorial_agent/storyline_planner.py`、`backend/tests/unit/test_yearly_storyline_planner.py`。

- Add planner tests
- Implement planner

---

## Task 5: Writer and Editor

涉及文件：`backend/domains/ai_reports/editorial_agent/writer.py`、`backend/domains/ai_reports/editorial_agent/editor.py`、`backend/tests/unit/test_yearly_writer_editor.py`。

- Write writer/editor tests
- Extend models for edited article
- Implement writer
- Implement editor

---

## Task 6: Claim Checker

涉及文件：`backend/domains/ai_reports/editorial_agent/claim_checker.py`、`backend/tests/unit/test_yearly_claim_checker.py`。

- Write claim checker tests
- Implement claim checker

---

## Task 7: Taste Rubric

涉及文件：`backend/domains/ai_reports/editorial_agent/taste_rubric.py`、`scripts/evaluate_yearly_report_taste.py`、`backend/tests/unit/test_yearly_taste_rubric.py`。

- Write taste rubric tests
- Extend models for taste score
- Implement rubric
- Add CLI evaluator

---

## Task 8: Editorial Agent Pipeline Orchestrator

涉及文件：`backend/domains/ai_reports/editorial_agent/pipeline.py`、`backend/tests/unit/test_yearly_editorial_agent_pipeline.py`。

- Write pipeline tests
- Implement pipeline

---

## Task 9: Integrate Pipeline Into Visual Yearly Artifact Service

涉及文件：`backend/domains/ai_reports/visual_yearly_artifact_service.py`、`backend/services/ai_task_service.py`、`backend/models/ai_tasks.py`、`backend/services/ai_insights_service.py`、`backend/tests/unit/test_visual_yearly_artifact_service.py`、`backend/tests/unit/test_ai_report_tasks.py`、`backend/tests/contract/test_yearly_editorial_agent_contract.py`。

- Add request and metadata contract tests
- Add request flag model

Ensure `backend/services/ai_task_service.py` keeps the field when normalizing report requests. If there is a whitelist or request dict builder, add:

- Add pipeline hook to visual artifact service

Merge metadata:

- Include writer pipeline in visual cache key

In `backend/services/ai_task_service.py`, keep result metadata unchanged for UI, but use the same discriminator for cache read/write. Add a unit test asserting a cache-only request without `writer_pipeline` does not return a cached `writer_pipeline=editorial_agent_v1` artifact.

---

## Task 10: Task Progress and Frontend Metadata

涉及文件：`backend/services/ai_task_service.py`、`frontend/src/features/ai-tasks/AITaskProgress.tsx`、`frontend/src/features/ai-insights/ReportCard.tsx`、`frontend/src/tests/ai-task-components.test.tsx`、`frontend/src/tests/visual-yearly-report.test.tsx`。

- Add frontend tests for progress labels
- Add metadata badge test
- Add stage labels

Merge with existing labels instead of replacing unrelated stages.

- Add ReportCard badges

---

## Task 11: Probe and Taste Acceptance

涉及文件：`scripts/probe_visual_yearly_report_artifact.py`。

- Add probe arguments

When building the task payload:

- Validate metadata and taste score

Run with backend already running on `127.0.0.1:8000`:

```json
{
  "ok": true,
  "summary": {
    "metadata": {
      "writer_pipeline_version": "yearly_editorial_agent_v1",
      "claim_check_passed": true
    }
  }
}
```

---

- 历史验收要求：2025 and 2026 both pass. 2026 includes `截至 2026-06-23`; 2025 does not use year-midpoint phrasing as a full-year report.
- 历史验收要求：exit 0, `ok=true`, `total >= 26`.

## Task 12: Make Editorial Agent Default After Taste Gate

涉及文件：`frontend/src/features/ai-insights/AiReportsPanel.tsx`、`backend/services/ai_task_service.py`、`frontend/src/tests/ai-insights-task-flow.test.tsx`、`backend/tests/unit/test_ai_report_tasks.py`。

- Add default request tests

In `backend/tests/unit/test_ai_report_tasks.py`, add an assertion that yearly visual artifact generation preserves `writer_pipeline`.

- Default yearly visual requests to editorial agent

Ensure generation inherits the same payload because `startGenerateReport` spreads `reportPayload`.

- Backend fallback default

This keeps API clients aligned with the frontend default.

---

## Task 13: Browser Acceptance

- No code files unless the browser check reveals a defect.
- Start or reuse backend and frontend

Run if servers are not already active:

- Backend reachable at `http://127.0.0.1:8000/health`.
- Frontend reachable at `http://localhost:5173/ai-insights`.
- Browser flow

In the in-app browser:

1. Open `http://localhost:5173/ai-insights`.
2. Click `报告`.
3. Click `年度叙事`.
4. Click `今年`.
5. Click `刷新报告`.
6. Wait until the report finishes.

Expected UI:

- Progress shows yearly writing stages such as `正在选择年度主题`, `正在撰写年报正文`, `正在编辑成稿`, `正在核对事实口径`.
- Final report badge includes `Editorial Agent`, `事实已核对`, and `口味评分`.
- Report renders hero, cards, sections, and charts.
- No console error/warn.
- Horizontal overflow is 0.
- Task result metadata includes `writer_pipeline_version=yearly_editorial_agent_v1`.
- Compare report quality manually

Read the generated 2026 report and score it using:

- Article feel: at least 4/5.
- Clear yearly thesis: at least 4/5.
- Insight density: at least 4/5.
- Personalization: at least 4/5.
- Fact safety: exactly 5/5.
- Readability: at least 4/5.
- Visual integration: at least 4/5.

历史验收预期： total at least 26/35 and no obvious return to deterministic template voice.

---

## Task 14: Documentation and Final Verification

涉及文件：`README.md`、`AGENTS.md`、`CLAUDE.md`、`backend/CLAUDE.md`、`docs/README.md`、`docs/CHANGELOG.md`。

- Update durable docs

Add a concise durable note to AI report sections:

```markdown
AI 年度叙事默认走 `visual_yearly_artifact` + `writer_pipeline=editorial_agent_v1`：后端先构建 Research Brief 和确定性图表数据，再由 LLM 规划主题、撰写正文、编辑改稿，最后用 Claim Checker 和 taste rubric 校验事实与可读性；缓存 key 包含 writer pipeline version，避免旧 deterministic 年报挡住新结果。
```

Use this in `README.md`, `AGENTS.md`, `CLAUDE.md`, and `backend/CLAUDE.md` where current AI yearly report notes live.

- Update docs index and changelog

```markdown
| [`superpowers/specs/2026-07-04-ai-yearly-report-editorial-agent-pipeline-design.md`](superpowers/specs/2026-07-04-ai-yearly-report-editorial-agent-pipeline-design.md) | AI Yearly Report Editorial Agent Pipeline 设计：Research Brief、Storyline Planner、LLM 主笔、LLM 编辑、Claim Checker、Taste Rubric 与 artifact 兼容迁移 |
| [`superpowers/plans/2026-07-04-ai-yearly-report-editorial-agent-pipeline.md`](superpowers/plans/2026-07-04-ai-yearly-report-editorial-agent-pipeline.md) | AI Yearly Report Editorial Agent Pipeline 实施计划：模型、研究简报、LLM 写作/编辑、claim checker、taste rubric、缓存隔离、默认切换和验收步骤 |
```

- backend pipeline changes.
- frontend metadata/progress changes.
- probe/taste acceptance.
- validation commands actually run.

- Final git commit after all repairs

Only after all implementation tasks and validation pass, commit all relevant AI yearly report files together. Exclude unrelated artist genre resolution changes unless the user explicitly says they belong in this batch.

历史验收预期： one final repair commit containing spec, plan, implementation, tests, probes, and docs.

---

## Self-Review

Spec coverage:

- Research Brief: Task 2.
- Storyline Planner: Task 4.
- LLM writer: Task 5.
- LLM editor: Task 5.
- Claim Checker: Task 6 and Task 8.
- Taste Rubric: Task 7 and Task 11.
- Artifact compatibility: Task 9.
- Cache and writer pipeline version: Task 9.
- Task progress and UX: Task 10 and Task 13.
- Browser acceptance: Task 13.
- Documentation and final commit boundary: Task 14.

Scope check:

- The plan does not implement artist genre resolution.
- The plan does not redesign frontend visuals.
- The plan keeps chart data deterministic.
- The plan uses explicit `writer_pipeline=editorial_agent_v1` first and switches default only after taste probe/browser acceptance.

Placeholder scan:

- No unresolved placeholder markers, no vague “handle edge cases”, and no empty test steps.
- Each implementation task has exact files, test commands, and concrete code snippets.

Plan complete and saved to `docs/superpowers/plans/2026-07-04-ai-yearly-report-editorial-agent-pipeline.md`. Two execution options:

1. Subagent-Driven (recommended) — dispatch a fresh subagent per task, review between tasks, fast iteration.
2. Inline Execution — execute tasks in this session with checkpoints.
