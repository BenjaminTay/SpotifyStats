import { useState } from 'react'

import { useSettings } from '@/hooks/useSettings'
import {
  useWeeklyDigest,
  useMonthlyPersonality,
  useYearlyStory,
} from '@/hooks/useAiInsights'

import { ReportCard } from './ReportCard'
import { ChatInterface } from './ChatInterface'
import { REPORT_LABELS, REPORT_DESCRIPTIONS } from './aiInsightsData'
import { LlmNotConfiguredState, EmptyState } from './AiInsightsPrimitives'
import type { ReportType } from '@/types/ai-insights'

export function AiInsightsExperience() {
  const { settings } = useSettings()
  const llmAvailable = settings?.llm_enabled && settings?.has_llm_key

  const [activeTab, setActiveTab] = useState<'reports' | 'chat'>('reports')
  const [reportType, setReportType] = useState<ReportType>('weekly')

  // Weekly digest state
  const now = new Date()
  const weekAgo = new Date(now.getTime() - 7 * 86400000)
  const fmt = (d: Date) => d.toISOString().slice(0, 10)
  const [weekStart, setWeekStart] = useState(fmt(weekAgo))
  const [weekEnd, setWeekEnd] = useState(fmt(now))

  // Monthly state
  const monthDefault = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  const [month, setMonth] = useState(monthDefault)
  const [yearForMonthly, setYearForMonthly] = useState(now.getFullYear())

  // Yearly state
  const [year, setYear] = useState(now.getFullYear())

  const weekly = useWeeklyDigest(weekStart, weekEnd)
  const monthly = useMonthlyPersonality(month, yearForMonthly)
  const yearly = useYearlyStory(year)

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
      ) : activeTab === 'reports' ? (
        <div className="space-y-6">
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
            <div className="flex items-center gap-2 text-[13px]">
              {reportType === 'weekly' && (
                <div className="flex items-center gap-2 text-[12px] text-muted-foreground">
                  <input
                    type="date"
                    value={weekStart}
                    onChange={(e) => setWeekStart(e.target.value)}
                    className="rounded-full border border-border bg-card/40 px-3 py-1.5 text-[12px] backdrop-blur-[8px] outline-none"
                  />
                  <span>至</span>
                  <input
                    type="date"
                    value={weekEnd}
                    onChange={(e) => setWeekEnd(e.target.value)}
                    className="rounded-full border border-border bg-card/40 px-3 py-1.5 text-[12px] backdrop-blur-[8px] outline-none"
                  />
                </div>
              )}

              {reportType === 'monthly' && (
                <div className="flex items-center gap-2 text-[12px] text-muted-foreground">
                  <input
                    type="month"
                    value={month}
                    onChange={(e) => {
                      setMonth(e.target.value)
                      const y = parseInt(e.target.value.split('-')[0], 10)
                      if (!isNaN(y)) setYearForMonthly(y)
                    }}
                    className="rounded-full border border-border bg-card/40 px-3 py-1.5 text-[12px] backdrop-blur-[8px] outline-none"
                  />
                </div>
              )}

              {reportType === 'yearly' && (
                <div className="flex items-center gap-2 text-[12px] text-muted-foreground">
                  <input
                    type="number"
                    value={year}
                    onChange={(e) => setYear(parseInt(e.target.value, 10) || now.getFullYear())}
                    min={2010}
                    max={now.getFullYear()}
                    className="w-20 rounded-full border border-border bg-card/40 px-3 py-1.5 text-[12px] backdrop-blur-[8px] outline-none"
                  />
                </div>
              )}
            </div>
          </div>

          <p className="text-[12px] text-muted-foreground/60">
            {REPORT_DESCRIPTIONS[reportType]}
          </p>

          {/* Report card */}
          {reportType === 'weekly' && (
            <>
              {weekly.data && !weekly.data.success && weekly.data.error ? (
                <EmptyState message={weekly.data.error} />
              ) : (
                <ReportCard
                  title={`${REPORT_LABELS.weekly} · ${weekStart} ~ ${weekEnd}`}
                  report={weekly.data?.report ?? null}
                  cached={weekly.data?.cached ?? false}
                  loading={weekly.loading}
                  error={weekly.error}
                  onRetry={() => weekly.refetch()}
                />
              )}
            </>
          )}

          {reportType === 'monthly' && (
            <>
              {monthly.data && !monthly.data.success && monthly.data.error ? (
                <EmptyState message={monthly.data.error} />
              ) : (
                <ReportCard
                  title={`${REPORT_LABELS.monthly} · ${month}`}
                  report={monthly.data?.report ?? null}
                  cached={monthly.data?.cached ?? false}
                  loading={monthly.loading}
                  error={monthly.error}
                  onRetry={() => monthly.refetch()}
                />
              )}
            </>
          )}

          {reportType === 'yearly' && (
            <>
              {yearly.data && !yearly.data.success && yearly.data.error ? (
                <EmptyState message={yearly.data.error} />
              ) : (
                <ReportCard
                  title={`${REPORT_LABELS.yearly} · ${year}`}
                  report={yearly.data?.report ?? null}
                  cached={yearly.data?.cached ?? false}
                  loading={yearly.loading}
                  error={yearly.error}
                  onRetry={() => yearly.refetch()}
                />
              )}
            </>
          )}
        </div>
      ) : (
        <ChatInterface />
      )}
    </div>
  )
}
