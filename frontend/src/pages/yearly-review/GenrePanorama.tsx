import { GlassCard } from '@/components/shared/GlassCard'
import type {
  GenreAxisDistribution,
  GenreItem,
  GenrePanorama as GenrePanoramaType,
} from '@/types/yearly-review'

interface GenrePanoramaProps {
  genrePanorama: GenrePanoramaType | null
}

function formatHours(hours: number) {
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(hours)
}

function confidenceLabel(tier?: string) {
  if (tier === 'high') return '高置信'
  if (tier === 'low') return '低置信'
  return '中置信'
}

function confidenceClass(tier?: string) {
  if (tier === 'high') return 'text-emerald-700 dark:text-emerald-300'
  if (tier === 'low') return 'text-rose-700 dark:text-rose-300'
  return 'text-amber-700 dark:text-amber-300'
}

function riskText(code: string) {
  if (code === 'single_artist_dominance') return '单一艺人主导'
  if (code === 'missing_evidence_url') return '部分来源缺少证据链接'
  if (code === 'llm_majority') return 'LLM 来源占比过高'
  if (code === 'source_confidence') return '来源置信度有限'
  return '需要复核'
}

function StyleRows({ genres }: { genres: GenreItem[] }) {
  const maxShare = Math.max(...genres.map((genre) => genre.play_share), 1)
  return (
    <div className="space-y-3">
      {genres.map((genre) => {
        const risks = genre.risk_flags ?? []
        return (
          <div key={genre.name}>
            <div className="mb-1.5 flex min-w-0 items-end justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate font-sans text-[13px] font-medium text-foreground">
                  {genre.label || genre.name}
                </p>
                {genre.top_artists?.length ? (
                  <p className="truncate text-[11px] text-muted-foreground">
                    主要来自 {genre.top_artists.slice(0, 2).map((artist) => artist.artist_name).join('、')}
                  </p>
                ) : null}
              </div>
              <div className="flex shrink-0 items-center gap-2 text-[11px]">
                <span className={confidenceClass(genre.confidence_tier)}>{confidenceLabel(genre.confidence_tier)}</span>
                <span className="font-mono text-[13px] font-semibold text-foreground">{genre.play_share}%</span>
              </div>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-accent-foreground/75 transition-all duration-700"
                style={{ width: `${(genre.play_share / maxShare) * 100}%` }}
              />
            </div>
            {risks.length > 0 && (
              <p className="mt-1 text-[10.5px] leading-relaxed text-muted-foreground">
                {risks.slice(0, 2).map((risk) => riskText(risk.code)).join(' · ')}
              </p>
            )}
          </div>
        )
      })}
    </div>
  )
}

function AxisSummary({ axis }: { axis: GenreAxisDistribution }) {
  return (
    <div aria-label={`${axis.label}流派轴`} className="min-w-0 border-t border-border pt-3">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h4 className="text-[12.5px] font-semibold text-foreground">{axis.label}</h4>
          <p className="mt-0.5 truncate text-[10.5px] text-muted-foreground">{axis.interpretation}</p>
        </div>
        <span className="shrink-0 font-mono text-[11px] text-muted-foreground">覆盖 {axis.coverage_pct}%</span>
      </div>
      {axis.buckets.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {axis.buckets.slice(0, 4).map((bucket) => (
            <span className="rounded-md bg-muted px-2 py-1 text-[11px] text-foreground" key={bucket.name}>
              {bucket.label || bucket.name} {bucket.share_pct}%
            </span>
          ))}
        </div>
      ) : (
        <p className="mt-2 text-[11px] text-muted-foreground">本年度没有足够的已识别标签。</p>
      )}
    </div>
  )
}

export function GenrePanorama({ genrePanorama }: GenrePanoramaProps) {
  const topGenres = genrePanorama?.top_genres.slice(0, 8) ?? []
  const languageDist = genrePanorama?.language_dist
  const axes = genrePanorama?.axes ?? []
  const styleAxis = axes.find((axis) => axis.axis === 'style')
  const secondaryAxes = axes.filter((axis) => axis.axis !== 'style')
  const hasGenres = topGenres.length > 0 || axes.some((axis) => axis.buckets.length > 0)
  const hasLanguage = Boolean(languageDist?.buckets.length)

  if (!hasGenres && !hasLanguage) {
    return (
      <section className="mb-12">
        <h2 className="mb-6 font-serif text-[28px] font-bold">曲风与语言</h2>
        <GlassCard className="p-8 text-center">
          <p className="font-sans text-[14px] text-muted-foreground">曲风与语言数据不足，多听听歌获取更多洞察</p>
        </GlassCard>
      </section>
    )
  }

  return (
    <section className="mb-12">
      <h2 className="mb-6 font-serif text-[28px] font-bold">曲风与语言</h2>
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {hasGenres && (
          <GlassCard className="p-5">
            <div className="mb-4 flex items-start justify-between gap-3">
              <div>
                <h3 className="font-sans text-[12px] font-semibold uppercase text-muted-foreground">主要声音风格</h3>
                <p className="mt-1 text-[11px] text-muted-foreground">百分比按已识别 style 标签单独计算</p>
              </div>
              {styleAxis && (
                <span className="shrink-0 font-mono text-[11px] text-muted-foreground">覆盖 {styleAxis.coverage_pct}%</span>
              )}
            </div>
            {topGenres.length > 0 ? <StyleRows genres={topGenres} /> : (
              <p className="text-[12px] text-muted-foreground">本年度没有足够的声音风格标签。</p>
            )}
            {secondaryAxes.length > 0 && (
              <div className="mt-5 space-y-3">
                {secondaryAxes.map((axis) => <AxisSummary axis={axis} key={axis.axis} />)}
              </div>
            )}
            {genrePanorama?.caveat && (
              <p className="mt-4 border-l-2 border-accent-foreground/40 pl-3 text-[11px] leading-relaxed text-muted-foreground">
                {genrePanorama.caveat}
              </p>
            )}
          </GlassCard>
        )}

        {hasLanguage && languageDist && (
          <GlassCard className="p-5">
            <h3 className="font-sans text-[12px] font-semibold uppercase text-muted-foreground">艺人语言归属</h3>
            <p className="mt-1 text-[11px] text-muted-foreground">按已审核艺人事实和主艺人播放时长估算</p>
            <div className="mb-5 mt-4 grid grid-cols-2 gap-3">
              <p className="rounded-md bg-muted px-3 py-2 font-sans text-[13px] font-semibold tabular-nums">已分类 {languageDist.classified_pct}%</p>
              <p className="rounded-md bg-muted px-3 py-2 font-sans text-[13px] font-semibold tabular-nums">未知 {languageDist.unknown_pct}%</p>
            </div>
            <div className="space-y-4">
              {languageDist.buckets.map((bucket) => (
                <div key={bucket.key}>
                  <div className="mb-1.5 flex min-w-0 items-center justify-between gap-3">
                    <span className="min-w-0 truncate font-sans text-[13px] font-medium">{bucket.label}</span>
                    <span className="flex shrink-0 items-center gap-2 font-sans text-[12px] text-muted-foreground tabular-nums">
                      <span>{formatHours(bucket.hours)} 小时</span><span aria-hidden="true">·</span><span>{bucket.artist_count} 位艺人</span>
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="h-4 flex-1 overflow-hidden rounded-full bg-muted">
                      <div className="h-full rounded-full bg-accent-foreground/70" style={{ width: `${Math.min(Math.max(bucket.share_pct, 0), 100)}%` }} />
                    </div>
                    <span className="w-12 shrink-0 text-right font-sans text-[13px] font-semibold tabular-nums">{bucket.share_pct}%</span>
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
