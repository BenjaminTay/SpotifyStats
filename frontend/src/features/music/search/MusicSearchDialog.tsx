import { Search, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { useMusicSearch } from '@/hooks/useAnalysis'

import { MusicSearchResults } from './MusicSearchResults'
import { fullSearchHref, trimSearchQuery } from './musicSearchUtils'

type MusicSearchDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function MusicSearchDialog({ open, onOpenChange }: MusicSearchDialogProps) {
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const inputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    if (!open) return
    const focusTimer = window.setTimeout(() => inputRef.current?.focus(), 0)
    return () => window.clearTimeout(focusTimer)
  }, [open])

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(trimSearchQuery(query)), 250)
    return () => window.clearTimeout(timer)
  }, [query])

  useEffect(() => {
    if (!open) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onOpenChange(false)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onOpenChange, open])

  const { data, loading, error } = useMusicSearch(debouncedQuery, undefined, 5)
  const fullHref = fullSearchHref(query)

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
