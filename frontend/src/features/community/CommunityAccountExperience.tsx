import { useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'

import { useCommunityFeed } from '@/hooks/useCommunity'
import { AccountAvatar } from './AccountAvatar'
import { CommunitySidebar } from './CommunitySidebar'
import { CommunityTimeline } from './CommunityTimeline'
import { ACCOUNT_CONFIG, formatFollowerCount } from './communityData'

export function CommunityAccountExperience() {
  const { handle } = useParams<{ handle: string }>()
  const decodedHandle = decodeURIComponent(handle ?? '')
  const account = ACCOUNT_CONFIG[decodedHandle]

  const filters = useMemo(() => {
    const f: Record<string, string | number | boolean> = { limit: 50, offset: 0 }
    if (decodedHandle) f.accounts = decodedHandle
    return f
  }, [decodedHandle])

  const { posts, meta, loading, loadingMore, error, refetch, hasMore, loadMore } = useCommunityFeed(filters)

  if (!account) {
    return (
      <>
        <section className="mb-6">
          <p className="mb-4 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
            Community / Account
          </p>
          <h1 className="font-serif text-[48px] font-bold leading-[1.06] tracking-[-1.2px]">
            Account not found
          </h1>
        </section>
        <div className="max-w-[720px] mx-auto text-center py-20">
          <p className="text-muted-foreground">This account does not exist.</p>
          <Link to="/community" className="mt-3 inline-block text-[15px] text-accent-foreground hover:underline">
            Back to community
          </Link>
        </div>
      </>
    )
  }

  return (
    <>
      {/* Hero — same as other pages */}
      <section className="mb-6">
        <p className="mb-4 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
          Community / Account
        </p>
        <h1 className="font-serif text-[48px] font-bold leading-[1.06] tracking-[-1.2px]">
          榜单社区
        </h1>
      </section>

      {/* Two-column layout */}
      <div className="flex gap-8">
        {/* Main: profile + feed */}
        <div className="flex-1 max-w-[720px] min-h-[70vh]">
          {/* Back button */}
          <div className="flex items-center gap-6 h-[53px] border-b border-white/10">
          <Link
            to="/community"
            className="flex items-center justify-center w-9 h-9 rounded-full hover:bg-white/10 transition-colors -ml-1"
            aria-label="Back"
          >
            <svg className="w-5 h-5 text-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </Link>
          <div>
            <p className="text-[17px] font-bold text-foreground">{account.display_name}</p>
            <p className="text-[13px] text-muted-foreground">{posts.length} posts</p>
          </div>
        </div>

        {/* Profile header — X style */}
        <div className="border-b border-white/10">
          {/* Banner area with real photo, CSS gradient fallback */}
          <div
            className="relative h-48 overflow-hidden"
            style={{ background: account.banner_bg ?? account.avatar.bg_gradient }}
          >
            {account.banner_url && (
              <img
                src={account.banner_url}
                alt=""
                className="absolute inset-0 w-full h-full object-cover"
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = 'none'
                }}
              />
            )}
            {/* Subtle dark overlay for text readability */}
            <div className="absolute inset-0 bg-black/20" />
            {/* Subtle vignette */}
            <div
              className="absolute inset-0"
              style={{
                background: 'radial-gradient(ellipse at center, transparent 40%, rgba(0,0,0,0.35) 100%)',
              }}
            />
            {/* Large watermark initials */}
            <div
              className="absolute right-6 -bottom-4 select-none pointer-events-none"
              style={{
                fontFamily: "'Playfair Display', serif",
                fontSize: '120px',
                fontWeight: 900,
                lineHeight: 1,
                color: 'rgba(255,255,255,0.08)',
                letterSpacing: '-4px',
              }}
            >
              {account.avatar.initials}
            </div>
          </div>

          {/* Avatar + actions row */}
          <div className="px-4 pb-3 relative z-10">
            <div className="flex justify-between items-end -mt-12 mb-3">
              <div className="rounded-full ring-4 ring-background">
                <AccountAvatar handle={decodedHandle} size="xl" />
              </div>
            </div>

            {/* Name + handle */}
            <p className="text-[20px] font-extrabold text-foreground">{account.display_name}</p>
            <p className="text-[15px] text-muted-foreground">{account.handle}</p>

            {/* Bio */}
            <p className="mt-3 text-[15px] text-foreground leading-5">{account.bio}</p>

            {/* Stats row */}
            <div className="flex items-center gap-4 mt-3 text-[13px]">
              <span>
                <strong className="text-foreground">{formatFollowerCount(account.follower_tier)}</strong>
                {' '}
                <span className="text-muted-foreground">Followers</span>
              </span>
            </div>
          </div>

          {/* Mini nav: Posts tab indicator */}
          <div className="flex border-b border-white/10">
            <button
              type="button"
              className="flex-1 flex items-center justify-center h-[53px] relative text-[15px] font-semibold text-foreground"
            >
              Posts
              <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-12 h-1 rounded-full bg-accent-foreground" />
            </button>
          </div>
        </div>

        {/* Account's posts feed */}
        {(() => {
          if (loading && posts.length === 0) {
            return (
              <div>
                {Array.from({ length: 3 }).map((_, i) => (
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
              <div className="flex flex-col items-center justify-center py-20 text-muted-foreground gap-2">
                <p className="text-[15px] font-medium">Failed to load</p>
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

        {/* Right sidebar */}
        <aside className="w-[340px] shrink-0 hidden lg:block">
          <div className="sticky top-4 max-h-[calc(100vh-2rem)] overflow-y-auto scrollbar-thin">
            <CommunitySidebar posts={posts} meta={meta} />
          </div>
        </aside>
      </div>
    </>
  )
}
