# AI Yearly Final Artifact Quality Gate Implementation Plan

> 历史实施提纲：已省略大段实现／测试代码草稿、重复命令及红绿测试步骤，保留设计要求、分工、接口示例与原验收事实。正文中的任务和Expected属于当时计划；当前行为见[文档地图](../../../README.md)。

**Goal:** Make the AI yearly visual report pass quality checks on the exact artifact text and chart blocks users see after refresh.

**Architecture:** Keep the existing `visual_yearly_artifact` and `editorial_agent_v1` pipeline. Add a backend final-visible-artifact quality gate, fix artifact section/chart assembly before caching, and add frontend renderer safeguards so repeated chart refs or internal chart copy cannot leak into the UI.

**Tech Stack:** FastAPI backend, Python dataclasses/unit tests, SQLite-backed AI task results, React + Vitest + Testing Library, Playwright/browser manual acceptance.

---

## Current Failure Evidence

The 2026 yearly report refreshed successfully in the browser, but the generated artifact exposed quality failures:

- Report task `0bffaba94e9f` was a real forced yearly generation with `report_mode=visual_yearly_artifact` and `writer_pipeline=editorial_agent_v1`.
- Page showed `Editorial Agent`, `事实核对通过`, `口味评分 35`, and `已通过编辑审稿`.
- User-visible text still contained repeated sections and chart blocks.
- Section decks leaked planner/internal copy such as `展示Olivia Rodrigo...` and `解释播放领先专辑...`.
- `YearlyChartBlock` rendered `chartSpec.insight`, which is currently written like an internal explanation in several specs.
- Existing critic and probe passed because they mostly validate `section.prose`, not the final visible artifact composed from title, subtitle, decks, prose, chart blocks, observations, and frontend chart dedup behavior.

This plan fixes the root cause: the final cacheable artifact must be judged and sanitized as a user-visible product, not as separate LLM draft fragments.

## File Structure

- Create `backend/domains/ai_reports/final_artifact_quality.py`
  - Owns final visible text extraction and deterministic quality checks.
  - Checks section deck/prose, repeated section fingerprints, repeated chart refs, internal planning language, placeholder tokens, and misleading accepted metadata.

- Modify `backend/domains/ai_reports/visual_yearly_artifact_service.py`
  - Replace `section.purpose` as deck source.
  - Deduplicate editorial sections and globally assign each chart ref to one section.
  - Merge final quality issues into critic metadata.

- Modify `backend/domains/ai_reports/visual_yearly_critic.py`
  - Include section `deck`, `pull_quote`, and user-visible chart observations in critic text.
  - Reject internal brief/purpose language in decks, not only in prose.

- Modify `scripts/probe_visual_yearly_report_artifact.py`
  - Validate final visible artifact text and duplicate chart rendering.
  - Fail when metadata says accepted but final visible text fails.

- Modify `frontend/src/features/ai-insights/yearly-artifact/VisualYearlyReport.tsx`
  - Pre-filter duplicate chart refs across sections.

- Modify `frontend/src/features/ai-insights/yearly-artifact/YearlySection.tsx`
  - Accept already-filtered section refs without changing artifact data shape.

- Modify `frontend/src/features/ai-insights/yearly-artifact/YearlyChartBlock.tsx`
  - Stop rendering `spec.insight` as user copy.
  - Keep chart observations from deterministic `chart_data` visible.

- Modify `frontend/src/features/ai-insights/AiReportsPanel.tsx`
  - Clear stale report task state on report-type switch.
  - Add accessible selected state for report-type buttons.

- Tests:
  - Create `backend/tests/unit/test_final_artifact_quality.py`.
  - Extend `backend/tests/unit/test_visual_yearly_artifact_service.py`.
  - Extend `backend/tests/unit/test_visual_yearly_critic.py`.
  - Extend `frontend/src/tests/visual-yearly-report.test.tsx`.
  - Extend `frontend/src/tests/ai-insights-task-flow.test.tsx`.

---

### Task 1: Backend Final Visible Artifact Quality Gate

涉及文件：`backend/domains/ai_reports/final_artifact_quality.py`、`backend/tests/unit/test_final_artifact_quality.py`。

- Implement the final quality module

---

### Task 2: Sanitize Backend Artifact Assembly Before Critic And Cache

涉及文件：`backend/domains/ai_reports/visual_yearly_artifact_service.py`、`backend/tests/unit/test_visual_yearly_artifact_service.py`。

- Add failing service tests for purpose leaks and duplicate charts
- Import final quality gate
- `purpose` 属于内部写作提纲，不能作为用户可见的 deck；应使用面向读者的章节简介。
- 组装 artifact 时去重章节正文和 chart refs，再执行 critic 与缓存写入。
- 将最终可见质量检查合入 critic issues／metadata；若最终门禁失败，不能继续标记 accepted、critic 或 taste 通过，fallback level 也须反映最终结果。
- `_list` 只处理字典列表；字符串形式的 `repair_instructions` 使用 `_str_list` 读取，避免过滤掉修复要求。

---

### Task 3: Expand Visual Critic To Judge Decks And Final Text

涉及文件：`backend/domains/ai_reports/visual_yearly_critic.py`、`backend/tests/unit/test_visual_yearly_critic.py`。

- Add failing critic test for deck leakage
- critic 同时检查 heading、deck、prose 等最终可见内容，不能只检查正文。
- 内部提纲泄漏模式包括以“展示／解释／说明／分析／揭示”引导的证据任务措辞，以及 `chart_refs`、`evidence_refs`、`interpretation_guidance` 和 `safe_speculation_rules`；critic 扩展词还包括“证据强度”“不要写成”“展示Olivia”“展示播放”“解释播放领先”“揭示偏好深度”“说明偏好会在特定月份”。

---

### Task 4: Frontend Renderer Dedup And Chart Copy Cleanup

涉及文件：`frontend/src/features/ai-insights/yearly-artifact/VisualYearlyReport.tsx`、`frontend/src/features/ai-insights/yearly-artifact/YearlyChartBlock.tsx`、`frontend/src/tests/visual-yearly-report.test.tsx`。

- Add failing frontend tests

- Deduplicate chart refs in VisualYearlyReport
- 不把 chart spec 内部 insight 渲染为用户文案；缺失图表数据时保留 fallback，图表说明继续使用 `chart_data` 的确定性 observations。

---

### Task 5: Report Type Switch State Guard

涉及文件：`frontend/src/features/ai-insights/AiReportsPanel.tsx`、`frontend/src/tests/ai-insights-task-flow.test.tsx`。

- Add failing UI flow test for yearly switch payload and stale content
- Clear stale task state on report type switch

---

- 历史验收要求：the new test fails if weekly content remains visible or yearly payload is not sent.

### Task 6: Probe The Same Final Visible Text The User Sees

涉及文件：`scripts/probe_visual_yearly_report_artifact.py`、`backend/tests/unit/test_visual_yearly_critic.py`。

- Add failing probe test for deck leak and duplicate chart refs
- Add final-visible checks to probe script

---

### Task 7: Verification Matrix And Browser Acceptance

- No code changes unless failures point to a previous task.

With backend running on port 8000:

- Exit code `0`.
- JSON `ok` is `true`.
- 2025 and 2026 summaries contain `metadata.final_artifact_quality_passed: true`.
- No issue contains `internal brief leakage`.
- No issue contains `duplicate chart refs`.
- Browser acceptance for actual user flow

Use the in-app browser or Playwright to execute:

1. Open `http://localhost:5173/ai-insights`.
2. Click `报告`.
3. Click `年度叙事`.
4. Click `2026`.
5. Click `刷新报告`.
6. Wait until the task progress disappears and the report card shows `刷新报告`.
7. Confirm the card title is `年度叙事 · 2026`.
8. Confirm badges do not show `口味评分 35` unless `final_artifact_quality_passed` is true.
9. Confirm visible text does not contain:
   - `展示Olivia`
   - `解释播放领先`
   - `揭示偏好深度`
   - `interpretation_guidance`
   - `safe_speculation_rules`
10. Confirm each visible chart title appears at most once.
11. Confirm `Taylor Swift 以 1115 次播放位列艺人榜第一` or equivalent stable-return paragraph appears at most once as a full paragraph.

---

- 历史验收要求：pass all checks, no console errors, no fallback composer badge, and no weekly report content after switching to yearly.

## Self-Review

**Spec coverage:**

- Final visible text gate: Task 1 and Task 2.
- Internal brief leakage: Task 1, Task 2, Task 3, Task 6.
- Duplicate sections and duplicate chart refs: Task 1, Task 2, Task 4, Task 6.
- Frontend chart insight leakage: Task 4.
- Report type switch stale state: Task 5.
- Probe catches what browser catches: Task 6 and Task 7.

**Placeholder scan:** This plan contains no unresolved placeholder markers, no open-ended validation instructions, and no cross-task shorthand implementation steps.

**Type consistency:** The backend quality helper returns a dict with `ok`, `issues`, and `visible_text_length`; service metadata stores `final_artifact_quality_passed` and `final_artifact_quality`; probe reads the same keys.

**Commit guidance:** Do not commit automatically while executing this plan unless the user explicitly asks. After all verification passes, summarize modified files and test evidence first.
