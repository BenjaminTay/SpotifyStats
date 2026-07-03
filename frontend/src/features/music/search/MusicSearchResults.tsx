import { ArrowUpRight, Disc3, Music2, UserRound } from 'lucide-react'
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
  onResultClick?: () => void
}

const GROUPS: Array<{
  kind: MusicSearchKind
  icon: typeof Music2
  pick: (data: MusicSearchResponse) => MusicSearchResult[]
}> = [
  { kind: 'track', icon: Music2, pick: (data) => data.tracks },
  { kind: 'album', icon: Disc3, pick: (data) => data.albums },
  { kind: 'artist', icon: UserRound, pick: (data) => data.artists },
]

export function MusicSearchResults({
  data,
  query,
  loading = false,
  error = null,
  compact = false,
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
    return (
      <div className="space-y-2" aria-label="正在查找音乐详情">
        {Array.from({ length: compact ? 3 : 6 }).map((_, index) => (
          <div key={index} className="h-16 animate-pulse rounded-lg border border-border bg-muted/35" />
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
    <div className={cn('grid gap-3', compact ? 'grid-cols-1' : 'lg:grid-cols-3')}>
      {GROUPS.map((group) => {
        const items = group.pick(data)
        if (items.length === 0) return null
        return (
          <ResultGroup
            key={group.kind}
            label={MUSIC_SEARCH_KIND_PLURAL_LABELS[group.kind]}
            icon={group.icon}
            items={items}
            compact={compact}
            onResultClick={onResultClick}
          />
        )
      })}
    </div>
  )
}

type ResultGroupProps = {
  label: string
  icon: typeof Music2
  items: MusicSearchResult[]
  compact: boolean
  onResultClick?: () => void
}

function ResultGroup({ label, icon: Icon, items, compact, onResultClick }: ResultGroupProps) {
  return (
    <section
      aria-label={label}
      className={cn(
        'min-w-0 rounded-lg border border-border bg-card/80',
        compact ? 'p-2' : 'p-3',
      )}
    >
      <div className="mb-2 flex items-center gap-2 px-1 text-xs font-semibold uppercase tracking-[1.2px] text-muted-foreground">
        <Icon className="size-3.5" aria-hidden="true" />
        <span>{label.replace('结果', '')}</span>
        <span className="ml-auto tabular-nums">{items.length}</span>
      </div>
      <div className="space-y-1.5">
        {items.map((item, index) => (
          <Link
            key={`${item.kind}:${item.href}`}
            to={item.href}
            onClick={onResultClick}
            className="group flex min-w-0 items-center gap-3 rounded-lg border border-transparent px-2.5 py-2.5 text-left transition-colors hover:border-border hover:bg-muted/45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45"
          >
            <CoverCell
              index={index}
              coverUrl={item.cover_url}
              className="size-9 shrink-0"
              label={item.label}
            />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-semibold text-foreground">{item.label}</span>
              {item.subtitle && (
                <span className="mt-0.5 block truncate text-xs text-muted-foreground">{item.subtitle}</span>
              )}
            </span>
            <span className="hidden shrink-0 text-xs tabular-nums text-muted-foreground sm:inline">
              {formatPlayEvents(item.play_events)}
            </span>
            <ArrowUpRight className="size-3.5 shrink-0 text-muted-foreground transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" aria-hidden="true" />
          </Link>
        ))}
      </div>
    </section>
  )
}
