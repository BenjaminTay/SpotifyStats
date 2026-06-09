import type { AlbumEnrichmentResponse, ReleaseCycleAlbumDetailResponse } from '@/types/billboard'
import { GlassCard } from '@/components/shared/GlassCard'
import { displayName } from '@/lib/chinese'
import { formatDateShort } from './MusicDetailPrimitives'

type AlbumReleaseCompositionSectionProps = {
  enrichment: AlbumEnrichmentResponse | null
  releaseCycle: ReleaseCycleAlbumDetailResponse
}

export function AlbumReleaseCompositionSection({
  enrichment,
  releaseCycle,
}: AlbumReleaseCompositionSectionProps) {
  const hasWikiSingles = (enrichment?.wiki?.infobox?.singles.length ?? 0) > 0
  const shouldRender = releaseCycle.is_grouped || releaseCycle.advance_singles.length > 0 || hasWikiSingles

  if (!shouldRender) {
    return null
  }

  return (
    <div className="mb-8">
      <h3 className="mb-4 font-serif text-xl font-semibold">发行构成</h3>
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {releaseCycle.is_grouped && (
          <GlassCard className="p-5">
            <h4 className="mb-3 font-serif text-[18px] font-semibold">版本家族</h4>
            <p className="font-sans text-[13px] text-muted-foreground">
              主版本：{displayName(releaseCycle.primary_name || releaseCycle.canonical_name)}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {releaseCycle.group_albums.map((name) => (
                <span key={name} className="rounded-full border border-border px-3 py-1 font-sans text-[12px] text-foreground/75">
                  {displayName(name)}
                </span>
              ))}
            </div>
          </GlassCard>
        )}
        {releaseCycle.advance_singles.length > 0 && (
          <GlassCard className="p-5">
            <h4 className="mb-3 font-serif text-[18px] font-semibold">先行单曲</h4>
            <div className="space-y-2">
              {releaseCycle.advance_singles.map((single) => (
                <div key={`${single.single_name}-${single.release_date}`} className="flex items-center justify-between gap-4 border-b border-border/60 pb-2 last:border-0 last:pb-0">
                  <span className="font-sans text-[13px] font-semibold">{displayName(single.single_name)}</span>
                  <span className="font-sans text-[12px] text-muted-foreground">{formatDateShort(single.release_date)}</span>
                </div>
              ))}
            </div>
          </GlassCard>
        )}
        {enrichment?.wiki?.infobox?.singles && enrichment.wiki.infobox.singles.length > 0 && (
          <GlassCard className="p-5">
            <h4 className="mb-3 font-serif text-[18px] font-semibold">单曲发行</h4>
            <div className="space-y-2">
              {enrichment.wiki.infobox.singles.slice(0, 12).map((s, i) => (
                <div key={`${s.name}-${i}`} className="flex items-center justify-between gap-4 border-b border-border/60 pb-2 last:border-0 last:pb-0">
                  <span className="font-sans text-[13px] font-semibold">{displayName(s.name)}</span>
                  {s.date && <span className="font-sans text-[12px] text-muted-foreground">{s.date}</span>}
                </div>
              ))}
            </div>
          </GlassCard>
        )}
      </div>
    </div>
  )
}
