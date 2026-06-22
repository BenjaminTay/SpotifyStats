# Settings Page UX Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Settings page easier to understand, more visually coherent, and safer to operate by separating onboarding, routine settings, advanced parameters, rebuild actions, and LLM profile management.

**Architecture:** Keep the existing route and feature-component structure. Add small settings-specific primitives instead of a broad redesign: a status overview, one rebuild banner, richer section summaries, and a reliable active LLM profile contract from the backend. Preserve the current editorial + liquid-glass visual system from `frontend/UI_STYLE_GUIDE.md`.

**Tech Stack:** FastAPI + Pydantic response models, React 19 + TypeScript + Vite, TanStack Query, Tailwind CSS v4, shadcn/ui primitives, Vitest + Testing Library, existing frontend smoke scripts.

---

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
  - Cover overview, single rebuild CTA, and advanced-section behavior.
- Modify `frontend/src/tests/settings-llm-section.test.tsx`
  - Cover active profile display and one translation switch.
- Optional update `frontend/UI_STYLE_GUIDE.md`
  - Add Settings-specific layout rules after implementation if the pattern becomes canonical.

---

### Task 1: Add Backend Active LLM Profile Contract

**Files:**
- Modify: `backend/models/common.py`
- Modify: `backend/api/settings.py`
- Test: `backend/tests/contract/test_settings_api_mutations.py`

- [ ] **Step 1: Write the failing contract assertions**

Add these assertions after applying a profile in `test_llm_profile_crud_apply_and_secret_redaction`:

```python
settings = client.get("/api/settings").json()
assert settings["llm_provider"] == "openai"
assert settings["llm_model"] == "gpt-contract-updated"
assert settings["has_llm_key"] is True
assert settings["llm_active_profile_id"] == profile_id
assert settings["llm_active_profile_name"] == "Contract Profile"
assert "llm_api_key" not in settings
```

- [ ] **Step 2: Run the focused backend test and confirm it fails**

Run:

```bash
.venv/bin/pytest backend/tests/contract/test_settings_api_mutations.py::test_llm_profile_crud_apply_and_secret_redaction -q
```

Expected: `KeyError: 'llm_active_profile_id'` or equivalent missing-field failure.

- [ ] **Step 3: Extend the settings response model**

In `backend/models/common.py`, add these fields to `SettingsResponse`:

```python
llm_active_profile_id: int | None = None
llm_active_profile_name: str | None = None
```

- [ ] **Step 4: Implement profile matching in the settings response**

In `backend/api/settings.py`, add a helper near `_build_settings_response`:

```python
def _find_active_llm_profile(conn: Connection, current: dict) -> dict[str, int | str | None]:
    row = conn.execute(
        """
        SELECT id, profile_name
        FROM llm_profiles
        WHERE llm_provider = ?
          AND llm_model = ?
          AND COALESCE(llm_api_key, '') = ?
          AND COALESCE(llm_base_url, '') = ?
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """,
        (
            current.get("llm_provider", ""),
            current.get("llm_model", ""),
            current.get("llm_api_key", ""),
            current.get("llm_base_url", ""),
        ),
    ).fetchone()
    if not row:
        return {"llm_active_profile_id": None, "llm_active_profile_name": None}
    return {"llm_active_profile_id": row["id"], "llm_active_profile_name": row["profile_name"]}
```

Then merge it into `_build_settings_response` before redacting secrets:

```python
resp.update(_find_active_llm_profile(conn, _current))
```

- [ ] **Step 5: Verify backend contract**

Run:

```bash
.venv/bin/pytest backend/tests/contract/test_settings_api_mutations.py -q
```

Expected: all tests in the file pass.

---

### Task 2: Add Top Settings Overview

**Files:**
- Create: `frontend/src/features/settings/components/SettingsOverview.tsx`
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Test: `frontend/src/tests/settings-sections.test.tsx`

- [ ] **Step 1: Write a failing overview test**

Append a test to `frontend/src/tests/settings-sections.test.tsx`:

```tsx
import { SettingsOverview } from '@/features/settings/components/SettingsOverview'

it('summarizes setup status at the top of Settings', () => {
  render(
    <SettingsOverview
      dbRecordCount={1200}
      accountImported
      spotifyConnected
      hasLlmKey
      llmProvider="deepseek"
      llmModel="deepseek-chat"
      rebuildPending={false}
    />,
  )

  expect(screen.getByText('数据就绪')).toBeInTheDocument()
  expect(screen.getByText('Spotify 已连接')).toBeInTheDocument()
  expect(screen.getByText('统计已生效')).toBeInTheDocument()
  expect(screen.getByText('DeepSeek')).toBeInTheDocument()
})
```

- [ ] **Step 2: Run the focused frontend test and confirm it fails**

Run:

```bash
cd frontend && npm test -- settings-sections.test.tsx
```

Expected: import or component-not-found failure.

- [ ] **Step 3: Create the overview component**

Create `frontend/src/features/settings/components/SettingsOverview.tsx`:

```tsx
import { CheckCircle2, Database, Link, RefreshCw, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'

function StatusCell({
  icon,
  label,
  value,
  tone = 'neutral',
}: {
  icon: React.ReactNode
  label: string
  value: string
  tone?: 'good' | 'warn' | 'neutral'
}) {
  return (
    <div className="rounded-xl border border-border bg-card/70 p-4">
      <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[1.2px] text-muted-foreground">
        {icon}
        {label}
      </div>
      <div
        className={cn(
          'mt-2 font-sans text-[14px] font-semibold',
          tone === 'good' && 'text-green-700 dark:text-green-400',
          tone === 'warn' && 'text-amber-700 dark:text-amber-300',
          tone === 'neutral' && 'text-foreground',
        )}
      >
        {value}
      </div>
    </div>
  )
}

export function SettingsOverview({
  dbRecordCount,
  accountImported,
  spotifyConnected,
  hasLlmKey,
  llmProvider,
  llmModel,
  rebuildPending,
}: {
  dbRecordCount: number
  accountImported: boolean
  spotifyConnected: boolean
  hasLlmKey: boolean
  llmProvider: string
  llmModel: string
  rebuildPending: boolean
}) {
  const dataReady = dbRecordCount > 0 && accountImported
  const providerLabel = llmProvider === 'deepseek'
    ? 'DeepSeek'
    : llmProvider === 'openai'
      ? 'OpenAI'
      : llmProvider === 'anthropic'
        ? 'Anthropic'
        : llmProvider || '未配置'

  return (
    <section className="grid grid-cols-1 gap-3 md:grid-cols-4">
      <StatusCell
        icon={dataReady ? <CheckCircle2 className="size-3.5" /> : <Database className="size-3.5" />}
        label="数据状态"
        value={dataReady ? '数据就绪' : '需要导入'}
        tone={dataReady ? 'good' : 'warn'}
      />
      <StatusCell
        icon={<Link className="size-3.5" />}
        label="Spotify"
        value={spotifyConnected ? 'Spotify 已连接' : '未连接'}
        tone={spotifyConnected ? 'good' : 'neutral'}
      />
      <StatusCell
        icon={<RefreshCw className="size-3.5" />}
        label="统计口径"
        value={rebuildPending ? '有改动待生效' : '统计已生效'}
        tone={rebuildPending ? 'warn' : 'good'}
      />
      <StatusCell
        icon={<Sparkles className="size-3.5" />}
        label="当前模型"
        value={hasLlmKey ? `${providerLabel} · ${llmModel || '默认模型'}` : '缺少 API Key'}
        tone={hasLlmKey ? 'good' : 'warn'}
      />
    </section>
  )
}
```

- [ ] **Step 4: Render overview below the page hero**

In `frontend/src/pages/SettingsPage.tsx`, import and render:

```tsx
import { SettingsOverview } from '@/features/settings/components/SettingsOverview'
```

Add:

```tsx
const [rebuildPending, setRebuildPending] = useState(false)
```

Render after the hero section:

```tsx
<SettingsOverview
  dbRecordCount={settings.db_record_count}
  accountImported={settings.account_data_imported}
  spotifyConnected={settings.spotify_connected}
  hasLlmKey={settings.has_llm_key}
  llmProvider={settings.llm_provider}
  llmModel={settings.llm_model}
  rebuildPending={rebuildPending}
/>
```

- [ ] **Step 5: Verify overview**

Run:

```bash
cd frontend && npm test -- settings-sections.test.tsx
cd frontend && npm run build
```

Expected: tests and build pass.

---

### Task 3: Centralize Rebuild Action

**Files:**
- Create: `frontend/src/features/settings/components/RebuildNotice.tsx`
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/features/settings/components/DataFilteringSection.tsx`
- Modify: `frontend/src/features/settings/components/BillboardParamsSection.tsx`
- Test: `frontend/src/tests/settings-sections.test.tsx`

- [ ] **Step 1: Add a failing test for a single rebuild CTA**

Add a test that renders `RebuildNotice`:

```tsx
import { RebuildNotice } from '@/features/settings/components/RebuildNotice'

it('shows one global rebuild action when statistics settings are pending', () => {
  render(
    <RebuildNotice
      pending
      loading={false}
      message=""
      onRebuild={vi.fn()}
    />,
  )

  expect(screen.getByText('统计口径有改动待生效')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '应用改动并重建统计' })).toBeInTheDocument()
})
```

- [ ] **Step 2: Create `RebuildNotice`**

```tsx
import { AlertCircle, CheckCircle2, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function RebuildNotice({
  pending,
  loading,
  message,
  onRebuild,
}: {
  pending: boolean
  loading: boolean
  message: string
  onRebuild: () => void
}) {
  if (!pending && !message) return null

  return (
    <div className={cn(
      'rounded-xl border px-4 py-3',
      pending ? 'border-amber-500/30 bg-amber-500/5' : 'border-green-500/30 bg-green-500/5',
    )}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-2.5">
          {pending ? (
            <AlertCircle className="mt-0.5 size-4 shrink-0 text-amber-600 dark:text-amber-300" />
          ) : (
            <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-green-600 dark:text-green-400" />
          )}
          <div>
            <div className="text-[13px] font-semibold text-foreground">
              {pending ? '统计口径有改动待生效' : message}
            </div>
            {pending && (
              <p className="mt-0.5 text-[12px] leading-relaxed text-muted-foreground">
                播放过滤或榜单参数已改变。应用后，所有榜单和统计会按新规则重新计算。
              </p>
            )}
          </div>
        </div>
        {pending && (
          <Button size="sm" onClick={onRebuild} disabled={loading} className="gap-1.5">
            <RefreshCw className={cn('size-3.5', loading && 'animate-spin')} />
            {loading ? '重建中...' : '应用改动并重建统计'}
          </Button>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Track pending rebuild at page level**

In `SettingsPage.tsx`, add:

```tsx
const [rebuildPending, setRebuildPending] = useState(false)

const handleSettingsRequireRebuild = () => {
  setRebuildPending(true)
}
```

Update `handleRebuild`:

```tsx
const handleRebuild = () => {
  setRebuildLoading(true)
  setRebuildMsg('')
  rebuildAgg().then((res) => {
    setRebuildMsg(res.status === 'done' ? '聚合表重建完成' : '重建完成')
    setRebuildPending(false)
    setRebuildLoading(false)
  }).catch((e) => {
    setRebuildMsg(e instanceof Error ? e.message : '重建失败，请重试')
    setRebuildLoading(false)
  })
}
```

- [ ] **Step 4: Render global notice below the overview**

```tsx
<RebuildNotice
  pending={rebuildPending}
  loading={rebuildLoading}
  message={rebuildMsg}
  onRebuild={handleRebuild}
/>
```

- [ ] **Step 5: Remove duplicate rebuild buttons from child sections**

In `DataFilteringSection.tsx` and `BillboardParamsSection.tsx`, replace direct rebuild buttons with a prop:

```tsx
onRequiresRebuild: () => void
```

Call it after settings changes that affect statistics:

```tsx
const updateAndRequireRebuild = (p: SettingsUpdatePayload) => {
  update(p)
  onRequiresRebuild()
}
```

Use `updateAndRequireRebuild` for `min_ms`, `music_only`, `merge_enabled`, `bb_top_n`, `bb_album_top_n`, `bb_artist_top_n`, `bb_week_start_dow`, and `bb_week_start_hour`.

- [ ] **Step 6: Verify single rebuild CTA**

Run:

```bash
cd frontend && npm test -- settings-sections.test.tsx
cd frontend && npm run build
```

Expected: no test should find more than one rebuild CTA in rendered section tests.

---

### Task 4: Progressive Disclosure and Naming Cleanup

**Files:**
- Modify: `frontend/src/features/settings/components/SettingsHelpers.tsx`
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/features/settings/components/DataImportSection.tsx`
- Modify: `frontend/src/features/settings/components/DataFilteringSection.tsx`
- Modify: `frontend/src/features/settings/components/BillboardParamsSection.tsx`
- Modify: `frontend/src/features/settings/components/VersionMergeSection.tsx`
- Modify: `frontend/src/features/settings/components/LLMTranslationSection.tsx`
- Test: `frontend/src/tests/settings-sections.test.tsx`

- [ ] **Step 1: Define Chinese section titles**

Use these titles:

```text
01 · Spotify 连接
02 · 数据导入
03 · 数据与显示
04 · 榜单参数
05 · 版本合并
06 · LLM 配置
```

- [ ] **Step 2: Add summary support for every collapsible section**

Keep `CollapsibleSection` API but ensure collapsed sections always show useful summaries:

```tsx
<CollapsibleSection
  num={4}
  title="榜单参数"
  desc={`${bbName} 周榜的计算边界和榜单容量。`}
  defaultOpen={false}
  summary={`单曲 ${settings.bb_top_n} · 专辑 ${settings.bb_album_top_n} · 艺人 ${settings.bb_artist_top_n}`}
>
```

- [ ] **Step 3: Default advanced sections closed**

Set:

```tsx
<BillboardParamsSection defaultOpen={false} />
<VersionMergeSection defaultOpen={false} />
```

If passing `defaultOpen` would create too much prop churn, set it directly inside those section components.

- [ ] **Step 4: Keep onboarding sections open when incomplete**

`DataImportSection` already does this:

```tsx
defaultOpen={!imported}
```

Use the same principle for Spotify:

```tsx
defaultOpen={!connected}
summary={connected ? '已连接，可同步收藏时间' : '未连接'}
```

- [ ] **Step 5: Verify title consistency**

Add test assertions:

```tsx
expect(screen.queryByText('Data Import')).not.toBeInTheDocument()
expect(screen.queryByText('Data & Display')).not.toBeInTheDocument()
expect(screen.queryByText('Billboard Parameters')).not.toBeInTheDocument()
expect(screen.getByText(/数据导入/)).toBeInTheDocument()
expect(screen.getByText(/数据与显示/)).toBeInTheDocument()
expect(screen.getByText(/榜单参数/)).toBeInTheDocument()
```

- [ ] **Step 6: Verify**

Run:

```bash
cd frontend && npm test -- settings-sections.test.tsx
cd frontend && npm run build
```

Expected: title tests pass and build passes.

---

### Task 5: Improve LLM Profile Clarity

**Files:**
- Modify: `frontend/src/types/settings.ts`
- Modify: `frontend/src/features/settings/components/LLMTranslationSection.tsx`
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/hooks/useSettings.ts`
- Test: `frontend/src/tests/settings-llm-section.test.tsx`

- [ ] **Step 1: Add active profile fields to frontend type**

In `SettingsData`:

```ts
llm_active_profile_id: number | null
llm_active_profile_name: string | null
```

- [ ] **Step 2: Extend LLM section props**

Add:

```ts
activeProfileId: number | null
activeProfileName: string | null
```

Pass from `SettingsPage`:

```tsx
activeProfileId={settings.llm_active_profile_id}
activeProfileName={settings.llm_active_profile_name}
```

- [ ] **Step 3: Select active profile from backend contract**

Replace local-only selected logic:

```tsx
const selected = activeProfileId === profile.id || selectedProfileId === profile.id
```

Show active source only when meaningful:

```tsx
{activeProfileName && (
  <div className="mt-3 text-[12px] text-muted-foreground">
    当前档案：<span className="text-foreground">{activeProfileName}</span>
  </div>
)}
```

- [ ] **Step 4: Improve empty state action**

Use one clear empty state:

```tsx
<div className="rounded-xl border border-dashed border-border bg-muted/20 p-5">
  <p className="text-[13px] text-muted-foreground">
    暂无已保存的配置档案。添加第一个配置后，可在 DeepSeek、OpenAI、Anthropic 或自定义接口之间切换。
  </p>
  <Button size="sm" onClick={openAddProfileModal} className="mt-3 gap-1.5">
    <Plus className="size-3.5" />
    添加第一个配置
  </Button>
</div>
```

- [ ] **Step 5: Keep one translation switch**

Add or keep this test:

```tsx
expect(screen.getAllByRole('switch')).toHaveLength(1)
expect(screen.getByRole('switch', { name: '启用 Wikipedia LLM 翻译' })).toBeInTheDocument()
```

- [ ] **Step 6: Verify**

Run:

```bash
cd frontend && npm test -- settings-llm-section.test.tsx
cd frontend && npm run build
```

Expected: active profile and single-switch tests pass.

---

### Task 6: Visual Polish and Responsive QA

**Files:**
- Modify: `frontend/src/features/settings/components/SettingsOverview.tsx`
- Modify: `frontend/src/features/settings/components/RebuildNotice.tsx`
- Modify: `frontend/src/features/settings/components/SettingsHelpers.tsx`
- Modify: `frontend/src/features/settings/components/LLMTranslationSection.tsx`
- Test: existing frontend smoke scripts

- [ ] **Step 1: Align cards with UI guide**

Use the existing visual grammar:

```tsx
className="rounded-xl border border-border bg-card/70 p-4"
```

Avoid nested heavy cards inside cards; use subtle `bg-muted/20` panels only for related controls.

- [ ] **Step 2: Reduce noisy badges**

Keep badges only when they help user decisions:

```text
Keep: Key 已配置, 缺少 API Key, 当前, 已导入, 未导入
Remove or soften: raw internal keys like bb_top_n, llm_enabled, max_merge_gap_minutes from primary labels
```

Technical keys may remain in tooltips or smaller secondary text if needed.

- [ ] **Step 3: Add mobile constraints**

Use these patterns where necessary:

```tsx
className="min-w-0"
className="truncate"
className="grid grid-cols-1 gap-4 md:grid-cols-2"
className="w-full max-w-[200px]"
```

- [ ] **Step 4: Run route smoke**

With backend `8000` and frontend `5173` running:

```bash
node scripts/frontend_route_smoke.mjs --base-url http://localhost:5173 --viewport both --max-scroll-overflow 0 --fail-on-console-warning
```

Expected: `/settings` has no console warnings/errors and no horizontal overflow.

- [ ] **Step 5: Run interaction smoke**

```bash
node scripts/frontend_interaction_smoke.mjs --base-url http://localhost:5173
```

Expected: settings controls and data import flow pass.

- [ ] **Step 6: Run control inventory**

```bash
node scripts/frontend_control_inventory_smoke.mjs --base-url http://localhost:5173 --viewport both --include-detail-routes
```

Expected: no unnamed visible controls, no nested interactive controls, no duplicate ids.

---

### Task 7: Final Validation and Documentation

**Files:**
- Optional modify: `frontend/UI_STYLE_GUIDE.md`
- Verify: no required code file changes

- [ ] **Step 1: Run focused frontend tests**

```bash
cd frontend && npm test -- settings-sections.test.tsx settings-llm-section.test.tsx
```

Expected: all focused Settings tests pass.

- [ ] **Step 2: Run frontend build**

```bash
cd frontend && npm run build
```

Expected: TypeScript and Vite build pass.

- [ ] **Step 3: Run backend settings contract tests**

```bash
.venv/bin/pytest backend/tests/contract/test_settings_api_mutations.py -q
```

Expected: all settings mutation/profile contract tests pass.

- [ ] **Step 4: Run full frontend tests when time allows**

```bash
cd frontend && npm test
```

Expected: existing architecture guardrails may fail only if unrelated pre-existing line-count issues remain; any new Settings tests must pass.

- [ ] **Step 5: Update style guide only if the new pattern is stable**

If Settings overview and global rebuild banner should become canonical, add a short section to `frontend/UI_STYLE_GUIDE.md`:

```markdown
### Settings Page Pattern

- Settings pages start with a compact status overview.
- Common/onboarding sections open by default when incomplete.
- Advanced computational sections collapse by default and provide summaries.
- Rebuild actions are centralized in one page-level notice.
- LLM provider identity uses local SVG logos with text fallback.
```

- [ ] **Step 6: Final UX acceptance checklist**

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

## Implementation Order

1. Backend active LLM profile contract.
2. Top Settings overview.
3. Global rebuild notice and duplicate rebuild removal.
4. Progressive disclosure and naming cleanup.
5. LLM active profile display.
6. Visual polish and responsive QA.
7. Final validation and style-guide note.

This order keeps runtime safety first, then makes the page easier to scan, then improves beauty and polish.

## Risk Notes

- Do not remove existing advanced settings; hide or summarize them.
- Do not infer active LLM profile purely in frontend state; use backend response.
- Do not add another card layer inside every panel; keep visual depth restrained.
- Do not run destructive settings or import operations in smoke tests.
- Do not commit automatically unless the user explicitly asks.

