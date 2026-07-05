import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { useLatestListeningRange } from '@/hooks/useAiInsights'
import { useAiTask, useCancelAiTask, useStartReportTask } from '@/hooks/useAiTasks'
import type { ReportTaskRequest } from '@/hooks/useAiTasks'
import type { ReportEntities, ReportType } from '@/types/ai-insights'
import type { AiTaskCreatePayload } from '@/types/ai-tasks'
import { AITaskProgress } from '@/features/ai-tasks/AITaskProgress'
import {
  isVisualYearlyArtifact,
  type VisualYearlyArtifact,
} from '@/features/ai-insights/yearly-artifact/yearlyArtifactTypes'

import { EmptyState } from './AiInsightsPrimitives'
import {
  AiInsightsTimeSelectors,
  currentMonthValue,
  currentWeekRange,
  monthValueFrom,
  weekRangeEndingAt,
} from './AiInsightsTimeSelectors'
import { REPORT_DESCRIPTIONS, REPORT_LABELS } from './aiInsightsData'
import { buildAiTaskFilterPayload } from './aiTaskFilters'
import { ReportCard } from './ReportCard'

interface ReportTaskResult {
  success?: boolean
  report: string | null
  artifact: VisualYearlyArtifact | null
  cached: boolean
  cached_at: string | null
  entities: ReportEntities | null
  metadata: Record<string, unknown> | null
  error?: string | null
  needs_generation?: boolean
}

interface CurrentReportTaskState {
  key: string
  mode: 'cache' | 'generate'
  taskId: string | null
  result: ReportTaskResult | null
  error: string | null
}

interface AiReportsPanelProps {
  settings: unknown
  onFollowUp: (question: string, label: string, reportType: ReportType) => void
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value != null && typeof value === 'object' && !Array.isArray(value)
}

function normalizeEntities(value: unknown): ReportEntities | null {
  if (!isRecord(value)) return null
  const artists = Array.isArray(value.artists)
    ? value.artists.filter((item): item is string => typeof item === 'string')
    : []
  const tracks = Array.isArray(value.tracks)
    ? value.tracks.filter((item): item is string => typeof item === 'string')
    : []
  return { artists, tracks }
}

function reportResultFromPayload(value: unknown): ReportTaskResult | null {
  if (!isRecord(value)) return null
  return {
    success: typeof value.success === 'boolean' ? value.success : undefined,
    report: typeof value.report === 'string' ? value.report : null,
    artifact: isVisualYearlyArtifact(value.artifact) ? value.artifact : null,
    cached: value.cached === true,
    cached_at: typeof value.cached_at === 'string' ? value.cached_at : null,
    entities: normalizeEntities(value.entities),
    metadata: isRecord(value.metadata) ? value.metadata : null,
    error: typeof value.error === 'string' ? value.error : null,
    needs_generation: value.needs_generation === true,
  }
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

export function AiReportsPanel({ settings, onFollowUp }: AiReportsPanelProps) {
  const latestRange = useLatestListeningRange()
  const defaultRangeApplied = useRef(false)
  const userChangedRange = useRef(false)
  const [defaultRangeReady, setDefaultRangeReady] = useState(false)
  const now = useMemo(() => new Date(), [])

  const [reportType, setReportType] = useState<ReportType>('weekly')
  const currentWeek = useMemo(() => currentWeekRange(), [])
  const [weekStart, setWeekStart] = useState(currentWeek.start)
  const [weekEnd, setWeekEnd] = useState(currentWeek.end)
  const currentMonth = useMemo(() => currentMonthValue(), [])
  const [month, setMonth] = useState(currentMonth)
  const [yearForMonthly, setYearForMonthly] = useState(now.getFullYear())
  const [year, setYear] = useState(now.getFullYear())
  const [weekPickerOpen, setWeekPickerOpen] = useState(false)
  const [monthPickerOpen, setMonthPickerOpen] = useState(false)

  const { mutateAsync: startReportTask, isPending: startingReportTask } = useStartReportTask()
  const cancelReportTask = useCancelAiTask()
  const [currentReportTask, setCurrentReportTask] = useState<CurrentReportTaskState | null>(null)
  const [activeReportTaskId, setActiveReportTaskId] = useState<string | null>(null)
  const reportPayloadKeyRef = useRef<string | null>(null)
  const activeReportTask = useAiTask(activeReportTaskId)

  useEffect(() => {
    if (!latestRange.latestDate || defaultRangeApplied.current || userChangedRange.current) return

    const latestWeek = weekRangeEndingAt(latestRange.latestDate)
    const latestMonth = latestRange.latestDate.slice(0, 7)
    const latestYear = parseInt(latestRange.latestDate.slice(0, 4), 10)

    setWeekStart(latestWeek.start)
    setWeekEnd(latestWeek.end)
    setMonth(latestMonth)
    if (!isNaN(latestYear)) {
      setYearForMonthly(latestYear)
      setYear(latestYear)
    }
    defaultRangeApplied.current = true
    setDefaultRangeReady(true)
  }, [latestRange.latestDate])

  const reportPayload = useMemo<ReportTaskRequest>(() => {
    const basePayload = buildAiTaskFilterPayload(settings)
    if (reportType === 'weekly') {
      return {
        report_type: 'weekly',
        action: 'cache_only',
        week_start: weekStart,
        week_end: weekEnd,
        ...basePayload,
      }
    }
    if (reportType === 'monthly') {
      return {
        report_type: 'monthly',
        action: 'cache_only',
        month,
        year: yearForMonthly,
        ...basePayload,
      }
    }
    return {
      report_type: 'yearly',
      action: 'cache_only',
      report_mode: 'visual_yearly_artifact',
      writer_pipeline: 'agent_synthesis_v2',
      year,
      ...basePayload,
    }
  }, [month, reportType, settings, weekEnd, weekStart, year, yearForMonthly])

  const reportPayloadKey = useMemo(() => JSON.stringify(reportPayload), [reportPayload])
  const reportsReady = !latestRange.loading
    && (userChangedRange.current || defaultRangeReady || !latestRange.latestDate)

  const startCacheCheck = useCallback(async () => {
    const key = reportPayloadKey
    reportPayloadKeyRef.current = key
    setActiveReportTaskId(null)
    setCurrentReportTask({ key, mode: 'cache', taskId: null, result: null, error: null })

    try {
      const response = await startReportTask({ ...reportPayload, action: 'cache_only' })
      if (reportPayloadKeyRef.current !== key) return
      setCurrentReportTask({
        key,
        mode: 'cache',
        taskId: response.task_id,
        result: reportResultFromPayload(response.result),
        error: null,
      })
    } catch (error) {
      if (reportPayloadKeyRef.current !== key) return
      setCurrentReportTask({ key, mode: 'cache', taskId: null, result: null, error: errorMessage(error) })
    }
  }, [reportPayload, reportPayloadKey, startReportTask])

  const startGenerateReport = useCallback(async () => {
    const key = reportPayloadKey
    reportPayloadKeyRef.current = key
    setActiveReportTaskId(null)
    setCurrentReportTask({ key, mode: 'generate', taskId: null, result: null, error: null })

    try {
      const response: AiTaskCreatePayload = await startReportTask({
        ...reportPayload,
        action: 'generate',
        force: true,
      })
      if (reportPayloadKeyRef.current !== key) return
      setActiveReportTaskId(response.task_id)
      setCurrentReportTask({
        key,
        mode: 'generate',
        taskId: response.task_id,
        result: reportResultFromPayload(response.result),
        error: null,
      })
    } catch (error) {
      if (reportPayloadKeyRef.current !== key) return
      setCurrentReportTask({ key, mode: 'generate', taskId: null, result: null, error: errorMessage(error) })
    }
  }, [reportPayload, reportPayloadKey, startReportTask])

  useEffect(() => {
    if (reportsReady) void startCacheCheck()
  }, [reportsReady, startCacheCheck])

  useEffect(() => {
    if (!activeReportTaskId || !activeReportTask.task) return
    const taskResult = reportResultFromPayload(activeReportTask.task.result)
    const taskError = activeReportTask.task.status === 'error'
      ? activeReportTask.task.error || activeReportTask.error
      : null

    setCurrentReportTask((previous) => {
      if (!previous || previous.taskId !== activeReportTaskId) return previous
      return { ...previous, result: taskResult ?? previous.result, error: taskError }
    })
    if (
      activeReportTask.task.status === 'done'
      || activeReportTask.task.status === 'error'
      || activeReportTask.task.status === 'cancelled'
    ) {
      setActiveReportTaskId(null)
    }
  }, [activeReportTask.error, activeReportTask.task, activeReportTaskId])

  const weeklyQuickValue = `${weekStart}_${weekEnd}`
  const weeklyQuickOptions = useMemo(
    () => [
      {
        label: '前 7 天',
        value: latestRange.latestDate
          ? `${weekRangeEndingAt(latestRange.latestDate, -1).start}_${weekRangeEndingAt(latestRange.latestDate, -1).end}`
          : `${currentWeek.start}_${currentWeek.end}`,
      },
      {
        label: '近 7 天',
        value: latestRange.latestDate
          ? `${weekRangeEndingAt(latestRange.latestDate).start}_${weekRangeEndingAt(latestRange.latestDate).end}`
          : `${currentWeek.start}_${currentWeek.end}`,
      },
    ],
    [latestRange.latestDate, currentWeek],
  )

  const monthlyQuickOptions = useMemo(
    () => [
      { label: '上月', value: latestRange.latestDate ? monthValueFrom(latestRange.latestDate, -1) : currentMonth },
      { label: '最新月', value: latestRange.latestDate ? latestRange.latestDate.slice(0, 7) : currentMonth },
    ],
    [latestRange.latestDate, currentMonth],
  )

  const yearlyQuickOptions = useMemo(
    () => [
      { label: '去年', value: String(now.getFullYear() - 1) },
      { label: '今年', value: String(now.getFullYear()) },
    ],
    [now],
  )

  const handleWeeklyQuick = (value: string) => {
    const [start, end] = value.split('_')
    userChangedRange.current = true
    setWeekStart(start)
    setWeekEnd(end)
  }

  const handleMonthlyQuick = (value: string) => {
    userChangedRange.current = true
    setMonth(value)
    const parsedYear = parseInt(value.split('-')[0], 10)
    if (!isNaN(parsedYear)) setYearForMonthly(parsedYear)
  }

  const handleReportTypeChange = (type: ReportType) => {
    if (type === reportType) return
    reportPayloadKeyRef.current = null
    setActiveReportTaskId(null)
    setCurrentReportTask(null)
    setReportType(type)
  }

  const handleReportRetry = useCallback(() => {
    if (currentReportTask?.mode === 'cache' && currentReportTask.error) {
      void startCacheCheck()
      return
    }
    void startGenerateReport()
  }, [currentReportTask?.error, currentReportTask?.mode, startCacheCheck, startGenerateReport])

  const handleCancelReport = useCallback(async () => {
    if (!activeReportTaskId) return
    try {
      const task = await cancelReportTask.mutateAsync(activeReportTaskId)
      const taskResult = reportResultFromPayload(task.result)
      setCurrentReportTask((previous) => {
        if (!previous || previous.taskId !== activeReportTaskId) return previous
        return {
          ...previous,
          result: taskResult ?? previous.result,
          error: task.status === 'cancelled'
            ? '报告生成已取消'
            : task.status === 'error'
              ? task.error || '报告生成失败'
              : null,
        }
      })
      if (task.status === 'done' || task.status === 'error' || task.status === 'cancelled') {
        setActiveReportTaskId(null)
      }
    } catch (error) {
      setCurrentReportTask((previous) => previous
        ? { ...previous, error: errorMessage(error) }
        : previous)
    }
  }, [activeReportTaskId, cancelReportTask])

  const reportTaskMatchesCurrentPayload = currentReportTask?.key === reportPayloadKey
  const reportTaskResult = reportTaskMatchesCurrentPayload ? currentReportTask?.result ?? null : null
  const reportTaskError = reportTaskMatchesCurrentPayload
    ? currentReportTask?.error ?? activeReportTask.error
    : null
  const checkingCache = reportTaskMatchesCurrentPayload
    && currentReportTask?.mode === 'cache'
    && startingReportTask
  const generatingReport = reportTaskMatchesCurrentPayload
    && currentReportTask?.mode === 'generate'
    && (
      startingReportTask
        || activeReportTask.loading
        || activeReportTask.task?.status === 'queued'
        || activeReportTask.task?.status === 'running'
    )
  const reportNeedsGeneration = reportTaskResult?.needs_generation === true
  const reportEmptyError = reportTaskResult?.success === false && reportTaskResult.error
    ? reportTaskResult.error
    : null
  const showTaskProgress = reportTaskMatchesCurrentPayload
    && currentReportTask?.mode === 'generate'
    && Boolean(activeReportTaskId)
  const canCancelReport = showTaskProgress && generatingReport
  const reportTitle = reportType === 'weekly'
    ? `${REPORT_LABELS.weekly} · ${weekStart} ~ ${weekEnd}`
    : reportType === 'monthly'
      ? `${REPORT_LABELS.monthly} · ${month}`
      : `${REPORT_LABELS.yearly} · ${year}`

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex gap-1 rounded-full border border-border bg-card/40 p-1 backdrop-blur-[8px]">
          {(Object.keys(REPORT_LABELS) as ReportType[]).map((type) => (
            <button
              key={type}
              onClick={() => handleReportTypeChange(type)}
              aria-pressed={reportType === type}
              className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.8px] transition-all ${
                reportType === type
                  ? 'bg-accent-foreground text-card'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {REPORT_LABELS[type]}
            </button>
          ))}
        </div>

        <AiInsightsTimeSelectors
          reportType={reportType}
          weekStart={weekStart}
          weekEnd={weekEnd}
          onWeekChange={(start, end) => {
            userChangedRange.current = true
            setWeekStart(start)
            setWeekEnd(end)
          }}
          weekPickerOpen={weekPickerOpen}
          onWeekPickerOpenChange={setWeekPickerOpen}
          latestDate={latestRange.latestDate}
          weeklyQuickOptions={weeklyQuickOptions}
          weeklyQuickValue={weeklyQuickValue}
          onWeeklyQuick={handleWeeklyQuick}
          month={month}
          onMonthChange={(nextMonth, nextYear) => {
            userChangedRange.current = true
            setMonth(nextMonth)
            setYearForMonthly(nextYear)
          }}
          monthPickerOpen={monthPickerOpen}
          onMonthPickerOpenChange={setMonthPickerOpen}
          monthlyQuickOptions={monthlyQuickOptions}
          onMonthlyQuick={handleMonthlyQuick}
          year={year}
          onYearChange={(nextYear) => {
            userChangedRange.current = true
            setYear(nextYear)
          }}
          nowYear={now.getFullYear()}
          yearlyQuickOptions={yearlyQuickOptions}
          onYearlyQuick={(value) => {
            userChangedRange.current = true
            setYear(parseInt(value, 10) || now.getFullYear())
          }}
        />
      </div>

      <p className="text-[12px] text-muted-foreground/60">
        {REPORT_DESCRIPTIONS[reportType]}
      </p>

      {reportEmptyError ? (
        <EmptyState message={reportEmptyError} />
      ) : (
        <div className="space-y-4">
          {showTaskProgress && (
            <AITaskProgress task={activeReportTask.task} events={activeReportTask.events} />
          )}
          <ReportCard
            reportType={reportType}
            title={reportTitle}
            report={reportTaskResult?.report ?? null}
            artifact={reportTaskResult?.artifact ?? null}
            cached={reportTaskResult?.cached ?? false}
            cachedAt={reportTaskResult?.cached_at ?? null}
            entities={reportTaskResult?.entities ?? null}
            metadata={reportTaskResult?.metadata ?? null}
            loading={checkingCache || generatingReport}
            fetching={generatingReport}
            error={reportTaskError}
            onRetry={handleReportRetry}
            onCancel={canCancelReport ? handleCancelReport : undefined}
            onFollowUp={(question, label) => onFollowUp(question, label, reportType)}
            showGenerateAction={reportNeedsGeneration}
            generateLoading={generatingReport}
            onGenerate={() => { void startGenerateReport() }}
          />
        </div>
      )}
    </div>
  )
}
