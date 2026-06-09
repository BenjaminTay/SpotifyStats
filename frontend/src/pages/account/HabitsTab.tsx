import { useMemo } from 'react'
import { GlassCard } from '@/components/shared/GlassCard'
import { KpiCard } from '@/components/shared/KpiCard'
import { cn } from '@/lib/utils'
import { displayName } from '@/lib/chinese'
import {
  Search,
  Mic,
  Video,
  Clock,
  Target,
  Crown,
  Medal,
  Zap,
  Compass,
  Heart,
  Megaphone,
  Hash,
} from 'lucide-react'
import type {
  SearchData,
  ArtistTiersData,
  MarqueeData,
  PodcastData,
  VideoData,
} from '@/types/account'

/* ------------------------------------------------------------------ */
/*  Props                                                              */
/* ------------------------------------------------------------------ */

interface HabitsTabProps {
  search: SearchData
  tiers: ArtistTiersData
  marquee: MarqueeData
  podcast: PodcastData
  video: VideoData
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function fmtInt(n: number): string {
  return n.toLocaleString('zh-CN')
}

function fmtHours(h: number): string {
  if (h < 1) return `${Math.round(h * 60)} 分钟`
  return `${h.toFixed(1)} 小时`
}

function fmtPct(n: number, total: number): string {
  if (total === 0) return '0%'
  return `${Math.round((n / total) * 100)}%`
}

function safeDiv(a: number, b: number): number {
  return b === 0 ? 0 : a / b
}

/* ------------------------------------------------------------------ */
/*  Personality Inference                                              */
/* ------------------------------------------------------------------ */

interface PersonalityResult {
  type: string
  description: string
  metrics: { label: string; value: string; detail: string }[]
}

function inferPersonality(
  search: SearchData,
  video: VideoData,
): PersonalityResult {
  // -- late-night search activity (0:00 – 5:00) --
  let lateNightSearches = 0
  let totalSearches = 0
  if (search.available && !search.empty && search.heatmap?.z) {
    const { z } = search.heatmap
    for (let dow = 0; dow < z.length; dow++) {
      for (let h = 0; h < (z[dow]?.length ?? 0); h++) {
        const v = z[dow][h] ?? 0
        totalSearches += v
        if (h >= 0 && h <= 5) lateNightSearches += v
      }
    }
  }
  const lateNightPct = safeDiv(lateNightSearches, totalSearches)

  // -- search precision (artist + track vs general) --
  let preciseSearches = 0
  let allIntentSearches = 0
  if (search.available && !search.empty && search.intent_dist) {
    for (const item of search.intent_dist) {
      allIntentSearches += item.count
      if (item.intent === '艺人搜索' || item.intent === '曲目搜索') {
        preciseSearches += item.count
      }
    }
  }
  const precisionPct = safeDiv(preciseSearches, allIntentSearches)

  // -- multimedia index --
  const videoTotal =
    video.available && !video.empty
      ? video.total_video_plays + video.total_audio_plays
      : 0
  const videoPct = safeDiv(
    video.available && !video.empty ? video.total_video_plays : 0,
    videoTotal,
  )

  // -- decide personality --
  if (lateNightPct > 0.2 && precisionPct > 0.55) {
    return {
      type: '午夜诗人',
      description:
        '深夜是你与音乐灵魂共振的时刻，每一次精准搜索都是一场静谧的探险。',
      metrics: [
        { label: '深夜活跃度', value: fmtPct(lateNightSearches, totalSearches), detail: '夜间 0-5 时搜索占比' },
        { label: '搜索精准度', value: fmtPct(preciseSearches, allIntentSearches), detail: '艺人/曲目直接搜索占比' },
        { label: '多媒体指数', value: fmtPct(video.total_video_plays ?? 0, videoTotal), detail: '视频播放占比' },
      ],
    }
  }
  if (precisionPct > 0.6) {
    return {
      type: '精准猎手',
      description:
        '你从不漫无目的地搜索，每一次查询都直指目标，音乐品味清晰而坚定。',
      metrics: [
        { label: '搜索精准度', value: fmtPct(preciseSearches, allIntentSearches), detail: '艺人/曲目直接搜索占比' },
        { label: '深夜活跃度', value: fmtPct(lateNightSearches, totalSearches), detail: '夜间 0-5 时搜索占比' },
        { label: '多媒体指数', value: fmtPct(video.total_video_plays ?? 0, videoTotal), detail: '视频播放占比' },
      ],
    }
  }
  if (videoPct > 0.3 && (video.available && !video.empty)) {
    return {
      type: '多维旅人',
      description:
        '你游走于音频与视频之间，用双眼和双耳共同感受音乐的多维魅力。',
      metrics: [
        { label: '多媒体指数', value: fmtPct(video.total_video_plays ?? 0, videoTotal), detail: '视频播放占比' },
        { label: '搜索精准度', value: fmtPct(preciseSearches, allIntentSearches), detail: '艺人/曲目直接搜索占比' },
        { label: '深夜活跃度', value: fmtPct(lateNightSearches, totalSearches), detail: '夜间 0-5 时搜索占比' },
      ],
    }
  }
  if (precisionPct < 0.4) {
    return {
      type: '随性漫游者',
      description:
        '你喜欢随意浏览探索，享受音乐发现的偶然与惊喜，不设限的搜索带来无限灵感。',
      metrics: [
        { label: '搜索精准度', value: fmtPct(preciseSearches, allIntentSearches), detail: '艺人/曲目直接搜索占比' },
        { label: '深夜活跃度', value: fmtPct(lateNightSearches, totalSearches), detail: '夜间 0-5 时搜索占比' },
        { label: '多媒体指数', value: fmtPct(video.total_video_plays ?? 0, videoTotal), detail: '视频播放占比' },
      ],
    }
  }
  return {
    type: '均衡鉴赏家',
    description:
      '你的音乐习惯平衡而多元，既是理性的探索者，也是感性的聆听者。',
    metrics: [
      { label: '搜索精准度', value: fmtPct(preciseSearches, allIntentSearches), detail: '艺人/曲目直接搜索占比' },
      { label: '深夜活跃度', value: fmtPct(lateNightSearches, totalSearches), detail: '夜间 0-5 时搜索占比' },
      { label: '多媒体指数', value: fmtPct(video.total_video_plays ?? 0, videoTotal), detail: '视频播放占比' },
    ],
  }
}

/* ------------------------------------------------------------------ */
/*  Pre-computed analysis helpers                                      */
/* ------------------------------------------------------------------ */

function getMostActiveDay(heatmap: SearchData['heatmap']): {
  dayLabel: string
  hours: number[]
  total: number
} | null {
  if (!heatmap?.z || !heatmap.y) return null
  const { z, y } = heatmap
  let maxSum = 0
  let maxIdx = 0
  for (let i = 0; i < z.length; i++) {
    const sum = (z[i] ?? []).reduce((a, b) => a + (b ?? 0), 0)
    if (sum > maxSum) {
      maxSum = sum
      maxIdx = i
    }
  }
  return {
    dayLabel: y[maxIdx] ?? `DOW ${maxIdx}`,
    hours: z[maxIdx] ?? [],
    total: maxSum,
  }
}

function getIntentColors(): Record<string, string> {
  return {
    '艺人搜索': 'bg-amber-500',
    '曲目搜索': 'bg-sky-500',
    '一般搜索': 'bg-slate-400',
  }
}

function getIntentLabels(): Record<string, string> {
  return {
    '艺人搜索': '艺人',
    '曲目搜索': '曲目',
    '一般搜索': '一般',
  }
}

/* ------------------------------------------------------------------ */
/*  Styles for gold / silver / bronze cards                            */
/* ------------------------------------------------------------------ */

const medalBorder: Record<number, string> = {
  1: 'border-amber-400 shadow-[0_0_20px_rgba(245,158,11,0.15)]',
  2: 'border-slate-300 shadow-[0_0_14px_rgba(148,163,184,0.12)]',
  3: 'border-orange-400/60 shadow-[0_0_10px_rgba(251,146,60,0.10)]',
}

const medalBadge: Record<number, string> = {
  1: 'bg-amber-500 text-white',
  2: 'bg-slate-300 text-slate-800',
  3: 'bg-orange-400/80 text-white',
}

const medalIcon: Record<number, React.ReactNode> = {
  1: <Crown className="h-4 w-4" />,
  2: <Medal className="h-4 w-4" />,
  3: <Medal className="h-4 w-4" />,
}

/* ------------------------------------------------------------------ */
/*  Unavailable stub                                                   */
/* ------------------------------------------------------------------ */

function UnavailableBlock({ title }: { title: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-10 text-muted-foreground">
      <div className="mb-2 rounded-full border border-border p-3">
        <Hash className="h-5 w-5" />
      </div>
      <p className="font-sans text-sm">{title}数据不可用</p>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export function HabitsTab({
  search,
  tiers,
  marquee,
  podcast,
  video,
}: HabitsTabProps) {
  /* ---- computed values ---- */
  const personality = useMemo(
    () => inferPersonality(search, video),
    [search, video],
  )

  const mostActiveDay = useMemo(
    () =>
      search.available && !search.empty
        ? getMostActiveDay(search.heatmap)
        : null,
    [search],
  )

  const intentTotal = useMemo(
    () =>
      search.available && !search.empty
        ? search.intent_dist.reduce((s, i) => s + i.count, 0)
        : 0,
    [search],
  )

  const tierEntries = useMemo(() => {
    if (!tiers.available || tiers.empty) return []
    return Object.entries(tiers.tier_counts)
      .map(([label, count]) => ({ label, count }))
      .sort((a, b) => b.count - a.count)
  }, [tiers])

  const tierTotal = useMemo(
    () => tierEntries.reduce((s, t) => s + t.count, 0),
    [tierEntries],
  )

  const superFans = useMemo(() => {
    if (!tiers.available || tiers.empty) return []
    return tiers.artists
      .filter((a) => a.tier === '超级粉丝 (Top 5)')
      .slice(0, 3)
  }, [tiers])

  const conicGradient = useMemo(() => {
    if (tierEntries.length === 0) return 'conic-gradient(#e5e7eb 0% 100%)'
    const palette = ['#f59e0b', '#3b82f6', '#8b5cf6', '#10b981', '#6b7280']
    let cumulative = 0
    const segments = tierEntries.map((t, i) => {
      const pct = safeDiv(t.count, tierTotal) * 100
      const start = cumulative
      cumulative += pct
      return `${palette[i % palette.length]} ${start}% ${cumulative}%`
    })
    return `conic-gradient(${segments.join(', ')})`
  }, [tierEntries, tierTotal])

  /* search insights */
  const topIntent = useMemo(() => {
    if (!search.available || search.empty) return null
    const sorted = [...search.intent_dist].sort((a, b) => b.count - a.count)
    return sorted[0] ?? null
  }, [search])

  const peakSearchDay = useMemo(() => {
    if (!search.available || search.empty || !search.daily_volume.length)
      return null
    return [...search.daily_volume].sort((a, b) => b.count - a.count)[0] ?? null
  }, [search])

  /* ---- render ---- */
  return (
    <div className="space-y-8">
      {/* ============================================================ */}
      {/*  1. Listening Personality Hero                                */}
      {/* ============================================================ */}
      <GlassCard className="relative overflow-hidden p-6 md:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex-1 space-y-2">
            <p className="font-sans text-[11px] font-semibold uppercase tracking-[2px] text-accent-foreground">
              你的收听人格
            </p>
            <h2 className="font-serif text-4xl font-bold tracking-[-0.5px] text-foreground md:text-5xl">
              {personality.type}
            </h2>
            <p className="max-w-lg font-sans text-sm leading-relaxed text-muted-foreground">
              {personality.description}
            </p>
          </div>

          <div className="flex flex-wrap gap-6 lg:gap-10">
            {personality.metrics.map((m) => (
              <div key={m.label} className="text-center">
                <p className="font-serif text-3xl font-bold text-foreground md:text-4xl">
                  {m.value}
                </p>
                <p className="mt-1 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">
                  {m.label}
                </p>
                <p className="mt-0.5 font-sans text-[10px] text-muted-foreground/60">
                  {m.detail}
                </p>
              </div>
            ))}
          </div>
        </div>
      </GlassCard>

      {/* ============================================================ */}
      {/*  2. Search Chronicles                                          */}
      {/* ============================================================ */}
      <GlassCard className="p-6">
        {!search.available || search.empty ? (
          <UnavailableBlock title="搜索" />
        ) : (
          <div className="space-y-6">
            {/* header */}
            <div className="flex items-center gap-2.5">
              <Search className="h-5 w-5 text-amber-500" />
              <h2 className="mb-5 font-serif text-xl font-semibold">搜索编年史</h2>
            </div>

            {/* top row: KPI sidebar + top queries */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              {/* left: KPI + intent bar */}
              <div className="space-y-5 lg:col-span-1">
                <KpiCard
                  label="总搜索次数"
                  value={fmtInt(search.total_searches)}
                />

                {/* intent distribution stacked bar */}
                <div className="space-y-2">
                  <p className="font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">
                    搜索意向分布
                  </p>
                  <div className="flex h-3 w-full overflow-hidden rounded-full">
                    {search.intent_dist.map((item) => {
                      const pct = safeDiv(item.count, intentTotal) * 100
                      if (pct === 0) return null
                      return (
                        <div
                          key={item.intent}
                          className={cn(
                            'h-full transition-all',
                            (getIntentColors() as Record<string, string>)[
                              item.intent
                            ] ?? 'bg-slate-300',
                          )}
                          style={{ width: `${pct}%` }}
                        />
                      )
                    })}
                  </div>
                  <div className="flex flex-wrap gap-3">
                    {search.intent_dist.map((item) => (
                      <span
                        key={item.intent}
                        className="flex items-center gap-1.5 font-sans text-xs text-muted-foreground"
                      >
                        <span
                          className={cn(
                            'inline-block h-2.5 w-2.5 rounded-full',
                            (getIntentColors() as Record<string, string>)[
                              item.intent
                            ] ?? 'bg-slate-300',
                          )}
                        />
                        {(getIntentLabels() as Record<string, string>)[
                          item.intent
                        ] ?? item.intent}{' '}
                        {fmtPct(item.count, intentTotal)}
                      </span>
                    ))}
                  </div>
                </div>

                {/* three discovery numbers */}
                <div className="space-y-3 rounded-xl border border-border bg-muted/40 p-4">
                  <p className="font-sans text-[10px] font-semibold uppercase tracking-[1.5px] text-muted-foreground">
                    搜索发现
                  </p>
                  {topIntent && (
                    <div className="flex items-center gap-3">
                      <Target className="h-4 w-4 shrink-0 text-sky-500" />
                      <div>
                        <p className="font-sans text-xs text-muted-foreground">
                          最爱搜索类型
                        </p>
                        <p className="font-serif text-sm font-semibold">
                          {topIntent.intent}
                        </p>
                      </div>
                    </div>
                  )}
                  {peakSearchDay && (
                    <div className="flex items-center gap-3">
                      <Zap className="h-4 w-4 shrink-0 text-amber-500" />
                      <div>
                        <p className="font-sans text-xs text-muted-foreground">
                          搜索最多的一天
                        </p>
                        <p className="font-serif text-sm font-semibold">
                          {peakSearchDay.date}（{peakSearchDay.count} 次）
                        </p>
                      </div>
                    </div>
                  )}
                  <div className="flex items-center gap-3">
                    <Compass className="h-4 w-4 shrink-0 text-emerald-500" />
                    <div>
                      <p className="font-sans text-xs text-muted-foreground">
                        独特搜索词
                      </p>
                      <p className="font-serif text-sm font-semibold">
                        {fmtInt(search.top_queries.length)} 个
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* right: top queries */}
              <div className="space-y-3 lg:col-span-2">
                <p className="font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">
                  热搜词 Top 10
                </p>
                <div className="space-y-1">
                  {search.top_queries.slice(0, 10).map((q, idx) => (
                    <div
                      key={q.query}
                      className="flex items-center gap-3 rounded-lg px-3 py-2 transition-colors hover:bg-muted/40"
                    >
                      <span className="w-6 text-right font-sans text-xs tabular-nums text-muted-foreground">
                        {idx + 1}
                      </span>
                      <span className="flex-1 truncate font-sans text-sm">
                        {q.query}
                      </span>
                      <span className="font-sans text-xs tabular-nums text-muted-foreground">
                        {q.count} 次
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* bottom: heatmap simplified – most active day */}
            {mostActiveDay && mostActiveDay.total > 0 && (
              <div className="space-y-3 rounded-xl border border-border bg-muted/30 p-5">
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-muted-foreground" />
                  <p className="font-sans text-xs font-semibold uppercase tracking-[0.5px] text-muted-foreground">
                    最活跃日 · {mostActiveDay.dayLabel} · 共{' '}
                    {mostActiveDay.total} 次搜索
                  </p>
                </div>
                <div className="flex items-end gap-[2px]">
                  {mostActiveDay.hours.map((v, h) => {
                    const max = Math.max(...mostActiveDay.hours, 1)
                    const heightPct = (v / max) * 100
                    return (
                      <div
                        key={h}
                        className="group relative flex-1"
                        title={`${h}:00 – ${v} 次`}
                      >
                        <div
                          className="w-full rounded-t-sm bg-amber-500/70 transition-all group-hover:bg-amber-500"
                          style={{ height: `${Math.max(heightPct, 2)}%` }}
                        />
                      </div>
                    )
                  })}
                </div>
                <div className="flex justify-between font-sans text-[10px] text-muted-foreground/60">
                  <span>0:00</span>
                  <span>6:00</span>
                  <span>12:00</span>
                  <span>18:00</span>
                  <span>23:00</span>
                </div>
              </div>
            )}
          </div>
        )}
      </GlassCard>

      {/* ============================================================ */}
      {/*  3. Fan Tiers                                                  */}
      {/* ============================================================ */}
      <GlassCard className="p-6">
        {!tiers.available || tiers.empty ? (
          <UnavailableBlock title="粉丝层级" />
        ) : (
          <div className="space-y-6">
            <div className="flex items-center gap-2.5">
              <Heart className="h-5 w-5 text-rose-500" />
              <h2 className="mb-5 font-serif text-xl font-semibold">粉丝层级</h2>
            </div>

            <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
              {/* left: donut chart */}
              <div className="flex flex-col items-center justify-center gap-4">
                <div className="relative h-48 w-48">
                  {/* conic-gradient donut */}
                  <div
                    className="h-full w-full rounded-full"
                    style={{ background: conicGradient }}
                  />
                  {/* inner hole */}
                  <div className="absolute inset-[28%] flex flex-col items-center justify-center rounded-full bg-card">
                    <p className="font-serif text-2xl font-bold">
                      {fmtInt(tiers.total_artists)}
                    </p>
                    <p className="font-sans text-[10px] uppercase tracking-[1px] text-muted-foreground">
                      总艺人
                    </p>
                  </div>
                </div>

                {/* legend */}
                <div className="flex flex-wrap justify-center gap-x-5 gap-y-1.5">
                  {tierEntries.map((t, i) => {
                    const palette = [
                      '#f59e0b',
                      '#3b82f6',
                      '#8b5cf6',
                      '#10b981',
                      '#6b7280',
                    ]
                    return (
                      <span
                        key={t.label}
                        className="flex items-center gap-1.5 font-sans text-xs text-muted-foreground"
                      >
                        <span
                          className="inline-block h-2.5 w-2.5 rounded-full"
                          style={{
                            backgroundColor: palette[i % palette.length],
                          }}
                        />
                        {t.label}（{t.count}）
                      </span>
                    )
                  })}
                </div>
              </div>

              {/* right: super fan cards */}
              <div className="space-y-4">
                <p className="font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">
                  超级粉丝档案
                </p>
                {superFans.length === 0 ? (
                  <p className="font-sans text-sm text-muted-foreground">
                    暂无超级粉丝数据
                  </p>
                ) : (
                  superFans.map((fan, idx) => (
                    <div
                      key={fan.artist_name}
                      className={cn(
                        'rounded-xl border bg-muted/20 p-4 transition-all',
                        medalBorder[idx + 1] ?? 'border-border',
                      )}
                    >
                      <div className="flex items-start gap-3">
                        {fan.cover_url ? (
                          <img
                            src={fan.cover_url}
                            alt={fan.artist_name}
                            className="h-12 w-12 shrink-0 rounded-full border border-border object-cover"
                          />
                        ) : (
                          <div
                            className={cn(
                              'flex h-7 w-7 shrink-0 items-center justify-center rounded-full',
                              medalBadge[idx + 1] ?? 'bg-muted',
                            )}
                          >
                            {medalIcon[idx + 1] ?? idx + 1}
                          </div>
                        )}
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-serif text-base font-semibold">
                            {displayName(fan.artist_name)}
                          </p>
                          <div className="mt-2 flex gap-5 font-sans text-xs text-muted-foreground">
                            <span>
                              播放{' '}
                              <strong className="text-foreground">
                                {fmtInt(fan.play_count)}
                              </strong>{' '}
                              次
                            </span>
                            <span>
                              收听{' '}
                              <strong className="text-foreground">
                                {fmtHours(fan.hours)}
                              </strong>
                            </span>
                            <span className="text-amber-500">#{fan.rank}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}
      </GlassCard>

      {/* ============================================================ */}
      {/*  4. Podcast + Marquee                                         */}
      {/* ============================================================ */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {/* podcast */}
        <GlassCard className="p-6">
          {!podcast.available || podcast.empty ? (
            <UnavailableBlock title="播客" />
          ) : (
            <div className="space-y-5">
              <div className="flex items-center gap-2.5">
                <Mic className="h-5 w-5 text-emerald-500" />
                <h2 className="mb-5 font-serif text-lg font-semibold">播客聆听</h2>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg border border-border bg-muted/30 p-3">
                  <p className="font-serif text-xl font-bold">
                    {fmtInt(podcast.total_plays)}
                  </p>
                  <p className="font-sans text-[10px] uppercase tracking-[0.5px] text-muted-foreground">
                    总播放
                  </p>
                </div>
                <div className="rounded-lg border border-border bg-muted/30 p-3">
                  <p className="font-serif text-xl font-bold">
                    {fmtHours(podcast.total_hours)}
                  </p>
                  <p className="font-sans text-[10px] uppercase tracking-[0.5px] text-muted-foreground">
                    总时长
                  </p>
                </div>
                <div className="rounded-lg border border-border bg-muted/30 p-3">
                  <p className="font-serif text-xl font-bold">
                    {fmtInt(podcast.unique_shows)}
                  </p>
                  <p className="font-sans text-[10px] uppercase tracking-[0.5px] text-muted-foreground">
                    独特节目
                  </p>
                </div>
                <div className="rounded-lg border border-border bg-muted/30 p-3">
                  <p className="font-serif text-xl font-bold">
                    {fmtInt(podcast.saved_shows)}
                  </p>
                  <p className="font-sans text-[10px] uppercase tracking-[0.5px] text-muted-foreground">
                    已收藏
                  </p>
                </div>
              </div>

              {/* top shows */}
              <div className="space-y-2">
                <p className="font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">
                  最爱节目 Top 5
                </p>
                {podcast.top_shows.slice(0, 5).map((s, idx) => (
                  <div
                    key={s.show_name}
                    className="flex items-center gap-3 rounded-lg px-3 py-1.5 transition-colors hover:bg-muted/30"
                  >
                    <span className="w-5 text-right font-sans text-xs tabular-nums text-muted-foreground">
                      {idx + 1}
                    </span>
                    <span className="flex-1 truncate font-sans text-sm">
                      {displayName(s.show_name)}
                    </span>
                    <span className="shrink-0 font-sans text-xs tabular-nums text-muted-foreground">
                      {fmtHours(s.hours)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </GlassCard>

        {/* marquee */}
        <GlassCard className="p-6">
          {!marquee.available || marquee.empty ? (
            <UnavailableBlock title="Marquee 推广" />
          ) : (
            <div className="space-y-5">
              <div className="flex items-center gap-2.5">
                <Megaphone className="h-5 w-5 text-violet-500" />
                <h2 className="mb-5 font-serif text-lg font-semibold">推广转化</h2>
              </div>

              <p className="font-sans text-xs leading-relaxed text-muted-foreground">
                Spotify Marquee
                是全屏推荐广告，以下为你看到推广后转化为实际收听的艺人排行（按转化率降序）。
              </p>

              <div className="space-y-3">
                {marquee.conversions.slice(0, 5).map((c) => {
                  const rate = c.conversion_rate * 100
                  return (
                    <div
                      key={`${c.artist_name}-${c.segment}`}
                      className="flex items-center gap-3 rounded-lg border border-border bg-muted/20 p-3"
                    >
                      {c.cover_url ? (
                        <img
                          src={c.cover_url}
                          alt={c.artist_name}
                          className="h-11 w-11 shrink-0 rounded-full border border-border object-cover"
                        />
                      ) : (
                        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-muted">
                          <Megaphone className="h-4 w-4 text-muted-foreground" />
                        </div>
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-serif text-sm font-semibold">
                          {displayName(c.artist_name)}
                        </p>
                        <p className="font-sans text-[10px] text-muted-foreground">
                          展示 {fmtInt(c.impressions)} 次 · 转化{' '}
                          {fmtInt(c.actual_plays)} 次
                        </p>
                      </div>
                      <div className="shrink-0 text-right">
                        <p
                          className={cn(
                            'font-serif text-lg font-bold',
                            rate > 5
                              ? 'text-emerald-500'
                              : rate > 2
                                ? 'text-amber-500'
                                : 'text-muted-foreground',
                          )}
                        >
                          {rate.toFixed(1)}%
                        </p>
                        <p className="font-sans text-[9px] uppercase tracking-[0.5px] text-muted-foreground">
                          转化率
                        </p>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </GlassCard>
      </div>

      {/* ============================================================ */}
      {/*  5. Video Analysis                                             */}
      {/* ============================================================ */}
      <GlassCard className="p-6">
        {!video.available || video.empty ? (
          <UnavailableBlock title="视频" />
        ) : (
          <div className="space-y-6">
            <div className="flex items-center gap-2.5">
              <Video className="h-5 w-5 text-rose-500" />
              <h2 className="mb-5 font-serif text-xl font-semibold">视频分析</h2>
            </div>

            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              {/* left: stats + platform dist */}
              <div className="space-y-5">
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-lg border border-border bg-muted/30 p-3">
                    <p className="font-serif text-xl font-bold">
                      {fmtInt(video.total_video_plays)}
                    </p>
                    <p className="font-sans text-[10px] uppercase tracking-[0.5px] text-muted-foreground">
                      视频播放
                    </p>
                  </div>
                  <div className="rounded-lg border border-border bg-muted/30 p-3">
                    <p className="font-serif text-xl font-bold">
                      {fmtInt(video.total_audio_plays)}
                    </p>
                    <p className="font-sans text-[10px] uppercase tracking-[0.5px] text-muted-foreground">
                      音频播放
                    </p>
                  </div>
                  <div className="rounded-lg border border-border bg-muted/30 p-3">
                    <p className="font-serif text-xl font-bold">
                      {Math.round(video.avg_duration_sec)}s
                    </p>
                    <p className="font-sans text-[10px] uppercase tracking-[0.5px] text-muted-foreground">
                      平均时长
                    </p>
                  </div>
                  <div className="rounded-lg border border-border bg-muted/30 p-3">
                    <p className="font-serif text-xl font-bold">
                      {fmtPct(
                        video.total_video_plays,
                        video.total_video_plays + video.total_audio_plays,
                      )}
                    </p>
                    <p className="font-sans text-[10px] uppercase tracking-[0.5px] text-muted-foreground">
                      视频占比
                    </p>
                  </div>
                </div>
              </div>

              {/* right: top video tracks */}
              <div className="space-y-3">
                <p className="font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">
                  视频播放 Top 5
                </p>
                {video.top_video_tracks.length === 0 ? (
                  <p className="font-sans text-sm text-muted-foreground">
                    暂无视频曲目数据
                  </p>
                ) : (
                  <div className="space-y-2">
                    {video.top_video_tracks.slice(0, 5).map((t, idx) => (
                      <div
                        key={`${t.track_name}-${t.artist_name}`}
                        className="flex items-center gap-3 rounded-lg px-3 py-2 transition-colors hover:bg-muted/30"
                      >
                        <span className="w-5 text-right font-sans text-xs tabular-nums text-muted-foreground">
                          {idx + 1}
                        </span>
                        {t.cover_url && (
                          <img
                            src={t.cover_url}
                            alt={t.track_name}
                            className="h-10 w-10 shrink-0 rounded border border-border object-cover"
                          />
                        )}
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-sans text-sm">
                            {displayName(t.track_name)}
                          </p>
                          <p className="truncate font-sans text-xs text-muted-foreground">
                            {displayName(t.artist_name)}
                          </p>
                        </div>
                        <div className="shrink-0 text-right">
                          <p className="font-sans text-xs font-semibold tabular-nums">
                            {fmtInt(t.video_plays)}
                          </p>
                          <p className="font-sans text-[9px] text-muted-foreground">
                            视频 · {fmtInt(t.audio_plays)} 音频
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </GlassCard>
    </div>
  )
}
