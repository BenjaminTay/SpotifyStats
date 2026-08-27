import { useState } from 'react'

import {
  AlertCircle,
  Check,
  CheckCircle2,
  ChevronDown,
  Circle,
  FileArchive,
  FolderCheck,
  Info,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { ImportFileReport, ImportPreflightResponse } from '@/types/data-import'

const numberFormatter = new Intl.NumberFormat('zh-CN')

function recordCount(value: number | undefined) {
  return numberFormatter.format(value ?? 0)
}

function duplicateRecordTotal(files: ImportFileReport[]) {
  return files.reduce((total, file) => total + (file.duplicate_record_count ?? 0), 0)
}

function affectedScope(preflight: ImportPreflightResponse) {
  const weeks = preflight.affected_weeks_count ?? 0
  const years = preflight.affected_years_count ?? 0
  if (weeks === 0 && years === 0) return ''
  return `，变化涉及 ${numberFormatter.format(weeks)} 个榜单周和 ${numberFormatter.format(years)} 个年度范围`
}

function relationSummary(preflight: ImportPreflightResponse) {
  const added = recordCount(preflight.added_record_count)
  const removed = recordCount(preflight.removed_record_count)
  const scope = affectedScope(preflight)
  switch (preflight.detected_relation) {
    case 'baseline_required':
      return '这是首次建立数据识别基线。当前只能核对总量和日期范围，还不能逐条计算新增或移除。系统会先创建数据库快照，再执行一次完整更新并保存基线。'
    case 'identical':
      return '数据包与当前数据库逐条一致，不需要重新导入。'
    case 'snapshot_superset':
      return `检测到当前数据基础上的完整追加：新增 ${added} 条记录${scope}。`
    case 'delta_tail':
      return `检测到尾部增量包：新增 ${added} 条记录${scope}。`
    case 'reconciled_snapshot':
      return `检测到历史数据修订：新增 ${added} 条、移除 ${removed} 条记录${scope}。`
    case 'truncated_or_regressive':
      return '输入包缺少当前库中的部分历史记录，无法安全自动替换。'
    case 'different_account':
      return '输入包与当前数据库的账号身份不同，不能作为自动增量更新。'
    case 'ambiguous':
      return '无法证明输入包是完整快照还是尾部增量，需要确认导入方式。'
    default:
      return '文件结构检查已完成；当前还没有可用的数据关系判断。'
  }
}

function strategyLabel(preflight: ImportPreflightResponse) {
  if (preflight.detected_relation === 'baseline_required') return '建立导入基线（推荐）'
  if (preflight.estimated_strategy === 'noop') return '无需更新'
  if (preflight.estimated_strategy === 'incremental') return '播放事实增量'
  if (preflight.estimated_strategy === 'mixed') return '混合更新'
  return '完整更新'
}

function dateRangeLabel(range: ImportPreflightResponse['existing_date_range']) {
  if (!range?.first_date && !range?.last_date) return '暂无'
  return `${range.first_date ?? '未知'} → ${range.last_date ?? '未知'}`
}

function fileStatusLabel(file: ImportFileReport) {
  if (file.status === 'ok') return `${recordCount(file.record_count)} 条`
  if (file.status === 'empty') return '文件为空'
  if (file.status === 'invalid') return '解析失败'
  return file.required ? '缺少必需文件' : '未提供（可选）'
}

export function ImportPreflightPanel({
  preflight,
  loading,
  error,
  onRun,
}: {
  preflight: ImportPreflightResponse | null
  loading: boolean
  error: string | null
  onRun: () => void
}) {
  const [filesOpen, setFilesOpen] = useState(false)
  const hasPlan = Boolean(preflight && (
    preflight.detected_relation || preflight.fingerprint_baseline_status || preflight.estimated_strategy
  ))
  const comparable = preflight?.record_delta_comparable
    ?? preflight?.fingerprint_baseline_status === 'ready'
  const boundaryOverlaps = preflight?.date_overlaps.filter((item) => (
    item.classification === 'boundary_only' || item.shared_record_count === 0
  )) ?? []
  const duplicateOverlaps = preflight?.date_overlaps.filter((item) => (
    item.classification === 'duplicate_records' || item.shared_record_count > 0
  )) ?? []

  return (
    <section className="rounded-[18px] border border-border/70 bg-card p-5 sm:p-6" aria-label="检查本地数据包">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex gap-3">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-full border border-border bg-muted/30">
            <FolderCheck className="size-4" />
          </div>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[1.65px] text-muted-foreground">Import readiness</p>
            <h3 className="mt-1 font-serif text-[20px] font-semibold leading-tight tracking-[-0.2px]">检查本地数据包</h3>
            <p className="mt-1.5 text-[12px] text-muted-foreground">只读取 Spotify 导出文件并在临时环境演练，不修改当前数据库。</p>
          </div>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={onRun} disabled={loading} className="min-h-9 gap-1.5">
          <RefreshCw className={cn('size-3.5', loading && 'animate-spin')} />
          {loading ? '正在检查…' : preflight ? '重新检查' : '检查数据包'}
        </Button>
      </div>

      <div className="mt-5 grid grid-cols-3 gap-2" aria-label="导入流程">
        <Step index={1} title="检查数据包" active={!preflight || loading} done={Boolean(preflight) && !loading} />
        <Step index={2} title="查看导入建议" active={Boolean(preflight) && !loading} done={false} />
        <Step index={3} title="确认并导入" active={false} done={false} />
      </div>

      {loading && (
        <div className="mt-4 rounded-xl border border-border/60 bg-muted/15 px-4 py-3 text-[12px] text-muted-foreground" aria-live="polite">
          正在解析文件、核对重复记录并建立临时 staging。数据包较大时通常需要十几秒。
        </div>
      )}
      {error && <p className="mt-4 rounded-xl bg-red-500/10 px-4 py-3 text-[12px] text-red-700 dark:text-red-300">检查失败：{error}</p>}

      {preflight && !loading && (
        <div className="mt-5 space-y-4">
          <div className={cn(
            'rounded-xl border px-4 py-4',
            preflight.blockers.length > 0
              ? 'border-red-500/25 bg-red-500/[0.045]'
              : 'border-emerald-500/20 bg-emerald-500/[0.045]',
          )}>
            <div className="flex items-start gap-2.5">
              {preflight.blockers.length > 0
                ? <AlertCircle className="mt-0.5 size-4 shrink-0 text-red-600" />
                : <ShieldCheck className="mt-0.5 size-4 shrink-0 text-emerald-600" />}
              <div>
                <p className="text-[12.5px] font-semibold">{preflight.blockers.length > 0 ? '需要先处理文件问题' : '数据包可以继续进入下一步'}</p>
                {preflight.blockers.length > 0
                  ? preflight.blockers.map((message) => <p key={message} className="mt-1 text-[11.5px] text-red-700 dark:text-red-300">· {message}</p>)
                  : <p className="mt-1 text-[11.5px] text-muted-foreground">文件可解析，系统已经给出本次导入建议；正式导入仍需单独确认。</p>}
              </div>
            </div>
          </div>

          {hasPlan && (
            <div className="rounded-xl border border-border/70 bg-background/45 px-4 py-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">系统建议</p>
                  <p className="mt-1 text-[14px] font-semibold">{strategyLabel(preflight)}</p>
                </div>
                <span className={cn(
                  'rounded-full px-2.5 py-1 text-[10.5px] font-medium',
                  preflight.requires_confirmation
                    ? 'bg-amber-500/15 text-amber-800 dark:text-amber-200'
                    : 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
                )}>
                  {preflight.requires_confirmation ? '导入前需要确认' : '可按建议继续'}
                </span>
              </div>
              <p className="mt-2 max-w-[720px] text-[12px] leading-relaxed text-foreground/85">{relationSummary(preflight)}</p>

              <div className="mt-3 grid gap-px overflow-hidden rounded-lg border border-border/60 bg-border/60 sm:grid-cols-2">
                <PlanMetric label="当前数据库" value={`${recordCount(preflight.existing_record_count)} 条`} note={dateRangeLabel(preflight.existing_date_range)} />
                <PlanMetric label="本地数据包" value={`${recordCount(preflight.incoming_record_count)} 条`} note={dateRangeLabel(preflight.incoming_date_range)} />
              </div>

              {comparable ? (
                <div className="mt-2 grid grid-cols-3 gap-2">
                  <SmallMetric label="可复用" value={recordCount(preflight.unchanged_record_count)} />
                  <SmallMetric label="新增" value={recordCount(preflight.added_record_count)} />
                  <SmallMetric label="移除" value={recordCount(preflight.removed_record_count)} />
                </div>
              ) : (
                <div className="mt-3 flex items-start gap-2 rounded-lg border border-sky-500/20 bg-sky-500/[0.045] px-3 py-2.5 text-[11.5px] text-muted-foreground">
                  <Info className="mt-0.5 size-3.5 shrink-0 text-sky-600" />
                  首次基线尚未建立，当前不能把输入总量解释成“新增记录”，因此不展示复用、新增和移除指标。
                </div>
              )}

              {(preflight.planned_actions?.length ?? 0) > 0 && (
                <div className="mt-3 border-t border-border/60 pt-3 text-[11.5px] text-muted-foreground">
                  <p className="font-medium text-foreground/80">执行时会做什么</p>
                  {preflight.planned_actions?.map((action) => <p key={action} className="mt-1">· {action}</p>)}
                </div>
              )}
            </div>
          )}

          {(duplicateRecordTotal(preflight.streaming_files) > 0 || preflight.duplicate_file_groups.length > 0 || duplicateOverlaps.length > 0) && (
            <div className="rounded-xl border border-amber-500/25 bg-amber-500/[0.045] px-4 py-3 text-[11.5px]">
              <p className="font-semibold">发现需要核对的重复</p>
              <p className="mt-1 text-muted-foreground">完全重复文件 {preflight.duplicate_file_groups.length} 组 · 文件内重复记录 {recordCount(duplicateRecordTotal(preflight.streaming_files))} 条 · 跨文件共同记录 {recordCount(duplicateOverlaps.reduce((total, item) => total + item.shared_record_count, 0))} 条</p>
            </div>
          )}

          {boundaryOverlaps.length > 0 && (
            <div className="rounded-xl border border-sky-500/20 bg-sky-500/[0.04] px-4 py-3 text-[11.5px]">
              <div className="flex items-start gap-2">
                <Info className="mt-0.5 size-3.5 shrink-0 text-sky-600" />
                <div>
                  <p className="font-medium">发现 {boundaryOverlaps.length} 对文件时间范围相邻或交叠</p>
                  <p className="mt-1 text-muted-foreground">逐条核对后没有发现相同记录，这通常只是导出分包边界，不会导致重复计数。</p>
                </div>
              </div>
            </div>
          )}

          <div className="rounded-xl border border-border/60">
            <button
              type="button"
              aria-expanded={filesOpen}
              onClick={() => setFilesOpen((open) => !open)}
              className="flex min-h-11 w-full items-center justify-between gap-3 px-4 text-left text-[12px] font-medium"
            >
              <span className="flex items-center gap-2"><FileArchive className="size-4 text-muted-foreground" />文件详情 · 串流 {preflight.streaming_files.length} 个 / 账号 {preflight.account_files.length} 个</span>
              <ChevronDown className={cn('size-4 text-muted-foreground transition-transform', filesOpen && 'rotate-180')} />
            </button>
            {filesOpen && (
              <div className="border-t border-border/60 px-4 py-3">
                <FileGroup title="串流记录" files={preflight.streaming_files} />
                <FileGroup title="账号档案" files={preflight.account_files} className="mt-4" />
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  )
}

function Step({ index, title, active, done }: { index: number; title: string; active: boolean; done: boolean }) {
  return (
    <div className={cn(
      'flex min-h-[54px] items-center gap-2 rounded-lg border px-2.5 py-2 text-[10.5px]',
      active ? 'border-primary/30 bg-primary/[0.045] text-foreground' : 'border-border/60 text-muted-foreground',
    )}>
      <span className={cn(
        'flex size-5 shrink-0 items-center justify-center rounded-full border text-[9px] font-semibold',
        done ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700' : active ? 'border-primary/30' : 'border-border',
      )}>
        {done ? <Check className="size-3" /> : index}
      </span>
      <span className="leading-tight">{title}</span>
    </div>
  )
}

function PlanMetric({ label, value, note }: { label: string; value: string; note: string }) {
  return <div className="bg-card px-3 py-2.5"><p className="text-[9.5px] uppercase tracking-[0.8px] text-muted-foreground">{label}</p><p className="mt-1 text-[13px] font-semibold tabular-nums">{value}</p><p className="mt-0.5 truncate text-[10px] text-muted-foreground" title={note}>{note}</p></div>
}

function SmallMetric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg border border-border/60 bg-muted/15 px-3 py-2"><p className="text-[9.5px] text-muted-foreground">{label}</p><p className="mt-0.5 text-[12px] font-semibold tabular-nums">{value}</p></div>
}

function FileGroup({ title, files, className }: { title: string; files: ImportFileReport[]; className?: string }) {
  return (
    <div className={className}>
      <p className="text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground">{title}</p>
      {files.length === 0 ? <p className="mt-2 text-[11px] text-muted-foreground">未发现该类型文件。</p> : (
        <div className="mt-2 divide-y divide-border/50">
          {files.map((file) => (
            <div key={`${file.source_key}:${file.file_name}`} className="flex flex-wrap items-center justify-between gap-2 py-2 text-[11px]">
              <div className="min-w-0"><p className="truncate font-medium" title={file.file_name}>{file.file_name}</p><p className="mt-0.5 text-[10px] text-muted-foreground">{file.label}{file.first_date || file.last_date ? ` · ${file.first_date ?? '未知'} → ${file.last_date ?? '未知'}` : ''}</p></div>
              <span className={cn('shrink-0', file.status === 'ok' ? 'text-emerald-600' : file.required ? 'text-red-600' : 'text-muted-foreground')}>
                {file.status === 'ok' ? <CheckCircle2 className="mr-1 inline size-3.5" /> : file.required ? <AlertCircle className="mr-1 inline size-3.5" /> : <Circle className="mr-1 inline size-3.5" />}
                {fileStatusLabel(file)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
