import { ChevronLeft, ChevronRight, Search } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef } from 'react'
import { useLocation, useNavigate, useNavigationType, useSearchParams } from 'react-router-dom'

import { MobilePageHeader } from '@/components/mobile'
import { useAnalysisFilters } from '@/hooks/useAnalysis'
import { useRuntimeCapabilities } from '@/hooks/useRuntimeCapabilities'
import { useViewportMode } from '@/hooks/useViewportMode'
import { cn } from '@/lib/utils'
import type { MusicSearchKind } from '@/types/music-search'

import { MusicSearchResults } from './MusicSearchResults'
import { RecentMusicEntityList } from './RecentMusicEntityList'
import { MUSIC_SEARCH_KIND_LABELS, trimSearchQuery } from './musicSearchUtils'
import { useRecentMusicEntities } from './recentMusicEntities'
import { useMusicSearchInputController } from './searchInputController'
import { useMusicSearchCandidates, useMusicSearchContext } from './useMusicSearch'

const KIND_TABS: Array<{ value: MusicSearchKind | 'all'; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'track', label: MUSIC_SEARCH_KIND_LABELS.track },
  { value: 'album', label: MUSIC_SEARCH_KIND_LABELS.album },
  { value: 'artist', label: MUSIC_SEARCH_KIND_LABELS.artist },
]

function parseKind(value: string | null): MusicSearchKind | undefined {
  return value === 'track' || value === 'album' || value === 'artist' ? value : undefined
}

function parsePage(value: string | null): number {
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1
}

function candidateEntityKeys(data: ReturnType<typeof useMusicSearchCandidates>['data']): string[] {
  if (!data) return []
  return [...data.tracks, ...data.albums, ...data.artists].map((item) => item.entity_key)
}

export function MusicSearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const location = useLocation()
  const navigate = useNavigate()
  const navigationType = useNavigationType()
  const qParam = searchParams.get('q') ?? ''
  const kindParam = parseKind(searchParams.get('kind'))
  const pageParam = kindParam ? parsePage(searchParams.get('page')) : 1
  const input = useMusicSearchInputController(qParam)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigationScrollSavedKeyRef = useRef<string | null>(null)
  const pendingScrollRestoreRef = useRef<{ storageKey: string; top: number } | null>(null)
  const query = input.draft
  const isPhone = useViewportMode() === 'phone'
  const { filters, loading: filtersLoading } = useAnalysisFilters()
  const { capabilities } = useRuntimeCapabilities()
  const recent = useRecentMusicEntities(capabilities.surface === 'private-admin')

  useEffect(() => {
    const storageKey = `spotify-stats:music-search-scroll:${location.pathname}${location.search}`
    let canPersist = false
    queueMicrotask(() => {
      canPersist = true
    })
    if (navigationType === 'POP') {
      try {
        const saved = Number(sessionStorage.getItem(storageKey))
        if (Number.isFinite(saved) && saved > 0) {
          pendingScrollRestoreRef.current = { storageKey, top: saved }
        }
      } catch {
        // Scroll restoration is a non-blocking convenience.
      }
    } else {
      pendingScrollRestoreRef.current = null
    }
    return () => {
      if (!canPersist) return
      if (navigationScrollSavedKeyRef.current === storageKey) return
      try {
        sessionStorage.setItem(storageKey, String(window.scrollY))
      } catch {
        // Scroll restoration is a non-blocking convenience.
      }
    }
  }, [location.pathname, location.search, navigationType])

  useEffect(() => {
    const state = location.state as { autofocusSearch?: boolean } | null
    if (!state?.autofocusSearch) return
    inputRef.current?.focus({ preventScroll: true })
    navigate(`${location.pathname}${location.search}`, {
      replace: true,
      state: { ...state, autofocusSearch: undefined },
    })
  }, [location.pathname, location.search, location.state, navigate])

  useEffect(() => {
    const trimmed = input.settledQuery
    if (trimmed === qParam && (!searchParams.has('page') || kindParam)) return
    const next = new URLSearchParams(searchParams)
    if (trimmed) next.set('q', trimmed)
    else next.delete('q')
    next.delete('page')
    setSearchParams(next, { replace: true })
  }, [input.settledQuery, kindParam, qParam, searchParams, setSearchParams])

  const requestQuery = input.canSearch ? input.settledQuery : ''
  const pageSize = kindParam ? 20 : 5
  const candidates = useMusicSearchCandidates({
    query: requestQuery,
    filters,
    filtersLoading,
    kind: kindParam,
    page: pageParam,
    pageSize,
  })
  const entityKeys = useMemo(() => candidateEntityKeys(candidates.data), [candidates.data])
  const context = useMusicSearchContext({
    entityKeys,
    filterFingerprint: candidates.data?.filter_fingerprint ?? null,
    filters,
    enabled: candidates.data?.snapshot_status === 'ready' && !candidates.isPlaceholderData,
  })
  const resultQuery = useMemo(() => trimSearchQuery(input.settledQuery), [input.settledQuery])
  const hasQuery = resultQuery.length > 0
  const kindTotal = kindParam ? candidates.data?.total_by_kind[kindParam] ?? 0 : 0
  const pageCount = kindParam ? Math.max(1, Math.ceil(kindTotal / pageSize)) : 1
  const resultStart = kindTotal > 0 ? (pageParam - 1) * pageSize + 1 : 0
  const resultEnd = Math.min(pageParam * pageSize, kindTotal)

  useEffect(() => {
    const pending = pendingScrollRestoreRef.current
    const storageKey = `spotify-stats:music-search-scroll:${location.pathname}${location.search}`
    const hasResultLayout = Boolean(candidates.data && candidates.data.total > 0)
    if (
      navigationType !== 'POP'
      || !pending
      || pending.storageKey !== storageKey
      || !hasResultLayout
    ) return

    let cancelled = false
    let frameId = 0
    let attempt = 0
    const restore = () => {
      if (cancelled || pendingScrollRestoreRef.current !== pending) return
      const maxScrollTop = Math.max(
        0,
        document.documentElement.scrollHeight - window.innerHeight,
      )
      if (maxScrollTop < pending.top && attempt < 8) {
        attempt += 1
        frameId = window.requestAnimationFrame(restore)
        return
      }
      window.scrollTo({ top: Math.min(pending.top, maxScrollTop), behavior: 'auto' })
      pendingScrollRestoreRef.current = null
    }
    frameId = window.requestAnimationFrame(restore)
    return () => {
      cancelled = true
      window.cancelAnimationFrame(frameId)
    }
  }, [
    candidates.data,
    candidates.isPlaceholderData,
    location.pathname,
    location.search,
    navigationType,
  ])

  useEffect(() => {
    if (!kindParam || !candidates.data || candidates.isPlaceholderData || pageParam <= pageCount) return
    const next = new URLSearchParams(searchParams)
    if (pageCount > 1) next.set('page', String(pageCount))
    else next.delete('page')
    setSearchParams(next, { replace: true })
  }, [candidates.data, candidates.isPlaceholderData, kindParam, pageCount, pageParam, searchParams, setSearchParams])

  const setKind = (kind: MusicSearchKind | 'all') => {
    const next = new URLSearchParams()
    const trimmed = trimSearchQuery(query)
    if (trimmed) next.set('q', trimmed)
    if (kind !== 'all') next.set('kind', kind)
    setSearchParams(next)
  }

  const setPage = (page: number) => {
    if (!kindParam || page < 1 || page > pageCount) return
    const next = new URLSearchParams(searchParams)
    if (page > 1) next.set('page', String(page))
    else next.delete('page')
    setSearchParams(next)
  }

  const handleResultClick = useCallback((item: Parameters<typeof recent.record>[0]) => {
    recent.record(item)
    const storageKey = `spotify-stats:music-search-scroll:${location.pathname}${location.search}`
    try {
      sessionStorage.setItem(storageKey, String(window.scrollY))
      navigationScrollSavedKeyRef.current = storageKey
    } catch {
      // Scroll restoration is a non-blocking convenience.
    }
  }, [location.pathname, location.search, recent])

  return (
    <div className={cn('mx-auto w-full max-w-[1100px] space-y-6', isPhone && 'mobile-m5-page mobile-music-search-page', isPhone && hasQuery && 'mobile-music-search-active')}>
      {isPhone ? (
        !hasQuery && <MobilePageHeader eyebrow="Music / Search" title="音乐查找" />
      ) : (
        <section>
          <p className="mb-4 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">Music / Search</p>
          <h1 className="font-serif text-[44px] font-bold leading-[1.06] tracking-[-0.4px] sm:text-[56px]">音乐查找</h1>
        </section>
      )}

      <section className={cn('space-y-3', isPhone && 'mobile-music-search-controls')} aria-label="音乐查找表单">
        {isPhone && hasQuery && <p className="mobile-music-search-caption">在本地音乐库中查找</p>}
        <div className={cn('flex min-w-0 items-center gap-3 rounded-lg border border-border bg-card px-4 py-3 shadow-sm', isPhone && 'mobile-music-search-input')}>
          <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <input
            ref={inputRef}
            type="search"
            role="searchbox"
            aria-label="搜索歌曲、专辑或艺人"
            value={query}
            onChange={(event) => input.setDraft(event.target.value)}
            onCompositionStart={input.onCompositionStart}
            onCompositionEnd={(event) => input.onCompositionEnd(event.currentTarget.value)}
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
                className={active
                  ? 'min-h-11 rounded-lg bg-accent-foreground px-3 py-1.5 text-sm font-semibold text-card'
                  : 'min-h-11 rounded-lg border border-border bg-card px-3 py-1.5 text-sm font-semibold text-muted-foreground transition-colors hover:bg-muted hover:text-foreground'}
              >
                {tab.label}
              </button>
            )
          })}
        </div>
      </section>

      <MusicSearchResults
        data={candidates.data}
        contextData={context.data}
        query={resultQuery}
        initialLoading={candidates.initialLoading}
        updating={candidates.updating}
        contextLoading={context.loading}
        error={candidates.error}
        contextError={context.error}
        onRetry={candidates.refetch}
        maintenanceHref={capabilities.settings && capabilities.metadata_governance
          ? '/settings#music-metadata-management'
          : null}
        publicReadonly={capabilities.surface === 'public-readonly'}
        mobile={isPhone}
        showGroupLinks
        onResultClick={handleResultClick}
      />

      {!hasQuery && <RecentMusicEntityList items={recent.items} onClear={recent.clear} />}

      {kindParam && candidates.data?.snapshot_status === 'ready' && kindTotal > 0 && (
        <nav className="flex min-h-11 items-center justify-center gap-3" aria-label="搜索结果分页">
          <button
            type="button"
            className="inline-flex size-11 items-center justify-center rounded-lg border border-border bg-card disabled:opacity-40"
            disabled={pageParam <= 1 || candidates.updating}
            onClick={() => setPage(pageParam - 1)}
            aria-label="上一页"
          >
            <ChevronLeft className="size-4" aria-hidden="true" />
          </button>
          <span className="min-w-32 text-center text-sm tabular-nums text-muted-foreground">
            {resultStart}–{resultEnd} / {kindTotal} · 第 {pageParam} / {pageCount} 页
          </span>
          <button
            type="button"
            className="inline-flex size-11 items-center justify-center rounded-lg border border-border bg-card disabled:opacity-40"
            disabled={pageParam >= pageCount || candidates.updating}
            onClick={() => setPage(pageParam + 1)}
            aria-label="下一页"
          >
            <ChevronRight className="size-4" aria-hidden="true" />
          </button>
        </nav>
      )}
    </div>
  )
}
