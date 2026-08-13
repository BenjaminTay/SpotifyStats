import { lazy, Suspense, useState } from 'react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { useAccount, useProfile } from '@/hooks/useAccount'
import { CollectionTab } from '@/pages/account/CollectionTab'
import { GlassCard } from '@/components/shared/GlassCard'
import { AnalysisPageHeader } from '@/components/shared/AnalysisPageHeader'
import { AnalysisSubNav } from '@/components/shared/AnalysisSubNav'
import { AlertCircle } from 'lucide-react'
import type { AccountSummary, ProfileData } from '@/types/account'
import { useViewportMode } from '@/hooks/useViewportMode'
import { MobileAccountHero } from '@/features/mobile/account/MobileAccountHero'
import { AccountArchiveDesktopRoute } from '@/features/account-archive/route/AccountArchiveDesktopRoute'

const HabitsTab = lazy(() =>
  import('@/features/account/habits/HabitsTab').then((m) => ({ default: m.HabitsTab })),
)

type TabKey = 'collection' | 'habits'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'collection', label: '你的收藏' },
  { key: 'habits', label: '你的习惯' },
]

function formatNumber(n: number): string {
  return new Intl.NumberFormat('zh-CN').format(n)
}

function AccountHero({
  profileData,
  collectionInsights,
}: {
  profileData: ProfileData | null
  collectionInsights?: AccountSummary['collection_insights'] | null
}) {
  const isPhone = useViewportMode() === 'phone'
  const profile = profileData?.profile
  const displayName = profile?.identity_displayName || profile?.identity_firstName || 'Spotify 用户'
  const imageUrl = profile?.identity_imageUrl
  const username = profile?.attr_username
  const country = profile?.attr_country
  const stats = profileData?.stats
  const firstPlayDate = stats?.first_play_date || null
  const totalPlays = stats?.total_audio_plays || 0
  const followsCount = profileData?.follows?.length || 0

  let listeningYears: number | null = null
  let startYear: number | null = null
  if (firstPlayDate) {
    const d = new Date(firstPlayDate)
    if (!isNaN(d.getTime())) {
      listeningYears = new Date().getFullYear() - d.getFullYear()
      startYear = d.getFullYear()
    }
  }

  const personality = collectionInsights?.available
    ? collectionInsights.personality
    : null

  if (isPhone) {
    return (
      <MobileAccountHero
        displayName={displayName}
        imageUrl={imageUrl}
        username={username}
        country={country}
        listeningYears={listeningYears}
        startYear={startYear}
        totalPlays={totalPlays}
        followsCount={followsCount}
        personality={personality}
      />
    )
  }

  return (
    <>
      <section className="mb-8">
        <p className="mb-3 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
          Account Center
        </p>

        {/* Hero card — editorial profile */}
        <GlassCard className="overflow-hidden p-0">
          <div className={cn(
            'flex flex-col gap-0',
            'bg-gradient-to-br from-[#faf8f5] via-[#f3efe8] to-[#e8e0d5]',
            'dark:from-[#1a1a2e] dark:via-[#16213e] dark:to-[#0f3460]',
          )}>
            {/* Main content */}
            <div className="flex flex-col gap-6 p-8 sm:flex-row sm:items-start">
              {/* Avatar */}
              <div className="flex-shrink-0">
                {imageUrl ? (
                  <img
                    src={imageUrl}
                    alt={displayName}
                    className="h-[88px] w-[88px] rounded-full object-cover ring-[3px] ring-white/40 dark:ring-white/15 shadow-lg"
                  />
                ) : (
                  <div className={cn(
                    'h-[88px] w-[88px] rounded-full flex items-center justify-center shadow-lg',
                    'bg-gradient-to-br from-amber-400 via-rose-400 to-indigo-500',
                  )}>
                    <span className="font-serif text-[38px] font-bold text-white">
                      {displayName.charAt(0).toUpperCase()}
                    </span>
                  </div>
                )}
              </div>

              {/* Info */}
              <div className="flex flex-1 flex-col gap-1.5 min-w-0">
                <h2 className="font-serif text-[34px] font-bold leading-[1.08] tracking-[-0.8px]">
                  {displayName}
                </h2>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 font-sans text-sm text-muted-foreground">
                  {username && <span>@{username}</span>}
                  {country && <span>&middot; {country}</span>}
                </div>
                <p className="mt-1 max-w-lg font-sans text-sm leading-relaxed text-muted-foreground dark:text-white/65">
                  {listeningYears !== null && startYear !== null
                    ? `从 ${startYear} 年开始用 Spotify 听歌，至今已 ${listeningYears} 年。累计播放 ${formatNumber(totalPlays)} 次，关注了 ${followsCount} 位音乐人。`
                    : `累计播放 ${formatNumber(totalPlays)} 次，关注了 ${followsCount} 位音乐人。`
                  }
                </p>
              </div>

              {/* Personality badge — right aligned */}
              {personality && (
                <div className="flex-shrink-0">
                  <span className={cn(
                    'inline-flex items-center gap-1.5 rounded-full px-4 py-2',
                    'bg-white/60 dark:bg-white/10',
                    'border border-border/40',
                    'shadow-sm',
                  )}>
                    <span className="text-base">{personality.icon}</span>
                    <span className="font-sans text-[13px] font-semibold">{personality.type}</span>
                  </span>
                </div>
              )}
            </div>

            {/* Stats bar */}
            <div className={cn(
              'grid grid-cols-2 divide-x divide-border/25 sm:grid-cols-4',
              'border-t border-border/20 bg-background/30 dark:bg-white/5',
            )}>
              {listeningYears !== null && (
                <div className="px-6 py-4 text-center">
                  <p className="font-serif text-[26px] font-bold leading-none">{listeningYears}</p>
                  <p className="mt-0.5 font-sans text-[11px] text-muted-foreground">收听年数</p>
                </div>
              )}
              <div className="px-6 py-4 text-center">
                <p className="font-serif text-[26px] font-bold leading-none">{formatNumber(totalPlays)}</p>
                <p className="mt-0.5 font-sans text-[11px] text-muted-foreground">总播放次数</p>
              </div>
              {startYear && (
                <div className="px-6 py-4 text-center">
                  <p className="font-serif text-[26px] font-bold leading-none">{startYear}</p>
                  <p className="mt-0.5 font-sans text-[11px] text-muted-foreground">起始年份</p>
                </div>
              )}
              <div className="px-6 py-4 text-center">
                <p className="font-serif text-[26px] font-bold leading-none">{followsCount}</p>
                <p className="mt-0.5 font-sans text-[11px] text-muted-foreground">关注</p>
              </div>
            </div>
          </div>
        </GlassCard>
      </section>
    </>
  )
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <div className="mb-8">
        <div className="mb-3 h-3 w-32 animate-pulse rounded bg-muted" />
        <div className="h-[200px] animate-pulse rounded-2xl bg-muted" />
      </div>
      <div className="flex gap-7 border-b border-border pb-0">
        {[1, 2].map((i) => (
          <div key={i} className="h-8 w-24 animate-pulse rounded bg-muted" />
        ))}
      </div>
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-48 animate-pulse rounded-xl bg-muted" />
        ))}
      </div>
    </div>
  )
}

function AccountContentSkeleton() {
  return (
    <>
      <div className="flex gap-7 border-b border-border pb-0">
        {[1, 2].map((i) => (
          <div key={i} className="h-8 w-24 animate-pulse rounded bg-muted" />
        ))}
      </div>
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-48 animate-pulse rounded-xl bg-muted" />
        ))}
      </div>
    </>
  )
}

function ErrorState({ error, onRetry }: { error: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center gap-4 py-20 text-center">
      <AlertCircle className="h-8 w-8 text-accent-foreground" />
      <p className="text-muted-foreground">加载失败：{error}</p>
      <button
        onClick={onRetry}
        className="rounded-full bg-accent-foreground px-6 py-2 text-[13px] font-semibold text-primary-foreground transition-opacity hover:opacity-85"
      >
        重新加载
      </button>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center gap-4 py-24">
      <p className="text-center font-serif text-xl font-semibold">尚未导入账号数据</p>
      <p className="max-w-md text-center text-[15px] leading-relaxed text-muted-foreground">
        前往
        <a href="/settings" className="mx-1 font-medium text-accent-foreground underline underline-offset-2">
          设置页面
        </a>
        导入 Spotify 账号数据（YourLibrary.json、SearchQueries.json 等），即可解锁你的音乐人格档案。
      </p>
    </div>
  )
}

function AccountPageShell({ children }: { children: ReactNode }) {
  return (
    <>
      <AnalysisPageHeader />
      <AnalysisSubNav />
      <div className="mx-auto max-w-[900px] space-y-6 px-0 pb-12 md:px-6">{children}</div>
    </>
  )
}

function LegacyPhoneAccountPage() {
  const { data, loading, error, refetch } = useAccount()
  const { data: profileData } = useProfile()
  const [activeTab, setActiveTab] = useState<TabKey>('collection')
  const profileForHero = data?.profile ?? profileData ?? null

  if (loading && !profileForHero) {
    return (
      <AccountPageShell>
        <LoadingSkeleton />
      </AccountPageShell>
    )
  }
  if (error) {
    return (
      <AccountPageShell>
        <ErrorState error={error} onRetry={refetch} />
      </AccountPageShell>
    )
  }
  if (loading) {
    return (
      <AccountPageShell>
        <AccountHero profileData={profileForHero} />
        <AccountContentSkeleton />
      </AccountPageShell>
    )
  }
  if (!data || !data.has_account_data) {
    return (
      <AccountPageShell>
        <EmptyState />
      </AccountPageShell>
    )
  }

  return (
    <AccountPageShell>
      <AccountHero profileData={profileForHero} collectionInsights={data.collection_insights} />

      {/* Tabs */}
      <div className="mobile-account-tabs flex gap-7 border-b border-border" role="tablist" aria-label="账号内容">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            role="tab"
            aria-selected={activeTab === tab.key}
            className={cn(
              '-mb-px cursor-pointer border-none bg-transparent px-0 pb-2.5 font-sans text-[13px] font-medium transition-[color,border] duration-200',
              'border-b-2',
              activeTab === tab.key
                ? 'border-accent-foreground font-semibold text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="mobile-account-content">
        {activeTab === 'collection' && data.collection_insights?.available && (
          <CollectionTab insights={data.collection_insights} />
        )}
        {activeTab === 'collection' && !data.collection_insights?.available && (
          <div className="py-12 text-center text-muted-foreground">收藏数据不可用</div>
        )}

        {activeTab === 'habits' && (
          <Suspense fallback={<div className="space-y-4 py-6">{Array.from({ length: 3 }).map((_, i) => (<div key={i} className="h-48 animate-pulse rounded-xl bg-muted" />))}</div>}>
            {data.search?.available ? (
              <HabitsTab
                search={data.search}
                tiers={data.insights_tiers}
                marquee={data.insights_marquee}
                podcast={data.podcast}
                video={data.video}
              />
            ) : (
              <div className="py-12 text-center text-muted-foreground">搜索/习惯数据不可用</div>
            )}
          </Suspense>
        )}
      </div>
    </AccountPageShell>
  )
}

export function AccountCenterPage() {
  const mode = useViewportMode()
  return mode === 'phone' ? <LegacyPhoneAccountPage /> : <AccountArchiveDesktopRoute />
}
