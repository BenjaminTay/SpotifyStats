import { Link } from 'react-router-dom'
import type { ArtistAlbumEntry, ArtistInfo } from '@/types/billboard'
import { CoverCell } from '@/components/shared/CoverCell'
import { GlassCard } from '@/components/shared/GlassCard'
import { displayName } from '@/lib/chinese'
import {
  KpiStrip,
  PlaysCell,
  formatDateShort,
  formatNumber,
} from './MusicDetailPrimitives'

export function ArtistAlbumsSection({
  artistName,
  info,
  albums,
}: {
  artistName: string
  info: ArtistInfo
  albums: ArtistAlbumEntry[]
}) {
  return (
    <div className="mb-8">
      <KpiStrip
        items={[
          {
            label: '#1 专辑',
            value: formatNumber(info.num_no1_albums),
            accent: info.num_no1_albums > 0,
          },
          {
            label: '冠军周数',
            value: formatNumber(info.album_no1_weeks),
            accent: info.album_no1_weeks > 0,
          },
          { label: '入榜专辑', value: formatNumber(albums.length) },
        ]}
      />

      {albums.length > 0 ? (
        <GlassCard className="overflow-hidden p-0">
          <table className="mx-7 my-0 w-[calc(100%-56px)] border-collapse">
            <thead>
              <tr>
                <th className="w-[44px] pb-3.5 pt-4 font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground" />
                <th className="pb-3.5 pt-4 text-left font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                  专辑
                </th>
                <th className="w-16 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                  峰值
                </th>
                <th className="w-14 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                  峰位周
                </th>
                <th className="w-14 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                  在榜
                </th>
                <th className="w-28 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                  总播放
                </th>
                <th className="w-[72px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                  走势点数
                </th>
                <th className="w-[60px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                  走势
                </th>
                <th className="w-[78px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                  首周
                </th>
                <th className="w-[78px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                  首次达峰
                </th>
                <th className="w-[78px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                  末周
                </th>
              </tr>
            </thead>
            <tbody>
              {(() => {
                const maxPlays = Math.max(...albums.map((album) => album.total_plays), 1)
                return albums.map((album, index) => (
                  <tr key={album.album_name} className="transition-colors hover:bg-muted/50">
                    <td className="py-3.5 pr-2">
                      <CoverCell index={index} coverUrl={album.cover_url} />
                    </td>
                    <td className="py-3.5 pl-1">
                      <Link
                        to={`/music/albums/${encodeURIComponent(album.album_name)}?artist=${encodeURIComponent(artistName)}`}
                        className="font-sans text-sm font-semibold leading-snug transition-colors hover:text-accent-foreground"
                      >
                        {displayName(album.album_name)}
                      </Link>
                      <div className="mt-0.5 font-sans text-[12px] italic text-muted-foreground">
                        {displayName(artistName)}
                      </div>
                    </td>
                    <td
                      className="py-3.5 text-right font-serif text-[22px] font-bold italic"
                      style={{ color: album.peak === 1 ? 'var(--accent-foreground)' : undefined }}
                    >
                      {album.peak}
                    </td>
                    <td className="py-3.5 text-right font-sans text-[13px] text-muted-foreground">
                      {album.pk_wks}
                    </td>
                    <td className="py-3.5 text-right font-sans text-[13px] text-muted-foreground">
                      {album.weeks}
                    </td>
                    <td className="py-3.5 text-right">
                      <PlaysCell plays={album.total_plays} maxPlays={maxPlays} />
                    </td>
                    <td className="py-3.5 text-right font-sans text-[13px] tabular-nums">
                      {album.power_score > 0 ? formatNumber(album.power_score) : '—'}
                    </td>
                    <td className="py-3.5 text-right font-serif text-[22px] italic text-muted-foreground">
                      {album.power_rank ?? '—'}
                    </td>
                    <td className="py-3.5 text-right">
                      <Link
                        to={`/billboard?week=${album.first_week}`}
                        className="font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                      >
                        {formatDateShort(album.first_week)}
                      </Link>
                    </td>
                    <td className="py-3.5 text-right">
                      <Link
                        to={`/billboard?week=${album.first_peak_week}`}
                        className="font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                      >
                        {formatDateShort(album.first_peak_week)}
                      </Link>
                    </td>
                    <td className="py-3.5 text-right">
                      <Link
                        to={`/billboard?week=${album.last_week}`}
                        className="font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                      >
                        {formatDateShort(album.last_week)}
                      </Link>
                    </td>
                  </tr>
                ))
              })()}
            </tbody>
          </table>
        </GlassCard>
      ) : (
        <p className="py-12 text-center font-sans text-[13px] text-muted-foreground">
          暂无专辑入榜数据
        </p>
      )}
    </div>
  )
}
