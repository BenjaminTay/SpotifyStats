import { useState, useMemo, useCallback, useEffect, useRef } from 'react'

import { useSettings } from '@/hooks/useSettings'
import {
  useWeeklyDigest,
  useLatestListeningRange,
  useMonthlyPersonality,
  useYearlyStory,
} from '@/hooks/useAiInsights'

import { ReportCard } from './ReportCard'
import { ChatInterface } from './ChatInterface'
import { REPORT_LABELS, REPORT_DESCRIPTIONS } from './aiInsightsData'
import { LlmNotConfiguredState, EmptyState } from './AiInsightsPrimitives'
import type { ReportType } from '@/types/ai-insights'

// ── Date helpers ──────────────────────────────────────────────────────────

const DAY_MS = 86400000

const fmt = (d: Date) => {
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function parseLocalDate(value: string) {
  return new Date(`${value}T00:00:00`)
}

function weekRange(offset: number) {
  const now = new Date()
  const end = new Date(now.getTime() + offset * 7 * DAY_MS)
  const start = new Date(end.getTime() - 6 * DAY_MS)
  return { start: fmt(start), end: fmt(end) }
}

function weekRangeEndingAt(endDate: string, offsetWeeks = 0) {
  const end = parseLocalDate(endDate)
  end.setDate(end.getDate() + offsetWeeks * 7)
  const start = new Date(end.getTime() - 6 * DAY_MS)
  return { start: fmt(start), end: fmt(end) }
}

function monthValue(offset: number) {
  const now = new Date()
  const d = new Date(now.getFullYear(), now.getMonth() + offset, 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

function monthValueFrom(dateString: string, offset: number) {
  const anchor = parseLocalDate(dateString)
  const d = new Date(anchor.getFullYear(), anchor.getMonth() + offset, 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

// ── Quick-select pills ────────────────────────────────────────────────────

function QuickPills({
  options,
  current,
  onSelect,
}: {
  options: { label: string; value: string }[]
  current: string
  onSelect: (v: string) => void
}) {
  return (
    <div className="flex flex-wrap gap-1">
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onSelect(opt.value)}
          className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.6px] transition-all ${
            current === opt.value
              ? 'bg-accent-foreground/10 text-accent-foreground'
              : 'text-muted-foreground/50 hover:text-muted-foreground'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

// ── Main experience ───────────────────────────────────────────────────────

export function AiInsightsExperience() {
  const { settings } = useSettings()
  const latestRange = useLatestListeningRange()
  const llmAvailable = settings?.llm_enabled && settings?.has_llm_key
  const defaultRangeApplied = useRef(false)
  const userChangedRange = useRef(false)

  const [activeTab, setActiveTab] = useState<'reports' | 'chat'>('reports')
  const [reportType, setReportType] = useState<ReportType>('weekly')

  // Weekly state
  const now = new Date()
  const currentWeek = useMemo(() => weekRange(0), [])
  const [weekStart, setWeekStart] = useState(currentWeek.start)
  const [weekEnd, setWeekEnd] = useState(currentWeek.end)
  const weeklyQuickValue = `${weekStart}_${weekEnd}`

  // Monthly state
  const currentMonth = useMemo(() => monthValue(0), [])
  const [month, setMonth] = useState(currentMonth)
  const [yearForMonthly, setYearForMonthly] = useState(now.getFullYear())

  // Yearly state
  const [year, setYear] = useState(now.getFullYear())

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
  }, [latestRange.latestDate])

  // Chat follow-up from report — capture context at the moment of transition
  const [chatInitialQuestion, setChatInitialQuestion] = useState<string | null>(null)
  const [chatContext, setChatContext] = useState<ReportType | undefined>(undefined)
  const [chatContextLabel, setChatContextLabel] = useState<string | undefined>(undefined)

  // Only fetch the currently active report type
  const reportsReady = !latestRange.loading || defaultRangeApplied.current
  const weeklyActive = reportsReady && activeTab === 'reports' && reportType === 'weekly'
  const monthlyActive = reportsReady && activeTab === 'reports' && reportType === 'monthly'
  const yearlyActive = reportsReady && activeTab === 'reports' && reportType === 'yearly'

  const weekly = useWeeklyDigest(weekStart, weekEnd, weeklyActive)
  const monthly = useMonthlyPersonality(month, yearForMonthly, monthlyActive)
  const yearly = useYearlyStory(year, yearlyActive)

  const handleFollowUp = useCallback((question: string, label: string) => {
    setChatInitialQuestion(question)
    setChatContext(reportType)
    setChatContextLabel(label)
    setActiveTab('chat')
  }, [reportType])

  const handleChatQuestionConsumed = useCallback(() => {
    setChatInitialQuestion(null)
  }, [])

  const handleBackToReport = useCallback(() => {
    setActiveTab('reports')
  }, [])

  const handleClearChatContext = useCallback(() => {
    setChatContext(undefined)
    setChatContextLabel(undefined)
  }, [])

  // ── Quick-select handlers ───────────────────────────────────────────────

  const weeklyQuickOptions = useMemo(
    () => [
      {
        label: '前 7 天',
        value: latestRange.latestDate
          ? `${weekRangeEndingAt(latestRange.latestDate, -1).start}_${weekRangeEndingAt(latestRange.latestDate, -1).end}`
          : `${weekRange(-1).start}_${weekRange(-1).end}`,
      },
      {
        label: '近 7 天',
        value: latestRange.latestDate
          ? `${weekRangeEndingAt(latestRange.latestDate).start}_${weekRangeEndingAt(latestRange.latestDate).end}`
          : `${weekRange(0).start}_${weekRange(0).end}`,
      },
    ],
    [latestRange.latestDate],
  )

  const monthlyQuickOptions = useMemo(
    () => [
      {
        label: '上月',
        value: latestRange.latestDate
          ? monthValueFrom(latestRange.latestDate, -1)
          : monthValue(-1),
      },
      {
        label: '最新月',
        value: latestRange.latestDate ? latestRange.latestDate.slice(0, 7) : monthValue(0),
      },
    ],
    [latestRange.latestDate],
  )

  const yearlyQuickOptions = useMemo(
    () => [
      { label: '去年', value: String(now.getFullYear() - 1) },
      { label: '今年', value: String(now.getFullYear()) },
    ],
    [now],
  )

  const handleWeeklyQuick = (v: string) => {
    const [s, e] = v.split('_')
    userChangedRange.current = true
    setWeekStart(s)
    setWeekEnd(e)
  }

  const handleMonthlyQuick = (v: string) => {
    userChangedRange.current = true
    setMonth(v)
    const y = parseInt(v.split('-')[0], 10)
    if (!isNaN(y)) setYearForMonthly(y)
  }

  const handleYearlyQuick = (v: string) => {
    userChangedRange.current = true
    setYear(parseInt(v, 10) || now.getFullYear())
  }

  const dateInputClass =
    'w-[132px] rounded-full border border-border bg-card/40 px-3 py-1.5 text-[12px] backdrop-blur-[8px] outline-none sm:w-auto'

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="font-serif text-[32px] font-bold tracking-[-0.5px]">AI 洞察</h1>
        <p className="mt-1 text-[13px] text-muted-foreground">
          由 AI 驱动的听歌数据解读与自然语言问答
        </p>
      </div>

      {/* Tab switcher */}
      <div className="flex gap-1 rounded-full border border-border bg-card/40 p-1 backdrop-blur-[8px] w-fit">
        {(['reports', 'chat'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`rounded-full px-4 py-1.5 text-[12px] font-semibold uppercase tracking-[1px] transition-all ${
              activeTab === tab
                ? 'bg-accent-foreground text-card'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            {tab === 'reports' ? '报告' : '问答'}
          </button>
        ))}
      </div>

      {/* Content */}
      {!llmAvailable ? (
        <LlmNotConfiguredState />
      ) : (
        <>
          {/* Reports tab — hidden instead of unmounted */}
          <div className={`space-y-6 ${activeTab === 'reports' ? '' : 'hidden'}`}>
            {/* Report type selector */}
            <div className="flex flex-wrap items-center gap-4">
              <div className="flex gap-1 rounded-full border border-border bg-card/40 p-1 backdrop-blur-[8px]">
                {(Object.keys(REPORT_LABELS) as ReportType[]).map((type) => (
                  <button
                    key={type}
                    onClick={() => setReportType(type)}
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

              {/* Time selectors */}
              <div className="flex min-w-0 flex-wrap items-center gap-3 text-[13px]">
                {reportType === 'weekly' && (
                  <>
                    <QuickPills
                      options={weeklyQuickOptions}
                      current={weeklyQuickValue}
                      onSelect={handleWeeklyQuick}
                    />
                    <div className="flex min-w-0 flex-wrap items-center gap-2 text-[12px] text-muted-foreground">
                      <input
                        type="date"
                        value={weekStart}
                        max={weekEnd}
                        onChange={(e) => {
                          userChangedRange.current = true
                          setWeekStart(e.target.value)
                        }}
                        className={dateInputClass}
                      />
                      <span>至</span>
                      <input
                        type="date"
                        value={weekEnd}
                        min={weekStart}
                        onChange={(e) => {
                          userChangedRange.current = true
                          setWeekEnd(e.target.value)
                        }}
                        className={dateInputClass}
                      />
                      {weekStart > weekEnd && (
                        <span className="text-[11px] text-red-500">起始日期不能晚于结束日期</span>
                      )}
                    </div>
                  </>
                )}

                {reportType === 'monthly' && (
                  <>
                    <QuickPills
                      options={monthlyQuickOptions}
                      current={month}
                      onSelect={handleMonthlyQuick}
                    />
                    <input
                      type="month"
                      value={month}
                      onChange={(e) => {
                        userChangedRange.current = true
                        setMonth(e.target.value)
                        const y = parseInt(e.target.value.split('-')[0], 10)
                        if (!isNaN(y)) setYearForMonthly(y)
                      }}
                      className={dateInputClass}
                    />
                  </>
                )}

                {reportType === 'yearly' && (
                  <>
                    <QuickPills
                      options={yearlyQuickOptions}
                      current={String(year)}
                      onSelect={handleYearlyQuick}
                    />
                    <select
                      value={year}
                      onChange={(e) => {
                        userChangedRange.current = true
                        setYear(parseInt(e.target.value, 10))
                      }}
                      className={`${dateInputClass} cursor-pointer appearance-none`}
                    >
                      {Array.from({ length: now.getFullYear() - 2009 }, (_, i) => now.getFullYear() - i).map(
                        (y) => (
                          <option key={y} value={y}>
                            {y}
                          </option>
                        ),
                      )}
                    </select>
                  </>
                )}
              </div>
            </div>

            <p className="text-[12px] text-muted-foreground/60">
              {REPORT_DESCRIPTIONS[reportType]}
            </p>

            {/* Report cards */}
            <div className={reportType === 'weekly' ? '' : 'hidden'}>
              {weekly.data && !weekly.data.success && weekly.data.error ? (
                <EmptyState message={weekly.data.error} />
              ) : (
                <ReportCard
                  reportType="weekly"
                  title={`${REPORT_LABELS.weekly} · ${weekStart} ~ ${weekEnd}`}
                  report={weekly.data?.report ?? null}
                  cached={weekly.data?.cached ?? false}
                  cachedAt={weekly.cachedAt}
                  entities={weekly.entities}
                  loading={weekly.loading}
                  fetching={weekly.fetching}
                  error={weekly.error}
                  onRetry={() => weekly.refetch()}
                  onCancel={weekly.cancel}
                  onFollowUp={handleFollowUp}
                />
              )}
            </div>

            <div className={reportType === 'monthly' ? '' : 'hidden'}>
              {monthly.data && !monthly.data.success && monthly.data.error ? (
                <EmptyState message={monthly.data.error} />
              ) : (
                <ReportCard
                  reportType="monthly"
                  title={`${REPORT_LABELS.monthly} · ${month}`}
                  report={monthly.data?.report ?? null}
                  cached={monthly.data?.cached ?? false}
                  cachedAt={monthly.cachedAt}
                  entities={monthly.entities}
                  loading={monthly.loading}
                  fetching={monthly.fetching}
                  error={monthly.error}
                  onRetry={() => monthly.refetch()}
                  onCancel={monthly.cancel}
                  onFollowUp={handleFollowUp}
                />
              )}
            </div>

            <div className={reportType === 'yearly' ? '' : 'hidden'}>
              {yearly.data && !yearly.data.success && yearly.data.error ? (
                <EmptyState message={yearly.data.error} />
              ) : (
                <ReportCard
                  reportType="yearly"
                  title={`${REPORT_LABELS.yearly} · ${year}`}
                  report={yearly.data?.report ?? null}
                  cached={yearly.data?.cached ?? false}
                  cachedAt={yearly.cachedAt}
                  entities={yearly.entities}
                  loading={yearly.loading}
                  fetching={yearly.fetching}
                  error={yearly.error}
                  onRetry={() => yearly.refetch()}
                  onCancel={yearly.cancel}
                  onFollowUp={handleFollowUp}
                />
              )}
            </div>
          </div>

          {/* Chat tab — hidden instead of unmounted */}
          <div className={activeTab === 'chat' ? '' : 'hidden'}>
            <ChatInterface
              initialQuestion={chatInitialQuestion}
              onQuestionConsumed={handleChatQuestionConsumed}
              reportContext={chatContext}
              reportContextLabel={chatContextLabel}
              onBackToReport={handleBackToReport}
              onClear={handleClearChatContext}
            />
          </div>
        </>
      )}
    </div>
  )
}
