import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { AlertCircle, CheckCircle2, Upload, RefreshCw } from 'lucide-react'
import type { ImportJob, TrackComparison } from '@/types/settings'

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

export function ImportProgressCard({
  title,
  label,
  job,
  onStart,
  statusBadge,
}: {
  title: string
  label: string
  job: ImportJob | null
  onStart: () => void
  statusBadge?: React.ReactNode
}) {
  const isRunning = job?.status === 'running'
  const isDone = job?.status === 'done'
  const isError = job?.status === 'error'

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="font-sans text-[13.5px] font-medium text-foreground">{title}</span>
        {statusBadge}
      </div>
      <p className="font-sans text-[13px] text-muted-foreground">{label}</p>

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
        <div className="flex items-center gap-1.5 text-[13px] text-green-600 dark:text-green-400">
          <CheckCircle2 className="size-3.5" />
          导入完成
        </div>
      )}
      {isError && (
        <div className="flex items-center gap-1.5 text-[13px] text-accent-foreground">
          <AlertCircle className="size-3.5" />
          {job.message || '导入失败'}
        </div>
      )}

      <Button
        variant="outline"
        size="sm"
        onClick={onStart}
        disabled={isRunning}
        className="w-fit gap-1.5"
      >
        {isRunning ? (
          <RefreshCw className="size-3.5 animate-spin" />
        ) : (
          <Upload className="size-3.5" />
        )}
        {isRunning ? '导入中...' : isDone ? '重新导入' : '开始导入'}
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
