import { Search, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog'
import { useAnalysisFilters } from '@/hooks/useAnalysis'
import { useRuntimeCapabilities } from '@/hooks/useRuntimeCapabilities'
import type { MusicSearchCandidate, MusicSearchCandidateResponse } from '@/types/music-search'

import { MusicSearchResults } from './MusicSearchResults'
import { RecentMusicEntityList } from './RecentMusicEntityList'
import { fullSearchHref, musicSearchOptionId, trimSearchQuery } from './musicSearchUtils'
import { useRecentMusicEntities } from './recentMusicEntities'
import { useMusicSearchInputController } from './searchInputController'
import { useMusicSearchCandidates, useMusicSearchContext } from './useMusicSearch'

type MusicSearchDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
}

function flattenSearchResults(data: MusicSearchCandidateResponse | null): MusicSearchCandidate[] {
  if (!data) return []
  return [...data.tracks, ...data.albums, ...data.artists]
}

export function MusicSearchDialog({ open, onOpenChange }: MusicSearchDialogProps) {
  const input = useMusicSearchInputController('')
  const query = input.draft
  const [activeEntityKey, setActiveEntityKey] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)
  const navigate = useNavigate()
  const { filters, loading: filtersLoading } = useAnalysisFilters()
  const { capabilities } = useRuntimeCapabilities()
  const recent = useRecentMusicEntities(capabilities.surface === 'private-admin')

  useEffect(() => {
    if (!open) return
    const focusTimer = window.setTimeout(() => inputRef.current?.focus(), 0)
    return () => window.clearTimeout(focusTimer)
  }, [open])

  const requestQuery = open && input.canSearch ? input.settledQuery : ''
  const candidates = useMusicSearchCandidates({
    query: requestQuery,
    filters,
    filtersLoading,
    pageSize: 3,
  })
  const resultItems = useMemo(() => flattenSearchResults(candidates.data), [candidates.data])
  const entityKeys = useMemo(() => resultItems.map((item) => item.entity_key), [resultItems])
  const context = useMusicSearchContext({
    entityKeys,
    filterFingerprint: candidates.data?.filter_fingerprint ?? null,
    filters,
    enabled: candidates.data?.snapshot_status === 'ready' && !candidates.isPlaceholderData,
  })
  const activeItem = activeEntityKey
    ? resultItems.find((item) => item.entity_key === activeEntityKey)
    : undefined
  const fullHref = fullSearchHref(query)
  const listboxId = 'music-search-dialog-results'

  const moveActiveResult = (direction: 1 | -1) => {
    if (resultItems.length === 0) return
    const current = activeEntityKey
      ? resultItems.findIndex((item) => item.entity_key === activeEntityKey)
      : -1
    const nextIndex = current < 0
      ? direction === 1 ? 0 : resultItems.length - 1
      : (current + direction + resultItems.length) % resultItems.length
    setActiveEntityKey(resultItems[nextIndex]?.entity_key ?? null)
  }

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
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
    if (event.key === 'Enter' && activeItem && event.target === inputRef.current) {
      event.preventDefault()
      recent.record(activeItem)
      onOpenChange(false)
      navigate(activeItem.href)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton={false}
        onKeyDown={handleKeyDown}
        className="!top-16 !max-h-[min(82dvh,720px)] w-[calc(100%-1.5rem)] max-w-[820px] !translate-y-0 gap-0 overflow-hidden p-0"
      >
        <DialogTitle className="sr-only">搜索音乐详情</DialogTitle>
        <DialogDescription className="sr-only">查找本地播放历史中的歌曲、专辑或艺人</DialogDescription>
        <div className="flex items-center gap-3 border-b border-border px-4 py-3">
          <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <input
            ref={inputRef}
            type="search"
            role="combobox"
            aria-label="搜索歌曲、专辑或艺人"
            aria-autocomplete="list"
            aria-controls={listboxId}
            aria-expanded={resultItems.length > 0}
            aria-activedescendant={activeEntityKey ? musicSearchOptionId(activeEntityKey) : undefined}
            value={query}
            onChange={(event) => {
              setActiveEntityKey(null)
              input.setDraft(event.target.value)
            }}
            onCompositionStart={input.onCompositionStart}
            onCompositionEnd={(event) => {
              setActiveEntityKey(null)
              input.onCompositionEnd(event.currentTarget.value)
            }}
            placeholder="搜索歌曲、专辑或艺人"
            className="h-10 min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-muted-foreground"
          />
          <DialogClose className="flex size-9 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground" aria-label="关闭搜索">
            <X className="size-4" aria-hidden="true" />
          </DialogClose>
        </div>
        <div className="max-h-[min(68dvh,620px)] overflow-y-auto overscroll-contain p-3 sm:p-4">
          <p className="sr-only" role="status" aria-live="polite">
            {candidates.data?.snapshot_status === 'ready'
              ? `找到 ${candidates.data.total} 个结果`
              : candidates.initialLoading
                ? '正在搜索'
                : ''}
          </p>
          <MusicSearchResults
            data={candidates.data}
            contextData={context.data}
            query={input.settledQuery}
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
            compact
            activeEntityKey={activeEntityKey}
            onActiveEntityKeyChange={setActiveEntityKey}
            onResultClick={(item) => {
              recent.record(item)
              onOpenChange(false)
            }}
            listboxId={listboxId}
          />
          {!trimSearchQuery(query) && (
            <div className="mt-3">
              <RecentMusicEntityList
                items={recent.items}
                onClear={recent.clear}
                onOpen={() => onOpenChange(false)}
                compact
              />
            </div>
          )}
        </div>
        {trimSearchQuery(query) && (
          <div className="flex justify-end border-t border-border px-4 py-3">
            <Link
              to={fullHref}
              onClick={() => onOpenChange(false)}
              className="min-h-11 rounded-lg px-3 py-2.5 text-sm font-semibold text-accent-foreground transition-colors hover:bg-muted"
            >
              查看全部结果
            </Link>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
