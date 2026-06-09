import type { AlbumDetailResponse, AlbumEnrichmentResponse, ReleaseCycleAlbumDetailResponse } from '@/types/billboard'
import { GlassCard } from '@/components/shared/GlassCard'
import { ReleaseTimelineChart } from '@/components/charts/ReleaseTimelineChart'
import { Skeleton } from '@/components/ui/skeleton'

type AlbumReleaseTimelineSectionProps = {
  data: AlbumDetailResponse
  enrichment: AlbumEnrichmentResponse | null
  releaseCycle: ReleaseCycleAlbumDetailResponse | null
  releaseCycleLoading: boolean
  releaseCycleError: string | null
}

export function AlbumReleaseTimelineSection({
  data,
  enrichment,
  releaseCycle,
  releaseCycleLoading,
  releaseCycleError,
}: AlbumReleaseTimelineSectionProps) {
  return (
    <div className="mb-8">
      <h3 className="mb-4 font-serif text-xl font-semibold">发行走势</h3>
      <GlassCard className="p-6">
        {releaseCycleLoading ? (
          <Skeleton className="h-[380px] w-full rounded-[12px]" />
        ) : (
          <ReleaseTimelineChart
            albumHistory={
              releaseCycle && !releaseCycle.error
                ? releaseCycle.album_ranks.map((e) => ({
                    week: e.billboard_week,
                    week_offset: e.week_offset,
                    rank: e.rank,
                    play_count: e.play_count,
                  }))
                : data.album_weekly_history.map((e) => ({
                    week: e.week,
                    rank: e.rank,
                    play_count: e.play_count,
                  }))
            }
            singlesOverlay={releaseCycle ? releaseCycle.best_track_ranks?.ranks ?? [] : data.best_singles_overlay}
            wikiSingles={enrichment?.wiki?.infobox?.singles ?? []}
            albumReleaseDate={releaseCycle?.release_date_iso ?? data.meta?.release_date ?? ''}
            albumTimeline={releaseCycle?.album_timeline ?? []}
            advanceSingleRanks={releaseCycle?.advance_single_ranks ?? []}
            bestTrackRanks={releaseCycle?.best_track_ranks ?? null}
          />
        )}
        {releaseCycleError && (
          <p className="mt-2 font-sans text-[11px] text-destructive">
            发行周期数据加载失败：{releaseCycleError}
          </p>
        )}
        {(releaseCycle || enrichment?.wiki) && (
          <p className="mt-2 font-sans text-[11px] text-muted-foreground">
            发行周期来自本地播放数据
            {enrichment?.wiki && <span> · 单曲发行标记来自 Wikipedia</span>}
            {(enrichment?.wiki?.infobox?.singles.length ?? 0) > 0 && (
              <span> · 共识别 {enrichment?.wiki?.infobox?.singles.length} 支单曲</span>
            )}
          </p>
        )}
      </GlassCard>
    </div>
  )
}
