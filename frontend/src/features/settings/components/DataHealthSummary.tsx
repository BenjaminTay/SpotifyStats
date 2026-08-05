import { useState } from 'react'

import { AlertCircle, CheckCircle2, ChevronDown, Database, RefreshCw, ShieldAlert } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { ImportHealthResponse } from '@/types/data-import'

const STATUS_LABELS: Record<ImportHealthResponse['status'], string> = {
  healthy: '数据健康',
  partial: '部分完成',
  blocked: '需要处理',
  stale: '派生数据待同步',
  failed: '检查失败',
}

const SEVERITY_LABELS = {
  critical: '阻断',
  high: '高风险',
  medium: '需关注',
  low: '低风险',
} as const

function formatNumber(value: number) {
  return new Intl.NumberFormat('zh-CN').format(value)
}

export function DataHealthSummary({
  health,
  loading,
  error,
  onRefresh,
}: {
  health: ImportHealthResponse | null
  loading: boolean
  error: string | null
  onRefresh: () => void
}) {
  const [detailsOpen, setDetailsOpen] = useState(false)
  const status = health?.status ?? 'blocked'
  const tone = status === 'healthy' ? 'good' : status === 'blocked' || status === 'failed' ? 'bad' : 'warn'

  return (
    <div className="rounded-xl border border-border/70 bg-muted/20 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {tone === 'good' ? (
            <CheckCircle2 className="size-4 text-green-600 dark:text-green-400" />
          ) : tone === 'bad' ? (
            <ShieldAlert className="size-4 text-red-600 dark:text-red-400" />
          ) : (
            <AlertCircle className="size-4 text-amber-600 dark:text-amber-300" />
          )}
          <span className="text-[13.5px] font-semibold">{STATUS_LABELS[status]}</span>
        </div>
        <Button type="button" variant="ghost" size="sm" onClick={onRefresh} disabled={loading} className="gap-1.5">
          <RefreshCw className={cn('size-3.5', loading && 'animate-spin')} />
          重新检查
        </Button>
      </div>

      {loading && <p className="mt-3 text-[12.5px] text-muted-foreground">正在检查数据库和派生数据...</p>}
      {!loading && error && <p className="mt-3 text-[12.5px] text-red-600 dark:text-red-400">无法读取健康状态：{error}</p>}
      {!loading && !error && health && (
        <>
          <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Metric label="播放记录" value={formatNumber(health.database.play_count)} icon={<Database className="size-3.5" />} />
            <Metric label="数据范围" value={health.database.first_play_date && health.database.last_play_date ? `${health.database.first_play_date} → ${health.database.last_play_date}` : '—'} />
            <Metric label="活跃日期" value={formatNumber(health.database.active_day_count)} />
            <Metric label="近期未解析" value={formatNumber(health.metadata.unresolved_recent_tracks + health.metadata.unresolved_recent_albums)} />
          </div>
          {(health.blockers.length > 0 || health.warnings.length > 0) && (
            <div className="mt-3 space-y-1 text-[12px] text-muted-foreground">
              {(health.issues.length > 0
                ? health.issues.slice(0, 3).map((issue) => `${issue.title}${issue.count ? `：${formatNumber(issue.count)}` : ''}`)
                : [...health.blockers, ...health.warnings]
              ).slice(0, 3).map((message) => (
                <p key={message}>· {message}</p>
              ))}
              {(health.issues.length > 3 || (health.issues.length === 0 && [...health.blockers, ...health.warnings].length > 3)) && (
                <p>· 还有更多问题，请查看问题详情。</p>
              )}
            </div>
          )}
          {health.issues.length > 0 && (
            <div className="mt-3">
              <Button
                type="button"
                variant="outline"
                size="sm"
                aria-expanded={detailsOpen}
                onClick={() => setDetailsOpen((open) => !open)}
                className="gap-1.5 text-[12px]"
              >
                <ChevronDown className={cn('size-3.5 transition-transform', detailsOpen && 'rotate-180')} />
                {detailsOpen ? '收起问题详情' : `查看问题详情（${formatNumber(health.issues.length)}）`}
              </Button>
              {detailsOpen && (
                <div className="mt-2 space-y-2">
                  {health.issues.map((issue) => (
                    <div key={issue.code} className="rounded-lg border border-border/60 bg-card/60 px-3 py-2.5 text-[12px]">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={cn(
                          'rounded-full px-1.5 py-0.5 text-[10px] font-medium',
                          issue.severity === 'critical' ? 'bg-red-500/15 text-red-700 dark:text-red-300' :
                            issue.severity === 'high' ? 'bg-orange-500/15 text-orange-700 dark:text-orange-300' :
                              issue.severity === 'medium' ? 'bg-amber-500/15 text-amber-700 dark:text-amber-300' :
                                'bg-muted text-muted-foreground',
                        )}>
                          {SEVERITY_LABELS[issue.severity]}
                        </span>
                        <span className="font-medium">{issue.title}</span>
                      </div>
                      <div className="mt-1 text-muted-foreground">
                        {issue.count > 0 && <span>关联记录：{formatNumber(issue.count)} 条 · </span>}
                        当前播放影响：{formatNumber(issue.affected_play_count)} 条
                      </div>
                      <p className="mt-1 text-muted-foreground">{issue.impact}</p>
                      <p className="mt-1 text-foreground/80">建议：{issue.recommended_action}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function Metric({ label, value, icon }: { label: string; value: string; icon?: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border/60 bg-card/70 px-3 py-2">
      <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">{icon}{label}</div>
      <div className="mt-1 truncate text-[12px] font-medium" title={value}>{value}</div>
    </div>
  )
}
