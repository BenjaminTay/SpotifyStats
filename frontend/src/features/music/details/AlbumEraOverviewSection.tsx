import type { AlbumDetailResponse, ReleaseCycleAlbumDetailResponse } from '@/types/billboard'
import { GlassCard } from '@/components/shared/GlassCard'
import { displayName } from '@/lib/chinese'
import {
  MiniStat,
  formatHalfLife,
} from './AlbumDetailPrimitives'
import {
  KpiCard,
  formatDateShort,
  formatNumber,
  formatOptionalRank,
} from './MusicDetailPrimitives'
import { formatAlbumKind } from './MusicDetailHeader'

type AlbumEraOverviewSectionProps = {
  data: AlbumDetailResponse
  releaseCycle: ReleaseCycleAlbumDetailResponse
}

export function AlbumEraOverviewSection({ data, releaseCycle }: AlbumEraOverviewSectionProps) {
  return (
    <>
      <div className="mb-8">
        <h3 className="mb-4 font-serif text-xl font-semibold">发行概览</h3>
        <GlassCard className="p-5">
          <div className="flex flex-col gap-5 md:flex-row md:items-start">
            {data.cover_url && (
              <img
                src={data.cover_url}
                alt={data.album_name}
                className="h-[104px] w-[104px] flex-shrink-0 rounded-[12px] object-cover shadow-md"
                loading="lazy"
              />
            )}
            <div className="min-w-0 flex-1">
              <p className="font-serif text-[24px] font-semibold leading-tight">
                {displayName(releaseCycle.primary_name || releaseCycle.album_name)}
              </p>
              <p className="mt-1 font-sans text-[13px] text-muted-foreground">
                {formatDateShort(releaseCycle.release_date_iso || releaseCycle.release_date)} · {formatAlbumKind(releaseCycle.album_type)}
              </p>
              <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
                <MiniStat label="主版本" value={displayName(releaseCycle.primary_name || releaseCycle.canonical_name)} />
                <MiniStat label="合并版本" value={releaseCycle.is_grouped ? `${releaseCycle.group_albums.length}` : '1'} />
                <MiniStat label="先行单曲" value={formatNumber(releaseCycle.advance_singles.length)} />
                <MiniStat label="周期窗口" value="发行前后" />
              </div>
            </div>
          </div>
        </GlassCard>
      </div>

      <div className="mb-8 grid grid-cols-2 gap-5 lg:grid-cols-4">
        <KpiCard
          label="空降排名"
          value={formatOptionalRank(releaseCycle.metrics.debut_rank)}
          sub={`发行周播放 ${formatNumber(releaseCycle.metrics.release_week_plays)}`}
          accent={releaseCycle.metrics.debut_rank === 1}
        />
        <KpiCard
          label="周期峰值"
          value={formatOptionalRank(releaseCycle.metrics.peak_rank)}
          sub={releaseCycle.metrics.weeks_to_peak != null ? `登顶/达峰需 ${releaseCycle.metrics.weeks_to_peak} 周` : '未入专辑榜'}
          accent={releaseCycle.metrics.peak_rank === 1}
        />
        <KpiCard
          label="半数播放距"
          value={formatHalfLife(releaseCycle.metrics.half_life)}
          sub={`峰值播放 ${formatNumber(releaseCycle.metrics.peak_play_count)}`}
        />
        <KpiCard
          label="收听冲击力"
          value={releaseCycle.metrics.artist_impact_fmt ?? '—'}
          sub={releaseCycle.metrics.market_impact_fmt ? `大盘 ${releaseCycle.metrics.market_impact_fmt}` : undefined}
          accent
        />
      </div>
    </>
  )
}
