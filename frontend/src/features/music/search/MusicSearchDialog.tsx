import { Search, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useMusicSearch } from '@/hooks/useAnalysis'
import type { MusicSearchResponse, MusicSearchResult } from '@/types/music-search'

import { MusicSearchResults } from './MusicSearchResults'
import { fullSearchHref, trimSearchQuery } from './musicSearchUtils'

type MusicSearchDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
}

function flattenSearchResults(data: MusicSearchResponse | null): MusicSearchResult[] {
  if (!data) return []
  return [...data.tracks, ...data.albums, ...data.artists]
}

export function MusicSearchDialog({ open, onOpenChange }: MusicSearchDialogProps) {
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(-1)
  const inputRef = useRef<HTMLInputElement | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (!open) return
    const focusTimer = window.setTimeout(() => inputRef.current?.focus(), 0)
    return () => window.clearTimeout(focusTimer)
  }, [open])

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(trimSearchQuery(query)), 250)
    return () => window.clearTimeout(timer)
  }, [query])

  const { data, loading, error } = useMusicSearch(debouncedQuery, undefined, 5, { includeChart: true })
  const resultItems = useMemo(() => flattenSearchResults(data), [data])
  const activeItem = activeIndex >= 0 ? resultItems[activeIndex] : undefined
  const resultsKey = useMemo(() => resultItems.map((item) => item.href).join('\u0000'), [resultItems])
  const fullHref = fullSearchHref(query)

  useEffect(() => {
    setActiveIndex(-1)
  }, [query, debouncedQuery, loading, open, resultItems.length, resultsKey])

  const moveActiveResult = (direction: 1 | -1) => {
    if (resultItems.length === 0) return
    setActiveIndex((current) => {
      if (current < 0) return direction === 1 ? 0 : resultItems.length - 1
      return (current + direction + resultItems.length) % resultItems.length
    })
  }

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const isSearchInput = event.target === inputRef.current
    if (event.key === 'Escape') {
      event.preventDefault()
      onOpenChange(false)
      return
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      moveActiveResult(1)
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      moveActiveResult(-1)
      return
    }
    if (event.key === 'Enter' && activeItem && isSearchInput) {
      event.preventDefault()
      onOpenChange(false)
      navigate(activeItem.href)
    }
  }

  const handleActiveHrefChange = (href: string) => {
    const nextIndex = resultItems.findIndex((item) => item.href === href)
    if (nextIndex >= 0) setActiveIndex(nextIndex)
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[80] flex items-start justify-center bg-background/70 px-3 py-16 backdrop-blur-[10px] sm:py-20">
      <button
        type="button"
        aria-label="关闭搜索"
        className="absolute inset-0 cursor-default"
        onClick={() => onOpenChange(false)}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="搜索音乐详情"
        onKeyDown={handleKeyDown}
        className="relative w-full max-w-[820px] rounded-lg border border-border bg-card shadow-2xl"
      >
        <div className="flex items-center gap-3 border-b border-border px-4 py-3">
          <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <input
            ref={inputRef}
            type="search"
            role="searchbox"
            aria-label="搜索歌曲、专辑或艺人"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索歌曲、专辑或艺人"
            className="h-10 min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-muted-foreground"
          />
          <button
            type="button"
            aria-label="关闭搜索"
            onClick={() => onOpenChange(false)}
            className="flex size-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>
        <div className="max-h-[min(68vh,620px)] overflow-y-auto p-3 sm:p-4">
          <MusicSearchResults
            data={data}
            query={debouncedQuery}
            loading={loading}
            error={error}
            compact
            activeHref={activeItem?.href}
            onActiveHrefChange={handleActiveHrefChange}
            onResultClick={() => onOpenChange(false)}
          />
        </div>
        {trimSearchQuery(query) && (
          <div className="flex justify-end border-t border-border px-4 py-3">
            <Link
              to={fullHref}
              onClick={() => onOpenChange(false)}
              className="rounded-lg px-3 py-1.5 text-sm font-semibold text-accent-foreground transition-colors hover:bg-muted"
            >
              查看全部结果
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}
