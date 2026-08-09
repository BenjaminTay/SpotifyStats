import { useRef, useState } from 'react'
import { Check, Columns3, Search, SlidersHorizontal, X } from 'lucide-react'

import {
  MobileBottomSheet,
  MobilePageHeader,
  MobileRankList,
  type MobileEntityRowProps,
} from '@/components/mobile'
import {
  PEAK_FILTER_OPTIONS,
  TABS,
  formatNumber,
  getColumnsForTab,
  type AllTimeRow,
  type ColumnDef,
  type EntityTab,
  type MergedAlbumRow,
  type MergedArtistRow,
  type MergedTrackRow,
  type PeakFilter,
} from '@/features/billboard/all-time/allTimeData'
import { displayName } from '@/lib/chinese'
import { billboardDetailLink } from '@/lib/navigation'
import { cn } from '@/lib/utils'

interface MobileAllTimeProps {
  activeTab: EntityTab
  rows: AllTimeRow[]
  total: number
  searchQuery: string
  peakFilter: PeakFilter
  sortKey: string
  sortDir: 'asc' | 'desc'
  visibleColumnIds: string[]
  page: number
  pageSize: number
  onTabChange: (tab: EntityTab) => void
  onSearchChange: (value: string) => void
  onPeakFilterChange: (value: PeakFilter) => void
  onSortChange: (column: ColumnDef<AllTimeRow>) => void
  onVisibleColumnsChange: (ids: string[]) => void
  onPageChange: (page: number) => void
}

const PRESET_LABELS = {
  comprehensive: '综合成绩',
  trend: '走势成绩',
  stable: '长期稳定',
  cross: '跨层级带动',
} as const

function presetColumns(tab: EntityTab, preset: keyof typeof PRESET_LABELS): string[] {
  if (preset === 'trend') return ['power_score', 'power_rank', 'weeks_on_chart']
  if (preset === 'stable') return ['weeks_on_chart', 'peak_position', tab === 'tracks' ? 'total_chart_plays' : 'total_plays']
  if (preset === 'cross' && tab !== 'tracks') {
    return tab === 'albums'
      ? ['track_power_sum', 'track_power_rank', 'power_score']
      : ['track_power_sum', 'album_power_sum', 'power_score']
  }
  return ['power_score', 'peak_position', 'weeks_on_chart']
}

function entityPresentation(tab: EntityTab, row: AllTimeRow) {
  if (tab === 'tracks') {
    const track = row as MergedTrackRow
    return { type: 'track' as const, title: track.track_name, subtitle: track.artist_name, cover: track.cover_url, to: billboardDetailLink(`/music/tracks/${track.track_id}`) }
  }
  if (tab === 'albums') {
    const album = row as MergedAlbumRow
    return { type: 'album' as const, title: album.album_name, subtitle: album.artist_name, cover: album.cover_url, to: billboardDetailLink(`/music/albums/${encodeURIComponent(album.album_name)}?artist=${encodeURIComponent(album.artist_name)}`) }
  }
  const artist = row as MergedArtistRow
  return { type: 'artist' as const, title: artist.artist_name, subtitle: '', cover: artist.cover_url, to: billboardDetailLink(`/music/artists/${encodeURIComponent(artist.artist_name)}`) }
}

function buildRows(tab: EntityTab, rows: AllTimeRow[], columns: ColumnDef<AllTimeRow>[], sortKey: string): MobileEntityRowProps[] {
  const main = columns.find((column) => column.key === sortKey) ?? columns.find((column) => column.key === 'power_score') ?? columns[0]
  const facts = columns.filter((column) => column.key !== main?.key).slice(0, 2)
  return rows.map((row) => {
    const entity = entityPresentation(tab, row)
    return {
      entityType: entity.type,
      rank: row.power_rank,
      title: displayName(entity.title),
      subtitle: displayName(entity.subtitle),
      coverUrl: entity.cover,
      metric: main ? main.format(row) : formatNumber(row.power_score),
      metricLabel: main?.label ?? '走势评分',
      facts: facts.map((column) => ({ label: column.label, value: column.rankStyle ? `#${column.format(row)}` : column.format(row) })),
      to: entity.to,
    }
  })
}

export function MobileAllTime({
  activeTab,
  rows,
  total,
  searchQuery,
  peakFilter,
  sortKey,
  sortDir,
  visibleColumnIds,
  page,
  pageSize,
  onTabChange,
  onSearchChange,
  onPeakFilterChange,
  onSortChange,
  onVisibleColumnsChange,
  onPageChange,
}: MobileAllTimeProps) {
  const [fieldOpen, setFieldOpen] = useState(false)
  const [sortOpen, setSortOpen] = useState(false)
  const fieldTriggerRef = useRef<HTMLButtonElement>(null)
  const sortTriggerRef = useRef<HTMLButtonElement>(null)
  const columns = getColumnsForTab(activeTab)
  const selectedColumns = columns
    .filter((column) => visibleColumnIds.includes(column.key))
    .sort((a, b) => a.mobilePriority - b.mobilePriority)
    .slice(0, 3)
  const displayColumns = selectedColumns.length > 0 ? selectedColumns : columns.slice(0, 3)
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize))
  const safePage = Math.min(page, totalPages)
  const pageRows = rows.slice((safePage - 1) * pageSize, safePage * pageSize)
  const currentSort = columns.find((column) => column.key === sortKey)

  return (
    <div className="mobile-m4-page" data-mobile-page="all-time">
      <MobilePageHeader eyebrow="Chart / All-Time" title="个人总榜" />

      <div className="mobile-segmented" role="group" aria-label="总榜实体类型">
        {TABS.map((tab) => <button key={tab.key} type="button" className={cn(tab.key === activeTab && 'active')} onClick={() => onTabChange(tab.key)}>{tab.label}</button>)}
      </div>

      <label className="mobile-search-field">
        <Search aria-hidden="true" />
        <span className="sr-only">在当前总榜中搜索</span>
        <input type="search" value={searchQuery} onChange={(event) => onSearchChange(event.target.value)} placeholder="在当前总榜中搜索" />
        {searchQuery && <button type="button" onClick={() => onSearchChange('')} aria-label="清除总榜搜索"><X aria-hidden="true" /></button>}
      </label>

      <div className="mobile-year-chips" aria-label="总榜峰值筛选">
        {PEAK_FILTER_OPTIONS.map((option) => <button key={option.value} type="button" className={cn(option.value === peakFilter && 'active')} aria-pressed={option.value === peakFilter} onClick={() => onPeakFilterChange(option.value)}>{option.label}</button>)}
      </div>

      <div className="mobile-list-toolbar">
        <span>显示 {rows.length} / {total}</span>
        <div>
          <button ref={fieldTriggerRef} type="button" onClick={() => setFieldOpen(true)} aria-haspopup="dialog" aria-expanded={fieldOpen}><Columns3 aria-hidden="true" />字段组合</button>
          <button ref={sortTriggerRef} type="button" onClick={() => setSortOpen(true)} aria-haspopup="dialog" aria-expanded={sortOpen}><SlidersHorizontal aria-hidden="true" />{currentSort?.label ?? '排序'}</button>
        </div>
      </div>

      <MobileRankList
        eyebrow={`${TABS.find((tab) => tab.key === activeTab)?.label ?? ''} / ${sortDir === 'desc' ? '降序' : '升序'}`}
        title="总榜排名"
        rows={buildRows(activeTab, pageRows, displayColumns, sortKey)}
        emptyTitle={searchQuery ? '没有匹配当前搜索的结果' : '暂无总榜数据'}
        page={safePage}
        pageCount={totalPages}
        onPageChange={onPageChange}
      />

      <MobileBottomSheet open={fieldOpen} onOpenChange={setFieldOpen} title="选择字段组合" eyebrow="Field Sheet" description="每组仅改变手机端展示，不生成新统计指标。" triggerRef={fieldTriggerRef} dataSheet="all-time-fields">
        <div className="mobile-field-presets">
          {(Object.keys(PRESET_LABELS) as (keyof typeof PRESET_LABELS)[]).map((preset) => {
            const ids = presetColumns(activeTab, preset).filter((id) => columns.some((column) => column.key === id))
            const selected = ids.length === displayColumns.length && ids.every((id) => displayColumns.some((column) => column.key === id))
            return <button key={preset} type="button" className={cn(selected && 'active')} onClick={() => { onVisibleColumnsChange(ids); setFieldOpen(false) }}><span><strong>{PRESET_LABELS[preset]}</strong><small>{ids.map((id) => columns.find((column) => column.key === id)?.label).filter(Boolean).join(' · ')}</small></span>{selected && <Check aria-hidden="true" />}</button>
          })}
        </div>
      </MobileBottomSheet>

      <MobileBottomSheet open={sortOpen} onOpenChange={setSortOpen} title="选择总榜排序" eyebrow="Sort" triggerRef={sortTriggerRef} dataSheet="all-time-sort">
        <div className="mobile-section-options" role="listbox" aria-label="总榜排序">
          {columns.map((column) => <button key={column.key} type="button" role="option" aria-selected={column.key === sortKey} className={cn(column.key === sortKey && 'active')} onClick={() => { onSortChange(column); setSortOpen(false) }}><span><strong>{column.label}</strong><small>{column.key === sortKey ? `当前${sortDir === 'desc' ? '降序' : '升序'}，再次选择可切换` : column.description ?? '点击按该字段排序'}</small></span>{column.key === sortKey && <Check aria-hidden="true" />}</button>)}
        </div>
      </MobileBottomSheet>
    </div>
  )
}
