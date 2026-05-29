import { useState } from 'react'
import { cn } from '@/lib/utils'
import { useAccount } from '@/hooks/useAccount'
import { CollectionTab } from '@/pages/account/CollectionTab'
import { HabitsTab } from '@/pages/account/HabitsTab'
import { IdentityTab } from '@/pages/account/IdentityTab'
import { GlassCard } from '@/components/shared/GlassCard'
import { KpiCard } from '@/components/shared/KpiCard'
import { AlertCircle } from 'lucide-react'
import type { AccountSummary } from '@/types/account'

type TabKey = 'collection' | 'habits' | 'identity'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'collection', label: '你的收藏' },
  { key: 'habits', label: '你的习惯' },
  { key: 'identity', label: '你的身份' },
]

function formatNumber(n: number): string {
  return new Intl.NumberFormat('zh-CN').format(n)
}

function AccountHero({ data }: { data: AccountSummary }) {
  const profile = data.profile?.profile
  const displayName = profile?.identity_displayName || profile?.identity_firstName || 'Spotify 用户'
  const imageUrl = profile?.identity_imageUrl
  const firstName = profile?.identity_firstName
  const lastName = profile?.identity_lastName
  const country = profile?.attr_country
  const stats = data.profile?.stats
  const firstPlayYear = stats?.first_play_date
    ? new Date(stats.first_play_date).getFullYear()
    : null
  const totalPlays = stats?.total_audio_plays || 0

  const personality = data.collection_insights?.available
    ? data.collection_insights.personality.type
    : null

  const searchData = data.search
  const videoData = data.video
  let secondaryPersonality = ''
  if (searchData?.available && videoData?.available) {
    const lateNightRatio = searchData.heatmap?.z
      ? searchData.heatmap.z.reduce((sum, row) => {
          for (let h = 23; h <= 23; h++) sum += row[23] || 0
          for (let h = 0; h < 5; h++) sum += row[h] || 0
          return sum
        }, 0) / Math.max(searchData.total_searches, 1)
      : 0
    if (lateNightRatio > 0.3) secondaryPersonality = '午夜活跃者'
    else if (videoData.total_video_plays > 100) secondaryPersonality = '全媒介达人'
    else secondaryPersonality = '专注聆听者'
  }

  return (
    <>
      {/* Page hero — standard pattern */}
      <section className="mb-10">
        <p className="mb-4 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
          Account / Center
        </p>
        <h1 className="mb-3 font-serif text-[44px] font-bold leading-[1.06] tracking-[-1.2px]">
          {displayName}
        </h1>
        <p className="max-w-[520px] font-sans text-[17px] leading-relaxed text-muted-foreground">
          我是怎样的听众？从收藏、习惯到身份，三层递进解码你的 Spotify 音乐人格。
        </p>
      </section>

      {/* Identity card with avatar */}
      <GlassCard className="mb-10 p-8">
        <div className="flex flex-col gap-8 sm:flex-row sm:items-center">
          {/* Avatar */}
          <div className="h-20 w-20 flex-shrink-0 overflow-hidden rounded-full bg-gradient-to-br from-[#667eea] to-[#764ba2] ring-2 ring-border">
            {imageUrl ? (
              <img src={imageUrl} alt={displayName} className="h-full w-full object-cover" />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-3xl">👤</div>
            )}
          </div>

          {/* Detail info */}
          <div className="flex flex-1 flex-wrap gap-x-10 gap-y-3">
            {firstName && lastName && (
              <div>
                <p className="font-sans text-[12px] font-semibold uppercase tracking-[1px] text-muted-foreground">姓名</p>
                <p className="font-sans text-[15px] font-medium">{firstName} {lastName}</p>
              </div>
            )}
            {country && (
              <div>
                <p className="font-sans text-[12px] font-semibold uppercase tracking-[1px] text-muted-foreground">国家</p>
                <p className="font-sans text-[15px] font-medium">{country}</p>
              </div>
            )}
            {firstPlayYear && (
              <div>
                <p className="font-sans text-[12px] font-semibold uppercase tracking-[1px] text-muted-foreground">始于</p>
                <p className="font-sans text-[15px] font-medium">{firstPlayYear} 年</p>
              </div>
            )}
            <div>
              <p className="font-sans text-[12px] font-semibold uppercase tracking-[1px] text-muted-foreground">总播放</p>
              <p className="font-sans text-[15px] font-medium">{formatNumber(totalPlays)}</p>
            </div>
          </div>

          {/* Personality badges */}
          <div className="flex flex-shrink-0 gap-2">
            {personality && (
              <span className="rounded-full bg-accent-foreground/8 px-4 py-1.5 text-xs font-semibold text-accent-foreground">
                {personality}
              </span>
            )}
            {secondaryPersonality && (
              <span className="rounded-full bg-muted px-4 py-1.5 text-xs font-semibold text-muted-foreground">
                {secondaryPersonality}
              </span>
            )}
          </div>
        </div>
      </GlassCard>
    </>
  )
}

function LoadingSkeleton() {
  return (
    <div className="mx-auto max-w-[900px] space-y-6 px-6 py-12">
      <div className="mb-12">
        <div className="mb-4 h-3 w-32 animate-pulse rounded bg-muted" />
        <div className="mb-3 h-[44px] w-80 animate-pulse rounded bg-muted" />
        <div className="h-5 w-96 animate-pulse rounded bg-muted" />
      </div>
      <div className="mb-10 h-[120px] animate-pulse rounded-2xl bg-muted" />
      <div className="flex gap-7 border-b border-border pb-0">
        {[1, 2, 3].map((i) => (
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
    <div className="mx-auto flex max-w-[900px] flex-col items-center gap-4 px-6 py-24">
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

export function AccountCenterPage() {
  const { data, loading, error, refetch } = useAccount()
  const [activeTab, setActiveTab] = useState<TabKey>('collection')

  if (loading) return <LoadingSkeleton />
  if (error) return <ErrorState error={error} onRetry={refetch} />
  if (!data || !data.has_account_data) return <EmptyState />

  return (
    <div className="mx-auto max-w-[900px] space-y-6 px-6 py-12">
      <AccountHero data={data} />

      {/* Tabs — matches Billboard pattern */}
      <div className="flex gap-7 border-b border-border">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
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
      <div>
        {activeTab === 'collection' && data.collection_insights?.available && (
          <CollectionTab insights={data.collection_insights} />
        )}
        {activeTab === 'collection' && !data.collection_insights?.available && (
          <div className="py-12 text-center text-muted-foreground">收藏数据不可用</div>
        )}

        {activeTab === 'habits' && data.search?.available && (
          <HabitsTab
            search={data.search}
            tiers={data.insights_tiers}
            marquee={data.insights_marquee}
            podcast={data.podcast}
            video={data.video}
          />
        )}
        {activeTab === 'habits' && !data.search?.available && (
          <div className="py-12 text-center text-muted-foreground">搜索/习惯数据不可用</div>
        )}

        {activeTab === 'identity' && (
          <IdentityTab
            profile={data.profile}
            wrappedHub={null}
            inferences={data.inferences || null}
            soundCapsule={data.sound_capsule || null}
          />
        )}
      </div>
    </div>
  )
}
