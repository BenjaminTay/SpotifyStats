import { useRef, useState } from 'react'
import { CalendarDays, ChevronLeft, ChevronRight } from 'lucide-react'

import {
  MobileBottomSheet,
  MobilePageHeader,
  MobileRankList,
} from '@/components/mobile'
import { cn } from '@/lib/utils'
import { displayName } from '@/lib/chinese'
import { getBillboardName } from '@/lib/billboard-name'
import type { BillboardWeeklyResponse } from '@/types/billboard'
import {
  BILLBOARD_WEEKLY_TABS,
  computeWeeklyRankChange,
  formatBillboardNumber,
  formatDateRange,
  formatWeekLabel,
  weeklyChangeLabel,
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
  page: number
  totalPages: number
  pageSize: number
  onPageChange: (page: number) => void
}

interface MobileWeekSelectorProps {
  allWeeks: string[]
  selectedWeek: string
  currentIndex: number
  totalWeeks: number
  onPreviousWeek: () => void
  onNextWeek: () => void
  onGoToWeek: (week: string) => void
}

function MobileWeekSelector({
  allWeeks,
  selectedWeek,
  currentIndex,
  totalWeeks,
  onPreviousWeek,
  onNextWeek,
  onGoToWeek,
}: MobileWeekSelectorProps) {
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const groupedWeeks = allWeeks.reduce<Map<string, string[]>>((groups, week) => {
    const year = week.slice(0, 4)
    groups.set(year, [...(groups.get(year) ?? []), week])
    return groups
  }, new Map())

  const chooseWeek = (week: string) => {
    onGoToWeek(week)
    setOpen(false)
  }

  return (
    <>
      <div className="mobile-week-selector">
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
          ref={triggerRef}
          type="button"
          className="mobile-week-trigger"
          onClick={() => setOpen(true)}
          aria-haspopup="dialog"
          aria-expanded={open}
        >
          <CalendarDays aria-hidden="true" />
          <span>
            <strong>{formatWeekLabel(selectedWeek)}</strong>
            <small>{formatDateRange(selectedWeek)}</small>
          </span>
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

      <MobileBottomSheet
        open={open}
        onOpenChange={setOpen}
        title="选择榜单周次"
        eyebrow="Chart history"
        description="切换后会更新地址，可分享也可用浏览器返回。"
        triggerRef={triggerRef}
        dataSheet="billboard-week"
      >
        <div className="mobile-week-groups">
          {[...groupedWeeks.entries()].map(([year, weeks]) => (
            <section key={year} className="mobile-week-group">
              <h3>{year}</h3>
              <div>
                {weeks.map((week) => (
                  <button
                    key={week}
                    type="button"
                    className={cn(week === selectedWeek && 'active')}
                    aria-current={week === selectedWeek ? 'date' : undefined}
                    data-mobile-autofocus={week === selectedWeek ? 'true' : undefined}
                    onClick={() => chooseWeek(week)}
                  >
                    <strong>{formatWeekLabel(week)}</strong>
                    <span>{formatDateRange(week)}</span>
                  </button>
                ))}
              </div>
            </section>
          ))}
        </div>
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
  page,
  totalPages,
  pageSize,
  onPageChange,
}: MobileBillboardWeeklyProps) {
  const pageEntries = entries.slice((page - 1) * pageSize, page * pageSize)

  return (
    <div className="mobile-m3-page" data-mobile-page="billboard-weekly">
      <MobilePageHeader
        eyebrow="Chart / Weekly"
        title="本周榜单"
        description={`${getBillboardName()} 的个人周榜，周次与排名沿用桌面端同一统计口径。`}
        meta={<span>{formatDateRange(selectedWeek)}</span>}
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

      <MobileWeekSelector
        allWeeks={data.meta.all_weeks_desc}
        selectedWeek={selectedWeek}
        currentIndex={currentIndex}
        totalWeeks={totalWeeks}
        onPreviousWeek={onPreviousWeek}
        onNextWeek={onNextWeek}
        onGoToWeek={onGoToWeek}
      />

      <dl className="mobile-billboard-summary">
        <div><dt>新入榜</dt><dd>{summary.newCount}</dd></div>
        <div><dt>重回榜</dt><dd>{summary.reCount}</dd></div>
        <div><dt>最高播放</dt><dd>{formatBillboardNumber(summary.maxPlays)}</dd></div>
        <div><dt>当周总播放</dt><dd>{formatBillboardNumber(summary.totalPlays)}</dd></div>
      </dl>

      <MobileRankList
        eyebrow={`${formatWeekLabel(selectedWeek)} / ${BILLBOARD_WEEKLY_TABS.find((tab) => tab.key === activeTab)?.label ?? ''}`}
        title="完整周榜"
        rows={pageEntries.map((entry) => {
          const change = computeWeeklyRankChange(entry, previousEntries, historicalEntries, activeTab)
          return {
            entityType: activeTab === 'tracks' ? 'track' : activeTab === 'albums' ? 'album' : 'artist',
            rank: entry.rank,
            title: displayName(weeklyEntryName(entry, activeTab)),
            subtitle: displayName(weeklyEntrySubtitle(entry, activeTab)),
            coverUrl: entry.cover_url,
            metric: formatBillboardNumber(entry.play_count),
            metricLabel: '播放',
            facts: [
              { label: 'PK', value: `#${entry.running_peak ?? entry.rank}` },
              { label: '在榜', value: `${entry.running_wks ?? 1}周` },
            ],
            badges: [weeklyChangeLabel(change)],
            to: weeklyEntryDetailLink(entry, activeTab),
          }
        })}
        emptyTitle="当前周次没有榜单数据"
        page={page}
        pageCount={totalPages}
        onPageChange={onPageChange}
      />

      <p className="mobile-billboard-footer">
        共 {summary.total} {weeklyEntityLabel(activeTab)} · 数据更新时间 {new Date().toLocaleDateString('zh-CN')}
      </p>
    </div>
  )
}
