import { useMemo } from 'react'
import { Link } from 'react-router-dom'

import type { FeedMeta } from '@/types/community'
import type { TrendingEntity, TrendingData } from '@/hooks/useCommunity'
import { displayName, useChineseTextVersion } from '@/lib/chinese'

import { AccountAvatar } from './AccountAvatar'
import { ACCOUNT_CONFIG, formatFollowerCount } from './communityData'

interface CommunitySidebarProps {
  posts: { posted_at: string }[]
  meta: FeedMeta | null
  trendingArtists?: TrendingEntity[]
  trendingTracks?: TrendingEntity[]
  latestNo1?: TrendingData['latest_no1']
  latestDebut?: TrendingData['latest_debut']
}

export function CommunitySidebar({
  posts,
  meta,
  trendingArtists = [],
  trendingTracks = [],
  latestNo1,
  latestDebut,
}: CommunitySidebarProps) {
  useChineseTextVersion()
  const accounts = useMemo(() => Object.values(ACCOUNT_CONFIG), [])

  // Coverage period from oldest and newest post
  const coveragePeriod = useMemo(() => {
    if (posts.length === 0) return null
    const dates = posts.map(p => new Date(p.posted_at).getTime())
    const start = new Date(Math.min(...dates))
    const end = new Date(Math.max(...dates))
    const fmt = (d: Date) =>
      d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
    return `${fmt(start)} — ${fmt(end)}`
  }, [posts])

  return (
    <aside className="space-y-4">
      {/* Billboard Pulse */}
      <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
        <h3 className="text-[17px] font-extrabold text-foreground mb-3">榜单快讯</h3>
        {(latestNo1 || latestDebut) ? (
          <div className="space-y-3">
            {latestNo1 && (
              <div>
                <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground mb-0.5">
                  当前 #1
                </p>
                <p className="text-[14px] font-bold text-foreground truncate">{displayName(latestNo1.track ?? '')}</p>
                <p className="text-[12px] text-muted-foreground truncate">{displayName(latestNo1.artist ?? '')}</p>
              </div>
            )}
            {latestDebut && (
              <div>
                <p className="text-[11px] font-bold uppercase tracking-[1.2px] text-muted-foreground mb-0.5">
                  最高空降
                </p>
                <p className="text-[14px] font-bold text-foreground truncate">{displayName(latestDebut.track ?? '')}</p>
                <p className="text-[12px] text-muted-foreground truncate">{displayName(latestDebut.artist ?? '')}</p>
              </div>
            )}
          </div>
        ) : (
          <p className="text-[13px] text-muted-foreground">加载中...</p>
        )}
      </section>

      {/* Trending Artists */}
      {trendingArtists.length > 0 && (
        <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
          <h3 className="text-[17px] font-extrabold text-foreground mb-3">热议艺人</h3>
          <ol className="space-y-2">
            {trendingArtists.map((item, i) => (
              <li key={item.name} className="flex items-center gap-2.5">
                <span
                  className={`w-5 text-right shrink-0 tabular-nums text-[13px] font-bold ${
                    i === 0 ? 'text-accent-foreground' : 'text-muted-foreground'
                  }`}
                >
                  {i + 1}
                </span>
                <Link
                  to={`/music/artists/${encodeURIComponent(item.name)}`}
                  className="flex-1 min-w-0 text-[13px] font-medium text-foreground hover:text-accent-foreground hover:underline truncate transition-colors"
                >
                  {displayName(item.name)}
                </Link>
                <span className="text-[11px] text-muted-foreground shrink-0 tabular-nums">
                  {item.count} 帖
                </span>
              </li>
            ))}
          </ol>
        </section>
      )}

      {/* Trending Tracks */}
      {trendingTracks.length > 0 && (
        <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
          <h3 className="text-[17px] font-extrabold text-foreground mb-3">热议单曲</h3>
          <ol className="space-y-2">
            {trendingTracks.map((item, i) => {
              const link = item.entity_id ? `/music/tracks/${item.entity_id}` : null
              return (
                <li key={item.name} className="flex items-center gap-2.5">
                  <span
                    className={`w-5 text-right shrink-0 tabular-nums text-[13px] font-bold ${
                      i === 0 ? 'text-accent-foreground' : 'text-muted-foreground'
                    }`}
                  >
                    {i + 1}
                  </span>
                  <span className="flex-1 min-w-0">
                    {link ? (
                      <Link
                        to={link}
                        className="text-[13px] font-medium text-foreground hover:text-accent-foreground hover:underline truncate transition-colors"
                      >
                        {displayName(item.name)}
                      </Link>
                    ) : (
                      <span className="text-[13px] font-medium text-foreground truncate">{displayName(item.name)}</span>
                    )}
                  </span>
                  <span className="text-[11px] text-muted-foreground shrink-0 tabular-nums">
                    {item.count}
                  </span>
                </li>
              )
            })}
          </ol>
        </section>
      )}

      {/* Community Accounts */}
      <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
        <h3 className="text-[17px] font-extrabold text-foreground mb-3">社区账号</h3>
        <div className="space-y-1.5">
          {accounts.map(acc => (
            <Link
              key={acc.handle}
              to={`/community/account/${encodeURIComponent(acc.handle)}`}
              className="flex items-center gap-2.5 py-1.5 hover:bg-white/[0.04] rounded-lg px-1.5 -mx-1.5 transition-colors"
            >
              <AccountAvatar handle={acc.handle} size="sm" />
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-bold text-foreground truncate leading-tight">
                  {acc.display_name}
                </p>
                <p className="text-[11px] text-muted-foreground truncate">{acc.handle}</p>
              </div>
              <span className="text-[11px] text-muted-foreground shrink-0">
                {formatFollowerCount(acc.follower_tier)}
              </span>
            </Link>
          ))}
        </div>
      </section>

      {/* Stats Overview */}
      <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
        <h3 className="text-[17px] font-extrabold text-foreground mb-3">数据概况</h3>
        <div className="space-y-2 text-[13px]">
          <div className="flex justify-between items-center">
            <span className="text-muted-foreground">总帖子</span>
            <span className="font-bold text-foreground tabular-nums">
              {meta ? meta.total.toLocaleString() : '—'}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-muted-foreground">活跃账号</span>
            <span className="font-bold text-foreground tabular-nums">10</span>
          </div>
          {coveragePeriod && (
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">覆盖周期</span>
              <span className="font-bold text-foreground text-[11px]">{coveragePeriod}</span>
            </div>
          )}
        </div>
      </section>

      {/* Footer */}
      <p className="text-[11px] text-muted-foreground leading-5 px-1">
        数据来源于 Billboard Hot 100 榜单归档<br />
        与 Spotify Extended Streaming History
      </p>
    </aside>
  )
}
