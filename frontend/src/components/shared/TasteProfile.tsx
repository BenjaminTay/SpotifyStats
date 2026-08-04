import { GlassCard } from '@/components/shared/GlassCard'
import type { LanguageBucket } from '@/types/artist-language-metadata'
import type { ConsumerGenreBucket, ConsumerTasteProfile } from '@/types/yearly-review'

type DisplayBucket = Pick<ConsumerGenreBucket, 'key' | 'label' | 'hours' | 'share_pct'>

function formatHours(hours: number) {
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(hours)
}

function orderedBuckets<T extends { key: string }>(buckets: T[]): T[] {
  const known = buckets.filter((bucket) => bucket.key !== 'unknown').slice(0, 8)
  return [...known, ...buckets.filter((bucket) => bucket.key === 'unknown')]
}

function DistributionRows({ buckets }: { buckets: DisplayBucket[] }) {
  return (
    <div className="space-y-3.5">
      {orderedBuckets(buckets).map((bucket) => {
        const unknown = bucket.key === 'unknown'
        return (
          <div className={unknown ? 'pt-1 opacity-70' : ''} key={bucket.key}>
            <div className="mb-1.5 flex min-w-0 items-baseline justify-between gap-3">
              <span className="min-w-0 break-words font-sans text-[13px] font-medium text-foreground">
                {unknown ? '尚未归类' : bucket.label}
              </span>
              <span className="shrink-0 font-serif text-[20px] font-bold italic tabular-nums text-foreground">
                {bucket.share_pct}%
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-muted">
              <div
                className={unknown ? 'h-full rounded-full bg-muted-foreground/35' : 'h-full rounded-full bg-accent-foreground/75'}
                style={{ width: `${Math.min(Math.max(bucket.share_pct, 0), 100)}%` }}
              />
            </div>
            <p className="mt-1 font-sans text-[10.5px] text-muted-foreground">{formatHours(bucket.hours)} 小时</p>
          </div>
        )
      })}
    </div>
  )
}

function TasteCard({ eyebrow, title, note, buckets }: {
  eyebrow: string
  title: string
  note?: string
  buckets: DisplayBucket[]
}) {
  return (
    <GlassCard className="relative min-w-0 overflow-hidden p-5">
      <div aria-hidden="true" className="absolute right-4 top-3 font-serif text-[52px] font-bold italic leading-none text-foreground/[0.035]">
        {eyebrow}
      </div>
      <div className="relative mb-5 border-b border-border pb-4">
        <p className="font-sans text-[10px] font-bold uppercase tracking-[1.7px] text-accent-foreground">{eyebrow}</p>
        <h3 className="mt-1 font-serif text-[24px] font-bold leading-tight">{title}</h3>
        {note ? <p className="mt-2 max-w-[36ch] font-sans text-[11px] leading-5 text-muted-foreground">{note}</p> : null}
      </div>
      {buckets.length > 0 ? <DistributionRows buckets={buckets} /> : (
        <p className="py-8 text-center font-sans text-[12px] text-muted-foreground">当前时段还没有足够的数据</p>
      )}
    </GlassCard>
  )
}

function languageBuckets(buckets: LanguageBucket[]): DisplayBucket[] {
  return buckets.map((bucket) => ({
    key: bucket.key,
    label: bucket.key === 'unknown' ? '尚未归类' : bucket.label,
    hours: bucket.hours,
    share_pct: bucket.share_pct,
  }))
}

export function TasteProfileGrid({
  profile,
  showNotes = true,
}: {
  profile: ConsumerTasteProfile
  showNotes?: boolean
}) {
  const primaryStyles = profile.primary_styles?.buckets ?? []
  const regionalPop = profile.regional_pop?.buckets ?? []
  const languages = languageBuckets(profile.language_dist?.buckets ?? [])

  return (
    <div
      className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3"
      data-display-taxonomy={profile.display_taxonomy_version ?? 'legacy'}
    >
      <TasteCard
        eyebrow="01"
        title="主曲风"
        note={showNotes ? '占全部可归属有效聆听时长；风格可以多标签，并在同一维度内分摊。' : undefined}
        buckets={primaryStyles}
      />
      <TasteCard
        eyebrow="02"
        title="地区流行"
        note={showNotes ? '一首华语 R&B 可以同时体现 C-Pop 与 R&B，两种观察不会互相取代。' : undefined}
        buckets={regionalPop}
      />
      <TasteCard
        eyebrow="03"
        title="语言"
        note={showNotes ? '按艺人常用演唱语言与主艺人播放时长估算。' : undefined}
        buckets={languages}
      />
    </div>
  )
}
