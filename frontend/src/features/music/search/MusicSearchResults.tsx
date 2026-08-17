import { ArrowUpRight, RefreshCw } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { MobileEntityRow } from '@/components/mobile'
import { CoverCell } from '@/components/shared/CoverCell'
import { displayName, useChineseTextVersion } from '@/lib/chinese'
import { cn } from '@/lib/utils'
import type {
  MusicSearchCandidate,
  MusicSearchCandidateResponse,
  MusicSearchCandidateView,
  MusicSearchContextResponse,
  MusicSearchKind,
} from '@/types/music-search'

import {
  MUSIC_SEARCH_KIND_PLURAL_LABELS,
  formatPlayEvents,
  fullSearchHref,
  hasSearchQuery,
  musicSearchOptionId,
} from './musicSearchUtils'
import { HighlightedSearchText } from './HighlightedSearchText'

type MusicSearchResultsProps = {
  data: MusicSearchCandidateResponse | null
  contextData?: MusicSearchContextResponse | null
  query: string
  initialLoading?: boolean
  updating?: boolean
  contextLoading?: boolean
  error?: string | null
  contextError?: string | null
  compact?: boolean
  activeEntityKey?: string | null
  onActiveEntityKeyChange?: (entityKey: string) => void
  onResultClick?: (item: MusicSearchCandidate) => void
  mobile?: boolean
  showGroupLinks?: boolean
  listboxId?: string
  onRetry?: () => void
  maintenanceHref?: string | null
  publicReadonly?: boolean
}

const GROUP_PICKERS: Array<{
  kind: MusicSearchKind
  pick: (data: MusicSearchCandidateResponse) => MusicSearchCandidate[]
}> = [
  { kind: 'track', pick: (data) => data.tracks },
  { kind: 'album', pick: (data) => data.albums },
  { kind: 'artist', pick: (data) => data.artists },
]

function chartSummaryParts(item: MusicSearchCandidateView): string[] {
  const chart = item.context?.chart
  if (!chart?.peak_position || !chart.weeks_on_chart) return []
  const parts = [`PK #${chart.peak_position}`, `在榜 ${chart.weeks_on_chart}周`]
  if (chart.power_rank) parts.push(`走势 #${chart.power_rank}`)
  return parts
}

function ResultMetrics({
  item,
  contextLoading,
  contextError,
}: {
  item: MusicSearchCandidateView
  contextLoading: boolean
  contextError: string | null
}) {
  const chartParts = chartSummaryParts(item)
  return (
    <span className="mt-1 flex min-h-[18px] min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
      {item.context ? (
        <>
          <span className="shrink-0 tabular-nums">
            {formatPlayEvents(item.context.play_events)}
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
        </>
      ) : contextLoading ? (
        <span className="h-3 w-28 animate-pulse rounded bg-muted" aria-label="正在加载统计信息" />
      ) : contextError ? (
        <span className="text-[11px]">统计信息暂不可用</span>
      ) : null}
    </span>
  )
}

function groupedResults(
  data: MusicSearchCandidateResponse,
  contextData: MusicSearchContextResponse | null,
) {
  return GROUP_PICKERS.map((group) => ({
    kind: group.kind,
    label: MUSIC_SEARCH_KIND_PLURAL_LABELS[group.kind],
    total: data.total_by_kind[group.kind],
    items: group.pick(data).map<MusicSearchCandidateView>((item) => ({
      ...item,
      context: contextData?.items[item.entity_key] ?? null,
    })),
  })).filter((group) => group.items.length > 0)
}

function snapshotMessage(
  data: MusicSearchCandidateResponse | null,
  publicReadonly: boolean,
): { title: string; detail: string; canRetry: boolean } | null {
  if (!data || data.snapshot_status === 'ready') return null
  if (data.snapshot_status === 'warming') {
    return {
      title: '搜索数据正在准备',
      detail: '正在等待当前统计口径的搜索数据，准备完成后会自动刷新。',
      canRetry: false,
    }
  }
  if (data.snapshot_status === 'stale') {
    return {
      title: '搜索数据正在更新',
      detail: '筛选口径刚刚发生变化，更新完成后会自动刷新。',
      canRetry: false,
    }
  }
  if (data.snapshot_status === 'failed') {
    return {
      title: '搜索数据更新失败',
      detail: publicReadonly
        ? '当前公开页面只读取已准备的数据，请稍后重新检查。'
        : '后台维护没有完成，可以重新检查或前往设置查看数据维护状态。',
      canRetry: true,
    }
  }
  return {
    title: '搜索暂不可用',
    detail: publicReadonly
      ? '当前公开页面只读取已准备的数据，请稍后重新检查。'
      : '当前统计口径还没有可用数据，可以重新检查或前往设置查看数据维护状态。',
    canRetry: true,
  }
}

function resultTitle(item: MusicSearchCandidate, query: string): ReactNode {
  const label = displayName(item.label)
  return item.match_field === 'label'
    ? <HighlightedSearchText text={label} query={displayName(query)} />
    : label
}

function resultSubtitle(item: MusicSearchCandidate, query: string): ReactNode | null {
  const shouldHighlight = item.match_field === 'artist' || item.match_field === 'album'
  if (!item.subtitle) return null
  const subtitle = displayName(item.subtitle)
  return shouldHighlight
    ? <HighlightedSearchText text={subtitle} query={displayName(query)} />
    : subtitle
}

function SnapshotNotice({
  notice,
  onRetry,
  maintenanceHref,
}: {
  notice: NonNullable<ReturnType<typeof snapshotMessage>>
  onRetry?: () => void
  maintenanceHref?: string | null
}) {
  return (
    <div className="rounded-lg border border-border bg-card px-4 py-5 text-center" role="status" aria-live="polite">
      <p className="text-sm font-medium text-foreground">{notice.title}</p>
      <p className="mt-1 text-xs text-muted-foreground">{notice.detail}</p>
      {notice.canRetry && (
        <div className="mt-4 flex flex-wrap justify-center gap-2">
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm font-semibold text-foreground hover:bg-muted"
            >
              <RefreshCw className="size-3.5" aria-hidden="true" />
              重新检查
            </button>
          )}
          {maintenanceHref && (
            <Link
              to={maintenanceHref}
              className="inline-flex min-h-11 items-center rounded-lg px-3 py-2 text-sm font-semibold text-accent-foreground hover:bg-muted"
            >
              查看数据维护
            </Link>
          )}
        </div>
      )}
    </div>
  )
}

export function MusicSearchResults({
  data,
  contextData = null,
  query,
  initialLoading = false,
  updating = false,
  contextLoading = false,
  error = null,
  contextError = null,
  compact = false,
  activeEntityKey = null,
  onActiveEntityKeyChange,
  onResultClick,
  mobile = false,
  showGroupLinks = false,
  listboxId,
  onRetry,
  maintenanceHref = null,
  publicReadonly = false,
}: MusicSearchResultsProps) {
  useChineseTextVersion()

  if (!hasSearchQuery(query)) {
    return (
      <div className={cn('rounded-lg border border-dashed border-border bg-muted/30 px-4 py-8 text-center', compact && 'py-6')}>
        <p className="text-sm font-medium text-foreground">输入歌曲、专辑或艺人名称开始查找</p>
        <p className="mt-1 text-xs text-muted-foreground">搜索本地播放历史中的音乐详情页。</p>
      </div>
    )
  }

  if (initialLoading && !data) {
    const loadingRows = compact ? 3 : 6
    return (
      <div className={cn('space-y-2', compact && 'space-y-1.5')} aria-label="正在查找音乐详情" role="status" aria-live="polite">
        <div data-testid="music-search-loading-message" className="rounded-lg border border-border bg-muted/25 px-4 py-3">
          <p className="text-sm font-semibold text-foreground">正在加载搜索结果…</p>
        </div>
        {Array.from({ length: loadingRows }).map((_, index) => (
          <div key={index} data-testid="music-search-loading-row" className="h-16 animate-pulse rounded-lg border border-border bg-muted/35" />
        ))}
      </div>
    )
  }

  if (error && !data) {
    return <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-6 text-sm text-destructive">{error}</div>
  }

  const snapshotNotice = snapshotMessage(data, publicReadonly)
  if (snapshotNotice && (!data || data.total === 0)) {
    return <SnapshotNotice notice={snapshotNotice} onRetry={onRetry} maintenanceHref={maintenanceHref} />
  }

  if (!data || data.total === 0) {
    return (
      <div className="rounded-lg border border-border bg-card px-4 py-8 text-center">
        <p className="text-sm font-medium text-foreground">没有找到匹配的音乐详情</p>
        <p className="mt-1 text-xs text-muted-foreground">换一个歌曲、专辑或艺人名称试试。</p>
      </div>
    )
  }

  return (
    <div
      id={listboxId}
      role={listboxId ? 'listbox' : undefined}
      aria-label={listboxId ? '音乐搜索结果' : undefined}
      className={cn('space-y-3', compact && 'space-y-2')}
    >
      {(updating || error) && (
        <p className={cn('text-xs font-medium', error ? 'text-destructive' : 'text-muted-foreground')} role="status" aria-live="polite">
          {error ?? '正在更新结果…'}
        </p>
      )}
      {snapshotNotice && (
        <SnapshotNotice notice={snapshotNotice} onRetry={onRetry} maintenanceHref={maintenanceHref} />
      )}
      {groupedResults(data, contextData).map((group) => (
        <ResultGroup
          key={group.kind}
          kind={group.kind}
          label={group.label}
          total={group.total}
          items={group.items}
          query={query}
          compact={compact}
          contextLoading={contextLoading}
          contextError={contextError}
          activeEntityKey={activeEntityKey}
          onActiveEntityKeyChange={onActiveEntityKeyChange}
          onResultClick={onResultClick}
          mobile={mobile}
          listboxMode={Boolean(listboxId)}
          showGroupLink={showGroupLinks && data.kind === null && group.total > group.items.length}
        />
      ))}
    </div>
  )
}

type ResultGroupProps = {
  kind: MusicSearchKind
  label: string
  total: number
  items: MusicSearchCandidateView[]
  query: string
  compact: boolean
  contextLoading: boolean
  contextError: string | null
  activeEntityKey?: string | null
  onActiveEntityKeyChange?: (entityKey: string) => void
  onResultClick?: (item: MusicSearchCandidate) => void
  mobile: boolean
  listboxMode: boolean
  showGroupLink: boolean
}

function ResultGroup({
  kind,
  label,
  total,
  items,
  query,
  compact,
  contextLoading,
  contextError,
  activeEntityKey,
  onActiveEntityKeyChange,
  onResultClick,
  mobile,
  listboxMode,
  showGroupLink,
}: ResultGroupProps) {
  const groupHref = fullSearchHref(query, kind)
  if (mobile) {
    return (
      <section aria-label={label} className="mobile-music-search-group" role="group">
        <header>
          <h2>{label.replace('结果', '')}</h2>
          {showGroupLink ? <Link to={groupHref}>查看全部 {total} 个</Link> : <span>{total}</span>}
        </header>
        <div className="mobile-rank-rows">
          {items.map((item) => {
            const chart = item.context?.chart
            return (
              <MobileEntityRow
                key={item.entity_key}
                entityType={item.kind}
                title={resultTitle(item, query)}
                subtitle={resultSubtitle(item, query) ?? undefined}
                coverUrl={item.cover_url}
                metric={item.context ? formatPlayEvents(item.context.play_events) : '—'}
                metricLabel={item.context ? '播放' : contextLoading ? '加载中' : '统计'}
                facts={chart?.peak_position && chart.weeks_on_chart ? [
                  { label: 'PK', value: `#${chart.peak_position}` },
                  { label: '在榜', value: `${chart.weeks_on_chart}周` },
                ] : []}
                badges={chart?.power_rank ? [`走势 #${chart.power_rank}`] : []}
                to={item.href}
                onClick={() => onResultClick?.(item)}
              />
            )
          })}
        </div>
      </section>
    )
  }

  return (
    <section aria-label={label} role="group" className={cn('min-w-0 overflow-hidden rounded-lg border border-border bg-card/85', compact && 'bg-card/90')}>
      <div className="flex min-h-11 items-center gap-2 border-b border-border/80 px-4 py-2.5 text-xs font-semibold text-muted-foreground">
        <span>{label.replace('结果', '')}</span>
        {showGroupLink ? (
          <Link to={groupHref} className="ml-auto rounded px-2 py-1 text-accent-foreground hover:bg-muted">
            查看全部 {total} 个
          </Link>
        ) : (
          <span className="ml-auto tabular-nums">{total}</span>
        )}
      </div>
      <ul aria-label={`${label}列表`} className="divide-y divide-border/75">
        {items.map((item, index) => (
          <ResultRow
            key={item.entity_key}
            item={item}
            query={query}
            index={index}
            compact={compact}
            contextLoading={contextLoading}
            contextError={contextError}
            isActive={item.entity_key === activeEntityKey}
            onActiveEntityKeyChange={onActiveEntityKeyChange}
            onResultClick={onResultClick}
            listboxMode={listboxMode}
          />
        ))}
      </ul>
    </section>
  )
}

function ResultRow({
  item,
  query,
  index,
  compact,
  contextLoading,
  contextError,
  isActive,
  onActiveEntityKeyChange,
  onResultClick,
  listboxMode,
}: {
  item: MusicSearchCandidateView
  query: string
  index: number
  compact: boolean
  contextLoading: boolean
  contextError: string | null
  isActive: boolean
  onActiveEntityKeyChange?: (entityKey: string) => void
  onResultClick?: (item: MusicSearchCandidate) => void
  listboxMode: boolean
}) {
  const subtitle = resultSubtitle(item, query)
  return (
    <li>
      <Link
        id={musicSearchOptionId(item.entity_key)}
        role={listboxMode ? 'option' : undefined}
        aria-selected={listboxMode ? isActive : undefined}
        to={item.href}
        onClick={() => onResultClick?.(item)}
        onFocus={() => onActiveEntityKeyChange?.(item.entity_key)}
        onMouseEnter={() => onActiveEntityKeyChange?.(item.entity_key)}
        className={cn(
          'group grid min-w-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 text-left transition-colors hover:bg-muted/35 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45',
          compact ? 'px-3 py-2.5' : 'px-4 py-3',
          isActive && 'bg-muted/50 ring-1 ring-accent-foreground/25',
        )}
      >
        <CoverCell index={index} coverUrl={item.cover_url} className={compact ? 'size-9 shrink-0' : 'size-11 shrink-0'} label={displayName(item.label)} />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-semibold text-foreground">
            {resultTitle(item, query)}
          </span>
          {subtitle && (
            <span className="mt-0.5 block truncate text-xs text-muted-foreground">
              {subtitle}
            </span>
          )}
          <ResultMetrics item={item} contextLoading={contextLoading} contextError={contextError} />
        </span>
        <ArrowUpRight className="size-3.5 shrink-0 text-muted-foreground transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" aria-hidden="true" />
      </Link>
    </li>
  )
}
