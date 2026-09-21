import { useMemo, useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Database,
  FileJson,
  History,
  Image,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  Upload,
} from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { useDataImport } from '@/hooks/useDataImport'
import { cn } from '@/lib/utils'
import type {
  ImportPreflightResponse,
  ImportRequestedMode,
  ImportRunDetail,
  ImportRunStage,
} from '@/types/data-import'

type ImportPresentation = 'phone' | 'compact' | 'desktop'

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '操作失败，请重试'
}

function formatDate(value: string | null | undefined) {
  if (!value) return '尚未完成'
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

function isCoverStage(stage: ImportRunStage) {
  return stage.stage.toLowerCase().includes('cover')
}

function stageTone(stage: ImportRunStage) {
  if (stage.status === 'succeeded' || stage.status === 'ready') return 'text-emerald-600 dark:text-emerald-400'
  if (stage.status === 'running' || stage.status === 'pending' || stage.freshness === 'warming') return 'text-amber-600 dark:text-amber-300'
  if (stage.status === 'failed' || stage.status === 'blocked' || stage.freshness === 'failed') return 'text-red-600 dark:text-red-300'
  return 'text-muted-foreground'
}

function stageText(stage: ImportRunStage) {
  if (stage.freshness === 'warming') return '正在后台更新；当前只展示已证明可用的旧结果'
  if (stage.freshness === 'unavailable') return '暂无可用结果，不能以 0 或旧状态代替'
  if (stage.freshness === 'failed') return stage.message || '本阶段失败，已保留播放事实与错误记录'
  if (stage.error_code?.includes('provider') || stage.error_code?.includes('credential')) {
    return '外部服务当前不可用；不影响已经提交的播放事实'
  }
  return stage.message || stage.status
}

function ResultDimension({
  title,
  state,
  detail,
  icon: Icon,
}: {
  title: string
  state: string
  detail: string
  icon: typeof Database
}) {
  return (
    <div className="min-w-0 rounded-xl border border-border/70 bg-background/45 p-3">
      <div className="flex items-center gap-2 text-[12px] font-semibold">
        <Icon className="size-4 text-accent-foreground" aria-hidden="true" />
        {title}
      </div>
      <p className="mt-2 text-[13px] font-medium text-foreground">{state}</p>
      <p className="mt-1 text-[11px] leading-5 text-muted-foreground">{detail}</p>
    </div>
  )
}

function ImportResult({
  run,
  onRetry,
  retrying,
  onRecheck,
  rechecking,
}: {
  run: ImportRunDetail
  onRetry: (stage: string) => void
  retrying: boolean
  onRecheck: () => void
  rechecking: boolean
}) {
  const coverStages = run.stages.filter(isCoverStage)
  const coreStages = run.stages.filter((stage) => !isCoverStage(stage))
  const failedCore = coreStages.filter((stage) => ['failed', 'blocked', 'retryable_failed'].includes(stage.status))
  const warmingCore = coreStages.filter((stage) => stage.freshness === 'warming' || ['pending', 'running'].includes(stage.status))
  const result = run.result ?? {}
  const qualityCount = Number(result.quality_issue_count ?? result.warning_count ?? 0)
  const noop = result.noop === true || result.executed_strategy === 'noop'
  const sourceUnregistered = result.source_registration_status === 'not_registered'
  const factsPublished = ['facts_committed', 'sources_published', 'core_ready', 'ready'].includes(run.publication_state)

  return (
    <section className="space-y-3" aria-label="导入结果">
      <div className="grid gap-2 md:grid-cols-3">
        <ResultDimension
          title={noop ? '数据未变化' : '数据已更新'}
          icon={Database}
          state={noop ? '播放事实保持不变' : factsPublished ? '播放事实已提交' : run.status === 'failed' ? '播放事实未更新' : '等待事实发布'}
          detail={noop
            ? sourceUnregistered
              ? '输入包与活动基线一致，播放事实未重写；活动原始来源尚未登记，请使用覆盖全部历史的完整导出并选择完整替换。'
              : '输入包与活动基线一致；没有重写播放事实或创建恢复备份。'
            : factsPublished ? `发布状态：${run.publication_state}` : run.message || '输入仍在检查或执行中'}
        />
        <ResultDimension
          title="统计准备情况"
          icon={Clock3}
          state={noop ? '无需重建' : failedCore.length > 0 ? '部分统计不可用' : warmingCore.length > 0 ? '统计仍在准备' : '必需统计已完成'}
          detail={noop
            ? '当前统计继续使用既有 ready 结果，没有安排派生或封面任务。'
            : failedCore.length > 0
            ? '失败不会伪装成 warming；请按阶段重试。'
            : warmingCore.length > 0
              ? '100% 播放写入不等于全部快照 ready。'
              : '当前运行没有待处理的核心阶段。'}
        />
        <ResultDimension
          title="数据质量事项"
          icon={ShieldCheck}
          state={qualityCount > 0 ? `${qualityCount} 项需要查看` : '没有新增阻断事项'}
          detail={qualityCount > 0 ? '质量事项与播放事实发布分开记录。' : '历史治理问题仍可在高级数据管理中查看。'}
        />
      </div>

      {coverStages.length > 0 && (
        <div className="rounded-xl border border-border/70 px-3 py-3">
          <div className="flex items-start gap-2">
            <Image className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            <div className="min-w-0">
              <p className="text-[12px] font-semibold">封面补充任务</p>
              <p className="mt-1 text-[11px] leading-5 text-muted-foreground">
                封面独立处理；失败或等待不会把已经完成的数据导入显示为失败。
              </p>
            </div>
          </div>
        </div>
      )}

      {run.stages.length > 0 && (
        <div className="divide-y divide-border/70 rounded-xl border border-border/70">
          {run.stages.map((stage) => (
            <div key={`${stage.stage}-${stage.attempt ?? 0}`} className="flex min-w-0 items-start gap-3 p-3">
              <span className={cn('mt-0.5 size-2 shrink-0 rounded-full bg-current', stageTone(stage))} />
              <div className="min-w-0 flex-1">
                <p className="break-words text-[12px] font-medium">{stage.stage}</p>
                <p className="mt-1 break-words text-[11px] leading-5 text-muted-foreground">{stageText(stage)}</p>
              </div>
              {stage.retryable && ['failed', 'blocked', 'retryable_failed'].includes(stage.status) && (
                <Button className="min-h-11 shrink-0" size="sm" variant="outline" disabled={retrying} onClick={() => onRetry(stage.stage)}>
                  重试
                </Button>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {run.retryable && ['planned', 'failed_before_facts'].includes(run.publication_state) && (
          <Button className="min-h-11" size="sm" variant="outline" disabled={retrying} onClick={() => onRetry('facts')}>
            重试播放事实阶段
          </Button>
        )}
        <Button className="min-h-11" size="sm" variant="outline" disabled={rechecking} onClick={onRecheck}>
          <RefreshCw className={cn('size-4', rechecking && 'animate-spin')} />
          重新检查统计
        </Button>
        <Link className="inline-flex min-h-11 items-center rounded-lg px-3 text-[12px] font-medium hover:bg-muted" to="/settings?panel=advanced">
          打开治理入口
        </Link>
        <a className="inline-flex min-h-11 items-center rounded-lg px-3 text-[12px] font-medium hover:bg-muted" href={`/api/import/runs/${run.run_id}/report?format=markdown`} target="_blank" rel="noreferrer">
          查看运行报告
        </a>
      </div>
    </section>
  )
}

function PlanSummary({ preflight }: { preflight: ImportPreflightResponse }) {
  const comparable = preflight.record_delta_comparable === true
  return (
    <section className="rounded-xl border border-border/70 bg-background/45 p-3" aria-label="导入计划">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[12px] font-semibold">检查计划</p>
          <p className="mt-1 text-[11px] text-muted-foreground">
            {preflight.detected_relation === 'baseline_required'
              ? '当前缺少可比较基线；首次确认会建立基线，不展示虚假新增数量。'
              : `输入关系：${preflight.detected_relation ?? 'unknown'} · 建议策略：${preflight.estimated_strategy ?? 'full'}`}
          </p>
        </div>
        <span className={cn(
          'rounded-full px-2 py-1 text-[10px] font-semibold',
          preflight.blockers.length > 0 ? 'bg-red-500/10 text-red-600' : 'bg-emerald-500/10 text-emerald-600',
        )}>
          {preflight.blockers.length > 0 ? `${preflight.blockers.length} 项阻断` : '可以继续'}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <div><span className="text-[10px] text-muted-foreground">输入记录</span><strong className="block text-[14px]">{(preflight.incoming_record_count ?? 0).toLocaleString('zh-CN')}</strong></div>
        <div><span className="text-[10px] text-muted-foreground">复用记录</span><strong className="block text-[14px]">{comparable ? (preflight.unchanged_record_count ?? 0).toLocaleString('zh-CN') : '不可比较'}</strong></div>
        <div><span className="text-[10px] text-muted-foreground">新增记录</span><strong className="block text-[14px]">{comparable ? (preflight.added_record_count ?? 0).toLocaleString('zh-CN') : '建立基线后可知'}</strong></div>
        <div><span className="text-[10px] text-muted-foreground">移除记录</span><strong className="block text-[14px]">{comparable ? (preflight.removed_record_count ?? 0).toLocaleString('zh-CN') : '建立基线后可知'}</strong></div>
      </div>
      {[...preflight.blockers, ...preflight.warnings].length > 0 && (
        <ul className="mt-3 space-y-1 text-[11px] leading-5 text-muted-foreground">
          {[...preflight.blockers, ...preflight.warnings].map((item) => <li key={item}>· {item}</li>)}
        </ul>
      )}
    </section>
  )
}

export function DataImportWorkspace({
  presentation,
  dbRecordCount,
  accountImported,
}: {
  presentation: ImportPresentation
  dbRecordCount: number
  accountImported: boolean
}) {
  const [files, setFiles] = useState<File[]>([])
  const [batchId, setBatchId] = useState<string | null>(null)
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [mode, setMode] = useState<ImportRequestedMode>('auto')
  const [confirmWarnings, setConfirmWarnings] = useState(false)
  const [actionError, setActionError] = useState('')
  const dataImport = useDataImport({ batchId, runId: selectedRunId, mode })
  const run = dataImport.run
  const busy = dataImport.creatingBatch || dataImport.uploadingFile || dataImport.finalizingBatch
  const currentStep = dataImport.preflight ? 2 : batchId ? 1 : 0
  const history = useMemo(() => {
    const seen = new Set<string>()
    return dataImport.historyRuns.filter((item) => !seen.has(item.run_id) && seen.add(item.run_id))
  }, [dataImport.historyRuns])

  const receiveFiles = async () => {
    if (files.length === 0) return
    setActionError('')
    // A second upload must not leave the previous batch's executable plan on
    // screen while the new immutable batch is still being received/frozen.
    setBatchId(null)
    setSelectedRunId(null)
    setConfirmWarnings(false)
    try {
      const batch = await dataImport.createBatch({ kind: 'snapshot' })
      for (const file of files) {
        await dataImport.uploadFile({
          batchId: batch.batch_id,
          file,
          sourceType: file.name.toLowerCase().includes('video') ? 'video' : 'audio',
        })
      }
      const frozen = await dataImport.finalizeBatch(batch.batch_id)
      setBatchId(frozen.batch_id)
    } catch (error) {
      setActionError(errorMessage(error))
    }
  }

  const execute = async () => {
    if (!batchId || !dataImport.preflight?.confirmation_token) return
    setActionError('')
    try {
      const result = await dataImport.executeRun({
        targetBatchId: batchId,
        payload: {
          mode,
          confirmation_token: dataImport.preflight.confirmation_token,
          confirm_warnings: confirmWarnings,
          confirm_plan: dataImport.preflight.requires_confirmation === true,
        },
      })
      setSelectedRunId(result.run_id)
    } catch (error) {
      setActionError(errorMessage(error))
    }
  }

  return (
    <div className={cn('min-w-0 space-y-4', presentation === 'phone' && 'overflow-x-hidden')} data-import-presentation={presentation}>
      <div className="grid grid-cols-4 gap-1" aria-label="导入步骤">
        {['选择包', '接收', '检查', '执行'].map((label, index) => (
          <div key={label} className={cn('rounded-lg px-2 py-2 text-center text-[10px] font-semibold', index <= currentStep ? 'bg-accent-foreground/10 text-accent-foreground' : 'bg-muted/60 text-muted-foreground')}>
            {index + 1}. {label}
          </div>
        ))}
      </div>

      <section className="rounded-xl border border-border/70 p-3" aria-label="选择导入数据包">
        <label className="flex min-h-11 cursor-pointer items-center gap-3 rounded-lg border border-dashed border-border px-3 py-2 hover:bg-muted/40">
          <Upload className="size-4 shrink-0 text-accent-foreground" aria-hidden="true" />
          <span className="min-w-0 flex-1 text-[12px]">
            <strong className="block">选择 Spotify Extended Streaming History JSON</strong>
            <span className="mt-0.5 block truncate text-[10px] text-muted-foreground">
              {files.length > 0 ? `已选择 ${files.length} 个文件` : '可多选；浏览器路径不会作为服务器路径使用'}
            </span>
          </span>
          <input className="sr-only" type="file" accept=".json,application/json" multiple onChange={(event) => setFiles(Array.from(event.target.files ?? []))} />
        </label>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button className="min-h-11" size="sm" disabled={files.length === 0 || busy} onClick={() => void receiveFiles()}>
            {busy ? <LoaderCircle className="size-4 animate-spin" /> : <FileJson className="size-4" />}
            接收并检查
          </Button>
          <span className="text-[10px] text-muted-foreground">现有数据库 {dbRecordCount.toLocaleString('zh-CN')} 条 · 账号资料{accountImported ? '已导入' : '未导入'}</span>
        </div>
      </section>

      <section className="flex min-w-0 flex-wrap items-center gap-3 rounded-xl border border-border/70 p-3" aria-label="账号资料导入">
        <div className="min-w-0 flex-1">
          <p className="text-[12px] font-semibold">账号资料包</p>
          <p className="mt-1 break-words text-[10px] leading-5 text-muted-foreground">
            {dataImport.accountJob?.message || (accountImported ? '收藏、搜索与播客资料已导入' : '使用服务器已配置的账号资料目录')}
          </p>
        </div>
        <Button className="min-h-11 shrink-0" size="sm" variant="outline" disabled={dataImport.accountImporting} onClick={() => void dataImport.startAccountImport()}>
          {dataImport.accountImporting && <LoaderCircle className="size-4 animate-spin" />}
          {accountImported ? '再次导入' : '导入账号资料'}
        </Button>
      </section>

      {dataImport.preflightLoading && <p className="text-[12px] text-muted-foreground">正在核对不可变清单与活动基线…</p>}
      {dataImport.preflight && <PlanSummary preflight={dataImport.preflight} />}

      {dataImport.preflight && (
        <section className="rounded-xl border border-border/70 p-3" aria-label="执行导入">
          {dataImport.preflight.requires_confirmation && (
            <div className="mb-3 flex flex-wrap gap-2">
              {(['auto', 'append', 'replace'] as ImportRequestedMode[]).map((value) => (
                <button key={value} type="button" className={cn('min-h-11 rounded-lg border px-3 text-[11px] font-semibold', mode === value && 'border-accent-foreground bg-accent-foreground/10')} onClick={() => setMode(value)}>
                  {value === 'auto' ? '按计划' : value === 'append' ? '仅追加' : '完整替换'}
                </button>
              ))}
            </div>
          )}
          {dataImport.preflight.warnings.length > 0 && (
            <label className="mb-3 flex min-h-11 items-center gap-2 text-[11px]">
              <input type="checkbox" checked={confirmWarnings} onChange={(event) => setConfirmWarnings(event.target.checked)} />
              我已核对上述警告与计划
            </label>
          )}
          <Button className="min-h-11" size="sm" disabled={busy || dataImport.preflight.blockers.length > 0 || dataImport.executingRun || (dataImport.preflight.warnings.length > 0 && !confirmWarnings)} onClick={() => void execute()}>
            {dataImport.executingRun && <LoaderCircle className="size-4 animate-spin" />}
            执行已确认计划
          </Button>
        </section>
      )}

      {actionError && (
        <div className="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/5 p-3 text-[12px] text-red-700 dark:text-red-300">
          <AlertCircle className="mt-0.5 size-4 shrink-0" />{actionError}
        </div>
      )}

      {dataImport.error && !run && (
        <div className="flex items-start gap-2 rounded-xl border border-border bg-muted/40 p-3 text-[12px] text-muted-foreground">
          <AlertCircle className="mt-0.5 size-4 shrink-0" />
          暂时无法读取持久运行状态；没有可用记录时不会显示虚假成功或 warming。
        </div>
      )}

      {run && (
        <div className="space-y-3 rounded-xl border border-border/70 p-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[12px] font-semibold">当前运行 · {run.status}</p>
              <p className="mt-1 break-words text-[11px] text-muted-foreground">{run.message || `开始于 ${formatDate(run.started_at)}`}</p>
            </div>
            {['pending', 'queued', 'running', 'retrying', 'warming'].includes(run.status) && <LoaderCircle className="size-4 shrink-0 animate-spin text-accent-foreground" />}
          </div>
          {(run.error_code?.includes('provider') || run.error_code?.includes('credential')) && (
            <p className="rounded-lg bg-amber-500/10 p-2 text-[11px] leading-5 text-amber-800 dark:text-amber-200">
              外部服务当前不可用；已提交的播放事实不会因此回滚，相关补充阶段可稍后重试。
            </p>
          )}
          <ImportResult
            run={run}
            retrying={dataImport.retryingStage}
            rechecking={dataImport.recheckingRun}
            onRetry={(stage) => void dataImport.retryStage({ runId: run.run_id, stage })}
            onRecheck={() => void dataImport.recheckRun(run.run_id)}
          />
        </div>
      )}

      <section className="space-y-2" aria-label="导入运行历史">
        <div className="flex items-center gap-2 text-[12px] font-semibold"><History className="size-4" />运行历史</div>
        {history.length === 0 && !dataImport.historyLoading ? (
          <p className="rounded-xl border border-dashed border-border p-3 text-[11px] text-muted-foreground">暂无持久运行记录。</p>
        ) : (
          <div className="divide-y divide-border/70 rounded-xl border border-border/70">
            {history.map((item) => (
              <button key={item.run_id} type="button" className="flex min-h-11 w-full min-w-0 items-center gap-3 px-3 py-2 text-left hover:bg-muted/40" onClick={() => setSelectedRunId(item.run_id)}>
                {item.status === 'succeeded' ? <CheckCircle2 className="size-4 shrink-0 text-emerald-500" /> : ['failed', 'blocked', 'retryable_failed', 'superseded'].includes(item.status) ? <AlertCircle className="size-4 shrink-0 text-red-500" /> : <Clock3 className="size-4 shrink-0 text-amber-500" />}
                <span className="min-w-0 flex-1"><strong className="block truncate text-[11px]">{item.message || item.status}</strong><small className="mt-0.5 block text-[9px] text-muted-foreground">{formatDate(item.started_at)} · {item.publication_state}</small></span>
                <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
              </button>
            ))}
          </div>
        )}
        {dataImport.hasNextHistoryPage && (
          <Button className="min-h-11 w-full" variant="outline" size="sm" disabled={dataImport.isFetchingNextHistoryPage} onClick={() => void dataImport.fetchNextHistoryPage()}>
            {dataImport.isFetchingNextHistoryPage ? '正在加载…' : '加载更早记录'}
          </Button>
        )}
      </section>
    </div>
  )
}
