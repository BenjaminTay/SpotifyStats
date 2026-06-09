import type { ReleaseCycleAlbumDetailResponse } from '@/types/billboard'
import { GlassCard } from '@/components/shared/GlassCard'
import { displayName } from '@/lib/chinese'
import { formatNumber } from './MusicDetailPrimitives'

type AlbumReleaseOverflowSectionProps = {
  releaseCycle: ReleaseCycleAlbumDetailResponse
}

export function AlbumReleaseOverflowSection({ releaseCycle }: AlbumReleaseOverflowSectionProps) {
  if (releaseCycle.catalog_reentries.length === 0 && releaseCycle.bonus_tracks.length === 0) {
    return null
  }

  return (
    <div className="mb-8">
      <h3 className="mb-4 font-serif text-xl font-semibold">外溢影响</h3>
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {releaseCycle.catalog_reentries.length > 0 && (
          <div>
            <h4 className="mb-3 font-serif text-[18px] font-semibold">老歌回榜</h4>
            <GlassCard className="overflow-hidden p-0">
              <table className="mx-6 my-0 w-[calc(100%-48px)] border-collapse">
                <tbody>
                  {releaseCycle.catalog_reentries.map((item) => (
                    <tr key={`${item.track_name}-${item.reentry_offset}`} className="border-b border-border/60 last:border-0">
                      <td className="py-3 font-sans text-[13px] font-semibold">{displayName(item.track_name)}</td>
                      <td className="py-3 font-sans text-[12px] text-muted-foreground">{displayName(item.source_album)}</td>
                      <td className="py-3 text-right font-sans text-[12px] text-muted-foreground">+{item.reentry_offset} 周</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </GlassCard>
          </div>
        )}
        {releaseCycle.bonus_tracks.length > 0 && (
          <div>
            <h4 className="mb-3 font-serif text-[18px] font-semibold">加曲来源</h4>
            <GlassCard className="overflow-hidden p-0">
              <table className="mx-6 my-0 w-[calc(100%-48px)] border-collapse">
                <tbody>
                  {releaseCycle.bonus_tracks.slice(0, 12).map((item) => (
                    <tr key={`${item.track_name}-${item.source_album}`} className="border-b border-border/60 last:border-0">
                      <td className="py-3 font-sans text-[13px] font-semibold">{displayName(item.track_name)}</td>
                      <td className="py-3 font-sans text-[12px] text-muted-foreground">{displayName(item.source_album)}</td>
                      <td className="py-3 text-right font-sans text-[12px] tabular-nums">{formatNumber(item.play_count)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </GlassCard>
          </div>
        )}
      </div>
    </div>
  )
}
