import { useState, useMemo, useCallback, useEffect, useRef } from 'react'
import { parseISO } from 'date-fns'
import { Calendar as CalendarIcon, MessageSquare } from 'lucide-react'

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
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Calendar } from '@/components/ui/calendar'
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
    // Clear report context when switching to a different session
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
                    <Popover open={weekPickerOpen} onOpenChange={setWeekPickerOpen}>
                      <PopoverTrigger asChild>
                        <button className={`${dateInputClass} cursor-pointer flex items-center gap-1.5 hover:border-accent-foreground/20 transition-colors`}>
                          <CalendarIcon className="h-3 w-3 text-muted-foreground/50 shrink-0" />
                          <span className="truncate">{weekStart} ~ {weekEnd}</span>
                        </button>
                      </PopoverTrigger>
                      <PopoverContent className="w-auto p-0 bg-card/80 backdrop-blur-xl border-border/60 shadow-xl" align="start" sideOffset={8}>
                        <Calendar
                          mode="single"
                          month={parseISO(weekStart)}
                          endMonth={latestRange.latestDate ? parseISO(latestRange.latestDate) : undefined}
                          modifiers={{
                            selectedWeek: [{ from: parseISO(weekStart), to: parseISO(weekEnd) }]
                          }}
                          modifiersClassNames={{
                            selectedWeek: '!bg-accent-foreground/12 !text-accent-foreground font-semibold rounded-none first:rounded-l-full last:rounded-r-full'
                          }}
                          onDayClick={(day) => {
                            const start = day
                            const end = new Date(start.getTime() + 6 * DAY_MS)
                            userChangedRange.current = true
                            setWeekStart(fmt(start))
                            setWeekEnd(fmt(end))
                            setWeekPickerOpen(false)
                          }}
                          footer="点击日期选择以该日开始的 7 天"
                        />
                      </PopoverContent>
                    </Popover>
                  </>
                )}

                {reportType === 'monthly' && (
                  <>
                    <QuickPills
                      options={monthlyQuickOptions}
                      current={month}
                      onSelect={handleMonthlyQuick}
                    />
                    <Popover open={monthPickerOpen} onOpenChange={setMonthPickerOpen}>
                      <PopoverTrigger asChild>
                        <button className={`${dateInputClass} cursor-pointer flex items-center gap-1.5 hover:border-accent-foreground/20 transition-colors`}>
                          <CalendarIcon className="h-3 w-3 text-muted-foreground/50 shrink-0" />
                          <span>{month}</span>
                        </button>
                      </PopoverTrigger>
                      <PopoverContent className="w-auto p-0 bg-card/80 backdrop-blur-xl border-border/60 shadow-xl" align="start" sideOffset={8}>
                        <Calendar
                          mode="single"
                          defaultView="months"
                          month={parseISO(`${month}-01`)}
                          endMonth={latestRange.latestDate ? parseISO(latestRange.latestDate) : undefined}
                          onMonthSelect={(monthIdx, year) => {
                            userChangedRange.current = true
                            const m = `${year}-${String(monthIdx + 1).padStart(2, '0')}`
                            setMonth(m)
                            setYearForMonthly(year)
                            setMonthPickerOpen(false)
                          }}
                        />
                      </PopoverContent>
                    </Popover>
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
