import { useState, useEffect, useCallback, useRef } from 'react'
import type {
  CollectionInsights,
  ChemistryType,
  SaveTimelinePoint,
  TopSavedArtist,
} from '@/types/account'
import { GlassCard } from '@/components/shared/GlassCard'
import { KpiCard } from '@/components/shared/KpiCard'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'

/* ------------------------------------------------------------------ */
/*  1. Collection Personality Hero                                     */
/* ------------------------------------------------------------------ */

function PersonalityHero({ insights }: { insights: CollectionInsights }) {
  const { personality } = insights
  const { metrics } = personality

  return (
    <GlassCard className="overflow-hidden p-0">
      <div className="flex flex-col gap-0 bg-gradient-to-br from-[#1a1a2e] via-[#16213e] to-[#0f3460] text-white">
        {/* Top: icon + name / description vs metrics */}
        <div className="flex flex-col gap-6 p-8 lg:flex-row lg:items-start lg:justify-between">
          {/* Left */}
          <div className="flex-1 space-y-3">
            <span className="text-5xl">{personality.icon}</span>
            <h2 className="font-serif text-4xl font-bold tracking-[-0.5px]">
              {personality.type}
            </h2>
            <p className="max-w-lg font-sans text-sm leading-relaxed text-white/70">
              {personality.description}
            </p>
          </div>

          {/* Right: 3 ring metrics */}
          <div className="flex gap-8 lg:gap-12">
            <RingMetric
              label="慢热指数"
              value={metrics.avg_plays_before_save}
              max={20}
              unit="次"
            />
            <RingMetric
              label="留存率"
              value={metrics.retention_pct}
              max={100}
              unit="%"
            />
            <RingMetric
              label="冲动收藏"
              value={metrics.impulsive_pct}
              max={100}
              unit="%"
            />
          </div>
        </div>

        {/* Bottom: 3 key numbers */}
        <div className="grid grid-cols-3 border-t border-white/10">
          <div className="px-8 py-4 text-center">
            <p className="font-serif text-2xl font-bold">
              {metrics.avg_plays_before_save.toFixed(1)}
            </p>
            <p className="font-sans text-xs text-white/50">收藏前平均播放</p>
          </div>
          <div className="border-x border-white/10 px-8 py-4 text-center">
            <p className="font-serif text-2xl font-bold">
              {metrics.retention_pct.toFixed(0)}%
            </p>
            <p className="font-sans text-xs text-white/50">长期留存率</p>
          </div>
          <div className="px-8 py-4 text-center">
            <p className="font-serif text-2xl font-bold">
              {metrics.impulsive_pct.toFixed(0)}%
            </p>
            <p className="font-sans text-xs text-white/50">冲动收藏比例</p>
          </div>
        </div>
      </div>
    </GlassCard>
  )
}

/** Pure-CSS ring progress indicator */
function RingMetric({
  label,
  value,
  max,
  unit,
}: {
  label: string
  value: number
  max: number
  unit: string
}) {
  const pct = Math.min((value / max) * 100, 100)

  return (
    <div className="flex flex-col items-center gap-1.5">
      {/* Ring */}
      <div
        className="relative flex h-20 w-20 items-center justify-center rounded-full"
        style={{
          background: `conic-gradient(rgba(255,255,255,0.85) ${pct * 3.6}deg, rgba(255,255,255,0.12) ${pct * 3.6}deg)`,
        }}
      >
        <div className="absolute inset-[6px] flex flex-col items-center justify-center rounded-full bg-[#0f3460]">
          <span className="font-serif text-lg font-bold leading-none">
            {value.toFixed(0)}
          </span>
          <span className="-mt-0.5 font-sans text-[10px] text-white/60">
            {unit}
          </span>
        </div>
      </div>
      <p className="font-sans text-[11px] font-medium text-white/70">{label}</p>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  2. Collection Overview                                             */
/* ------------------------------------------------------------------ */

function CollectionOverviewBlock({
  insights,
}: {
  insights: CollectionInsights
}) {
  const { overview } = insights

  return (
    <section className="space-y-4">
      <h2 className="mb-5 font-serif text-xl font-semibold">
        收藏纵览
      </h2>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        {/* Left: 4 KPI cards */}
        <GlassCard className="col-span-2 p-6">
          <div className="grid grid-cols-2 gap-4">
            <KpiCard
              label="收藏曲目"
              value={overview.saved_tracks.toLocaleString()}
            />
            <KpiCard
              label="收藏专辑"
              value={overview.saved_albums.toLocaleString()}
            />
            <KpiCard
              label="收藏艺人"
              value={overview.saved_artists.toLocaleString()}
            />
            <KpiCard
              label="播放列表"
              value={overview.playlists.toLocaleString()}
            />
          </div>
        </GlassCard>

        {/* Right: yearly bar chart (pure DOM) */}
        <GlassCard className="col-span-3 p-6">
          <p className="mb-4 font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
            年度收藏量
          </p>
          <SaveTimelineChart timeline={overview.save_timeline} />

          {/* Biggest save day */}
          {overview.biggest_save_day && (
            <div className="mt-4 flex items-center gap-2 rounded-lg bg-accent-foreground/5 px-4 py-2.5">
              <span className="font-sans text-xs text-muted-foreground">
                最大收藏日
              </span>
              <span className="font-serif text-sm font-semibold tabular-nums">
                {overview.biggest_save_day.date}
              </span>
              <span className="font-sans text-xs text-muted-foreground">
                一口气收藏
              </span>
              <span className="font-serif text-sm font-bold text-accent-foreground">
                {overview.biggest_save_day.count}
              </span>
              <span className="font-sans text-xs text-muted-foreground">首</span>
            </div>
          )}
        </GlassCard>
      </div>
    </section>
  )
}

/** Pure-DOM bar chart for save timeline */
function SaveTimelineChart({
  timeline,
}: {
  timeline: SaveTimelinePoint[]
}) {
  if (!timeline || timeline.length === 0) {
    return (
      <p className="py-8 text-center font-sans text-sm text-muted-foreground">
        暂无数据
      </p>
    )
  }

  const maxCount = Math.max(...timeline.map((p) => p.count), 1)

  return (
    <div className="flex items-end gap-1.5" style={{ height: 140 }}>
      {timeline.map((point) => {
        const heightPct = (point.count / maxCount) * 100
        return (
          <div
            key={point.year}
            className="group relative flex flex-1 flex-col items-center justify-end"
          >
            {/* Tooltip on hover */}
            <div className="invisible absolute -top-8 z-10 whitespace-nowrap rounded-md bg-card border border-border px-2 py-0.5 font-sans text-xs shadow-lg group-hover:visible">
              {point.year}: {point.count.toLocaleString()}
            </div>
            {/* Bar */}
            <div
              className="w-full max-w-[32px] rounded-t-sm bg-accent-foreground/85 transition-all duration-300 hover:bg-accent-foreground"
              style={{ height: `${Math.max(heightPct, 2)}%` }}
            />
            {/* Year label */}
            <span className="mt-1.5 font-sans text-[10px] text-muted-foreground">
              {point.year}
            </span>
          </div>
        )
      })}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  3. First Save Story + Archive Facts                                 */
/* ------------------------------------------------------------------ */

function FirstSaveStoryBlock({
  insights,
}: {
  insights: CollectionInsights
}) {
  const { first_save_story, archive_facts } = insights

  return (
    <section className="space-y-4">
      <h2 className="mb-5 font-serif text-xl font-semibold">
        第一首收藏的故事
      </h2>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Story card */}
        <GlassCard className="border-l-2 border-accent-foreground p-8">
          {first_save_story ? (
            <div className="flex h-full flex-col justify-between space-y-6">
              <div className="space-y-3">
                <p className="font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
                  {first_save_story.save_date}
                </p>
                <p className="font-serif text-lg leading-relaxed">
                  你收藏了{' '}
                  <span className="font-semibold">
                    {first_save_story.artist_name}
                  </span>{' '}
                  的《
                  <span className="font-semibold">
                    {first_save_story.track_name}
                  </span>
                  》，从此<span className="font-semibold">收藏夹</span>
                  的故事开始了。从那天算起，你一共播放了这首歌{' '}
                  <span className="font-semibold">
                    {first_save_story.total_plays}
                  </span>{' '}
                  次，平均每{' '}
                  <span className="font-semibold">
                    {first_save_story.avg_interval_days.toFixed(1)}
                  </span>{' '}
                  天就回来听一次。
                </p>
              </div>

              {/* Bottom metrics */}
              <div className="grid grid-cols-3 gap-4 rounded-lg bg-muted/40 p-4">
                <div className="text-center">
                  <p className="font-serif text-2xl font-bold tabular-nums">
                    {first_save_story.days_since.toLocaleString()}
                  </p>
                  <p className="font-sans text-[11px] text-muted-foreground">
                    陪伴天数
                  </p>
                </div>
                <div className="text-center">
                  <p className="font-serif text-2xl font-bold tabular-nums">
                    {first_save_story.total_plays.toLocaleString()}
                  </p>
                  <p className="font-sans text-[11px] text-muted-foreground">
                    累计播放
                  </p>
                </div>
                <div className="text-center">
                  <p className="font-serif text-2xl font-bold tabular-nums">
                    {first_save_story.avg_interval_days.toFixed(1)}
                  </p>
                  <p className="font-sans text-[11px] text-muted-foreground">
                    平均间隔 (天)
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex h-full items-center justify-center py-12">
              <p className="font-sans text-sm text-muted-foreground">
                暂无第一首收藏的记录
              </p>
            </div>
          )}
        </GlassCard>

        {/* Archive facts */}
        <GlassCard className="p-8">
          <p className="mb-4 font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
            收藏夹档案
          </p>
          <div className="space-y-6">
            <div>
              <p className="font-serif text-4xl font-bold leading-none tabular-nums">
                {archive_facts.total_duration_hrs.toLocaleString()}
              </p>
              <p className="mt-1 font-sans text-sm text-muted-foreground">
                总时长（小时）
              </p>
            </div>
            <div>
              <p className="font-serif text-4xl font-bold leading-none">
                {archive_facts.year_span ?? '--'}
              </p>
              <p className="mt-1 font-sans text-sm text-muted-foreground">
                年代跨度
              </p>
            </div>
            <div>
              {archive_facts.oldest_track ? (
                <>
                  <p className="font-serif text-xl font-semibold leading-tight">
                    {archive_facts.oldest_track.track_name}
                  </p>
                  <p className="mt-0.5 font-sans text-sm text-muted-foreground">
                    {archive_facts.oldest_track.artist_name} &middot;{' '}
                    {archive_facts.oldest_track.year}
                  </p>
                </>
              ) : (
                <p className="font-serif text-xl font-semibold leading-tight text-muted-foreground">
                  无
                </p>
              )}
              <p className="mt-0.5 font-sans text-xs text-muted-foreground">
                最老曲目
              </p>
            </div>
          </div>
        </GlassCard>
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------ */
/*  4. Save Lifecycle                                                  */
/* ------------------------------------------------------------------ */

function SaveLifecycleBlock({
  insights,
}: {
  insights: CollectionInsights
}) {
  const { lifecycle } = insights

  const stages = [
    { key: 'honeymoon', data: lifecycle.honeymoon, color: 'bg-rose-500/70' },
    { key: 'cooling', data: lifecycle.cooling, color: 'bg-amber-500/70' },
    { key: 'settling', data: lifecycle.settling, color: 'bg-sky-500/70' },
  ] as const

  return (
    <section className="space-y-4">
      <h2 className="mb-5 font-serif text-xl font-semibold">
        收藏生命周期
      </h2>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
        {stages.map(({ key, data, color }) => (
          <GlassCard key={key} className="flex flex-col p-6">
            <div className={cn('mb-3 h-1.5 w-10 rounded-full', color)} />
            <p className="font-serif text-lg font-semibold">{data.label}</p>
            <p className="mt-0.5 font-sans text-xs text-muted-foreground">
              {data.weeks}
            </p>
            <p className="mt-3 font-serif text-3xl font-bold leading-none tabular-nums">
              {data.avg_per_week.toFixed(1)}
            </p>
            <p className="mt-0.5 font-sans text-[11px] text-muted-foreground">
              周均播放
            </p>
          </GlassCard>
        ))}

        {/* Fate card (one year later) */}
        <GlassCard className="flex flex-col p-6">
          <div className="mb-3 h-1.5 w-10 rounded-full bg-emerald-500/70" />
          <p className="font-serif text-lg font-semibold">一年后</p>
          <p className="mt-0.5 font-sans text-xs text-muted-foreground">
            收藏分化结果
          </p>

          {/* Stacked horizontal bar */}
          <div className="mt-4 space-y-2.5">
            <FateBar
              label="常青"
              pct={lifecycle.fate.evergreen_pct}
              color="bg-emerald-500"
            />
            <FateBar
              label="偶尔"
              pct={lifecycle.fate.occasional_pct}
              color="bg-amber-500"
            />
            <FateBar
              label="遗忘"
              pct={lifecycle.fate.forgotten_pct}
              color="bg-muted-foreground/30"
            />
          </div>
        </GlassCard>
      </div>
    </section>
  )
}

function FateBar({
  label,
  pct,
  color,
}: {
  label: string
  pct: number
  color: string
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-8 font-sans text-[11px] font-medium">{label}</span>
      <div className="h-3 flex-1 overflow-hidden rounded-full bg-muted">
        <div
          className={cn('h-full rounded-full transition-all', color)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-10 text-right font-sans text-[11px] tabular-nums text-muted-foreground">
        {pct.toFixed(0)}%
      </span>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  5. Chemistry (3x2 grid)                                            */
/* ------------------------------------------------------------------ */

function ChemistryBlock({ insights }: { insights: CollectionInsights }) {
  const { chemistry } = insights

  const types: ChemistryType[] = [
    chemistry.love_at_first_listen,
    chemistry.slow_burn,
    chemistry.flash_in_the_pan,
    chemistry.late_bloomer,
    chemistry.steady_favorite,
    chemistry.shelf_sitter,
  ]

  return (
    <section className="space-y-4">
      <h2 className="mb-5 font-serif text-xl font-semibold">
        收藏化学反应
      </h2>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {types.map((chem) => (
          <ChemistryCard
            key={chem.label}
            chem={chem}
            total={chemistry.total_with_dates}
          />
        ))}
      </div>
    </section>
  )
}

function ChemistryCard({
  chem,
  total,
}: {
  chem: ChemistryType
  total: number
}) {
  const pct = total > 0 ? (chem.count / total) * 100 : 0
  const example = chem.examples?.[0]

  return (
    <GlassCard className="flex flex-col p-5">
      <div className="mb-2 flex items-start justify-between">
        <span className="text-3xl">{chem.icon}</span>
        <span className="font-serif text-sm font-bold tabular-nums">
          {chem.count} 首
        </span>
      </div>

      <p className="font-serif text-base font-semibold">{chem.label}</p>
      <p className="mt-0.5 font-sans text-xs leading-relaxed text-muted-foreground">
        {chem.description}
      </p>

      {/* Percentage bar */}
      <div className="mt-3 flex items-center gap-2">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-accent-foreground/60"
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="font-sans text-[11px] tabular-nums text-muted-foreground">
          {pct.toFixed(0)}%
        </span>
      </div>

      {/* Example track */}
      {example && (
        <div className="mt-3 rounded-md bg-muted/40 px-3 py-2">
          <p className="font-sans text-xs font-medium truncate">
            {example.track_name}
          </p>
          <p className="font-sans text-[11px] text-muted-foreground truncate">
            {example.artist_name}
          </p>
        </div>
      )}
    </GlassCard>
  )
}

/* ------------------------------------------------------------------ */
/*  6. Flip Side + Taste Migration                                     */
/* ------------------------------------------------------------------ */

function FlipSideAndMigrationBlock({
  insights,
}: {
  insights: CollectionInsights
}) {
  const { flip_side, keyword_migration, co_saved_artists } = insights
  const top4 = flip_side.slice(0, 4)

  return (
    <section className="space-y-4">
      <h2 className="mb-5 font-serif text-xl font-semibold">
        另一面 &middot; 品味迁徙
      </h2>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Left: Flip Side */}
        <GlassCard className="p-6">
          <p className="mb-4 font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
            播放最多却没收藏的歌
          </p>

          {top4.length === 0 ? (
            <p className="py-8 text-center font-sans text-sm text-muted-foreground">
              没有漏网的鱼
            </p>
          ) : (
            <div className="divide-y divide-border">
              {top4.map((track, i) => (
                <div
                  key={`${track.track_name}-${track.artist_name}`}
                  className="flex items-center justify-between py-3 first:pt-0 last:pb-0"
                >
                  <div className="min-w-0 flex-1">
                    <p className="font-sans text-sm font-medium truncate">
                      {track.track_name}
                    </p>
                    <p className="font-sans text-xs text-muted-foreground truncate">
                      {track.artist_name}
                    </p>
                  </div>
                  <span className="ml-3 shrink-0 font-serif text-sm font-bold tabular-nums text-muted-foreground">
                    {track.play_count} 次
                  </span>
                </div>
              ))}
            </div>
          )}
        </GlassCard>

        {/* Right: Taste Migration */}
        <GlassCard className="p-6">
          <p className="mb-4 font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
            品味迁徙
          </p>

          {/* Keyword cloud by year */}
          {Object.keys(keyword_migration).length === 0 ? (
            <p className="py-8 text-center font-sans text-sm text-muted-foreground">
              暂无数据
            </p>
          ) : (
            <div className="mb-5 space-y-3">
              {Object.entries(keyword_migration).map(([year, keywords]) => (
                <div key={year} className="flex items-start gap-3">
                  <span className="shrink-0 font-serif text-sm font-bold">
                    {year}
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {keywords.map((kw) => (
                      <span
                        key={kw}
                        className="rounded-full border border-border bg-muted/40 px-2.5 py-0.5 font-sans text-[11px] leading-relaxed"
                      >
                        {kw}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Co-saved artists (Double Chef Moments) */}
          {co_saved_artists.length > 0 && (
            <>
              <p className="mb-2 font-sans text-[11px] font-semibold uppercase text-muted-foreground">
                双厨时刻
              </p>
              <div className="space-y-1.5">
                {co_saved_artists.slice(0, 5).map((pair) => (
                  <p
                    key={`${pair.artist_a}-${pair.artist_b}`}
                    className="font-sans text-xs text-muted-foreground"
                  >
                    <span className="font-medium text-foreground">
                      {pair.artist_a}
                    </span>{' '}
                    &times;{' '}
                    <span className="font-medium text-foreground">
                      {pair.artist_b}
                    </span>
                    ：{pair.count} 首
                  </p>
                ))}
              </div>
            </>
          )}
        </GlassCard>
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------ */
/*  7. Leaderboards (Top 10 + Mismatch)                                 */
/* ------------------------------------------------------------------ */

function LeaderboardBlock({ insights }: { insights: CollectionInsights }) {
  const { top_saved_artists, mismatch } = insights

  return (
    <section className="space-y-4">
      <h2 className="mb-5 font-serif text-xl font-semibold">
        排行榜
      </h2>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Top saved artists */}
        <GlassCard className="p-6">
          <p className="mb-4 font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
            收藏曲目最多的艺人
          </p>

          {top_saved_artists.length === 0 ? (
            <p className="py-8 text-center font-sans text-sm text-muted-foreground">
              暂无数据
            </p>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="pb-2 text-left font-sans text-[10px] font-semibold uppercase text-muted-foreground">
                    #
                  </th>
                  <th className="pb-2 text-left font-sans text-[10px] font-semibold uppercase text-muted-foreground">
                    艺人
                  </th>
                  <th className="pb-2 text-right font-sans text-[10px] font-semibold uppercase text-muted-foreground">
                    收藏
                  </th>
                  <th className="pb-2 text-right font-sans text-[10px] font-semibold uppercase text-muted-foreground">
                    播放
                  </th>
                </tr>
              </thead>
              <tbody>
                {top_saved_artists.slice(0, 10).map((artist, idx) => (
                  <tr
                    key={artist.artist_name}
                    className="border-b border-border/50 last:border-0"
                  >
                    <td className="py-2.5 font-serif text-sm font-bold tabular-nums text-muted-foreground">
                      {idx + 1}
                    </td>
                    <td className="py-2.5 font-sans text-sm font-medium truncate max-w-[160px]">
                      {artist.artist_name}
                    </td>
                    <td className="py-2.5 text-right font-sans text-sm tabular-nums">
                      {artist.saved_count}
                    </td>
                    <td className="py-2.5 text-right font-sans text-sm tabular-nums text-muted-foreground">
                      {artist.total_plays.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </GlassCard>

        {/* Mismatch */}
        <GlassCard className="p-6">
          <p className="mb-4 font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
            错位榜
          </p>

          {/* Over-saved: saved a lot but play little */}
          <div className="mb-5">
            <p className="mb-2 font-sans text-[11px] font-semibold text-muted-foreground">
              收藏多，播放少
            </p>
            {mismatch.over_saved.length === 0 ? (
              <p className="font-sans text-xs text-muted-foreground">暂无</p>
            ) : (
              <MismatchTable artists={mismatch.over_saved} />
            )}
          </div>

          {/* Under-saved: play a lot but saved less */}
          <div>
            <p className="mb-2 font-sans text-[11px] font-semibold text-muted-foreground">
              播放多，收藏少
            </p>
            {mismatch.under_saved.length === 0 ? (
              <p className="font-sans text-xs text-muted-foreground">暂无</p>
            ) : (
              <MismatchTable artists={mismatch.under_saved} />
            )}
          </div>
        </GlassCard>
      </div>
    </section>
  )
}

function MismatchTable({ artists }: { artists: TopSavedArtist[] }) {
  return (
    <table className="w-full">
      <thead>
        <tr className="border-b border-border">
          <th className="pb-1.5 text-left font-sans text-[10px] font-semibold uppercase text-muted-foreground">
            艺人
          </th>
          <th className="pb-1.5 text-right font-sans text-[10px] font-semibold uppercase text-muted-foreground">
            收藏
          </th>
          <th className="pb-1.5 text-right font-sans text-[10px] font-semibold uppercase text-muted-foreground">
            播放
          </th>
        </tr>
      </thead>
      <tbody>
        {artists.slice(0, 5).map((artist) => (
          <tr
            key={artist.artist_name}
            className="border-b border-border/50 last:border-0"
          >
            <td className="py-1.5 font-sans text-xs font-medium truncate max-w-[130px]">
              {artist.artist_name}
            </td>
            <td className="py-1.5 text-right font-sans text-xs tabular-nums">
              {artist.saved_count}
            </td>
            <td className="py-1.5 text-right font-sans text-xs tabular-nums text-muted-foreground">
              {artist.total_plays.toLocaleString()}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/* ------------------------------------------------------------------ */
/*  8. Browser (placeholder)                                           */
/* ------------------------------------------------------------------ */

interface SavedTrackRow {
  track_uri: string
  track_name: string
  artist_name: string
  album_name: string
  added_date: string | null
}

interface SavedTracksPage {
  page: number
  limit: number
  total: number
  total_pages: number
  tracks: SavedTrackRow[]
}

function SavedTracksBrowser() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [data, setData] = useState<SavedTracksPage | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  // Debounce search
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(search)
      setPage(1)
    }, 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [search])

  const fetchPage = useCallback(async (p: number, q: string) => {
    setLoading(true)
    setError('')
    try {
      const result = await api.get<SavedTracksPage>(
        `/library/saved-tracks?page=${p}&limit=50&search=${encodeURIComponent(q)}`
      )
      setData(result)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchPage(page, debouncedSearch)
  }, [page, debouncedSearch, fetchPage])

  const totalPages = data?.total_pages || 0
  const hasNext = page < totalPages
  const hasPrev = page > 1

  return (
    <section className="space-y-4">
      <h2 className="mb-5 font-serif text-xl font-semibold">浏览器</h2>

      <GlassCard className="p-4">
        {/* Search bar */}
        <div className="mb-4 flex items-center gap-3">
          <div className="relative flex-1">
            <svg
              className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
              fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
            </svg>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索曲目或艺人..."
              className="w-full rounded-lg border border-border bg-background py-1.5 pl-9 pr-3 font-sans text-[13px] placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-accent-foreground"
            />
          </div>
          {data && (
            <span className="font-sans text-[12px] text-muted-foreground">
              {data.total} 首
            </span>
          )}
        </div>

        {/* Table */}
        {loading && (
          <div className="space-y-2 py-4">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-8 animate-pulse rounded bg-muted" />
            ))}
          </div>
        )}

        {error && (
          <div className="py-8 text-center text-[13px] text-red-500">{error}</div>
        )}

        {!loading && !error && data && (
          <>
            {data.tracks.length === 0 ? (
              <div className="py-8 text-center text-[13px] text-muted-foreground">
                {debouncedSearch ? '没有匹配的曲目' : '暂无收藏曲目'}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full font-sans text-[13px]">
                  <thead>
                    <tr className="border-b border-border text-left text-[11px] font-semibold uppercase tracking-[0.5px] text-muted-foreground">
                      <th className="pb-2 pr-4">曲目</th>
                      <th className="pb-2 pr-4">艺人</th>
                      <th className="pb-2 pr-4 hidden md:table-cell">专辑</th>
                      <th className="pb-2 text-right">收藏日期</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.tracks.map((t) => (
                      <tr key={t.track_uri} className="border-b border-border/50 last:border-b-0">
                        <td className="py-2 pr-4 font-medium">{t.track_name}</td>
                        <td className="py-2 pr-4 text-muted-foreground">{t.artist_name}</td>
                        <td className="py-2 pr-4 text-muted-foreground hidden md:table-cell">
                          {t.album_name}
                        </td>
                        <td className="py-2 text-right text-muted-foreground whitespace-nowrap">
                          {t.added_date
                            ? new Date(t.added_date).toLocaleDateString('zh-CN')
                            : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="mt-4 flex items-center justify-between border-t border-border pt-3">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={!hasPrev}
                  className="rounded-md px-3 py-1 font-sans text-[12px] text-muted-foreground transition hover:text-foreground disabled:opacity-30"
                >
                  上一页
                </button>
                <span className="font-sans text-[12px] text-muted-foreground">
                  第 {page} / {totalPages} 页
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={!hasNext}
                  className="rounded-md px-3 py-1 font-sans text-[12px] text-muted-foreground transition hover:text-foreground disabled:opacity-30"
                >
                  下一页
                </button>
              </div>
            )}
          </>
        )}
      </GlassCard>
    </section>
  )
}

/* ------------------------------------------------------------------ */
/*  Not Available / Empty states                                       */
/* ------------------------------------------------------------------ */

function NotAvailable() {
  return (
    <GlassCard className="p-12">
      <div className="flex flex-col items-center justify-center space-y-3 text-center">
        <p className="font-serif text-xl font-semibold">暂无收藏数据</p>
        <p className="font-sans text-sm text-muted-foreground">
          你的 Spotify 账号数据中尚未包含收藏记录。请导入账号数据包后查看收藏分析。
        </p>
      </div>
    </GlassCard>
  )
}

/* ------------------------------------------------------------------ */
/*  Main export                                                        */
/* ------------------------------------------------------------------ */

export function CollectionTab({ insights }: { insights: CollectionInsights }) {
  if (!insights.available || insights.empty) {
    return (
      <div className="space-y-6">
        <h2 className="font-serif text-3xl font-bold tracking-tight">
          你的收藏
        </h2>
        <NotAvailable />
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <h2 className="font-serif text-3xl font-bold tracking-tight">
        你的收藏
      </h2>

      {/* 1. Personality Hero */}
      <PersonalityHero insights={insights} />

      {/* 2. Collection Overview */}
      <CollectionOverviewBlock insights={insights} />

      {/* 3. First Save Story + Archive Facts */}
      <FirstSaveStoryBlock insights={insights} />

      {/* 4. Save Lifecycle */}
      <SaveLifecycleBlock insights={insights} />

      {/* 5. Chemistry */}
      <ChemistryBlock insights={insights} />

      {/* 6. Flip Side + Taste Migration */}
      <FlipSideAndMigrationBlock insights={insights} />

      {/* 7. Leaderboards */}
      <LeaderboardBlock insights={insights} />

      {/* 8. Browser placeholder */}
      <SavedTracksBrowser />
    </div>
  )
}
