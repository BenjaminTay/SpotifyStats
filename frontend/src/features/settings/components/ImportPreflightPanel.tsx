import { AlertCircle, CheckCircle2, ClipboardCheck, RefreshCw } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { ImportFileReport, ImportPreflightResponse } from '@/types/data-import'

function fileStatusLabel(file: ImportFileReport) {
  if (file.status === 'ok') return `已发现 · ${new Intl.NumberFormat('zh-CN').format(file.record_count)} 条`
  if (file.status === 'empty') return '文件为空'
  if (file.status === 'invalid') return '解析失败'
  return file.required ? '缺少必需文件' : '未提供（可选）'
}

function duplicateRecordTotal(files: ImportFileReport[]) {
  return files.reduce((total, file) => total + (file.duplicate_record_count ?? 0), 0)
}

const numberFormatter = new Intl.NumberFormat('zh-CN')

function recordCount(value: number | undefined) {
  return numberFormatter.format(value ?? 0)
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
      return '当前数据库尚未建立记录指纹基线，本次仍将使用完整导入。'
    case 'identical':
      return '与当前数据完全相同，不需要重新导入。'
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
      return '已完成文件检查；当前接口尚未提供数据关系判断。'
  }
}

function strategyLabel(strategy: ImportPreflightResponse['estimated_strategy']) {
  if (strategy === 'noop') return '无需更新'
  if (strategy === 'incremental') return '播放事实增量'
  if (strategy === 'mixed') return '混合更新'
  return '完整更新'
}

function dateRangeLabel(range: ImportPreflightResponse['existing_date_range']) {
  if (!range?.first_date && !range?.last_date) return '暂无'
  return `${range.first_date ?? '未知'} → ${range.last_date ?? '未知'}`
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
  const hasImportPlan = Boolean(
    preflight
    && (
      preflight.detected_relation
      || preflight.fingerprint_baseline_status
      || preflight.estimated_strategy
    ),
  )

  return (
    <div className="rounded-xl border border-border/70 bg-card/60 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-[13.5px] font-semibold">
            <ClipboardCheck className="size-4" />
            导入前检查
          </div>
          <p className="mt-1 text-[12px] text-muted-foreground">只读取本地 Spotify 数据包，不会修改数据库。</p>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={onRun} disabled={loading} className="gap-1.5">
          <RefreshCw className={cn('size-3.5', loading && 'animate-spin')} />
          {loading ? '检查中...' : '开始检查'}
        </Button>
      </div>

      {error && <p className="mt-3 text-[12.5px] text-red-600 dark:text-red-400">检查失败：{error}</p>}
      {preflight && (
        <>
          {preflight.blockers.length > 0 && (
            <div className="mt-3 space-y-1 rounded-lg bg-red-500/10 px-3 py-2 text-[12px] text-red-700 dark:text-red-300">
              {preflight.blockers.map((message) => <p key={message}>· {message}</p>)}
            </div>
          )}
          {(preflight.duplicate_file_groups.length > 0 || preflight.date_overlaps.length > 0 || duplicateRecordTotal(preflight.streaming_files) > 0) && (
            <div className="mt-3 space-y-1 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[12px] text-amber-800 dark:text-amber-200">
              <p className="font-medium">唯一性与日期检查</p>
              <p>完全重复文件：{preflight.duplicate_file_groups.length} 组</p>
              <p>文件内重复记录：{new Intl.NumberFormat('zh-CN').format(duplicateRecordTotal(preflight.streaming_files))} 条</p>
              <p>日期范围重叠：{preflight.date_overlaps.length} 对</p>
              {preflight.date_overlaps.slice(0, 6).map((overlap) => (
                <p key={`${overlap.left_file}:${overlap.right_file}`} className="pl-2 text-[11.5px]">
                  {overlap.left_file} ↔ {overlap.right_file}：{overlap.overlap_start} 至 {overlap.overlap_end}，共同记录 {overlap.shared_record_count} 条
                </p>
              ))}
              {preflight.date_overlaps.length > 6 && <p className="pl-2 text-[11.5px]">其余日期重叠已省略，请查看接口详情。</p>}
            </div>
          )}
          {hasImportPlan && (
            <div className="mt-3 rounded-lg border border-border/60 bg-background/45 px-3 py-2.5 text-[12px]">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-medium">预计导入策略</p>
                <span className={cn(
                  'rounded-full px-2 py-0.5 text-[11px] font-medium',
                  preflight.requires_confirmation
                    ? 'bg-amber-500/15 text-amber-800 dark:text-amber-200'
                    : 'bg-primary/10 text-primary',
                )}>
                  {preflight.requires_confirmation ? '需要确认' : strategyLabel(preflight.estimated_strategy)}
                </span>
              </div>
              <p className="mt-1.5 text-foreground/90">{relationSummary(preflight)}</p>
              {preflight.estimated_strategy === 'incremental' && (
                <p className="mt-1 text-[11.5px] text-muted-foreground">
                  当前仅播放事实增量写入；榜单、搜索和其他派生数据仍执行完整维护。
                </p>
              )}
              <div className="mt-2 grid gap-x-5 gap-y-1 text-[11.5px] text-muted-foreground sm:grid-cols-2">
                <p>当前 / 输入：{recordCount(preflight.existing_record_count)} / {recordCount(preflight.incoming_record_count)} 条</p>
                <p>复用 / 新增 / 移除：{recordCount(preflight.unchanged_record_count)} / {recordCount(preflight.added_record_count)} / {recordCount(preflight.removed_record_count)} 条</p>
                <p>当前范围：{dateRangeLabel(preflight.existing_date_range)}</p>
                <p>输入范围：{dateRangeLabel(preflight.incoming_date_range)}</p>
              </div>
              {(preflight.planned_actions?.length ?? 0) > 0 && (
                <div className="mt-2 border-t border-border/50 pt-2 text-[11.5px] text-muted-foreground">
                  <p className="font-medium text-foreground/80">计划动作</p>
                  {preflight.planned_actions?.map((action) => <p key={action} className="mt-0.5">· {action}</p>)}
                </div>
              )}
            </div>
          )}
          <div className="mt-3 grid gap-1.5 sm:grid-cols-2">
            {[...preflight.streaming_files, ...preflight.account_files].map((file) => (
              <div key={`${file.source_key}:${file.file_name}`} className="flex items-center justify-between gap-3 rounded-lg border border-border/50 px-3 py-2 text-[11.5px]">
                <span className="truncate">{file.label}</span>
                <span className={cn('shrink-0', file.status === 'ok' ? 'text-green-600 dark:text-green-400' : file.required ? 'text-red-600 dark:text-red-400' : 'text-muted-foreground')}>
                  {file.status === 'ok' ? <CheckCircle2 className="mr-1 inline size-3.5" /> : <AlertCircle className="mr-1 inline size-3.5" />}
                  {fileStatusLabel(file)}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
