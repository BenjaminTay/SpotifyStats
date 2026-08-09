import { useRef, useState } from 'react'
import { ArrowDownAZ, Check } from 'lucide-react'

import {
  MobileBottomSheet,
  MobilePageHeader,
  MobileRankList,
  type MobileEntityRowProps,
} from '@/components/mobile'
import { YearEndHonors } from '@/features/billboard/year-end/YearEndHonors'
import {
  YEAR_END_TABS,
  entityNameForRow,
  formatYearEndNumber,
  subtitleForRow,
  type YearEndRow,
  type YearEndSortDir,
  type YearEndSortKey,
  type YearEndTab,
} from '@/features/billboard/year-end/yearEndData'
import { displayName } from '@/lib/chinese'
import { billboardDetailLink, primaryArtistName } from '@/lib/navigation'
import { cn } from '@/lib/utils'
import type {
  BillboardYearEndAlbumRow,
  BillboardYearEndArtistRow,
  BillboardYearEndResponse,
  BillboardYearEndTrackRow,
} from '@/types/billboard'

const SORT_OPTIONS: { key: YearEndSortKey; label: string; defaultDir: YearEndSortDir }[] = [
  { key: 'year_end_score', label: '年度积分', defaultDir: 'desc' },
  { key: 'year_end_rank', label: '原始年终排名', defaultDir: 'asc' },
  { key: 'peak_position', label: '年度最高排名', defaultDir: 'asc' },
  { key: 'weeks_on_chart', label: '年度在榜周数', defaultDir: 'desc' },
  { key: 'weeks_at_no1', label: '年度冠军周数', defaultDir: 'desc' },
  { key: 'chart_plays', label: '在榜播放次数', defaultDir: 'desc' },
]

interface MobileYearEndProps {
  data: BillboardYearEndResponse
  selectedYear?: number | null
  availableYears: number[]
  coverageMessage: string | null
  activeTab: YearEndTab
  rows: YearEndRow[]
  sortKey: YearEndSortKey
  sortDir: YearEndSortDir
  page: number
  pageSize: number
  onYearChange: (year: number) => void
  onTabChange: (tab: YearEndTab) => void
  onSortChange: (key: YearEndSortKey) => void
  onPageChange: (page: number) => void
}

function detailLink(tab: YearEndTab, row: YearEndRow): string {
  if (tab === 'tracks') return billboardDetailLink(`/music/tracks/${(row as BillboardYearEndTrackRow).track_id}`)
  if (tab === 'albums') {
    const album = row as BillboardYearEndAlbumRow
    return billboardDetailLink(`/music/albums/${encodeURIComponent(album.album_name)}?artist=${encodeURIComponent(album.artist_name)}`)
  }
  return billboardDetailLink(`/music/artists/${encodeURIComponent(primaryArtistName(row as BillboardYearEndArtistRow))}`)
}

function mobileRows(tab: YearEndTab, rows: YearEndRow[]): MobileEntityRowProps[] {
  return rows.map((row) => ({
    entityType: tab === 'tracks' ? 'track' : tab === 'albums' ? 'album' : 'artist',
    rank: row.year_end_rank,
    title: displayName(entityNameForRow(tab, row)),
    subtitle: displayName(subtitleForRow(tab, row)),
    coverUrl: row.cover_url,
    metric: formatYearEndNumber(row.year_end_score),
    metricLabel: 'Year-End Score',
    facts: [
      { label: 'PK', value: `#${row.peak_position}` },
      { label: '在榜', value: `${row.weeks_on_chart}周` },
    ],
    to: detailLink(tab, row),
  }))
}

export function MobileYearEnd({
  data,
  selectedYear,
  availableYears,
  coverageMessage,
  activeTab,
  rows,
  sortKey,
  sortDir,
  page,
  pageSize,
  onYearChange,
  onTabChange,
  onSortChange,
  onPageChange,
}: MobileYearEndProps) {
  const [sortOpen, setSortOpen] = useState(false)
  const sortTriggerRef = useRef<HTMLButtonElement>(null)
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize))
  const safePage = Math.min(page, totalPages)
  const pageRows = rows.slice((safePage - 1) * pageSize, safePage * pageSize)
  const sortLabel = SORT_OPTIONS.find((option) => option.key === sortKey)?.label ?? '年度积分'

  return (
    <div className="mobile-m4-page" data-mobile-page="year-end">
      <MobilePageHeader
        eyebrow="Chart / Year-End"
        title="个人年榜"
        meta={<span>已统计 {data.meta.observed_weeks}/{data.meta.expected_weeks} 个榜单周</span>}
      />

      <div className="mobile-year-chips" aria-label="切换年榜年份">
        {[...availableYears].reverse().map((year) => <button key={year} type="button" className={cn(year === selectedYear && 'active')} aria-pressed={year === selectedYear} onClick={() => onYearChange(year)}>{year}</button>)}
      </div>

      {coverageMessage && <div className="mobile-coverage-warning" role="status"><strong>阶段年榜</strong><p>{coverageMessage}</p></div>}

      <YearEndHonors honors={data.honors} isCompleteYear={data.meta.is_complete_year} />

      <div className="mobile-segmented" role="group" aria-label="年榜类型">
        {YEAR_END_TABS.map((tab) => <button key={tab.key} type="button" className={cn(activeTab === tab.key && 'active')} onClick={() => onTabChange(tab.key)}>{tab.label}</button>)}
      </div>

      <div className="mobile-list-toolbar">
        <span>{rows.length} 个实体</span>
        <button ref={sortTriggerRef} type="button" onClick={() => setSortOpen(true)} aria-haspopup="dialog" aria-expanded={sortOpen}>
          <ArrowDownAZ aria-hidden="true" />{sortLabel} · {sortDir === 'desc' ? '降序' : '升序'}
        </button>
      </div>

      <MobileRankList
        eyebrow={`${selectedYear ?? ''} / ${YEAR_END_TABS.find((tab) => tab.key === activeTab)?.label ?? ''}`}
        title="年度完整排名"
        rows={mobileRows(activeTab, pageRows)}
        emptyTitle="当前年份暂无年榜数据"
        page={safePage}
        pageCount={totalPages}
        onPageChange={onPageChange}
      />

      <MobileBottomSheet open={sortOpen} onOpenChange={setSortOpen} title="选择年榜排序" eyebrow="Sort" triggerRef={sortTriggerRef} dataSheet="year-end-sort">
        <div className="mobile-section-options" role="listbox" aria-label="年榜排序">
          {SORT_OPTIONS.map((option) => (
            <button key={option.key} type="button" role="option" aria-selected={sortKey === option.key} className={cn(sortKey === option.key && 'active')} onClick={() => { onSortChange(option.key); setSortOpen(false) }}>
              <span><strong>{option.label}</strong><small>{sortKey === option.key ? `当前${sortDir === 'desc' ? '降序' : '升序'}，再次选择可切换` : `默认${option.defaultDir === 'desc' ? '降序' : '升序'}`}</small></span>
              {sortKey === option.key && <Check aria-hidden="true" />}
            </button>
          ))}
        </div>
      </MobileBottomSheet>
    </div>
  )
}
