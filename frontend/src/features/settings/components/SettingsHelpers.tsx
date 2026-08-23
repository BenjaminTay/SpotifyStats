import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { AlertCircle, CheckCircle2, ChevronDown, Upload, RefreshCw } from 'lucide-react'
import type { ImportJob, TrackComparison } from '@/types/settings'
import type { ImportPreflightResponse, ImportRequestedMode, StreamingImportOptions } from '@/types/data-import'

// ── Toggle ──────────────────────────────────────────────────

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors duration-200',
        checked ? 'bg-accent-foreground' : 'bg-muted',
      )}
    >
      <span
        className={cn(
          'pointer-events-none block h-4 w-4 rounded-full bg-white shadow-sm transition-transform duration-200',
          checked ? 'translate-x-5' : 'translate-x-0.5',
        )}
      />
      <span className="sr-only">{label}</span>
    </button>
  )
}

// ── Section Header ──────────────────────────────────────────

export function SectionHeader({ num, title, desc }: { num: number; title: string; desc: string }) {
  return (
    <div className="mb-6">
      <div className="mb-1 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
        {String(num).padStart(2, '0')} · {title}
      </div>
      <p className="font-sans text-[14px] leading-relaxed text-muted-foreground">{desc}</p>
    </div>
  )
}

// ── Collapsible Section ────────────────────────────────────

export function CollapsibleSection({
  num,
  title,
  desc,
  defaultOpen = true,
  children,
  summary,
  tone,
}: {
  num: number
  title: string
  desc: string
  defaultOpen?: boolean
  children: React.ReactNode
  summary?: React.ReactNode
  tone?: 'default' | 'advanced'
}) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="group mb-6 w-full text-left focus-visible:outline-none"
      >
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <div className="mb-1 flex items-center gap-2 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
              <span>{String(num).padStart(2, '0')} · {title}</span>
              {tone === 'advanced' && (
                <span className="rounded-full bg-muted px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-muted-foreground">
                  高级
                </span>
              )}
            </div>
            {open && (
              <p className="font-sans text-[14px] leading-relaxed text-muted-foreground">{desc}</p>
            )}
            {!open && summary && (
              <p className="font-sans text-[13px] text-muted-foreground">{summary}</p>
            )}
          </div>
          <ChevronDown
            className={cn(
              'size-4 shrink-0 text-muted-foreground transition-transform duration-200',
              open && 'rotate-180',
            )}
          />
        </div>
      </button>
      {open && <div>{children}</div>}
    </div>
  )
}

// ── FieldLabel ──────────────────────────────────────────────

export function FieldLabel({ label, badge }: { label: string; badge?: string | number }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="font-sans text-[13.5px] font-medium text-foreground">{label}</span>
      {badge !== undefined && (
        <span className="font-mono text-[12px] text-accent-foreground">{badge}</span>
      )}
    </div>
  )
}

// ── Inline Notice ───────────────────────────────────────────

export function InlineNotice({ show, children }: { show: boolean; children: React.ReactNode }) {
  return (
    <div
      className={cn(
        'overflow-hidden transition-all duration-300',
        show ? 'mb-4 max-h-10 opacity-100' : 'mb-0 max-h-0 opacity-0',
      )}
    >
      <div className="flex items-center gap-2 rounded-lg bg-accent-foreground/10 px-3 py-2 text-[13px] text-accent-foreground">
        <CheckCircle2 className="size-3.5 shrink-0" />
        {children}
      </div>
    </div>
  )
}

// ── ImportProgressCard ──────────────────────────────────────

function resultString(result: Record<string, unknown> | null, key: string) {
  const value = result?.[key]
  return typeof value === 'string' ? value : null
}

function resultNumber(result: Record<string, unknown> | null, key: string) {
  const value = result?.[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

function nestedResultStatus(result: Record<string, unknown> | null, key: string) {
  const value = result?.[key]
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const status = (value as Record<string, unknown>).status
  return typeof status === 'string' ? status : null
}

function maintenanceLabel(job: ImportJob | null) {
  const explicitNoop = job?.result?.noop
  const executedStrategy = resultString(job?.result ?? null, 'executed_strategy')
  const hasCanonicalOutcome = typeof explicitNoop === 'boolean' || executedStrategy !== null
  const isNoop = explicitNoop === true
    || executedStrategy === 'noop'
    || (!hasCanonicalOutcome && (
      resultString(job?.result ?? null, 'estimated_strategy') === 'noop'
      || resultString(job?.result ?? null, 'detected_relation') === 'identical'
    ))
  if (isNoop) return '数据未变化，已跳过导入'
  const status = resultString(job?.result ?? null, 'maintenance_status')
  const searchSnapshotStatus = resultString(job?.result ?? null, 'music_search_snapshot_status')
  const health = job?.result?.post_import_health
  const healthStatus = health && typeof health === 'object' && !Array.isArray(health)
    ? (health as Record<string, unknown>).status
    : null
  if (healthStatus === 'partial' || healthStatus === 'stale') return '导入完成，数据可用但有健康提醒'
  if (status === 'partial') return '播放数据已导入，部分 Spotify 元数据待补全'
  if (searchSnapshotStatus === 'warming') return '导入完成，音乐查找统计正在后台更新'
  if (status === 'ok') return '导入完成，派生数据已更新'
  return '导入完成'
}

function maintenanceChips(job: ImportJob | null) {
  const result = job?.result ?? null
  return [
    ['tracks_metadata_updated', '曲目元数据', '+'],
    ['albums_metadata_updated', '专辑元数据', '+'],
    ['unresolved_recent_tracks', '未解析曲目', ''],
    ['unresolved_recent_albums', '未解析专辑', ''],
    ['duplicate_records_skipped', '跳过重复记录', ''],
  ]
    .map(([key, label, prefix]) => {
      const value = resultNumber(result, key)
      return value > 0 ? `${label} ${prefix}${value}` : null
    })
    .filter(Boolean)
}

export function ImportProgressCard({
  title,
  label,
  job,
  onStart,
  statusBadge,
  reimportLabel,
  helpLink,
  preflight,
  supportsImportMode = false,
  onRecheck,
}: {
  title: string
  label: string
  job: ImportJob | null
  onStart: (options?: StreamingImportOptions) => void
  statusBadge?: React.ReactNode
  reimportLabel?: string
  helpLink?: { text: string; href: string }
  preflight?: ImportPreflightResponse | null
  supportsImportMode?: boolean
  onRecheck?: () => void
}) {
  const [importMode, setImportMode] = useState<ImportRequestedMode>(preflight?.requested_mode ?? 'auto')
  const isRunning = job?.status === 'running'
  const isDone = job?.status === 'done'
  const isError = job?.status === 'error'
  const isBlocked = job?.status === 'blocked'
  const needsConfirmation = job?.status === 'needs_confirmation'
  const jobPreflight = job?.result?.preflight
  const jobPlan = jobPreflight && typeof jobPreflight === 'object' && !Array.isArray(jobPreflight)
    ? jobPreflight as Record<string, unknown>
    : null
  const jobPlanNeedsConfirmation = jobPlan?.requires_confirmation === true
  const jobConfirmationToken = resultString(jobPlan, 'confirmation_token')
  const stalePlanReason = resultString(job?.result ?? null, 'confirmation_reason') === 'stale_plan'
  const stalePlan = stalePlanReason
    && (!jobConfirmationToken || preflight?.confirmation_token !== jobConfirmationToken)
  const stalePlanResolved = stalePlanReason && !stalePlan
  const confirmationToken = needsConfirmation
    ? jobConfirmationToken
    : preflight?.confirmation_token ?? null
  const canUsePreflightPlan = !isRunning && !isDone && !isBlocked
  const planNeedsConfirmation = supportsImportMode
    && (needsConfirmation
      ? jobPlanNeedsConfirmation
      : canUsePreflightPlan && preflight?.requires_confirmation === true)
  const jobWarnings = jobPlan?.warnings
  const warningNeedsConfirmation = needsConfirmation
    && !stalePlan
    && !stalePlanResolved
    && (!jobPlanNeedsConfirmation || (Array.isArray(jobWarnings) && jobWarnings.length > 0))
  const planRelation = needsConfirmation
    ? resultString(jobPlan, 'detected_relation')
    : preflight?.detected_relation ?? null
  const canTryAppend = planNeedsConfirmation
    && ['ambiguous', 'truncated_or_regressive', 'reconciled_snapshot'].includes(planRelation ?? '')
  const explicitModeSelected = importMode === 'append' || importMode === 'replace'
  const replaceSelected = importMode === 'replace'
  const postHealth = job?.result?.post_import_health
  const postHealthStatus = postHealth && typeof postHealth === 'object' && !Array.isArray(postHealth)
    ? (postHealth as Record<string, unknown>).status
    : null
  const isPartial = resultString(job?.result ?? null, 'maintenance_status') === 'partial'
    || postHealthStatus === 'partial'
    || postHealthStatus === 'stale'
  const rollbackStatus = nestedResultStatus(job?.result ?? null, 'rollback')
  const snapshotStatus = nestedResultStatus(job?.result ?? null, 'database_snapshot')
  const chips = maintenanceChips(job)

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="font-sans text-[13.5px] font-medium text-foreground">{title}</span>
        {statusBadge}
      </div>
      <p className="font-sans text-[13px] text-muted-foreground">{label}</p>

      {helpLink && (
        <p className="text-[12px] text-muted-foreground">
          <a
            href={helpLink.href}
            target="_blank"
            rel="noopener noreferrer"
            className="underline underline-offset-2 hover:text-foreground"
          >
            {helpLink.text}
          </a>
        </p>
      )}

      {isRunning && (
        <div className="space-y-1.5">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-accent-foreground transition-all duration-300"
              style={{ width: `${Math.round((job.progress_pct ?? 0) * 100)}%` }}
            />
          </div>
          <p className="text-[12px] text-muted-foreground">{job.message}</p>
        </div>
      )}
      {isDone && (
        <div className="space-y-2">
          <div
            className={cn(
              'flex items-center gap-1.5 text-[13px]',
              isPartial
                ? 'text-amber-700 dark:text-amber-300'
                : 'text-green-600 dark:text-green-400',
            )}
          >
            {isPartial ? <AlertCircle className="size-3.5" /> : <CheckCircle2 className="size-3.5" />}
            {maintenanceLabel(job)}
          </div>
          {chips.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {chips.map((chip) => (
                <span
                  key={chip}
                  className="rounded-md border border-border/70 bg-muted/50 px-2 py-0.5 text-[11px] text-muted-foreground"
                >
                  {chip}
                </span>
              ))}
            </div>
          )}
          {snapshotStatus === 'created' && (
            <p className="text-[12px] text-muted-foreground">导入前数据库快照已保留，可用于后续回滚。</p>
          )}
        </div>
      )}
      {isError && (
        <div className="space-y-1 text-[13px] text-accent-foreground">
          <div className="flex items-center gap-1.5">
            <AlertCircle className="size-3.5" />
            {job.message || '导入失败'}
          </div>
          {rollbackStatus === 'restored' && (
            <p className="pl-5 text-[12px] text-green-700 dark:text-green-300">
              已恢复导入前数据库，原有播放数据保持不变。
            </p>
          )}
          {rollbackStatus === 'removed_new_database' && (
            <p className="pl-5 text-[12px] text-green-700 dark:text-green-300">
              首次导入未完成，已清理本次创建的半成品数据库。
            </p>
          )}
          {rollbackStatus === 'failed' && (
            <p className="pl-5 text-[12px] font-medium text-red-700 dark:text-red-300">
              自动回滚未完成，请先停止继续导入并检查数据库快照。
            </p>
          )}
        </div>
      )}
      {(isBlocked || needsConfirmation) && (
        <div className={cn(
          'space-y-1 text-[13px]',
          isBlocked ? 'text-red-700 dark:text-red-300' : 'text-amber-700 dark:text-amber-300',
        )}>
          <div className="flex items-center gap-1.5">
            <AlertCircle className="size-3.5" />
            {job.message}
          </div>
          {needsConfirmation && (
            <p className="pl-5 text-[12px]">
              {stalePlan
                ? '旧确认已失效；请重新运行上方检查，查看最新记录数量、关系和策略。'
                : planNeedsConfirmation
                ? '播放事实尚未修改；Phase B 无法自动判定，请选择验证尾部追加或完整替换。'
                : '数据库尚未修改；再次点击按钮表示你已核对这些警告并继续。'}
            </p>
          )}
        </div>
      )}

      {planNeedsConfirmation && (
        <div className="space-y-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-[12px]">
          <p className="font-medium text-amber-900 dark:text-amber-100">选择安全处理方式</p>
          <div className="flex flex-wrap gap-2">
            {canTryAppend && (
              <button
                type="button"
                aria-pressed={importMode === 'append'}
                onClick={() => setImportMode('append')}
                className={cn(
                  'rounded-md border px-3 py-2 text-left transition-colors',
                  importMode === 'append'
                    ? 'border-amber-600 bg-background text-foreground'
                    : 'border-border/70 bg-background/60 text-muted-foreground hover:text-foreground',
                )}
              >
                <span className="block font-medium">作为尾部增量验证</span>
                <span className="mt-0.5 block text-[11px]">仅在属于当前账号时选择；验证失败会阻断，不会删除历史。</span>
              </button>
            )}
            <button
              type="button"
              aria-pressed={importMode === 'replace'}
              onClick={() => setImportMode('replace')}
              className={cn(
                'rounded-md border px-3 py-2 text-left transition-colors',
                importMode === 'replace'
                  ? 'border-amber-600 bg-background text-foreground'
                  : 'border-border/70 bg-background/60 text-muted-foreground hover:text-foreground',
              )}
            >
              <span className="block font-medium">使用输入包替换</span>
              <span className="mt-0.5 block text-[11px]">将输入包视为完整快照，覆盖当前播放数据。</span>
            </button>
          </div>
          <p className="text-[11px] text-amber-800 dark:text-amber-200">
            追加只接受可证明的尾部记录；完整替换前会创建数据库快照。两种写入后的榜单和其他派生数据暂时都按完整维护流程更新。
          </p>
        </div>
      )}

      <Button
        variant="outline"
        size="sm"
        onClick={() => {
          if (stalePlan) {
            setImportMode('auto')
            onRecheck?.()
            return
          }
          onStart({
            mode: isDone || isBlocked ? 'auto' : importMode,
            confirmWarnings: warningNeedsConfirmation,
            confirmPlan: planNeedsConfirmation && replaceSelected,
            ...(confirmationToken ? { confirmationToken } : {}),
          })
        }}
        disabled={isRunning
          || (stalePlan && !onRecheck)
          || (!stalePlan && planNeedsConfirmation && !explicitModeSelected)}
        className="w-fit gap-1.5"
      >
        {isRunning ? (
          <RefreshCw className="size-3.5 animate-spin" />
        ) : (
          <Upload className="size-3.5" />
        )}
        {isRunning
          ? '导入中...'
          : stalePlan
            ? '重新检查最新计划'
          : stalePlanResolved
            ? '按最新计划导入'
          : planNeedsConfirmation
            ? importMode === 'append'
              ? '验证并追加'
              : replaceSelected ? '确认完整替换并导入' : '请先选择处理方式'
            : needsConfirmation
            ? '确认风险并导入'
            : isDone
              ? (reimportLabel || '重新导入')
              : isBlocked
                ? '重新检查'
                : '开始导入'}
      </Button>
    </div>
  )
}

// ── TrackComparePanel ───────────────────────────────────────

export function TrackComparePanel({ data }: { data: TrackComparison | null }) {
  if (!data) return <Skeleton className="h-20 w-full" />

  const allEmpty = data.shared.length === 0 && data.only_in_a.length === 0 && data.only_in_b.length === 0
  if (allEmpty) {
    return <p className="py-4 text-center text-[13px] text-muted-foreground">无曲目数据</p>
  }

  const renderTrack = (row: TrackComparison['shared'][number], idx: number) => (
    <div key={idx} className="flex items-center justify-between py-1 text-[12.5px]">
      <span className="truncate pr-2">
        {row[0]}
        <span className="ml-1 text-muted-foreground">{row[1]}</span>
      </span>
      <span className="shrink-0 text-muted-foreground">
        {row[2] !== null ? `Track ${row[2]}` : ''}
        {row[3] !== null ? ` · Disc ${row[3]}` : ''}
      </span>
    </div>
  )

  return (
    <div className="space-y-3">
      {data.shared.length > 0 && (
        <div>
          <div className="mb-1 flex items-center gap-1.5 text-[12px] font-semibold text-green-600 dark:text-green-400">
            <span className="size-1.5 rounded-full bg-current" />
            共享曲目 ({data.shared.length})
          </div>
          <div className="divide-y divide-border/50">{data.shared.map(renderTrack)}</div>
        </div>
      )}
      {data.only_in_a.length > 0 && (
        <div>
          <div className="mb-1 flex items-center gap-1.5 text-[12px] font-semibold text-blue-600 dark:text-blue-400">
            <span className="size-1.5 rounded-full bg-current" />
            仅主版本 ({data.only_in_a.length})
          </div>
          <div className="divide-y divide-border/50">{data.only_in_a.map(renderTrack)}</div>
        </div>
      )}
      {data.only_in_b.length > 0 && (
        <div>
          <div className="mb-1 flex items-center gap-1.5 text-[12px] font-semibold text-amber-600 dark:text-amber-400">
            <span className="size-1.5 rounded-full bg-current" />
            仅对比版本 ({data.only_in_b.length})
          </div>
          <div className="divide-y divide-border/50">{data.only_in_b.map(renderTrack)}</div>
        </div>
      )}
    </div>
  )
}
