import { Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { useMusicSearch } from '@/hooks/useAnalysis'
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
  const [query, setQuery] = useState(qParam)

  useEffect(() => {
    setQuery(qParam)
  }, [qParam])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const trimmed = trimSearchQuery(query)
      if (trimmed === qParam) return
      const next = new URLSearchParams()
      if (trimmed) next.set('q', trimmed)
      if (kindParam) next.set('kind', kindParam)
      setSearchParams(next, { replace: true })
    }, 250)
    return () => window.clearTimeout(timer)
  }, [kindParam, qParam, query, setSearchParams])

  const { data, loading, error } = useMusicSearch(query, kindParam, 5, { includeChart: true })
  const resultQuery = useMemo(() => trimSearchQuery(query), [query])

  const setKind = (kind: MusicSearchKind | 'all') => {
    const next = new URLSearchParams()
    const trimmed = trimSearchQuery(query)
    if (trimmed) next.set('q', trimmed)
    if (kind !== 'all') next.set('kind', kind)
    setSearchParams(next, { replace: true })
  }

  return (
    <div className="mx-auto w-full max-w-[1100px] space-y-6">
      <section>
        <p className="mb-4 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
          Music / Search
        </p>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="font-serif text-[44px] font-bold leading-[1.06] tracking-[-0.4px] sm:text-[56px]">
              音乐查找
            </h1>
            <p className="mt-3 max-w-[620px] text-sm leading-6 text-muted-foreground">
              搜索本地播放记录里的歌曲、专辑和艺人，直接打开对应详情页。
            </p>
          </div>
        </div>
      </section>

      <section className="space-y-3" aria-label="音乐查找表单">
        <div className="flex min-w-0 items-center gap-3 rounded-lg border border-border bg-card px-4 py-3 shadow-sm">
          <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <input
            type="search"
            role="searchbox"
            aria-label="搜索歌曲、专辑或艺人"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="输入歌曲、专辑或艺人名称"
            className="h-10 min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-muted-foreground"
          />
        </div>
        <div className="flex flex-wrap gap-2" role="tablist" aria-label="音乐查找类型">
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
      />
    </div>
  )
}
