import { Link } from 'react-router-dom'

import { BillboardSubNav } from '@/components/shared/BillboardSubNav'
import { ChangeCell } from '@/components/shared/ChangeCell'
import { CoverCell } from '@/components/shared/CoverCell'
import { GlassCard } from '@/components/shared/GlassCard'
import { ArtistLinks } from '@/components/shared/ArtistLinks'
import { PaginationBar } from '@/components/shared/PaginationBar'
import { WeekSelector } from '@/components/shared/WeekSelector'
import { cn } from '@/lib/utils'
import { displayName, useChineseTextVersion } from '@/lib/chinese'
import { billboardDetailLink } from '@/lib/navigation'
import { getBillboardName } from '@/lib/billboard-name'
import type { BillboardWeeklyResponse, WeeklyTrackEntry } from '@/types/billboard'
import {
  BILLBOARD_WEEKLY_TABS,
  computeWeeklyRankChange,
  formatBillboardNumber,
  formatDateRange,
  formatWeekLabel,
  weeklyEntryDetailLink,
  weeklyEntityLabel,
  weeklyEntryName,
  weeklyEntrySubtitle,
  type BillboardWeeklyEntry,
  type BillboardWeeklySummary,
  type BillboardWeeklyTab,
} from './weeklyPresentation'

interface DesktopBillboardWeeklyProps {
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

export function DesktopBillboardWeekly({
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
}: DesktopBillboardWeeklyProps) {
  useChineseTextVersion()
  const pageEntries = entries.slice((page - 1) * pageSize, page * pageSize)

  return (
    <>
      <BillboardSubNav active="weekly" />

      <section className="mb-6 mt-6">
        <p className="mb-4 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
          Chart / Weekly
        </p>
        <h1 className="font-serif text-[44px] font-bold leading-[1.06] tracking-[-1.2px]">
          {getBillboardName()} 周榜
        </h1>
      </section>

      <div className="mb-5 flex items-end justify-between border-b border-border">
        <div className="flex gap-7">
          {BILLBOARD_WEEKLY_TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => onTabChange(tab.key)}
              className={cn(
                '-mb-px cursor-pointer border-b-2 border-none bg-transparent px-0 pb-2.5 font-sans text-[13px] font-medium transition-[color,border] duration-200',
                activeTab === tab.key
                  ? 'border-accent-foreground font-semibold text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground',
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <WeekSelector
        weekLabel={formatWeekLabel(selectedWeek)}
        dateRange={formatDateRange(selectedWeek)}
        onPrev={onPreviousWeek}
        onNext={onNextWeek}
        disablePrev={currentIndex >= totalWeeks - 1}
        disableNext={currentIndex <= 0}
        allWeeks={data.meta.all_weeks_desc}
        selectedWeek={selectedWeek}
        onGoToWeek={onGoToWeek}
      />

      <div className="mb-6 flex gap-9 border-b border-border py-4">
        <div>
          <span className="font-serif text-2xl font-semibold text-[#3B5998] dark:text-[#7B9CC8]">{summary.newCount}</span>
          <span className="ml-2 font-sans text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground">新入榜</span>
        </div>
        <div>
          <span className="font-serif text-2xl font-semibold text-[#B8860B] dark:text-[#D4A24E]">{summary.reCount}</span>
          <span className="ml-2 font-sans text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground">重回榜</span>
        </div>
        <div>
          <span className="font-serif text-2xl font-semibold">{formatBillboardNumber(summary.maxPlays)}</span>
          <span className="ml-2 font-sans text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground">当周最高播放</span>
        </div>
        <div>
          <span className="font-serif text-2xl font-semibold">{formatBillboardNumber(summary.totalPlays)}</span>
          <span className="ml-2 font-sans text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground">当周总播放</span>
        </div>
      </div>

      <GlassCard className="overflow-hidden p-0">
        <table className="mx-7 my-0 w-[calc(100%-56px)] border-collapse">
          <thead>
            <tr>
              <th className="w-10 pb-3.5 pt-4 text-center font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">#</th>
              <th className="w-11 pb-3.5 pt-4 font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">变动</th>
              <th className="w-[52px] pb-3.5 pt-4" />
              <th className="pb-3.5 pt-4 text-left font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">名称</th>
              <th className="pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">播放</th>
              <th className="w-14 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">PK</th>
              <th className="w-16 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">PK Wks</th>
              <th className="w-14 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">在榜</th>
            </tr>
          </thead>
          <tbody>
            {pageEntries.map((entry, index) => {
              const dataIndex = (page - 1) * pageSize + index
              const change = computeWeeklyRankChange(entry, previousEntries, historicalEntries, activeTab)
              const isNewOrRe = change.type === 'new' || change.type === 're'
              const rankColor = entry.rank === 1
                ? 'text-accent-foreground'
                : entry.rank === 2
                  ? 'text-muted-foreground'
                  : 'text-[#C17A4E] dark:text-[#C97B6B]'
              const name = weeklyEntryName(entry, activeTab)
              const subtitle = weeklyEntrySubtitle(entry, activeTab)
              const runningPeak = entry.running_peak ?? entry.rank
              const runningWeeks = entry.running_wks ?? 1
              const runningPeakWeeks = entry.running_peak_wks ?? 0

              return (
                <tr key={`${activeTab}-${entry.rank}-${name}`} className="transition-colors hover:bg-muted/50">
                  <td className={cn(
                    'pb-3.5 pt-3.5 text-center font-serif text-[22px] font-semibold',
                    entry.rank <= 3 ? rankColor : 'text-muted-foreground',
                  )}>
                    {String(entry.rank).padStart(2, '0')}
                  </td>
                  <td className="pb-3.5 pt-3.5 text-center"><ChangeCell change={change} /></td>
                  <td className="pb-3.5 pt-3.5">
                    <CoverCell index={dataIndex} isNewOrRe={isNewOrRe} coverUrl={entry.cover_url} label={displayName(name)} />
                  </td>
                  <td className="pb-3.5 pt-3.5">
                    <Link to={weeklyEntryDetailLink(entry, activeTab)} className="font-sans text-sm font-semibold transition-colors hover:text-accent-foreground">
                      {displayName(name)}
                    </Link>
                    {activeTab === 'tracks' ? (
                      <ArtistLinks
                        artistName={(entry as WeeklyTrackEntry).artist_name}
                        artistNames={(entry as WeeklyTrackEntry).artist_names}
                        className="mt-0.5 block font-sans text-[12px] italic text-muted-foreground"
                      />
                    ) : activeTab === 'albums' ? (
                      <Link
                        to={billboardDetailLink(`/music/artists/${encodeURIComponent(subtitle)}`)}
                        className="mt-0.5 block font-sans text-[12px] italic text-muted-foreground transition-colors hover:text-accent-foreground"
                      >
                        {displayName(subtitle)}
                      </Link>
                    ) : (
                      <div className="mt-0.5 font-sans text-[12px] italic text-muted-foreground">{subtitle}</div>
                    )}
                  </td>
                  <td className="pb-3.5 pt-3.5 text-right font-sans text-[15px] font-semibold tabular-nums">
                    {formatBillboardNumber(entry.play_count)}
                    <span className="ml-2 inline-block h-[3px] w-[70px] rounded-[2px] bg-muted align-middle">
                      <span
                        className="block h-full rounded-[2px] bg-accent-foreground transition-[width] duration-300"
                        style={{ width: `${Math.round((entry.play_count / (summary.maxPlays || 1)) * 100)}%` }}
                      />
                    </span>
                  </td>
                  <td className={cn(
                    'pb-3.5 pt-3.5 text-right font-sans text-[13px]',
                    runningPeak === 1 ? 'font-bold text-accent-foreground' : 'text-muted-foreground',
                  )}>
                    {runningPeak}
                  </td>
                  <td className="pb-3.5 pt-3.5 text-right font-sans text-[13px] text-muted-foreground">
                    {runningPeakWeeks > 0 ? <span className="font-semibold">{runningPeakWeeks}</span> : '—'}
                  </td>
                  <td className="pb-3.5 pt-3.5 text-right font-sans text-[13px] text-muted-foreground">{runningWeeks}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <PaginationBar
          page={page}
          totalPages={totalPages}
          totalEntries={entries.length}
          pageSize={pageSize}
          onPageChange={onPageChange}
        />
      </GlassCard>

      <p className="mt-6 font-serif text-[13px] italic text-muted-foreground">
        共 {summary.total} {weeklyEntityLabel(activeTab)} · 更新时间 {new Date().toLocaleDateString('zh-CN')} CST
      </p>
    </>
  )
}
