import { Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { MobilePageHeader } from '@/components/mobile'
import { useMusicSearch } from '@/hooks/useAnalysis'
import { useViewportMode } from '@/hooks/useViewportMode'
import { cn } from '@/lib/utils'
import type { MusicSearchKind } from '@/types/music-search'

import { MusicSearchResults } from './MusicSearchResults'
import { MUSIC_SEARCH_KIND_LABELS, trimSearchQuery } from './musicSearchUtils'

const KIND_TABS: Array<{ value: MusicSearchKind | 'all'; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'track', label: MUSIC_SEARCH_KIND_LABELS.track },
  { value: 'album', label: MUSIC_SEARCH_KIND_LABELS.album },
  { value: 'artist', label: MUSIC_SEARCH_KIND_LABELS.artist },
]

function parseKind(value: string | null): MusicSearchKind | undefined {
  return value === 'track' || value === 'album' || value === 'artist' ? value : undefined
}

export function MusicSearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const qParam = searchParams.get('q') ?? ''
  const kindParam = parseKind(searchParams.get('kind'))
  const [queryState, setQueryState] = useState({ source: qParam, value: qParam })
  const query = queryState.source === qParam ? queryState.value : qParam
  const setQuery = (value: string) => setQueryState({ source: qParam, value })
  const [isComposing, setIsComposing] = useState(false)
  const isPhone = useViewportMode() === 'phone'

  useEffect(() => {
    if (isComposing) return
    const timer = window.setTimeout(() => {
      const trimmed = trimSearchQuery(query)
      if (trimmed === qParam) return
      const next = new URLSearchParams()
      if (trimmed) next.set('q', trimmed)
      if (kindParam) next.set('kind', kindParam)
      setSearchParams(next, { replace: true })
    }, 250)
    return () => window.clearTimeout(timer)
  }, [isComposing, kindParam, qParam, query, setSearchParams])

  const { data, loading, error } = useMusicSearch(query, kindParam, 5, { includeChart: true })
  const resultQuery = useMemo(() => trimSearchQuery(query), [query])
  const hasQuery = resultQuery.length > 0

  const setKind = (kind: MusicSearchKind | 'all') => {
    const next = new URLSearchParams()
    const trimmed = trimSearchQuery(query)
    if (trimmed) next.set('q', trimmed)
    if (kind !== 'all') next.set('kind', kind)
    setSearchParams(next, { replace: true })
  }

  return (
    <div className={cn('mx-auto w-full max-w-[1100px] space-y-6', isPhone && 'mobile-m5-page mobile-music-search-page', isPhone && hasQuery && 'mobile-music-search-active')}>
      {isPhone ? (
        !hasQuery && (
          <MobilePageHeader
            eyebrow="Music / Search"
            title="音乐查找"
          />
        )
      ) : <section>
        <p className="mb-4 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
          Music / Search
        </p>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="font-serif text-[44px] font-bold leading-[1.06] tracking-[-0.4px] sm:text-[56px]">
              音乐查找
            </h1>
          </div>
        </div>
      </section>}

      <section className={cn('space-y-3', isPhone && 'mobile-music-search-controls')} aria-label="音乐查找表单">
        {isPhone && hasQuery && <p className="mobile-music-search-caption">在本地音乐库中查找</p>}
        <div className={cn('flex min-w-0 items-center gap-3 rounded-lg border border-border bg-card px-4 py-3 shadow-sm', isPhone && 'mobile-music-search-input')}>
          <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <input
            type="search"
            role="searchbox"
            aria-label="搜索歌曲、专辑或艺人"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onCompositionStart={() => setIsComposing(true)}
            onCompositionEnd={(event) => {
              setQuery(event.currentTarget.value)
              setIsComposing(false)
            }}
            placeholder="输入歌曲、专辑或艺人名称"
            className="h-10 min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-muted-foreground"
          />
        </div>
        <div className={cn('flex flex-wrap gap-2', isPhone && 'mobile-music-search-kinds')} role="tablist" aria-label="音乐查找类型">
          {KIND_TABS.map((tab) => {
            const active = (kindParam ?? 'all') === tab.value
            return (
              <button
                key={tab.value}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => setKind(tab.value)}
                className={
                  active
                    ? 'rounded-lg bg-accent-foreground px-3 py-1.5 text-sm font-semibold text-card'
                    : 'rounded-lg border border-border bg-card px-3 py-1.5 text-sm font-semibold text-muted-foreground transition-colors hover:bg-muted hover:text-foreground'
                }
              >
                {tab.label}
              </button>
            )
          })}
        </div>
      </section>

      <MusicSearchResults
        data={data}
        query={resultQuery}
        loading={loading}
        error={error}
        mobile={isPhone}
      />
    </div>
  )
}
