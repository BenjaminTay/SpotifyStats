import { ExternalLink } from 'lucide-react'
import type { AlbumDetailResponse, AlbumEnrichmentResponse, ReleaseCycleAlbumDetailResponse } from '@/types/billboard'
import { GlassCard } from '@/components/shared/GlassCard'
import {
  AlbumEnrichmentView,
  albumSingleCompactCoverKey,
  albumSingleCoverKey,
} from '@/components/shared/AlbumEnrichmentView'
import {
  AlbumStoryCard,
  InfoRow,
} from './AlbumDetailPrimitives'

type AlbumEnrichmentSectionProps = {
  data: AlbumDetailResponse
  enrichment: AlbumEnrichmentResponse | null
  releaseCycle: ReleaseCycleAlbumDetailResponse | null
}

function addSingleCoverEntry(entries: Record<string, string>, name: string, coverUrl: string) {
  entries[name] = coverUrl
  entries[albumSingleCoverKey(name)] = coverUrl
  entries[albumSingleCompactCoverKey(name)] = coverUrl
}

function buildSingleCoverUrls(
  data: AlbumDetailResponse,
  releaseCycle: ReleaseCycleAlbumDetailResponse | null,
) {
  const entries: Record<string, string> = {}
  for (const track of data.tracks ?? []) {
    if (!track.track_name || !track.cover_url) continue
    addSingleCoverEntry(entries, track.track_name, track.cover_url)
  }
  for (const single of releaseCycle?.advance_singles ?? []) {
    if (!single.cover_url) continue
    addSingleCoverEntry(entries, single.single_name, single.cover_url)
  }
  return entries
}

export function AlbumEnrichmentSection({ data, enrichment, releaseCycle }: AlbumEnrichmentSectionProps) {
  const singleCoverUrls = buildSingleCoverUrls(data, releaseCycle)

  if (enrichment?.wiki?.structured) {
    return (
      <div className="mb-8">
        <h3 className="mb-4 font-serif text-xl font-semibold">专辑简介</h3>
        <AlbumEnrichmentView data={enrichment.wiki.structured} singleCoverUrls={singleCoverUrls} />
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
    )
  }

  return (
    <>
      {(enrichment?.wiki?.sections?.background || enrichment?.wiki?.summary) && (
        <div className="mb-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div>
            <h3 className="mb-4 font-serif text-xl font-semibold">专辑故事</h3>
            <AlbumStoryCard
              summary={enrichment.wiki.summary_zh || enrichment.wiki.summary}
              background={enrichment.wiki.sections_zh?.background || enrichment.wiki.sections.background}
              url={enrichment.wiki.url}
            />
          </div>
          <div>
            <h3 className="mb-4 font-serif text-xl font-semibold">制作信息</h3>
            <GlassCard className="p-5">
              <dl className="space-y-3">
                {enrichment.wiki.infobox.genre && (
                  <InfoRow label="流派" value={enrichment.wiki.infobox.genre.replace(/^\*\s*/gm, '').replace(/\*/g, ' · ')} />
                )}
                {enrichment.wiki.infobox.label && (
                  <InfoRow label="厂牌" value={enrichment.wiki.infobox.label.replace(/^\*\s*/gm, '').replace(/\*/g, ' · ')} />
                )}
                {enrichment.wiki.infobox.producer && (
                  <InfoRow label="制作人" value={enrichment.wiki.infobox.producer.replace(/^\*\s*/gm, '').replace(/\*/g, ' · ')} />
                )}
                {enrichment.wiki.infobox.recorded && (
                  <InfoRow label="录制" value={enrichment.wiki.infobox.recorded} />
                )}
                {enrichment.wiki.infobox.studio && (
                  <InfoRow label="录音室" value={enrichment.wiki.infobox.studio} />
                )}
                {enrichment.wiki.infobox.length && (
                  <InfoRow label="时长" value={enrichment.wiki.infobox.length} />
                )}
                {data.meta?.popularity != null && (
                  <InfoRow label="Spotify 流行度" value={`${data.meta.popularity}/100`} />
                )}
              </dl>
            </GlassCard>
          </div>
        </div>
      )}
      {enrichment?.wiki?.sections?.reception && (
        <div className="mb-8">
          <h3 className="mb-4 font-serif text-xl font-semibold">专业评价</h3>
          <AlbumStoryCard
            summary=""
            background={enrichment.wiki.sections_zh?.reception || enrichment.wiki.sections.reception}
            url={enrichment.wiki.url}
          />
        </div>
      )}
    </>
  )
}
