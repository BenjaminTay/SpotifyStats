/** 探索与品味 */

import { Compass } from 'lucide-react'
import { Link } from 'react-router-dom'
import { displayName, useChineseTextVersion } from '@/lib/chinese'
import type { PlaybackDiscoveryRecords, PlaybackRecordRow } from '@/types/analysis'
import { EntityRecordCard, RecordCard, MiniRankTable, RankNum, TrackCell, ArtistCell, AlbumCell, SectionHeader, ValueBar } from './PlaybackRecordsPrimitives'

interface Props { data: PlaybackDiscoveryRecords }

function SameNameArtistVersions({ row }: { row: PlaybackRecordRow }) {
  useChineseTextVersion()
  const names = row.artist_names?.length
    ? row.artist_names
    : (row.caption?.split('、').filter(Boolean) ?? [])
  return (
    <div className="mobile-record-same-name-versions flex min-w-0 flex-wrap gap-2 py-1">
      {names.map((name, index) => {
        const coverUrl = row.artist_cover_urls?.[index]
        const plays = row.artist_play_counts?.[index]
        return (
          <Link key={`${name}-${index}`} to={`/music/artists/${encodeURIComponent(name)}`} className="inline-flex max-w-full items-center gap-2 rounded-full border border-border/70 bg-muted/20 py-1 pr-2.5 pl-1 transition-colors hover:bg-muted/50">
            <span aria-hidden="true" className="relative flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded-full border border-accent-foreground/20 bg-accent-foreground/10 font-serif text-[11px] font-semibold text-accent-foreground">
              {displayName(name).slice(0, 1).toUpperCase()}
              {coverUrl && (
                <img
                  src={coverUrl}
                  alt=""
                  className="absolute inset-0 h-full w-full object-cover"
                  loading="lazy"
                  decoding="async"
                  onError={(event) => { event.currentTarget.style.display = 'none' }}
                />
              )}
            </span>
            <span className="font-sans text-[12px] font-medium leading-tight break-words">{displayName(name)}</span>
            {plays != null && <span className="shrink-0 rounded-full bg-background/80 px-1.5 py-0.5 font-sans text-[10px] font-semibold tabular-nums text-muted-foreground">{plays.toLocaleString('zh-CN')} 次</span>}
          </Link>
        )
      })}
    </div>
  )
}

export function DiscoverySection({ data }: Props) {
  useChineseTextVersion()
  const featTrackRows = data.feat_lover?.track ?? []
  const featSummaryRow = featTrackRows.find((row) =>
    row.rank === 0 || row.name === '合作曲播放佔比' || row.name === '合作曲播放占比',
  )
  const featTrackRankRows = featSummaryRow
    ? featTrackRows.filter((row) => row !== featSummaryRow)
    : featTrackRows
  const featArtistRows = data.feat_lover?.artist ?? []
  const featAlbumRows = data.feat_lover?.album ?? []
  const discoveryRows = data.discovery_day ?? { track: [], album: [], artist: [] }

  return (
    <div>
      <SectionHeader icon={Compass} title="探索与品味" subtitle="从新发现、完整专辑、合作歌曲与同名作品中，看见你的聆听广度。" />
      <EntityRecordCard title="发现日 · Discovery Day" subtitle="单日首次播放的新歌曲/专辑/艺人数量最多的日期"
        recordsByEntity={{ track: data.discovery_day?.track ?? [], album: data.discovery_day?.album ?? [], artist: data.discovery_day?.artist ?? [] }}
        mobileRowClassName="mobile-record-discovery-row"
        columns={(entity) => {
          const rows = discoveryRows[entity] ?? []
          const max = Math.max(0, ...rows.map((row) => row.value))
          return [
          { header: '#', width: '48px', align: 'center', render: (_, i) => <RankNum rank={i + 1} /> },
          { header: '日期', mobileRole: 'entity', render: (row) => <span className="mobile-record-discovery-date font-sans text-[14px] font-medium tabular-nums">{displayName(row.name)}</span> },
          { header: '新发现', width: '170px', align: 'right', mobileRole: 'primary', render: (row) => <ValueBar value={row.value} max={max} suffix={displayName(row.unit)} label={`${displayName(row.name)}新发现数量`} /> },
          ]
        }} />
      <EntityRecordCard title="专辑全碟回放 · Full Album Replays" subtitle="仅统计曲目总数可靠且已听完全部曲目的专辑；完整回放次数取各曲目播放次数的最小值"
        recordsByEntity={{ album: data.album_completionist?.album ?? [] }} defaultEntity="album"
        columns={() => [
          { header: '#', width: '48px', align: 'center', render: (_, i) => <RankNum rank={i + 1} /> },
          { header: '专辑', mobileRole: 'entity', render: (row) => <AlbumCell name={row.name} artistName={row.artist_name} coverUrl={row.cover_url} /> },
          { header: '完整回放', width: '130px', align: 'right', mobileRole: 'primary', render: (row) => <span className="font-serif text-[20px] font-semibold tabular-nums">{row.value}<span className="ml-1 font-sans text-[12px] font-normal text-muted-foreground">{displayName(row.unit)}</span></span> },
          { header: '曲目覆盖', width: '110px', align: 'right', mobileRole: 'fact', render: (row) => <span className="font-sans text-[12px] text-muted-foreground">{row.secondary_value}{displayName(row.secondary_unit ?? '')}</span> },
          { header: '总播放', width: '100px', align: 'right', mobileRole: 'fact', render: (row) => <span className="font-sans text-[12px] text-muted-foreground">{row.total_plays ?? '—'} 次</span> },
        ]} />
      <EntityRecordCard title="合作曲排行 · Feat Ranking" subtitle="合作歌曲与常出现的合作艺人排行"
          headerExtra={featSummaryRow ? (
            <div aria-label="合作曲播放摘要" className="flex max-w-full flex-wrap items-center gap-x-3 gap-y-1 rounded-[8px] border border-accent-foreground/20 bg-accent-foreground/[0.05] px-3 py-1.5 font-sans text-[10px] text-muted-foreground">
              <span>播放次数 <strong className="ml-1 font-serif text-[15px] font-semibold tabular-nums text-foreground">{Number(featSummaryRow.secondary_value ?? 0).toLocaleString('zh-CN')}</strong></span>
              <span className="hidden h-4 w-px bg-border sm:block" aria-hidden="true" />
              <span>占全部有效播放 <strong className="ml-1 font-serif text-[15px] font-semibold tabular-nums text-accent-foreground">{featSummaryRow.value}%</strong></span>
            </div>
          ) : undefined}
          recordsByEntity={{ track: featTrackRankRows, album: featAlbumRows, artist: featArtistRows }} defaultEntity="track"
          columns={(entity) => {
            const rows = entity === 'track' ? featTrackRankRows : entity === 'album' ? featAlbumRows : featArtistRows
            const max = Math.max(0, ...rows.map((row) => row.value))
            return [
            { header: '#', width: '48px', align: 'center', render: (_, i) => <RankNum rank={i + 1} /> },
            entity === 'track'
              ? { header: '歌曲', mobileRole: 'entity' as const, render: (row: PlaybackRecordRow) => <TrackCell trackId={row.entity_id} name={row.name} artistName={row.artist_name} coverUrl={row.cover_url} /> }
              : entity === 'album'
                ? { header: '专辑', mobileRole: 'entity' as const, render: (row: PlaybackRecordRow) => <AlbumCell name={row.name} artistName={row.artist_name} coverUrl={row.cover_url} /> }
                : { header: '艺人', mobileRole: 'entity' as const, render: (row: PlaybackRecordRow) => <ArtistCell name={row.name} coverUrl={row.cover_url} /> },
            { header: '播放次数', width: '156px', align: 'right', mobileRole: 'primary' as const, render: (row) => <ValueBar value={row.value} max={max} suffix="次" label={`${displayName(row.name)}合作曲播放次数`} /> },
            ]
          }} />
      <RecordCard title="同名异曲 · Same Name, Different Artist" subtitle="以歌名为索引，对照你听过的所有不同艺人版本">
          <MiniRankTable
            rows={data.same_name_diff_artist}
            mobileRenderRow={(row, index) => (
              <article className="mobile-record-same-name-row">
                <div className="mobile-record-rank-number"><RankNum rank={index + 1} /></div>
                <div className="mobile-record-same-name-title">{displayName(row.name)}</div>
                <SameNameArtistVersions row={row} />
              </article>
            )}
            columns={[
            { header: '歌名', width: '24%', verticalAlign: 'middle', mobileRole: 'entity', render: (row) => (
              <div className="min-w-0 pr-3 font-serif text-[17px] font-semibold leading-snug break-words">{displayName(row.name)}</div>
            ) },
            { header: '艺人版本', verticalAlign: 'middle', mobileRole: 'fact', render: (row) => <SameNameArtistVersions row={row} /> },
          ]} />
      </RecordCard>
    </div>
  )
}
