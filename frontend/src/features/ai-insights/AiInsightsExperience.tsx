import { useState, useMemo, useCallback, useEffect, useRef } from 'react'
import { MessageSquare } from 'lucide-react'

import { useSettings } from '@/hooks/useSettings'
import {
  useWeeklyDigest,
  useLatestListeningRange,
  useMonthlyPersonality,
  useYearlyStory,
  useChatSessions,
  useDeleteSession,
} from '@/hooks/useAiInsights'

import { ReportCard } from './ReportCard'
import { ChatInterface } from './ChatInterface'
import { ChatSessionList } from './ChatSessionList'
import { ChatSessionDrawer } from './ChatSessionDrawer'
import { REPORT_LABELS, REPORT_DESCRIPTIONS } from './aiInsightsData'
import { LlmNotConfiguredState, EmptyState } from './AiInsightsPrimitives'
import {
  AiInsightsTimeSelectors,
  weekRangeEndingAt,
  monthValueFrom,
  currentWeekRange,
  currentMonthValue,
} from './AiInsightsTimeSelectors'
import type { ReportType } from '@/types/ai-insights'

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
  const currentWeek = useMemo(() => currentWeekRange(), [])
  const [weekStart, setWeekStart] = useState(currentWeek.start)
  const [weekEnd, setWeekEnd] = useState(currentWeek.end)
  const weeklyQuickValue = `${weekStart}_${weekEnd}`

  // Monthly state
  const currentMonth = useMemo(() => currentMonthValue(), [])
  const [month, setMonth] = useState(currentMonth)
  const [yearForMonthly, setYearForMonthly] = useState(now.getFullYear())

  // Yearly state
  const [year, setYear] = useState(now.getFullYear())

  // Chat session management
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null)
  const [sessionDrawerOpen, setSessionDrawerOpen] = useState(false)
  const [chatResetKey, setChatResetKey] = useState(0)
  const { data: sessions = [], isLoading: sessionsLoading } = useChatSessions()
  const deleteSession = useDeleteSession()

  // Date picker popovers
  const [weekPickerOpen, setWeekPickerOpen] = useState(false)
  const [monthPickerOpen, setMonthPickerOpen] = useState(false)

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
    setActiveSessionId(null)
    setChatResetKey((k) => k + 1)
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

  // Session handlers
  const handleSessionCreated = useCallback((id: number) => {
    setActiveSessionId(id)
  }, [])

  const handleSessionSelect = useCallback((id: number) => {
    setActiveSessionId(id)
    setChatContext(undefined)
    setChatContextLabel(undefined)
    setChatInitialQuestion(null)
  }, [])

  const handleSessionDelete = useCallback((id: number) => {
    deleteSession.mutate(id)
    if (activeSessionId === id) {
      setActiveSessionId(null)
    }
  }, [deleteSession, activeSessionId])

  const handleSessionNew = useCallback(() => {
    setActiveSessionId(null)
    setChatInitialQuestion(null)
    setChatContext(undefined)
    setChatContextLabel(undefined)
    setChatResetKey((k) => k + 1)
  }, [])

  // ── Quick-select handlers ───────────────────────────────────────────────

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
      {
        label: '上月',
        value: latestRange.latestDate
          ? monthValueFrom(latestRange.latestDate, -1)
          : currentMonth,
      },
      {
        label: '最新月',
        value: latestRange.latestDate ? latestRange.latestDate.slice(0, 7) : currentMonth,
      },
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

  const handleWeeklyQuick = (v: string) => {
    const [s, e] = v.split('_')
    userChangedRange.current = true
    setWeekStart(s)
    setWeekEnd(e)
  }

  const handleWeeklyChange = (start: string, end: string) => {
    userChangedRange.current = true
    setWeekStart(start)
    setWeekEnd(end)
  }

  const handleMonthlyQuick = (v: string) => {
    userChangedRange.current = true
    setMonth(v)
    const y = parseInt(v.split('-')[0], 10)
    if (!isNaN(y)) setYearForMonthly(y)
  }

  const handleMonthlyChange = (m: string, y: number) => {
    userChangedRange.current = true
    setMonth(m)
    setYearForMonthly(y)
  }

  const handleYearlyQuick = (v: string) => {
    userChangedRange.current = true
    setYear(parseInt(v, 10) || now.getFullYear())
  }

  const handleYearlyChange = (y: number) => {
    userChangedRange.current = true
    setYear(y)
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <section className="mb-8">
        <p className="mb-4 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
          AI / Insights
        </p>
        <h1 className="font-serif text-[48px] font-bold leading-[1.06] tracking-[-1.2px]">
          AI 洞察
        </h1>
      </section>

      {/* Tab switcher */}
      <nav className="mb-7 flex gap-x-6 border-b border-border">
        {(['reports', 'chat'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`pb-2.5 font-sans text-[13px] font-medium border-b-2 transition-colors -mb-[1px] ${
              activeTab === tab
                ? 'border-accent-foreground text-foreground font-semibold'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            {tab === 'reports' ? '报告' : '问答'}
          </button>
        ))}
      </nav>

      {/* Content */}
      {!llmAvailable ? (
        <LlmNotConfiguredState />
      ) : (
        <>
          {/* Reports tab */}
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
              <AiInsightsTimeSelectors
                reportType={reportType}
                weekStart={weekStart}
                weekEnd={weekEnd}
                onWeekChange={handleWeeklyChange}
                weekPickerOpen={weekPickerOpen}
                onWeekPickerOpenChange={setWeekPickerOpen}
                latestDate={latestRange.latestDate}
                weeklyQuickOptions={weeklyQuickOptions}
                weeklyQuickValue={weeklyQuickValue}
                onWeeklyQuick={handleWeeklyQuick}
                month={month}
                onMonthChange={handleMonthlyChange}
                monthPickerOpen={monthPickerOpen}
                onMonthPickerOpenChange={setMonthPickerOpen}
                monthlyQuickOptions={monthlyQuickOptions}
                onMonthlyQuick={handleMonthlyQuick}
                year={year}
                onYearChange={handleYearlyChange}
                nowYear={now.getFullYear()}
                yearlyQuickOptions={yearlyQuickOptions}
                onYearlyQuick={handleYearlyQuick}
              />
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

          {/* Chat tab */}
          <div className={activeTab === 'chat' ? '' : 'hidden'}>
            <div className="flex w-full min-w-0 gap-8">
              {/* Main chat column */}
              <div className="min-w-0 flex-1">
                <ChatInterface
                  key={chatResetKey}
                  initialQuestion={chatInitialQuestion}
                  onQuestionConsumed={handleChatQuestionConsumed}
                  reportContext={chatContext}
                  reportContextLabel={chatContextLabel}
                  onBackToReport={handleBackToReport}
                  sessionId={activeSessionId}
                  onSessionCreated={handleSessionCreated}
                />
              </div>

              {/* Desktop sidebar */}
              <aside className="w-[340px] shrink-0 hidden lg:block">
                <div className="sticky top-4 max-h-[calc(100vh-2rem)] overflow-y-auto scrollbar-thin rounded-[16px] border border-border bg-card/30 backdrop-blur-[12px]">
                  <ChatSessionList
                    sessions={sessions}
                    activeId={activeSessionId}
                    onSelect={handleSessionSelect}
                    onDelete={handleSessionDelete}
                    onNew={handleSessionNew}
                    loading={sessionsLoading}
                  />
                </div>
              </aside>
            </div>

            {/* Mobile floating button */}
            <button
              onClick={() => setSessionDrawerOpen(true)}
              className="lg:hidden fixed bottom-6 right-6 z-30 flex h-11 w-11 items-center justify-center rounded-full border border-border bg-card/80 backdrop-blur-xl shadow-lg transition-colors hover:bg-card"
              aria-label="对话历史"
            >
              <MessageSquare className="h-5 w-5 text-muted-foreground" />
            </button>

            {/* Mobile drawer */}
            <ChatSessionDrawer
              open={sessionDrawerOpen}
              onClose={() => setSessionDrawerOpen(false)}
              sessions={sessions}
              activeId={activeSessionId}
              onSelect={handleSessionSelect}
              onDelete={handleSessionDelete}
              onNew={handleSessionNew}
              loading={sessionsLoading}
            />
          </div>
        </>
      )}
    </div>
  )
}
