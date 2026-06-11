import { useCallback, useMemo, useState } from 'react'

import { useCommunityFeed } from '@/hooks/useCommunity'

import { CommunitySidebar } from './CommunitySidebar'
import { CommunityTimeline } from './CommunityTimeline'
import { FeedToggle } from './FeedToggle'
import type { FeedTab } from './FeedToggle'
import { TimeFilter, ALL_PERIOD } from './TimeFilter'
import type { TimePeriod } from './TimeFilter'

// Module-level cache for UI state (permitted by Phase 5 rules)
let cachedTab: FeedTab = 'highlights'
let cachedPeriod: TimePeriod = ALL_PERIOD

export function CommunityExperience() {
  const [activeTab, setActiveTab] = useState<FeedTab>(cachedTab)
  const [period, setPeriod] = useState<TimePeriod>(cachedPeriod)

  // 精选 = newsworthy post types only, 全部 = no filter
  const filters = useMemo(() => {
    const f: Record<string, string | number | boolean> = { limit: 50, offset: 0 }
    if (activeTab === 'highlights') f.highlights_only = true
    if (period.date_from) f.date_from = period.date_from
    if (period.date_to) f.date_to = period.date_to
    return f
  }, [activeTab, period])

  const { posts, meta, loading, loadingMore, error, refetch, hasMore, loadMore } = useCommunityFeed(filters)

  const handleTabChange = useCallback((tab: FeedTab) => {
    cachedTab = tab
    setActiveTab(tab)
  }, [])

  const handlePeriodChange = useCallback((p: TimePeriod) => {
    cachedPeriod = p
    setPeriod(p)
  }, [])

  return (
    <>
      {/* Hero — same pattern as BillboardPage / NumberOnesPage */}
      <section className="mb-6">
        <p className="mb-4 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
          Community / Feed
        </p>
        <h1 className="font-serif text-[48px] font-bold leading-[1.06] tracking-[-1.2px]">
          榜单社区
        </h1>
      </section>

      {/* Two-column layout: feed + sidebar (X/Weibo style) */}
      <div className="flex gap-8">
        {/* Main feed column */}
        <div className="flex-1 max-w-[720px] min-h-[70vh]">
          {/* Feed toggle — X "For You" / "Following" style */}
          <FeedToggle
            active={activeTab}
            onChange={handleTabChange}
            highlightsCount={activeTab === 'highlights' ? meta?.total : undefined}
            allCount={meta?.total_all}
          />

          {/* Time period filter */}
          <TimeFilter selected={period} onChange={handlePeriodChange} />

          {/* Timeline content */}
          {(() => {
            if (loading && posts.length === 0) {
              return (
                <div>
                  {Array.from({ length: 5 }).map((_, i) => (
                    <div key={i} className="flex gap-3 py-3 border-b border-white/10 animate-pulse">
                      <div className="w-10 h-10 rounded-full bg-white/10 shrink-0" />
                      <div className="flex-1 space-y-2">
                        <div className="flex gap-2">
                          <div className="h-4 w-24 bg-white/10 rounded" />
                          <div className="h-4 w-16 bg-white/10 rounded" />
                        </div>
                        <div className="space-y-1.5">
                          <div className="h-4 w-full bg-white/10 rounded" />
                          <div className="h-4 w-3/4 bg-white/10 rounded" />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )
            }

            if (error) {
              return (
                <div className="flex flex-col items-center justify-center py-20 text-muted-foreground gap-2 px-4">
                  <p className="text-[15px] font-medium">Failed to load</p>
                  <p className="text-[13px] opacity-60">{error}</p>
                  <button
                    type="button"
                    className="mt-3 px-5 py-1.5 text-[14px] font-medium rounded-full bg-accent-foreground text-primary-foreground transition-opacity hover:opacity-85"
                    onClick={() => refetch()}
                  >
                    Retry
                  </button>
                </div>
              )
            }

            return (
              <CommunityTimeline
                posts={posts}
                loading={loadingMore}
                hasMore={hasMore}
                onLoadMore={loadMore}
              />
            )
          })()}
        </div>

        {/* Right sidebar — sticky, hidden on narrow screens */}
        <aside className="w-[340px] shrink-0 hidden lg:block">
          <div className="sticky top-4 max-h-[calc(100vh-2rem)] overflow-y-auto scrollbar-thin">
            <CommunitySidebar posts={posts} meta={meta} />
          </div>
        </aside>
      </div>
    </>
  )
}
