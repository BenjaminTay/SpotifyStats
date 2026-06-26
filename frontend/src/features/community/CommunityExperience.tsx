import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { useCommunityChartParams, useCommunityFeed, useCommunityTrending } from '@/hooks/useCommunity'

import { CommunitySidebar } from './CommunitySidebar'
import { CommunityTimeline } from './CommunityTimeline'
import { MobileSidebarDrawer } from './MobileSidebarDrawer'
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
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [searchInput, setSearchInput] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const searchTimer = useRef<ReturnType<typeof setTimeout>>(undefined)
  const chartParams = useCommunityChartParams()

  // Debounce search input → search query (300ms)
  const handleSearchChange = useCallback((value: string) => {
    setSearchInput(value)
    clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => setSearchQuery(value), 300)
  }, [])

  useEffect(() => {
    return () => clearTimeout(searchTimer.current)
  }, [])

  // 精选 = newsworthy post types only, 全部 = no filter
  const filters = useMemo(() => {
    const f: Record<string, string | number | boolean> = { ...chartParams, limit: 50, offset: 0 }
    if (activeTab === 'highlights') f.highlights_only = true
    if (period.date_from) f.date_from = period.date_from
    if (period.date_to) f.date_to = period.date_to
    if (searchQuery) f.search = searchQuery
    return f
  }, [activeTab, chartParams, period, searchQuery])

  const { posts, meta, loading, loadingMore, error, refetch, hasMore, loadMore } = useCommunityFeed(filters)

  // Trending data from server — independent of pagination
  const trendingParams = useMemo(() => {
    const params: Record<string, string | number | boolean> = { ...chartParams }
    if (period.date_from) params.date_from = period.date_from
    if (period.date_to) params.date_to = period.date_to
    return params
  }, [chartParams, period])
  const { trending } = useCommunityTrending(trendingParams)

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
      <div className="flex w-full min-w-0 gap-8">
        {/* Main feed column */}
        <div className="min-h-[70vh] w-full min-w-0 max-w-[720px] flex-1">
          {/* Feed toggle + search — X "For You" / "Following" style */}
          <FeedToggle
            active={activeTab}
            onChange={handleTabChange}
            highlightsCount={activeTab === 'highlights' ? meta?.total : undefined}
            allCount={meta?.total_all}
            rightSlot={
              <div className="relative w-[calc(100vw-80px)] max-w-full sm:w-[240px]">
                <svg
                  className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground"
                  viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                  strokeLinecap="round" strokeLinejoin="round"
                >
                  <circle cx="11" cy="11" r="8" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
                <input
                  type="text"
                  value={searchInput}
                  onChange={(e) => handleSearchChange(e.target.value)}
                  placeholder="搜索帖子、账号、艺人..."
                  className="w-full pl-9 pr-3 py-1.5 bg-white/[0.04] border border-white/10 rounded-full text-[13px] text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-accent-foreground/40 focus:bg-white/[0.06] transition-colors"
                />
              </div>
            }
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
            <CommunitySidebar
              posts={posts}
              meta={meta}
              trendingArtists={trending?.artists}
              trendingTracks={trending?.tracks}
              latestNo1={trending?.latest_no1}
              latestDebut={trending?.latest_debut}
            />
          </div>
        </aside>
      </div>

      {/* Mobile: floating button to open sidebar drawer */}
      <button
        type="button"
        onClick={() => setSidebarOpen(true)}
        className="lg:hidden fixed bottom-6 right-6 z-30 flex items-center justify-center w-12 h-12 rounded-full bg-accent-foreground text-primary-foreground shadow-lg hover:opacity-90 transition-opacity"
        aria-label="Open sidebar"
      >
        <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="6" x2="21" y2="6" />
          <line x1="3" y1="18" x2="21" y2="18" />
        </svg>
      </button>

      {/* Mobile sidebar drawer */}
      <MobileSidebarDrawer
        posts={posts}
        meta={meta}
        trendingArtists={trending?.artists}
        trendingTracks={trending?.tracks}
        latestNo1={trending?.latest_no1}
        latestDebut={trending?.latest_debut}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
    </>
  )
}
