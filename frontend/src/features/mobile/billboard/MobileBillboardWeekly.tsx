import { useRef, useState } from 'react'
import { CalendarDays, ChevronDown, ChevronLeft, ChevronRight } from 'lucide-react'

import {
  MobileBottomSheet,
  MobilePageHeader,
  MobileRankList,
} from '@/components/mobile'
import { ChangeCell } from '@/components/shared/ChangeCell'
import { BillboardWeekCalendar } from '@/components/shared/WeekSelector'
import { cn } from '@/lib/utils'
import { displayName } from '@/lib/chinese'
import type { BillboardWeeklyResponse } from '@/types/billboard'
import {
  BILLBOARD_WEEKLY_TABS,
  computeWeeklyRankChange,
  formatBillboardNumber,
  formatDateRange,
  formatWeekLabel,
  weeklyEntityLabel,
  weeklyEntryDetailLink,
  weeklyEntryName,
  weeklyEntrySubtitle,
  type BillboardWeeklyEntry,
  type BillboardWeeklySummary,
  type BillboardWeeklyTab,
} from '@/features/billboard/weekly/weeklyPresentation'

interface MobileBillboardWeeklyProps {
  data: BillboardWeeklyResponse
  activeTab: BillboardWeeklyTab
  onTabChange: (tab: BillboardWeeklyTab) => void
  selectedWeek: string
  currentIndex: number
  totalWeeks: number
  onPreviousWeek: () => void
  onNextWeek: () => void
  onGoToWeek: (week: string) => void
  entries: BillboardWeeklyEntry[]
  previousEntries: BillboardWeeklyEntry[]
  historicalEntries: BillboardWeeklyEntry[]
  summary: BillboardWeeklySummary
}

interface MobileWeekHeaderProps {
  allWeeks: string[]
  selectedWeek: string
  currentIndex: number
  totalWeeks: number
  onPreviousWeek: () => void
  onNextWeek: () => void
  onGoToWeek: (week: string) => void
}

function MobileWeekHeader({
  allWeeks,
  selectedWeek,
  currentIndex,
  totalWeeks,
  onPreviousWeek,
  onNextWeek,
  onGoToWeek,
}: MobileWeekHeaderProps) {
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)

  return (
    <>
      <MobilePageHeader
        eyebrow="Chart / Weekly"
        title={formatWeekLabel(selectedWeek)}
        meta={(
          <button
            ref={triggerRef}
            type="button"
            className="mobile-week-date-trigger"
            onClick={() => setOpen(true)}
            aria-label={`选择榜单周次：${formatWeekLabel(selectedWeek)}，${formatDateRange(selectedWeek)}`}
            aria-haspopup="dialog"
            aria-expanded={open}
          >
            <CalendarDays aria-hidden="true" />
            <span>{formatDateRange(selectedWeek)}</span>
            <ChevronDown aria-hidden="true" />
          </button>
        )}
        actions={(
          <div className="mobile-week-header-actions" role="group" aria-label="切换榜单周次">
            <button
              type="button"
              className="mobile-icon-button"
              onClick={onPreviousWeek}
              disabled={currentIndex >= totalWeeks - 1}
              aria-label="查看更早一周"
            >
              <ChevronLeft aria-hidden="true" />
            </button>
            <button
              type="button"
              className="mobile-icon-button"
              onClick={onNextWeek}
              disabled={currentIndex <= 0}
              aria-label="查看更新一周"
            >
              <ChevronRight aria-hidden="true" />
            </button>
          </div>
        )}
      />

      <MobileBottomSheet
        open={open}
        onOpenChange={setOpen}
        title="选择榜单周次"
        eyebrow="Chart history"
        triggerRef={triggerRef}
        dataSheet="billboard-week"
      >
        <BillboardWeekCalendar
          className="mobile-billboard-week-calendar"
          allWeeks={allWeeks}
          selectedWeek={selectedWeek}
          onGoToWeek={onGoToWeek}
          onWeekSelected={() => setOpen(false)}
        />
      </MobileBottomSheet>
    </>
  )
}

export function MobileBillboardWeekly({
  data,
  activeTab,
  onTabChange,
  selectedWeek,
  currentIndex,
  totalWeeks,
  onPreviousWeek,
  onNextWeek,
  onGoToWeek,
  entries,
  previousEntries,
  historicalEntries,
  summary,
}: MobileBillboardWeeklyProps) {
  return (
    <div className="mobile-m3-page" data-mobile-page="billboard-weekly">
      <MobileWeekHeader
        allWeeks={data.meta.all_weeks_desc}
        selectedWeek={selectedWeek}
        currentIndex={currentIndex}
        totalWeeks={totalWeeks}
        onPreviousWeek={onPreviousWeek}
        onNextWeek={onNextWeek}
        onGoToWeek={onGoToWeek}
      />

      <div className="mobile-segmented" role="group" aria-label="Billboard 榜单类型">
        {BILLBOARD_WEEKLY_TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={cn(activeTab === tab.key && 'active')}
            onClick={() => onTabChange(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <dl className="mobile-billboard-summary mobile-billboard-summary-compact">
        <div><dt>新入榜</dt><dd>{summary.newCount}</dd></div>
        <div><dt>重回榜</dt><dd>{summary.reCount}</dd></div>
        <div><dt>最高播放</dt><dd>{formatBillboardNumber(summary.maxPlays)}</dd></div>
        <div><dt>当周播放</dt><dd>{formatBillboardNumber(summary.totalPlays)}</dd></div>
      </dl>

      <MobileRankList
        rows={entries.map((entry) => {
          const change = computeWeeklyRankChange(entry, previousEntries, historicalEntries, activeTab)
          return {
            entityType: activeTab === 'tracks' ? 'track' : activeTab === 'albums' ? 'album' : 'artist',
            rank: entry.rank,
            rankAdornment: <ChangeCell change={change} />,
            title: displayName(weeklyEntryName(entry, activeTab)),
            subtitle: displayName(weeklyEntrySubtitle(entry, activeTab)),
            coverUrl: entry.cover_url,
            metric: formatBillboardNumber(entry.play_count),
            metricLabel: '播放',
            facts: [
              { label: 'Peak', value: `${entry.running_peak ?? entry.rank}` },
              { label: '在榜', value: `${entry.running_wks ?? 1}周` },
              { label: '峰值', value: `${entry.running_peak_wks ?? 0}周` },
            ],
            factsLimit: 3,
            to: weeklyEntryDetailLink(entry, activeTab),
            className: 'mobile-weekly-rank-row',
          }
        })}
        emptyTitle="当前周次没有榜单数据"
      />

      <p className="mobile-billboard-footer">
        共 {summary.total} {weeklyEntityLabel(activeTab)} · 数据更新时间 {new Date().toLocaleDateString('zh-CN')}
      </p>
    </div>
  )
}
