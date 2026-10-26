# AI Yearly Report Quality Implementation Plan

> 历史实施提纲：已省略大段实现／测试代码草稿、重复命令及红绿测试步骤，保留设计要求、分工、接口示例与原验收事实。正文中的任务和Expected属于当时计划；当前行为见[文档地图](../../../README.md)。

**Goal:** Make AI yearly reports trustworthy for partial-year data, entity-heavy summaries, personality interpretation, genre interpretation, year-over-year comparison, and evidence-grounded narrative writing.

**Architecture:** Keep the existing AI Insights report API and task progress flow. Add a deterministic yearly-report contract layer before the LLM, rewrite only the yearly story prompt, and add a lightweight yearly report validator with one retry before caching. Do not change the general chat Agent or frontend report UI unless a test reveals a regression.

**Tech Stack:** FastAPI service layer, SQLite, pandas-backed playback loaders, pytest unit/contract tests, existing AI task report orchestration, Markdown report output.

---

## Scope

Fix these issues from the 2026 yearly report review:

- Partial 2026 data was written as a complete year.
- Full-year 2025 vs partial-year 2026 comparison was treated as fair.
- Top artist, top track, and new artist names were dropped by the yearly AI data package.
- Personality score labels were mismatched.
- Genre shares were interpreted without the "其他流派" bucket or overlap caveat.
- Low-confidence highlights were over-dramatized.
- The report invented unsupported life scenes.
- Output lacked enough concrete names and evidence density.
- The yearly prompt over-encouraged generic emotional storytelling.

Out of scope:

- Do not implement the copyright/lyrics fix from review issue 8 in this plan.
- Do not redesign the AI Insights UI.
- Do not change weekly or monthly report semantics except where shared helpers require safe reuse.
- Do not expose new write tools or arbitrary SQL.

## Current Root Causes

- `backend/services/ai_insights_service.py::_gather_yearly_data()` reads `artist_name` and `track_name` from Wrapped top-list objects that actually expose `name`, so entity names are erased before the LLM sees them.
- `YEARLY_STORY_SYSTEM` requires "来年寄语" and emotional meaning for each data point, but it does not mention partial-year reports, same-period comparisons, unsupported scenes, genre overlap, or empty-entity handling.
- The yearly data payload exposes raw `personality.dimensions` but does not provide a normalized top-dimension summary, so the LLM can attach scores to the wrong labels.
- Wrapped `comparison.last_year` compares the selected year against the previous full year. For the latest partial year, that comparison is misleading unless replaced by same-period YTD or explicitly suppressed.

## File Map

- Create: `backend/domains/ai_reports/__init__.py`
  Package marker for deterministic AI report data-contract helpers.
- Create: `backend/domains/ai_reports/yearly_contract.py`
  Build reporting period metadata, normalized top lists, personality summary, genre caveat, same-period comparison, and writing constraints.
- Create: `backend/domains/ai_reports/yearly_validator.py`
  Validate generated yearly reports against the data contract and produce retry instructions.
- Create: `backend/tests/unit/test_ai_insights_yearly_quality.py`
  Regression tests for yearly report data shaping, partial-year context, same-period comparison, prompt guardrails, and validator retry.
- Modify: `backend/services/ai_insights_service.py`
  Use the yearly contract helpers, rewrite `YEARLY_STORY_SYSTEM`, run validation and one retry before caching.
- Modify: `backend/tests/unit/test_ai_insights_service.py`
  Add focused compatibility assertions if existing tests are easier to extend than the new yearly test file.
- Modify: `backend/tests/unit/test_ai_report_tasks.py`
  Ensure AI task yearly generation still returns entities and does not cache invalid yearly reports.
- Modify: `backend/tests/contract/test_ai_insights_contract.py`
  Keep `/api/ai-insights/yearly-story` contract stable while allowing richer result internals.
- Modify if needed: `docs/README.md`, `docs/CHANGELOG.md`, `AGENTS.md`, `CLAUDE.md`, `backend/CLAUDE.md`
  Only update if implementation changes prompt/data-contract behavior enough that repo guidance or changelog would become stale.

## Acceptance Criteria

- 2026 yearly report data includes `reporting_period.end_date == "2026-06-23"` on the current production DB and marks the report as partial-year.
- 2026 report text says "截至 2026-06-23" or equivalent, and does not frame the report as a completed full year.
- Top artist names, top track names, and new artist names are present in the LLM input and in generated text when available.
- Partial-year comparison uses same-period YTD metrics or explicitly says full-year comparison is not fair.
- Personality labels and scores match the normalized data contract.
- Genre text includes or accounts for "其他流派" when it is in the top genres, and includes an overlap/metadata caveat.
- Unsupported narrative scenes such as weather, insomnia, farewell, or major life turning points are not introduced unless present in the data.
- Low-confidence highlights are described proportionally. A top track played 4 times on the most active day cannot be called heavy looping.
- Invalid yearly reports are retried once and are not cached if severe validation issues remain.
- Existing AI report task progress, cache-first behavior, and report endpoint response contract remain compatible.

---

## Task 1: Add Regression Tests For The Yearly Report Contract

涉及文件：`backend/tests/unit/test_ai_insights_yearly_quality.py`。

- Create a test file with fake Wrapped data
- Add a failing test for entity names and partial-year period

Append this test:

- Add a failing test for normalized personality and genre caveat

- Add a failing test for prompt/validator retry behavior

Expected before implementation: failures for missing `reporting_period`, wrong entity fields, missing normalized summaries, and missing retry validation.

## Task 2: Add The Deterministic Yearly Contract Helper

涉及文件：`backend/domains/ai_reports/__init__.py`、`backend/domains/ai_reports/yearly_contract.py`、`backend/tests/unit/test_ai_insights_yearly_quality.py`。

- Create the package marker
- Implement name extraction, reporting period, personality, genre, and highlight helpers
- Implement same-period comparison helper
- Add direct tests for helper edge cases
- Verify helper tests

## Task 3: Wire The Contract Into Yearly Data Gathering

涉及文件：`backend/services/ai_insights_service.py`、`backend/tests/unit/test_ai_insights_yearly_quality.py`。

- Import yearly contract helpers
- Replace the yearly payload shaping block
- Keep entity extraction compatible

Update `_extract_entities()` only if the new object-shaped `new_artists` changes assumptions elsewhere. The existing top artist/track extraction should continue to work once `top_artists` and `top_tracks` use `name`.

Expected final behavior:

- Verify Task 1 tests now pass except validator retry

## Task 4: Rewrite The Yearly Story Prompt Around The Contract

涉及文件：`backend/services/ai_insights_service.py`、`backend/tests/unit/test_ai_insights_yearly_quality.py`。

- Replace `YEARLY_STORY_SYSTEM`

Replace the current yearly prompt with:

- Add a prompt regression assertion
- Verify prompt test

## Task 5: Add Yearly Report Validation And One Retry

涉及文件：`backend/domains/ai_reports/yearly_validator.py`、`backend/services/ai_insights_service.py`、`backend/tests/unit/test_ai_insights_yearly_quality.py`、`backend/tests/unit/test_ai_report_tasks.py`。

- Implement validator models and checks
- Wire validation and retry into yearly generation

Keep the existing cache write and success return after this block.

- Ensure invalid reports are not cached
- Verify validator tests

## Task 6: Preserve AI Task And API Compatibility

涉及文件：`backend/tests/unit/test_ai_report_tasks.py`、`backend/tests/contract/test_ai_insights_contract.py`。

- Add task-level entity preservation coverage

If the local task API uses different helper names in the current file, adapt only the invocation wrapper and keep the assertion unchanged.

- 历史验收要求：If a response model rejects the optional `entities` field in failure responses, update the model only to allow the existing field shape; do not add frontend-only fields.

## Task 7: Add A Real-Data Yearly Quality Probe

涉及文件：`scripts/probe_ai_yearly_report_quality.py`。

- Create a deterministic probe script

历史验收预期： exit code 0, with populated names and `reporting_period.is_partial_year=true`.

## Task 8: Real User-Behavior Verification

- No required code files.
- Optional output: `/tmp/spotify_ai_yearly_2026_quality.json`
- Start or reuse local services

历史验收预期： backend on `http://127.0.0.1:8000`, frontend on `http://localhost:5173`.

- Exercise the report endpoint without relying on cache

Use the app's AI report task flow from `/ai-insights`, select yearly report for 2026, and manually generate. If direct API probing is needed for debugging, call the task endpoint used by the frontend rather than adding a new endpoint.

Expected user-visible behavior:

- The progress UI shows data gathering and LLM generation stages.
- The final report says data is截至 `2026-06-23`.
- The report names Taylor Swift, Olivia Rodrigo, and the top songs instead of saying only "某位艺人" or "另一首歌".
- The report does not call 2026 a completed full year.
- The report does not claim a full-year 55% decline unless it is explicitly framed as invalid/full-year-unsafe.
- The report does not invent unsupported scenes.
- Check cache behavior

Generate the same 2026 yearly report again without force.

历史验收预期： cached report returns only if the validated report was stored. Invalid pre-fix cached reports may need manual cache bypass through existing force/manual generation behavior, not a migration.

## Task 9: Documentation And Final Verification

涉及文件：`docs/README.md`、`docs/CHANGELOG.md`、`AGENTS.md`、`CLAUDE.md`、`backend/CLAUDE.md`。

- Decide whether docs are necessary

If the implementation changed only internal helpers and tests, docs may be skipped. If it introduced durable AI report contract behavior, add one short changelog bullet and update AGENTS/CLAUDE AI Insights guidance.

If docs were not changed, omit those paths from `git add`.

## Plan Self-Review

- Spec coverage: all non-lyrics review issues are mapped to data contract, prompt, validator, or verification tasks.
- Placeholder scan: no `TBD`, `TODO`, or unspecified "add tests" steps remain.
- Scope check: this is one subsystem, AI Insights yearly reports, and does not require a broader AI Agent rewrite.
- Type consistency: `reporting_period`, `personality_summary`, `genre_summary`, `year_over_year`, `writing_constraints`, and `entities` names are used consistently across tasks.
- Risk note: the same-period comparison helper depends on `load_plays()` and should be tested with monkeypatch or real DB probe because `load_plays()` has cache behavior and uses the standard DB loader.
