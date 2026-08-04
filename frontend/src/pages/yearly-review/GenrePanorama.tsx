import { GlassCard } from '@/components/shared/GlassCard'
import { TasteProfileGrid } from '@/components/shared/TasteProfile'
import type {
  GenrePanorama as GenrePanoramaType,
} from '@/types/yearly-review'

interface GenrePanoramaProps {
  genrePanorama: GenrePanoramaType | null
}

export function GenrePanorama({ genrePanorama }: GenrePanoramaProps) {
  const primaryStyles = genrePanorama?.primary_styles?.buckets ?? (
    genrePanorama?.top_genres.map((genre) => ({
      key: genre.name,
      label: genre.label || genre.name,
      hours: genre.hours ?? 0,
      share_pct: genre.play_share,
      artist_count: 0,
    })) ?? []
  )
  const hasData = primaryStyles.length > 0
    || (genrePanorama?.regional_pop?.buckets.length ?? 0) > 0
    || (genrePanorama?.language_dist?.buckets.length ?? 0) > 0

  if (!hasData) {
    return (
      <section className="mb-12">
        <h2 className="mb-6 font-serif text-[28px] font-bold">今年的曲风与语言</h2>
        <GlassCard className="p-8 text-center">
          <p className="font-sans text-[14px] text-muted-foreground">曲风与语言数据不足，多听听歌获取更多洞察</p>
        </GlassCard>
      </section>
    )
  }

  return (
    <section
      className="mb-12"
      aria-labelledby="yearly-taste-heading"
    >
      <div className="mb-6">
        <p className="font-sans text-[10px] font-bold uppercase tracking-[2px] text-accent-foreground">Taste portrait</p>
        <h2 id="yearly-taste-heading" className="mt-1 font-serif text-[28px] font-bold">今年的曲风与语言</h2>
        <p className="mt-2 max-w-2xl font-sans text-[12px] leading-5 text-muted-foreground">
          声音风格、地区流行与语言分别观察，同一次聆听可以从不同角度被看见。
        </p>
      </div>
      <TasteProfileGrid showNotes={false} profile={{ ...genrePanorama, primary_styles: genrePanorama?.primary_styles ?? {
        axis: 'style', label: '主曲风', total_hours: 0, known_hours: 0, unknown_hours: 0,
        allows_multiple: true, buckets: primaryStyles,
      } }} />
    </section>
  )
}
