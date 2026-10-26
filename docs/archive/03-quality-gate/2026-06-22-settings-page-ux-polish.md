# Settings Page UX Polish Implementation Plan

> 历史实施提纲：已省略大段实现／测试代码草稿、重复命令及红绿测试步骤，保留设计要求、分工、接口示例与原验收事实。正文中的任务和Expected属于当时计划；当前行为见[文档地图](../../README.md)。

**Goal:** Make the Settings page easier to understand, more visually coherent, and safer to operate by separating onboarding, routine settings, advanced parameters, rebuild actions, and LLM profile management.

**Architecture:** Keep the existing route and feature-component structure. Add small settings-specific primitives instead of a broad redesign: a status overview, one rebuild banner, richer section summaries, and a reliable active LLM profile contract from the backend. Preserve the current editorial + liquid-glass visual system from `frontend/UI_STYLE_GUIDE.md`.

**Tech Stack:** FastAPI + Pydantic response models, React 19 + TypeScript + Vite, TanStack Query, Tailwind CSS v4, shadcn/ui primitives, Vitest + Testing Library, existing frontend smoke scripts.

---

## Latest Review Baseline

**Overall judgment:** UX direction is correct, but release readiness is **Fail** until the frontend build blocker is fixed. The page is now more understandable than the previous version, especially because the status overview, global rebuild notice, and LLM current-model card give users clearer answers. However, the current patch cannot be accepted as complete because `npm run build` fails and the focused tests do not cover the broken interaction/type path.

**Verified improvements:**

- The top overview answers the basic readiness questions: data status, Spotify connection, statistics/rebuild state, and current model.
- The rebuild action has moved toward one global CTA instead of duplicated per-section buttons.
- The LLM section is clearer: current model, provider logo, profile list, one Wikipedia translation switch, and translation-cache action are separated.
- The add-profile modal is visually stable on desktop: centered, constrained, and no longer distorts the full page.
- Browser spot check found no page-render error, no desktop console warning/error, and no 390px horizontal overflow.

**Current blockers and UX risks:**

- `frontend/src/features/settings/components/DataFilteringSection.tsx` destructures removed props (`onRebuild`, `rebuildLoading`) while calling `onRequiresRebuild()` without destructuring it. `cd frontend && npm run build` fails.
- `frontend/src/tests/settings-llm-section.test.tsx` does not pass the newly required `activeProfileId` and `activeProfileName` props, so TypeScript fails even though the focused Vitest run passes.
- The current focused tests only verify static rendering. They do not click a filtering control and confirm the global rebuild notice appears.
- The LLM add-profile modal allows saving an empty API Key, but the copy does not clearly explain that such a profile cannot call the model.
- The visual direction is improved but still a little engineering-heavy: `Settings / Configuration`, `Data Import`, `profile`, `llm_enabled`, and raw setting keys reduce the polished editorial feel.
- The mobile layout has no horizontal overflow, but top navigation and theme controls still consume enough space that Settings content feels lower than ideal on 390px.

Browser evidence:

```text
Desktop /settings: no visible render error, no console error/warning.
Add LLM config modal: centered, constrained, no horizontal overflow.
390px /settings: bodyScrollWidth = 390, htmlScrollWidth = 390.
```

## Target UX

The finished Settings page should answer four user questions quickly:

1. **Is my app ready?** The top overview shows data import, Spotify connection, current model, and whether a rebuild is needed.
2. **Where do I change common settings?** Data import, display, and LLM current model are visible; dangerous or advanced parameters are collapsed by default.
3. **Did my change take effect?** Settings that apply instantly show a saved notice; settings requiring rebuild mark the page as pending and surface one global rebuild action.
4. **Which model/profile is active?** The LLM section shows the actual active profile when it can be matched, not a locally guessed selection.

## File Map

- Modify `frontend/src/pages/SettingsPage.tsx`
  - Owns page-level state for pending rebuild changes and status overview data.
  - Passes one rebuild handler to sections and renders the new overview/banner.
- Create `frontend/src/features/settings/components/SettingsOverview.tsx`
  - Four compact status cells: data, Spotify, statistics/rebuild, LLM.
- Create `frontend/src/features/settings/components/RebuildNotice.tsx`
  - Single global rebuild CTA shown when statistics-affecting settings changed.
- Modify `frontend/src/features/settings/components/SettingsHelpers.tsx`
  - Add richer collapsible summaries and optional `tone`.
- Modify `frontend/src/features/settings/components/DataFilteringSection.tsx`
  - Move advanced playback controls behind an inner advanced block.
  - Notify parent when changes require rebuild.
- Modify `frontend/src/features/settings/components/BillboardParamsSection.tsx`
  - Remove duplicate rebuild button and rely on the global rebuild notice.
  - Make the section advanced/collapsed by default.
- Modify `frontend/src/features/settings/components/VersionMergeSection.tsx`
  - Make the section advanced/collapsed by default.
  - Add a plain-language summary for L1/L2/L3.
- Modify `frontend/src/features/settings/components/LLMTranslationSection.tsx`
  - Use backend-provided active profile metadata.
  - Keep the current model card, profile list, translation/cache controls, and modal.
- Modify `frontend/src/types/settings.ts`
  - Add optional `llm_active_profile_id` and `llm_active_profile_name`.
- Modify `frontend/src/hooks/useSettings.ts`
  - Ensure apply/create/delete invalidates both settings and profile queries.
- Modify `backend/models/common.py`
  - Add optional active profile fields to `SettingsResponse`.
- Modify `backend/api/settings.py`
  - Match current LLM settings to a saved profile and include active profile metadata.
- Modify `backend/tests/contract/test_settings_api_mutations.py`
  - Cover active LLM profile fields after applying a profile.
- Modify `frontend/src/tests/settings-sections.test.tsx`
  - Cover overview, single rebuild CTA, advanced-section behavior, and clicking a statistics-affecting control.
- Modify `frontend/src/tests/settings-llm-section.test.tsx`
  - Cover active profile display, one translation switch, provider logo, and required active-profile props.
- Optional update `frontend/UI_STYLE_GUIDE.md`
  - Add Settings-specific layout rules after implementation if the pattern becomes canonical.

---

### Task 0: Stabilize Latest CC Patch Before More UX Polish

涉及文件：`frontend/src/features/settings/components/DataFilteringSection.tsx`、`frontend/src/tests/settings-sections.test.tsx`、`frontend/src/tests/settings-llm-section.test.tsx`。

- Optional modify: `frontend/src/features/settings/components/LLMTranslationSection.tsx`
- Fix `DataFilteringSection` props

Remove any remaining `onRebuild` and `rebuildLoading` references from this file. The child section should only mark pending rebuild; the page-level `RebuildNotice` owns the rebuild action.

- Update the LLM focused test props

Keep the existing assertions for provider logo and single switch, then add:

- Add an interaction regression test for pending rebuild

Extend `frontend/src/tests/settings-sections.test.tsx` to click a filtering toggle and assert the parent callback fires:

- Decide whether `activeProfileName` should render

If this line makes the current-model card too dense, remove the prop from `LLMTranslationSection` and from the caller. Do not leave an unused required prop because `noUnusedLocals` will fail the build.

```text
Settings focused tests pass.
TypeScript build passes.
Vite build may emit the existing chunk-size warning, but no error.
```

Do not continue to visual polish tasks until this task passes.

---

- 历史实施约束：If keeping `activeProfileName` as a prop, render it in the current-model card.

### Task 1: Add Backend Active LLM Profile Contract

涉及文件：`backend/models/common.py`、`backend/api/settings.py`、`backend/tests/contract/test_settings_api_mutations.py`。

历史验收预期： `KeyError: 'llm_active_profile_id'` or equivalent missing-field failure.

- Extend the settings response model
- Implement profile matching in the settings response

Then merge it into `_build_settings_response` before redacting secrets:

- Verify backend contract

---

### Task 2: Add Top Settings Overview

涉及文件：`frontend/src/features/settings/components/SettingsOverview.tsx`、`frontend/src/pages/SettingsPage.tsx`、`frontend/src/tests/settings-sections.test.tsx`。

历史验收预期： import or component-not-found failure.

- Create the overview component
- Render overview below the page hero

Render after the hero section:

- Verify overview

---

### Task 3: Centralize Rebuild Action

涉及文件：`frontend/src/features/settings/components/RebuildNotice.tsx`、`frontend/src/pages/SettingsPage.tsx`、`frontend/src/features/settings/components/DataFilteringSection.tsx`、`frontend/src/features/settings/components/BillboardParamsSection.tsx`、`frontend/src/tests/settings-sections.test.tsx`。

- Add a failing test for a single rebuild CTA
- Create `RebuildNotice`
- Track pending rebuild at page level
- Render global notice below the overview
- Remove duplicate rebuild buttons from child sections

Use `updateAndRequireRebuild` for `min_ms`, `music_only`, `merge_enabled`, `bb_top_n`, `bb_album_top_n`, `bb_artist_top_n`, `bb_week_start_dow`, and `bb_week_start_hour`.

- Verify single rebuild CTA

历史验收预期： no test should find more than one rebuild CTA in rendered section tests.

---

### Task 4: Progressive Disclosure and Naming Cleanup

涉及文件：`frontend/src/features/settings/components/SettingsHelpers.tsx`、`frontend/src/pages/SettingsPage.tsx`、`frontend/src/features/settings/components/DataImportSection.tsx`、`frontend/src/features/settings/components/DataFilteringSection.tsx`、`frontend/src/features/settings/components/BillboardParamsSection.tsx`、`frontend/src/features/settings/components/VersionMergeSection.tsx`、`frontend/src/features/settings/components/LLMTranslationSection.tsx`、`frontend/src/tests/settings-sections.test.tsx`。

- Define Chinese section titles

Use these titles:

```text
01 · Spotify 连接
02 · 数据导入
03 · 数据与显示
04 · 榜单参数
05 · 版本合并
06 · LLM 配置
```

- Add summary support for every collapsible section

Keep `CollapsibleSection` API but ensure collapsed sections always show useful summaries:

- Default advanced sections closed

If passing `defaultOpen` would create too much prop churn, set it directly inside those section components.

- Keep onboarding sections open when incomplete

Use the same principle for Spotify:

- Verify title consistency

Add test assertions:

- Verify

---

### Task 5: Improve LLM Profile Clarity

涉及文件：`frontend/src/types/settings.ts`、`frontend/src/features/settings/components/LLMTranslationSection.tsx`、`frontend/src/pages/SettingsPage.tsx`、`frontend/src/hooks/useSettings.ts`、`frontend/src/tests/settings-llm-section.test.tsx`。

- Add active profile fields to frontend type
- Extend LLM section props

Pass from `SettingsPage`:

- Select active profile from backend contract

Show active source only when meaningful:

- Improve empty state action

Use one clear empty state:

- Keep one translation switch

Add or keep this test:

- Verify

---

### Task 6: Visual Polish and Responsive QA

涉及文件：`frontend/src/features/settings/components/SettingsOverview.tsx`、`frontend/src/features/settings/components/RebuildNotice.tsx`、`frontend/src/features/settings/components/SettingsHelpers.tsx`、`frontend/src/features/settings/components/LLMTranslationSection.tsx`。

- Align cards with UI guide

Avoid nested heavy cards inside cards; use subtle `bg-muted/20` panels only for related controls.

- Reduce noisy badges

Keep badges only when they help user decisions:

```text
Keep: Key 已配置, 缺少 API Key, 当前, 已导入, 未导入
Remove or soften: raw internal keys like bb_top_n, llm_enabled, max_merge_gap_minutes from primary labels
```

Technical keys may remain in tooltips or smaller secondary text if needed.

- Clean up mixed-language user-facing copy

Use Chinese-first section names and action labels. Keep product/provider names in English only when they are proper names.

Replace:

```text
Settings / Configuration
Data Import
profile
llm_enabled
```

```text
设置
数据导入
配置档案
Wikipedia 翻译
```

The top hero can keep a subtle English kicker only if it does not compete with the Chinese page title. Preferred copy:

- Make the LLM modal more intuitive

If empty-key profiles are intentionally supported for local gateway workflows, keep Save enabled but add an inline warning before the buttons:

- Add mobile constraints

Use these patterns where necessary:

- Check mobile first viewport

At 390px width, the Settings page should show at least one Settings-specific element without feeling buried under navigation. If the masthead remains visually heavy, reduce the page hero top padding for Settings only.

Do not hide navigation links unless the shared `Masthead` already has an established mobile pattern; this plan should not turn into a global navigation redesign.

历史验收预期： `/settings` has no console warnings/errors and no horizontal overflow.

历史验收预期： no unnamed visible controls, no nested interactive controls, no duplicate ids.

---

### Task 7: Final Validation and Documentation

- Optional modify: `frontend/UI_STYLE_GUIDE.md`
- Verify: no required code file changes

- Update style guide only if the new pattern is stable

If Settings overview and global rebuild banner should become canonical, add a short section to `frontend/UI_STYLE_GUIDE.md`:

```markdown
### Settings Page Pattern

- Settings pages start with a compact status overview.
- Common/onboarding sections open by default when incomplete.
- Advanced computational sections collapse by default and provide summaries.
- Rebuild actions are centralized in one page-level notice.
- LLM provider identity uses local SVG logos with text fallback.
```

- Final UX acceptance checklist

Manual check at `http://localhost:5173/settings`:

```text
[ ] First viewport shows hero, status overview, and at least one actionable next step.
[ ] Only one rebuild action is visible when pending.
[ ] Data Import collapses when complete and shows useful summary.
[ ] Billboard Parameters and Version Merge are collapsed or clearly advanced.
[ ] LLM current model shows provider logo, provider, model, key status, and active profile when known.
[ ] Only one Wikipedia LLM translation switch exists.
[ ] Add config modal is centered on desktop and 390px mobile.
[ ] No horizontal overflow at 390px.
[ ] No console error/warning.
```

---

- 历史验收要求：existing architecture guardrails may fail only if unrelated pre-existing line-count issues remain; any new Settings tests must pass.

## Implementation Order

0. Stabilize the latest CC patch: fix the frontend build blocker, update required props in tests, and add one interaction regression for rebuild pending state.
1. Backend active LLM profile contract.
2. Top Settings overview.
3. Global rebuild notice and duplicate rebuild removal.
4. Progressive disclosure and naming cleanup.
5. LLM active profile display.
6. Visual polish and responsive QA.
7. Final validation and style-guide note.

This order keeps release safety first. Do not spend time polishing the UI while `npm run build` is red; once the build is green, continue with clarity, then beauty and responsive QA.

## Risk Notes

- Do not remove existing advanced settings; hide or summarize them.
- Do not infer active LLM profile purely in frontend state; use backend response.
- Do not add another card layer inside every panel; keep visual depth restrained.
- Do not run destructive settings or import operations in smoke tests.
- Do not commit automatically unless the user explicitly asks.
- Do not treat focused Vitest success as sufficient when TypeScript build fails.
- Do not leave required props unused; either render them or remove them from the component contract.
