import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react'
import type { ArtistAlbumEntry, ArtistInfo } from '@/types/billboard'
import { CoverCell } from '@/components/shared/CoverCell'
import { GlassCard } from '@/components/shared/GlassCard'
import { displayName } from '@/lib/chinese'
import { MobileRankList } from '@/components/mobile'
import { useViewportMode } from '@/hooks/useViewportMode'
import {
  KpiStrip,
  PlaysCell,
  formatDateShort,
  formatNumber,
} from './MusicDetailPrimitives'

const PAGE_SIZE = 50

export function ArtistAlbumsSection({
  artistName,
  info,
  albums,
}: {
  artistName: string
  info: ArtistInfo
  albums: ArtistAlbumEntry[]
}) {
  const isPhone = useViewportMode() === 'phone'
  const pageSize = isPhone ? 20 : PAGE_SIZE
  const [pageState, setPageState] = useState({ source: albums, page: 1 })
  const page = pageState.source === albums ? pageState.page : 1
  const setPage = (next: number | ((page: number) => number)) => {
    setPageState((current) => {
      const currentPage = current.source === albums ? current.page : 1
      return { source: albums, page: typeof next === 'function' ? next(currentPage) : next }
    })
  }
  const totalPages = Math.max(1, Math.ceil(albums.length / pageSize))
  const safePage = Math.min(page, totalPages)
  const top5Albums = albums.filter((album) => album.peak <= 5).length
  const top10Albums = albums.filter((album) => album.peak <= 10).length

  const paged = albums.slice((safePage - 1) * pageSize, safePage * pageSize)
  if (isPhone) {
    return (
      <div className="mobile-detail-entity-section">
        <KpiStrip
          compactFive
          items={[
            { label: '入榜专辑', value: formatNumber(albums.length) },
            { label: 'No.1专辑', value: formatNumber(info.num_no1_albums), accent: info.num_no1_albums > 0 },
            { label: 'Top5专辑', value: formatNumber(top5Albums) },
            { label: 'Top10专辑', value: formatNumber(top10Albums) },
            { label: '冠军周数', value: formatNumber(info.album_no1_weeks), accent: info.album_no1_weeks > 0 },
          ]}
        />
        <MobileRankList
          title="专辑成绩"
          eyebrow="Albums / Chart"
          rows={paged.map((album) => ({
            entityType: 'album' as const,
            title: displayName(album.album_name),
            subtitle: displayName(artistName),
            rank: album.power_rank ?? undefined,
            coverUrl: album.cover_url,
            metric: `${album.peak}`,
            metricLabel: 'Peak',
            metricRank: album.peak,
            facts: [
              { label: '在榜', value: `${album.weeks}周` },
              { label: '峰值', value: `${album.pk_wks}周` },
            ],
            badges: [`${formatNumber(album.total_plays)} 次上榜播放`],
            to: `/music/albums/${encodeURIComponent(album.album_name)}?artist=${encodeURIComponent(artistName)}`,
          }))}
          page={safePage}
          pageCount={totalPages}
          onPageChange={totalPages > 1 ? (nextPage) => setPage(nextPage) : undefined}
        />
      </div>
    )
  }

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
                return paged.map((album, index) => (
                  <tr key={album.album_name} className="transition-colors hover:bg-muted/50">
                    <td className="py-3.5 pr-2">
                      <CoverCell index={index} coverUrl={album.cover_url} label={displayName(album.album_name)} />
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
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-border px-7 py-3">
              <span className="font-sans text-[12px] text-muted-foreground tabular-nums">
                显示 {(safePage - 1) * pageSize + 1}-{Math.min(safePage * pageSize, albums.length)} / 总数 {albums.length} 条
              </span>
              <div className="flex items-center gap-1">
                <span className="mr-2 font-sans text-[12px] text-muted-foreground tabular-nums">
                  {safePage} / {totalPages}
                </span>
                <button
                  onClick={() => setPage(1)}
                  disabled={safePage <= 1}
                  aria-label="第一页"
                  className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
                >
                  <ChevronsLeft className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={safePage <= 1}
                  aria-label="上一页"
                  className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={safePage >= totalPages}
                  aria-label="下一页"
                  className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setPage(totalPages)}
                  disabled={safePage >= totalPages}
                  aria-label="最后一页"
                  className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
                >
                  <ChevronsRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
        </GlassCard>
      ) : (
        <p className="py-12 text-center font-sans text-[13px] text-muted-foreground">
          暂无专辑入榜数据
        </p>
      )}
    </div>
  )
}
