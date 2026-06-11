import { useEffect, useCallback } from 'react'

import type { TrendingEntity, TrendingData } from '@/hooks/useCommunity'
import type { FeedMeta } from '@/types/community'

import { CommunitySidebar } from './CommunitySidebar'

interface MobileSidebarDrawerProps {
  posts: { posted_at: string }[]
  meta: FeedMeta | null
  trendingArtists?: TrendingEntity[]
  trendingTracks?: TrendingEntity[]
  latestNo1?: TrendingData['latest_no1']
  latestDebut?: TrendingData['latest_debut']
  open: boolean
  onClose: () => void
}

export function MobileSidebarDrawer({
  posts, meta, trendingArtists, trendingTracks,
  latestNo1, latestDebut, open, onClose,
}: MobileSidebarDrawerProps) {
  const onKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape') onClose()
  }, [onClose])

  useEffect(() => {
    if (open) {
      document.addEventListener('keydown', onKeyDown)
      document.body.style.overflow = 'hidden'
    }
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = ''
    }
  }, [open, onKeyDown])

  if (!open) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Bottom drawer */}
      <div className="fixed inset-x-0 bottom-0 z-50 max-h-[85vh] rounded-t-2xl bg-background border-t border-white/10 shadow-2xl overflow-hidden animate-slide-up">
        {/* Drag handle */}
        <div className="flex justify-center pt-3 pb-2">
          <div className="w-10 h-1 rounded-full bg-white/20" />
        </div>

        {/* Header */}
        <div className="flex items-center justify-between px-5 pb-3">
          <h2 className="text-[17px] font-extrabold text-foreground">探索</h2>
          <button
            type="button"
            onClick={onClose}
            className="flex items-center justify-center w-8 h-8 rounded-full hover:bg-white/10 transition-colors"
          >
            <svg className="w-5 h-5 text-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Scrollable content */}
        <div className="overflow-y-auto max-h-[calc(85vh-4rem)] px-4 pb-8">
          <CommunitySidebar
            posts={posts}
            meta={meta}
            trendingArtists={trendingArtists}
            trendingTracks={trendingTracks}
            latestNo1={latestNo1}
            latestDebut={latestDebut}
          />
        </div>
      </div>
    </>
  )
}
