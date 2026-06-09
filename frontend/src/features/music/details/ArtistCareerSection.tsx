import { ExternalLink } from 'lucide-react'
import type { ArtistEnrichmentResponse, ArtistSpotifyMeta } from '@/types/billboard'
import { GlassCard } from '@/components/shared/GlassCard'
import { FormattedText } from '@/components/shared/FormattedText'
import { ArtistEnrichmentView } from '@/components/shared/ArtistEnrichmentView'
import { Skeleton } from '@/components/ui/skeleton'
import { formatArtistFollowers } from './MusicDetailHeader'

export function ArtistCareerSection({
  enrichment,
  enrichmentLoading,
  meta,
}: {
  enrichment: ArtistEnrichmentResponse | null
  enrichmentLoading: boolean
  meta: ArtistSpotifyMeta | null
}) {
  return (
    <div className="mb-8">
      {enrichmentLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-[200px] w-full rounded-[16px]" />
          <Skeleton className="h-[120px] w-full rounded-[16px]" />
        </div>
      ) : enrichment?.wiki ? (
        <>
          {enrichment.wiki.structured ? (
            <div className="mb-8">
              <h3 className="mb-4 font-serif text-xl font-semibold">艺人简介</h3>
              <ArtistEnrichmentView data={enrichment.wiki.structured} />
              <div className="mt-4">
                <a
                  href={enrichment.wiki.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                >
                  <ExternalLink className="h-3 w-3" />
                  Wikipedia
                </a>
              </div>
            </div>
          ) : (
            <>
              <div className="mb-8">
                <h3 className="mb-4 font-serif text-xl font-semibold">艺人简介</h3>
                <GlassCard className="p-5">
                  <FormattedText
                    text={enrichment.wiki.summary_zh || enrichment.wiki.summary}
                    className="font-sans text-[14px] leading-relaxed text-foreground/85"
                  />
                  <div className="mt-3">
                    <a
                      href={enrichment.wiki.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                    >
                      <ExternalLink className="h-3 w-3" />
                      Wikipedia
                    </a>
                  </div>
                </GlassCard>
              </div>
              {(enrichment.wiki.sections_zh?.early_life || enrichment.wiki.sections.early_life) && (
                <div className="mb-8">
                  <h3 className="mb-4 font-serif text-xl font-semibold">早期生涯</h3>
                  <GlassCard className="p-5">
                    <FormattedText
                      text={enrichment.wiki.sections_zh?.early_life || enrichment.wiki.sections.early_life}
                      className="font-sans text-[14px] leading-relaxed text-foreground/85"
                    />
                  </GlassCard>
                </div>
              )}
            </>
          )}
        </>
      ) : (
        <div className="mb-8">
          <h3 className="mb-4 font-serif text-xl font-semibold">艺人简介</h3>
          <GlassCard className="p-5">
            <p className="font-sans text-[14px] leading-relaxed text-muted-foreground">
              未找到 Wikipedia 信息
            </p>
          </GlassCard>
        </div>
      )}

      {meta && (
        <div className="mb-8">
          <h3 className="mb-4 font-serif text-xl font-semibold">Spotify 档案</h3>
          <GlassCard className="p-5">
            <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
              {meta.popularity != null && (
                <div>
                  <p className="font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                    流行度
                  </p>
                  <div className="mt-2 flex items-center gap-2">
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-accent-foreground"
                        style={{ width: `${meta.popularity}%` }}
                      />
                    </div>
                    <span className="font-sans text-[13px] font-semibold tabular-nums">
                      {meta.popularity}
                    </span>
                  </div>
                </div>
              )}
              {meta.followers != null && (
                <div>
                  <p className="font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                    粉丝数
                  </p>
                  <p className="mt-1 font-serif text-[28px] font-bold">
                    {formatArtistFollowers(meta.followers)}
                  </p>
                </div>
              )}
              {meta.genres && meta.genres.length > 0 && (
                <div className="col-span-2">
                  <p className="font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                    流派
                  </p>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {meta.genres.map((genre) => (
                      <span
                        key={genre}
                        className="rounded-full border border-border px-3 py-1 font-sans text-[12px] text-foreground/75"
                      >
                        {genre}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </GlassCard>
        </div>
      )}
    </div>
  )
}
