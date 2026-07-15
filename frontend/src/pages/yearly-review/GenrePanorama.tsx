import { GlassCard } from '@/components/shared/GlassCard'
import type { GenrePanorama as GenrePanoramaType } from '@/types/yearly-review'

interface GenrePanoramaProps {
  genrePanorama: GenrePanoramaType | null
}

function formatHours(hours: number) {
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(hours)
}

export function GenrePanorama({ genrePanorama }: GenrePanoramaProps) {
  const topGenres = genrePanorama?.top_genres.slice(0, 10) ?? []
  const languageDist = genrePanorama?.language_dist
  const hasGenres = topGenres.length > 0
  const hasLanguage = Boolean(languageDist?.buckets.length)

  if (!hasGenres && !hasLanguage) {
    return (
      <section className="mb-12">
        <h2 className="font-serif text-[28px] font-bold tracking-[-0.5px] mb-6">曲风与语言</h2>
        <GlassCard className="p-8 text-center">
          <p className="font-sans text-[14px] text-muted-foreground">曲风与语言数据不足，多听听歌获取更多洞察</p>
        </GlassCard>
      </section>
    )
  }

  const maxShare = Math.max(...topGenres.map(g => g.play_share), 1)

  return (
    <section className="mb-12">
      <h2 className="font-serif text-[28px] font-bold tracking-[-0.5px] mb-6">曲风与语言</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {hasGenres && (
          <GlassCard className="p-5">
            <h3 className="font-sans text-[12px] font-semibold uppercase tracking-[1.5px] text-muted-foreground mb-4">Top 流派</h3>
            <div className="space-y-2.5">
              {topGenres.map((g) => (
                <div key={g.name} className="flex items-center gap-3">
                  <span className="font-sans text-[13px] text-muted-foreground w-20 truncate text-right flex-shrink-0">{g.name}</span>
                  <div className="flex-1 h-5 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full bg-accent-foreground/70 transition-all duration-700"
                      style={{ width: `${(g.play_share / maxShare) * 100}%` }}
                    />
                  </div>
                  <span className="font-sans text-[13px] font-semibold tabular-nums w-12 text-right">{g.play_share}%</span>
                </div>
              ))}
            </div>
          </GlassCard>
        )}

        {hasLanguage && languageDist && (
          <GlassCard className="p-5">
            <h3 className="font-sans text-[12px] font-semibold uppercase tracking-[1.5px] text-muted-foreground mb-4">语言分布</h3>
            <div className="grid grid-cols-2 gap-3 mb-5">
              <p className="rounded-md bg-muted px-3 py-2 font-sans text-[13px] font-semibold tabular-nums">
                已分类 {languageDist.classified_pct}%
              </p>
              <p className="rounded-md bg-muted px-3 py-2 font-sans text-[13px] font-semibold tabular-nums">
                未知 {languageDist.unknown_pct}%
              </p>
            </div>
            <div className="space-y-4">
              {languageDist.buckets.map((bucket) => (
                <div key={bucket.key}>
                  <div className="mb-1.5 flex min-w-0 items-center justify-between gap-3">
                    <span className="min-w-0 truncate font-sans text-[13px] font-medium">{bucket.label}</span>
                    <span className="flex flex-shrink-0 items-center gap-2 font-sans text-[12px] text-muted-foreground tabular-nums">
                      <span>{formatHours(bucket.hours)} 小时</span>
                      <span aria-hidden="true">·</span>
                      <span>{bucket.artist_count} 位艺人</span>
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="h-4 flex-1 overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-accent-foreground/70 transition-all duration-700"
                        style={{ width: `${Math.min(Math.max(bucket.share_pct, 0), 100)}%` }}
                      />
                    </div>
                    <span className="w-12 flex-shrink-0 text-right font-sans text-[13px] font-semibold tabular-nums">
                      {bucket.share_pct}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
            <p className="mt-5 font-sans text-[12px] leading-5 text-muted-foreground">{languageDist.caveat}</p>
            {languageDist.excluded_unattributed_hours > 0 && (
              <p className="mt-2 font-sans text-[12px] leading-5 text-muted-foreground">
                另有 {formatHours(languageDist.excluded_unattributed_hours)} 小时因无法归属主艺人而未纳入语言分布。
              </p>
            )}
          </GlassCard>
        )}
      </div>
    </section>
  )
}
