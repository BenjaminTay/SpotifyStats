# AI Visual Yearly Report Editorial Fix Implementation Plan

> 历史实施提纲：已省略大段实现／测试代码草稿、重复命令及红绿测试步骤，保留设计要求、分工、接口示例与原验收事实。正文中的任务和Expected属于当时计划；当前行为见[文档地图](../../../README.md)。

**Goal:** Fix the 2026 visual yearly report so it reads like a personal music-year article with specific, data-grounded insight instead of repeated template prose, internal instruction leakage, and incorrect data interpretations.

**Architecture:** Keep the existing `visual_yearly_artifact` pipeline, chart data builder, frontend renderer, and task/cache integration. Add a deterministic `Story Insight Builder` between evidence/narrative brief and section prose composition, then make the section writer consume structured insight modes such as aligned/divergent/missing. Upgrade the visual critic and probe so internal leakage, repeated meta prose, same-entity false contrast, and unsupported genre/artist claims are rejected before a report is accepted.

**Tech Stack:** FastAPI service layer, `backend/domains/ai_reports`, pytest unit/contract tests, `scripts/probe_visual_yearly_report_artifact.py`, React/Vitest smoke only for unchanged renderer regressions, Chrome CDP browser acceptance for `/ai-insights`.

---

## Source Evidence

Observed 2026 generated report problems:

- Repeated meta paragraph appears in almost every section: “图表负责回答……正文负责回答……”.
- Internal guidance leaks into user text: “证据强度可以先放在 high”, “不要写成重度单曲循环”.
- Album section writes false contrast when playback-leading album and personal-chart-leading album are the same: “The Life of a Showgirl 和 The Life of a Showgirl 说明了两种不同的喜欢”.
- Second-thread section hardcodes “华语、回望和现场感” for Olivia Rodrigo, which is unsupported by the artist and genre evidence.
- Visual critic passes the report despite those issues.

Root causes in current code:

- `backend/domains/ai_reports/visual_yearly_artifact_service.py` uses `_warm_extension()` for every section, causing repeated generic prose.
- `_long_discovery()` writes raw confidence labels into user prose.
- `_long_highlight()` writes raw `interpretation_guidance` into user prose.
- `_long_album_story()` assumes playback leader and chart leader are always different.
- `backend/domains/ai_reports/narrative_brief.py` hardcodes second-thread interpretation as “华语、记忆感或现场感”.
- `backend/domains/ai_reports/visual_yearly_critic.py` checks length and broad obligations but not internal leakage, repetition, or data-relationship contradictions.

## Scope

In scope:

- Add deterministic story insight classification for album relation, second-thread relation, highlight-day interpretation, discovery framing, and closing direction.
- Rewrite backend section prose generation to consume those insights.
- Upgrade critic and probe checks.
- Add tests that reproduce the exact 2026 failure modes.

Out of scope:

- New chart types.
- PDF/export/share features.
- Full LLM rewrite pipeline.
- Frontend visual redesign beyond verifying rendered text and existing chart blocks.

### Backend Create

- `backend/domains/ai_reports/story_insight_builder.py`
  - Converts context + narrative brief into section-level insight objects.
  - Produces normalized modes:
    - `album_relation.mode`: `aligned`, `divergent`, `playback_only`, `chart_only`, `missing`
    - `second_thread.mode`: `same_language_family`, `genre_contrast`, `artist_contrast`, `fallback`
    - `highlight_day.mode`: `multi_track_dense_day`, `repeat_day`, `low_confidence`
    - `discovery.mode`: `strong_new_thread`, `emerging_signal`, `small_signal`
  - Sanitizes internal evidence labels into user-safe wording.

- `backend/tests/unit/test_story_insight_builder.py`
  - Locks the exact relationship classifications that the section writer depends on.

### Backend Modify

- `backend/domains/ai_reports/visual_yearly_artifact_service.py`
  - Import and call `build_story_insights(context, narrative)`.
  - Replace `_warm_extension()` with section-specific prose.
  - Rewrite `_long_album_story()`, `_long_second_thread()`, `_long_highlight()`, `_long_discovery()`, and `_long_closing()` to consume insights.
  - Keep output schema unchanged: `artifact.sections[*].prose`, `chart_refs`, `insight_refs`.

- `backend/domains/ai_reports/narrative_brief.py`
  - Remove hardcoded “华语、记忆感或现场感” from second-thread interpretation.
  - Keep narrative brief factual and minimal; detailed interpretation moves to `story_insight_builder.py`.

- `backend/domains/ai_reports/visual_yearly_critic.py`
  - Add hard blockers for internal instruction leakage.
  - Add repeated sentence / repeated meta-prose detection.
  - Add same-entity false contrast detection.
  - Add context-aware album relationship checks when `context` is provided.

- `scripts/probe_visual_yearly_report_artifact.py`
  - Add golden checks for the 2026 editorial failures.
  - Ensure probe fails if internal terms or repeated meta prose appear.

- `docs/CHANGELOG.md`
  - Add a short implementation summary and actual verification commands after execution.

### Task 1: Add Story Insight Builder

涉及文件：`backend/domains/ai_reports/story_insight_builder.py`、`backend/tests/unit/test_story_insight_builder.py`。

- Implement story insight builder

### Task 2: Rewrite Section Prose To Consume Insights

涉及文件：`backend/domains/ai_reports/visual_yearly_artifact_service.py`、`backend/domains/ai_reports/narrative_brief.py`、`backend/tests/unit/test_visual_yearly_artifact_service.py`。

- Add failing service tests for the 2026 editorial failures
- Wire story insights into service

Then call:

- Replace repeated prose helpers

In `backend/domains/ai_reports/visual_yearly_artifact_service.py`, remove `_warm_extension()` usage from `_long_opening`, `_long_companionship`, `_long_second_thread`, `_long_album_story`, `_long_highlight`, `_long_discovery`, and `_long_closing`.

Replace section prose functions:

- Remove hardcoded second-thread interpretation from narrative brief

### Task 3: Harden Visual Critic

涉及文件：`backend/domains/ai_reports/visual_yearly_critic.py`、`backend/tests/unit/test_visual_yearly_critic.py`。

- Add failing critic tests

- Add critic checks

### Task 4: Update Probe Golden Checks

涉及文件：`scripts/probe_visual_yearly_report_artifact.py`。

- Extend forbidden terms
- Add 2026 same-album guard
- Add repeated-template guard

### Task 5: Full Targeted Verification

- No code changes in this task.

- Both probes exit 0.
- 2026 report does not contain `证据强度`, `不要写成`, `图表负责回答`, `The Life of a Showgirl 和 The Life of a Showgirl`.
- 2026 report contains either `热度与长留` or `同一张专辑`.

Use Chrome CDP, Playwright, or the in-app browser:

1. Navigate to `/ai-insights`.
2. Click `年度叙事`.
3. Generate or load 2026 report.
4. Confirm final page renders artifact, not Markdown-only fallback.
5. Confirm text does not contain `证据强度`, `不要写成`, `图表负责回答`, or `The Life of a Showgirl 和 The Life of a Showgirl`.
6. Confirm at least 6 sections and 6 chart blocks render.
7. Set viewport width to 390px and confirm horizontal overflow is 0.
8. Confirm console error/warning count is 0.

### Task 6: Documentation And Final Review

涉及文件：`docs/CHANGELOG.md`、`docs/superpowers/plans/2026-07-04-ai-visual-yearly-report-editorial-fix.md`。

- Update changelog after implementation

```markdown
### 修复

- 年度图文报告新增 Story Insight Builder，在写作前先判断播放榜/个人榜单关系、新发现强度、高光日类型和第二声音线，避免模板硬套数据。
- 修复 2026 年报中的内部指令泄漏、重复元叙述、同专辑误写成对比、Olivia Rodrigo 被错误绑定华语语境等问题。
- Visual critic 和 HTTP probe 增加内部词泄漏、重复模板、同实体 false contrast 和 2026 golden checks。

### 验证

- 填入实际运行过的 pytest、Vitest、build、ruff、probe 和 browser acceptance 结果。
```

- Mark this plan status

At the top of this plan, after the header block, add:

```markdown
## Implementation Status

Status: implemented and verified on 2026-07-04.

Acceptance evidence:

- Backend targeted pytest: command from Task 5 Step 1 and its final passed count.
- Frontend targeted Vitest/build: commands from Task 5 Step 2 and their pass/build status.
- Live 2025/2026 probes: commands from Task 5 Step 4 and their output JSON paths.
- Browser acceptance: viewport sizes, console issue count, horizontal overflow result, and screenshot paths.
```

- Final code review

Review these diffs manually:

- No user-facing prose contains internal guidance labels.
- Album aligned/divergent modes are both tested.
- Critic detects all failure modes observed in the 2026 report.
- Existing artifact schema remains unchanged.

## Acceptance Criteria

- 2026 generated visual yearly report has no internal instruction leakage.
- 2026 generated report does not repeat the same meta paragraph across sections.
- If playback-leading album and personal-chart-leading album are identical, the report writes aligned heat/long-tail interpretation, not contrast.
- Olivia Rodrigo is not described as bringing a Chinese-language or live-show thread unless the evidence explicitly supports that.
- Visual critic fails the original bad 2026 report pattern.
- HTTP probe fails on those same bad patterns.
- Browser acceptance passes on desktop and 390px mobile with 0 console warning/error and 0 horizontal overflow.

## Self-Review

- Spec coverage: all observed failures map to tasks:
  - Internal leakage: Tasks 1, 2, 3, 4.
  - Repeated template prose: Tasks 2, 3, 4.
  - Same-album false contrast: Tasks 1, 2, 3, 4.
  - Unsupported Olivia Rodrigo genre claim: Tasks 1, 2, 4.
  - Verification and browser acceptance: Task 5.
- 占位扫描：this plan contains no unresolved markers, no unassigned implementation step, and no open-ended “add tests” instruction without concrete tests.
- Type consistency:
  - `build_story_insights(context, narrative)` returns a `dict[str, Any]`.
  - Section writer consumes `album_relation`, `second_thread`, `highlight_day`, `discovery`, and `closing`.
  - Existing artifact schema remains `visual_yearly_v1`.
- Scope control:
  - This plan does not add new chart types or frontend redesign.
  - This plan does not replace the task/cache/report-mode integration already implemented.
  - This plan is a focused editorial-quality repair on top of the visual yearly artifact.
