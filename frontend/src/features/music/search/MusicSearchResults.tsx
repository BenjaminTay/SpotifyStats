import { ArrowUpRight } from 'lucide-react'
import { Link } from 'react-router-dom'

import { CoverCell } from '@/components/shared/CoverCell'
import { cn } from '@/lib/utils'
import type { MusicSearchKind, MusicSearchResponse, MusicSearchResult } from '@/types/music-search'

import {
  MUSIC_SEARCH_KIND_PLURAL_LABELS,
  formatPlayEvents,
  groupedSearchTotal,
  hasSearchQuery,
} from './musicSearchUtils'

type MusicSearchResultsProps = {
  data: MusicSearchResponse | null
  query: string
  loading?: boolean
  error?: string | null
  compact?: boolean
  activeHref?: string | null
  onActiveHrefChange?: (href: string) => void
  onResultClick?: () => void
}

const GROUP_PICKERS: Array<{
  kind: MusicSearchKind
  pick: (data: MusicSearchResponse) => MusicSearchResult[]
}> = [
  { kind: 'track', pick: (data) => data.tracks },
  { kind: 'album', pick: (data) => data.albums },
  { kind: 'artist', pick: (data) => data.artists },
]

function chartSummaryParts(item: MusicSearchResult): string[] {
  const chart = item.chart
  if (!chart?.peak_position || !chart.weeks_on_chart) {
    return []
  }
  const parts = [`PK #${chart.peak_position}`, `在榜 ${chart.weeks_on_chart}周`]
  if (chart.power_rank) {
    parts.push(`走势 #${chart.power_rank}`)
  }
  return parts
}

function ResultMetrics({
  item,
  showChartSummary,
}: {
  item: MusicSearchResult
  showChartSummary: boolean
}) {
  const chartParts = showChartSummary ? chartSummaryParts(item) : []
  return (
    <span className="mt-1 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
      <span className="shrink-0 tabular-nums">
        {formatPlayEvents(item.play_events)}
      </span>
      {chartParts.length > 0 && (
        <span className="min-w-0 text-[11px] font-medium text-muted-foreground/90">
          {chartParts.map((part, index) => (
            <span key={part}>
              {index > 0 && <span className="px-1 text-muted-foreground/45">/</span>}
              <span className={index === 0 ? 'font-semibold text-accent-foreground' : undefined}>
                {part}
              </span>
            </span>
          ))}
        </span>
      )}
    </span>
  )
}

function visibleSubtitle(item: MusicSearchResult): string | null {
  if (!item.subtitle || item.subtitle === formatPlayEvents(item.play_events)) {
    return null
  }
  return item.subtitle
}

function groupedResults(data: MusicSearchResponse) {
  return GROUP_PICKERS.map((group) => ({
    kind: group.kind,
    label: MUSIC_SEARCH_KIND_PLURAL_LABELS[group.kind],
    items: group.pick(data),
  })).filter((group) => group.items.length > 0)
}

export function MusicSearchResults({
  data,
  query,
  loading = false,
  error = null,
  compact = false,
  activeHref = null,
  onActiveHrefChange,
  onResultClick,
}: MusicSearchResultsProps) {
  if (!hasSearchQuery(query)) {
    return (
      <div className={cn('rounded-lg border border-dashed border-border bg-muted/30 px-4 py-8 text-center', compact && 'py-6')}>
        <p className="text-sm font-medium text-foreground">输入歌曲、专辑或艺人名称开始查找</p>
        <p className="mt-1 text-xs text-muted-foreground">搜索本地播放历史中的音乐详情页。</p>
      </div>
    )
  }

  if (loading) {
    const loadingRows = compact ? 0 : 6
    return (
      <div
        className={cn('space-y-2', compact && 'space-y-1.5')}
        aria-label="正在查找音乐详情"
        role="status"
        aria-live="polite"
      >
        <div
          data-testid="music-search-loading-message"
          className={cn(
            'rounded-lg border border-border bg-muted/25 px-4 py-3',
            compact && 'flex items-center gap-2 px-3 py-2',
          )}
        >
          {compact && <span className="size-1.5 shrink-0 animate-pulse rounded-full bg-accent-foreground" aria-hidden="true" />}
          <p className="text-sm font-semibold text-foreground">正在加载搜索结果…</p>
          <p className={cn('mt-1 text-xs text-muted-foreground', compact && 'mt-0 truncate')}>
            {compact ? '匹配播放记录与榜单信息' : '正在匹配本地播放记录与榜单信息。'}
          </p>
        </div>
        {Array.from({ length: loadingRows }).map((_, index) => (
          <div
            key={index}
            data-testid="music-search-loading-row"
            className="h-16 animate-pulse rounded-lg border border-border bg-muted/35"
          />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-6 text-sm text-destructive">
        {error}
      </div>
    )
  }

  if (!data || groupedSearchTotal(data) === 0) {
    return (
      <div className="rounded-lg border border-border bg-card px-4 py-8 text-center">
        <p className="text-sm font-medium text-foreground">没有找到匹配的音乐详情</p>
        <p className="mt-1 text-xs text-muted-foreground">换一个歌曲、专辑或艺人名称试试。</p>
      </div>
    )
  }

  return (
    <div className={cn('space-y-3', compact && 'space-y-2')}>
      {groupedResults(data).map((group) => (
        <ResultGroup
          key={group.kind}
          label={group.label}
          items={group.items}
          compact={compact}
          activeHref={activeHref}
          onActiveHrefChange={onActiveHrefChange}
          onResultClick={onResultClick}
        />
      ))}
    </div>
  )
}

type ResultGroupProps = {
  label: string
  items: MusicSearchResult[]
  compact: boolean
  activeHref?: string | null
  onActiveHrefChange?: (href: string) => void
  onResultClick?: () => void
}

function ResultGroup({
  label,
  items,
  compact,
  activeHref,
  onActiveHrefChange,
  onResultClick,
}: ResultGroupProps) {
  return (
    <section
      aria-label={label}
      className={cn(
        'min-w-0 overflow-hidden rounded-lg border border-border bg-card/85',
        compact && 'bg-card/90',
      )}
    >
      <div className="flex items-center gap-2 border-b border-border/80 px-4 py-2.5 text-xs font-semibold text-muted-foreground">
        <span>{label.replace('结果', '')}</span>
        <span className="ml-auto tabular-nums">{items.length}</span>
      </div>
      <ul aria-label={`${label}列表`} className="divide-y divide-border/75">
        {items.map((item, index) => (
          <ResultRow
            key={`${item.kind}:${item.href}`}
            item={item}
            index={index}
            compact={compact}
            showChartSummary
            isActive={item.href === activeHref}
            onActiveHrefChange={onActiveHrefChange}
            onResultClick={onResultClick}
          />
        ))}
      </ul>
    </section>
  )
}

type ResultRowProps = {
  item: MusicSearchResult
  index: number
  compact: boolean
  showChartSummary: boolean
  isActive?: boolean
  onActiveHrefChange?: (href: string) => void
  onResultClick?: () => void
}

function ResultRow({
  item,
  index,
  compact,
  showChartSummary,
  isActive = false,
  onActiveHrefChange,
  onResultClick,
}: ResultRowProps) {
  const subtitle = visibleSubtitle(item)
  return (
    <li>
      <Link
        to={item.href}
        aria-current={isActive ? 'true' : undefined}
        onClick={onResultClick}
        onFocus={() => onActiveHrefChange?.(item.href)}
        onMouseEnter={() => onActiveHrefChange?.(item.href)}
        className={cn(
          'group grid min-w-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 text-left transition-colors hover:bg-muted/35 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45',
          compact ? 'px-3 py-2.5' : 'px-4 py-3',
          isActive && 'bg-muted/50 ring-1 ring-accent-foreground/25',
        )}
      >
        <CoverCell
          index={index}
          coverUrl={item.cover_url}
          className={compact ? 'size-9 shrink-0' : 'size-11 shrink-0'}
          label={item.label}
        />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-semibold text-foreground">{item.label}</span>
          {subtitle && <span className="mt-0.5 block truncate text-xs text-muted-foreground">{subtitle}</span>}
          <ResultMetrics item={item} showChartSummary={showChartSummary} />
        </span>
        <ArrowUpRight className="size-3.5 shrink-0 text-muted-foreground transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" aria-hidden="true" />
      </Link>
    </li>
  )
}
