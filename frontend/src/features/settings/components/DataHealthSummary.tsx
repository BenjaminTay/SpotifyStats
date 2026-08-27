import { useMemo, useState } from 'react'

import {
  AlertTriangle,
  ChevronDown,
  CircleDot,
  Database,
  Eye,
  History,
  Info,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type {
  ImportCleanupPreviewResponse,
  ImportHealthIssue,
  ImportHealthResponse,
} from '@/types/data-import'

const numberFormatter = new Intl.NumberFormat('zh-CN')

function formatNumber(value: number) {
  return numberFormatter.format(value)
}

function issueScope(issue: ImportHealthIssue) {
  if (issue.impact_scope) return issue.impact_scope
  if (issue.code === 'audio_without_track') return 'source_exclusion'
  if (issue.affected_play_count > 0) return 'current_stats'
  return issue.category === 'relationship' ? 'historical_only' : 'current_stats'
}

function fallbackSummary(health: ImportHealthResponse) {
  const safeToUse = health.blockers.length === 0
  const historicalCount = health.issues.filter((issue) => (
    ['historical_only', 'non_music'].includes(issueScope(issue))
  )).length
  const currentCount = health.issues.filter((issue) => issueScope(issue) === 'current_stats').length
  return {
    safe_to_use: safeToUse,
    headline: !safeToUse
      ? '当前统计需要先处理关键问题'
      : historicalCount > 0
        ? '核心统计正常，有历史数据可整理'
        : '数据状态良好，核心统计可以正常使用',
    current_stats_issue_count: currentCount,
    current_stats_affected_play_count: health.issues
      .filter((issue) => issueScope(issue) === 'current_stats')
      .reduce((total, issue) => total + issue.affected_play_count, 0),
    historical_issue_count: historicalCount,
    informational_count: health.issues.filter((issue) => issueScope(issue) === 'source_exclusion').length,
    recommended_action: safeToUse ? '可继续使用；历史残留可在方便时预览整理' : '先处理阻断问题，再重新检查',
  }
}

export function DataHealthSummary({
  health,
  loading,
  error,
  onRefresh,
  preview = null,
  previewLoading = false,
  previewError = null,
  onPreview,
}: {
  health: ImportHealthResponse | null
  loading: boolean
  error: string | null
  onRefresh: () => void
  preview?: ImportCleanupPreviewResponse | null
  previewLoading?: boolean
  previewError?: string | null
  onPreview?: () => void
}) {
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [previewOpen, setPreviewOpen] = useState(false)
  const summary = health ? (health.summary ?? fallbackSummary(health)) : null
  const groupedIssues = useMemo(() => {
    const result = {
      current: [] as ImportHealthIssue[],
      historical: [] as ImportHealthIssue[],
      info: [] as ImportHealthIssue[],
    }
    for (const issue of health?.issues ?? []) {
      const scope = issueScope(issue)
      if (scope === 'source_exclusion') result.info.push(issue)
      else if (scope === 'historical_only' || scope === 'non_music') result.historical.push(issue)
      else result.current.push(issue)
    }
    return result
  }, [health])

  const requestPreview = () => {
    setPreviewOpen(true)
    onPreview?.()
  }

  return (
    <section className="overflow-hidden rounded-[18px] border border-border/70 bg-card" aria-label="数据健康治理">
      <div className={cn(
        'relative border-b px-5 py-5 sm:px-6',
        summary?.safe_to_use
          ? 'border-emerald-500/20 bg-emerald-500/[0.055]'
          : 'border-red-500/20 bg-red-500/[0.055]',
      )}>
        <div className={cn('absolute inset-y-0 left-0 w-1', summary?.safe_to_use ? 'bg-emerald-500' : 'bg-red-500')} aria-hidden="true" />
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 gap-3">
            <div className={cn(
              'mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-full border bg-background/80',
              summary?.safe_to_use ? 'border-emerald-500/25 text-emerald-600' : 'border-red-500/25 text-red-600',
            )}>
              {summary?.safe_to_use ? <ShieldCheck className="size-4.5" /> : <AlertTriangle className="size-4.5" />}
            </div>
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-[1.65px] text-muted-foreground">Data readiness</p>
              <h3 className="mt-1 font-serif text-[20px] font-semibold leading-tight tracking-[-0.2px]">
                {summary?.headline ?? '正在读取数据状态'}
              </h3>
              {summary && <p className="mt-1.5 max-w-[620px] text-[12.5px] leading-relaxed text-muted-foreground">{summary.recommended_action}</p>}
            </div>
          </div>
          <Button type="button" variant="ghost" size="sm" onClick={onRefresh} disabled={loading} className="gap-1.5">
            <RefreshCw className={cn('size-3.5', loading && 'animate-spin')} />
            重新检查
          </Button>
        </div>
      </div>

      <div className="px-5 py-5 sm:px-6">
        {loading && <p className="text-[12.5px] text-muted-foreground">正在核对数据库完整性、当前播放影响和派生数据状态…</p>}
        {!loading && error && <p className="text-[12.5px] text-red-600 dark:text-red-400">无法读取健康状态：{error}</p>}
        {!loading && !error && health && summary && (
          <>
            <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-border/70 bg-border/70 lg:grid-cols-4">
              <Metric label="播放记录" value={formatNumber(health.database.play_count)} icon={<Database className="size-3.5" />} />
              <Metric label="当前统计问题" value={`${formatNumber(summary.current_stats_issue_count)} 类`} note={`影响 ${formatNumber(summary.current_stats_affected_play_count)} 条播放`} />
              <Metric label="历史残留" value={`${formatNumber(summary.historical_issue_count)} 类`} icon={<History className="size-3.5" />} note="可稍后整理" />
              <Metric label="保留说明" value={`${formatNumber(summary.informational_count)} 类`} icon={<Info className="size-3.5" />} note="不建议自动删除" />
            </div>

            {groupedIssues.current.length > 0 && (
              <IssueGroup title="需要现在处理" description="这些项目可能影响当前统计或派生结果。" issues={groupedIssues.current} />
            )}

            {groupedIssues.historical.length > 0 && (
              <div className="mt-5 rounded-xl border border-border/70 bg-muted/[0.18] p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2 text-[13px] font-semibold"><History className="size-4 text-muted-foreground" />建议整理</div>
                    <p className="mt-1 text-[11.5px] text-muted-foreground">目前不影响核心统计；先看样本和依赖，再决定是否清理。</p>
                  </div>
                  {onPreview && (
                    <Button type="button" variant="outline" size="sm" onClick={requestPreview} disabled={previewLoading} className="gap-1.5">
                      <Eye className="size-3.5" />
                      {previewLoading ? '正在生成预览…' : '预览可整理内容'}
                    </Button>
                  )}
                </div>
                <div className="mt-3 divide-y divide-border/60 border-y border-border/60">
                  {groupedIssues.historical.map((issue) => <CompactIssue key={issue.code} issue={issue} />)}
                </div>
              </div>
            )}

            {groupedIssues.info.length > 0 && (
              <div className="mt-4 rounded-xl border border-sky-500/20 bg-sky-500/[0.045] px-4 py-3">
                <div className="flex items-start gap-2.5">
                  <Info className="mt-0.5 size-4 shrink-0 text-sky-600 dark:text-sky-300" />
                  <div className="space-y-2">
                    <p className="text-[12px] font-semibold">保留的原始记录</p>
                    {groupedIssues.info.map((issue) => (
                      <p key={issue.code} className="text-[11.5px] leading-relaxed text-muted-foreground">
                        {issue.user_title ?? issue.title}：{formatNumber(issue.count)} 条。{issue.user_explanation ?? issue.impact}
                      </p>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {previewOpen && <CleanupPreview preview={preview} loading={previewLoading} error={previewError} />}

            <div className="mt-4 border-t border-border/60 pt-3">
              <button
                type="button"
                aria-expanded={detailsOpen}
                onClick={() => setDetailsOpen((open) => !open)}
                className="flex min-h-11 w-full items-center justify-between gap-3 text-left text-[12px] font-medium text-muted-foreground transition-colors hover:text-foreground"
              >
                <span>技术详情与全部检查项</span>
                <ChevronDown className={cn('size-4 transition-transform', detailsOpen && 'rotate-180')} />
              </button>
              {detailsOpen && (
                <div className="mt-2 space-y-2">
                  {health.issues.length === 0 && <p className="text-[12px] text-muted-foreground">没有需要展示的技术问题。</p>}
                  {health.issues.map((issue) => <DetailedIssue key={issue.code} issue={issue} />)}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </section>
  )
}

function Metric({ label, value, note, icon }: { label: string; value: string; note?: string; icon?: React.ReactNode }) {
  return (
    <div className="min-h-[92px] bg-card px-4 py-3.5">
      <div className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-[0.8px] text-muted-foreground">{icon}{label}</div>
      <div className="mt-2 text-[17px] font-semibold tabular-nums tracking-[-0.2px]">{value}</div>
      {note && <div className="mt-0.5 text-[10.5px] text-muted-foreground">{note}</div>}
    </div>
  )
}

function IssueGroup({ title, description, issues }: { title: string; description: string; issues: ImportHealthIssue[] }) {
  return (
    <div className="mt-5 rounded-xl border border-amber-500/25 bg-amber-500/[0.045] p-4">
      <div className="flex items-center gap-2 text-[13px] font-semibold"><AlertTriangle className="size-4 text-amber-600" />{title}</div>
      <p className="mt-1 text-[11.5px] text-muted-foreground">{description}</p>
      <div className="mt-3 divide-y divide-amber-500/15 border-y border-amber-500/15">
        {issues.map((issue) => <CompactIssue key={issue.code} issue={issue} tone="action" />)}
      </div>
    </div>
  )
}

function CompactIssue({ issue, tone = 'neutral' }: { issue: ImportHealthIssue; tone?: 'action' | 'neutral' }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-3 text-[12px]">
      <div className="min-w-0">
        <p className="font-medium">{issue.user_title ?? issue.title}</p>
        <p className="mt-0.5 text-[11px] text-muted-foreground">{issue.user_explanation ?? issue.impact}</p>
      </div>
      <div className={cn('shrink-0 text-right tabular-nums', tone === 'action' ? 'text-amber-700 dark:text-amber-300' : 'text-muted-foreground')}>
        <p>{formatNumber(issue.count)} 条关系</p>
        <p className="mt-0.5 text-[10.5px]">当前播放影响：{formatNumber(issue.affected_play_count)}</p>
      </div>
    </div>
  )
}

function DetailedIssue({ issue }: { issue: ImportHealthIssue }) {
  return (
    <div className="rounded-lg border border-border/60 bg-muted/15 px-3.5 py-3 text-[11.5px]">
      <div className="flex flex-wrap items-center gap-2">
        <CircleDot className="size-3.5 text-muted-foreground" />
        <span className="font-medium">{issue.title}</span>
        <code className="rounded bg-muted px-1.5 py-0.5 text-[9.5px] text-muted-foreground">{issue.code}</code>
      </div>
      <p className="mt-1.5 text-muted-foreground">关联 {formatNumber(issue.count)} 条 · 当前播放影响 {formatNumber(issue.affected_play_count)} 条</p>
      <p className="mt-1 text-muted-foreground">{issue.impact}</p>
      <p className="mt-1 text-foreground/80">建议：{issue.recommended_action}</p>
    </div>
  )
}

function CleanupPreview({ preview, loading, error }: { preview: ImportCleanupPreviewResponse | null; loading: boolean; error: string | null }) {
  return (
    <div className="mt-4 rounded-xl border border-dashed border-border bg-background/70 p-4" aria-live="polite">
      <div className="flex items-center gap-2 text-[12.5px] font-semibold"><Eye className="size-4" />只读整理预览</div>
      <p className="mt-1 text-[11px] text-muted-foreground">这里只展示候选和样本，不会修改数据库，也不会自动删除播放记录。</p>
      {loading && <p className="mt-3 text-[12px] text-muted-foreground">正在计算依赖和样本…</p>}
      {error && <p className="mt-3 text-[12px] text-red-600 dark:text-red-400">预览失败：{error}</p>}
      {preview && (
        <div className="mt-3 space-y-2">
          <div className="flex flex-wrap gap-2 text-[10.5px] text-muted-foreground">
            <span className="rounded-full border border-border px-2 py-1">数据库 revision {preview.database_revision}</span>
            <span className="rounded-full border border-emerald-500/20 bg-emerald-500/[0.05] px-2 py-1 text-emerald-700 dark:text-emerald-300">写入 0</span>
          </div>
          {preview.groups.length === 0 && <p className="text-[12px] text-muted-foreground">当前没有可生成清理预览的历史关系。</p>}
          {preview.groups.map((group) => (
            <details key={group.issue_code} className="rounded-lg border border-border/60 bg-card px-3 py-2.5">
              <summary className="cursor-pointer list-none text-[11.5px] font-medium">
                {group.title} · {formatNumber(group.count)} 条 · 当前播放影响 {formatNumber(group.affected_play_count)}
              </summary>
              <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">{group.proposed_action}</p>
              {group.samples.length > 0 && (
                <pre className="mt-2 max-h-40 overflow-auto rounded-md bg-muted/35 p-2 text-[9.5px] leading-relaxed text-muted-foreground">{JSON.stringify(group.samples, null, 2)}</pre>
              )}
            </details>
          ))}
        </div>
      )}
    </div>
  )
}
