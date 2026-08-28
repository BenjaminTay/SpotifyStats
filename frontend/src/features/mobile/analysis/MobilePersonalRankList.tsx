import { useState, type ReactNode } from 'react'
import { Search, X } from 'lucide-react'

import { MobileRankList, MobileStatePanel } from '@/components/mobile'
import { cn } from '@/lib/utils'
import { displayName, useChineseTextVersion } from '@/lib/chinese'
import type { AnalysisChartRow, AnalysisChartsResponse, AnalysisMetric, LeaderboardEntity } from '@/types/analysis'

const PAGE_SIZE = 20

function formatNumber(value: number): string {
  return new Intl.NumberFormat('zh-CN').format(value)
}

function formatHours(value: number): string {
  return `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 1 }).format(value)}h`
}

function entityTitle(row: AnalysisChartRow, entity: LeaderboardEntity): string {
  if (entity === 'track') return row.track_name || '未知歌曲'
  if (entity === 'album') return row.album_name || '未知专辑'
  return row.artist_name || '未知艺人'
}

function entitySubtitle(row: AnalysisChartRow, entity: LeaderboardEntity): string {
  if (entity === 'artist') return `${row.unique_tracks ?? 0} 首有效歌曲`
  if (entity === 'track' && row.artist_names?.length) return row.artist_names.join('、')
  return row.artist_name || '未知艺人'
}

function entityLink(row: AnalysisChartRow, entity: LeaderboardEntity): string | undefined {
  if (entity === 'track' && row.track_id != null) return `/music/tracks/${row.track_id}`
  if (entity === 'album' && row.album_name) {
    return `/music/albums/${encodeURIComponent(row.album_name)}${row.artist_name ? `?artist=${encodeURIComponent(row.artist_name)}` : ''}`
  }
  if (entity === 'artist' && row.artist_name) return `/music/artists/${encodeURIComponent(row.artist_name)}`
  return undefined
}

function matchesSearch(row: AnalysisChartRow, entity: LeaderboardEntity, searchQuery: string): boolean {
  const query = searchQuery.normalize('NFKC').toLocaleLowerCase().replace(/\s+/g, ' ').trim()
  if (!query) return true
  const values = entity === 'track'
    ? [row.track_name, row.artist_name, ...(row.artist_names ?? []), row.album_name]
    : entity === 'album'
      ? [row.album_name, row.artist_name]
      : [row.artist_name]
  return values.some((value) => value && [value, displayName(value)].some((candidate) =>
    candidate.normalize('NFKC').toLocaleLowerCase().includes(query),
  ))
}

interface MobilePersonalRankListProps {
  data: AnalysisChartsResponse | null
  loading: boolean
  entity: LeaderboardEntity
  metric: AnalysisMetric
  searchQuery: string
  onSearchChange: (value: string) => void
  onEntityChange: (value: LeaderboardEntity) => void
  timeControl?: ReactNode
}

export function MobilePersonalRankList({
  data,
  loading,
  entity,
  metric,
  searchQuery,
  onSearchChange,
  onEntityChange,
  timeControl,
}: MobilePersonalRankListProps) {
  useChineseTextVersion()
  const [pageState, setPageState] = useState({ data, entity, searchQuery, page: 1 })
  const page = pageState.data === data && pageState.entity === entity && pageState.searchQuery === searchQuery
    ? pageState.page
    : 1
  const filteredRows = data?.rows.filter((row) => matchesSearch(row, entity, searchQuery)) ?? []
  const pageCount = Math.max(1, Math.ceil(filteredRows.length / PAGE_SIZE))
  const safePage = Math.min(page, pageCount)
  const rows = filteredRows.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE)
  const goToPage = (nextPage: number) => setPageState({ data, entity, searchQuery, page: nextPage })

  return (
    <div className="mobile-m3-page" data-mobile-page="analysis-charts">
      {timeControl && <div className="mobile-analysis-floating-time-control">{timeControl}</div>}

      <div className="mobile-rank-controls">
        <div className="mobile-segmented" role="group" aria-label="排行实体类型">
          {(['track', 'album', 'artist'] as const).map((value) => (
            <button key={value} type="button" className={cn(entity === value && 'active')} onClick={() => onEntityChange(value)}>
              {value === 'track' ? '歌曲' : value === 'album' ? '专辑' : '艺人'}
            </button>
          ))}
        </div>
      </div>

      <label className="mobile-search-field">
        <span className="sr-only">在当前播放排行中搜索</span>
        <Search aria-hidden="true" />
        <input
          type="search"
          value={searchQuery}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="搜索当前榜单"
        />
        {searchQuery && (
          <button type="button" onClick={() => onSearchChange('')} aria-label="清除播放排行搜索">
            <X aria-hidden="true" />
          </button>
        )}
      </label>

      {loading || !data ? (
        <MobileStatePanel variant="loading" />
      ) : (
        <MobileRankList
          eyebrow={`${entity === 'track' ? 'Tracks' : entity === 'album' ? 'Albums' : 'Artists'} / ${metric === 'plays' ? 'Plays' : 'Hours'}`}
          title={entity === 'track' ? '歌曲榜' : entity === 'album' ? '专辑榜' : '艺人榜'}
          rows={rows.map((row) => ({
            entityType: entity,
            rank: row.rank,
            title: displayName(entityTitle(row, entity)),
            subtitle: displayName(entitySubtitle(row, entity)),
            coverUrl: row.cover_url,
            metric: metric === 'plays' ? formatNumber(row.plays) : formatHours(row.hours),
            metricLabel: metric === 'plays' ? '播放' : '时长',
            facts: [
              { label: metric === 'plays' ? '时长' : '播放', value: metric === 'plays' ? formatHours(row.hours) : formatNumber(row.plays) },
              { label: '占比', value: `${row.share_pct}%` },
            ],
            to: entityLink(row, entity),
            className: 'mobile-personal-rank-row',
          }))}
          emptyTitle={searchQuery ? '没有匹配的榜单结果' : '当前范围没有排行数据'}
        page={safePage}
        pageCount={pageCount}
        onPageChange={goToPage}
        showTopPagination
        showItemCount={false}
      />
      )}
    </div>
  )
}
