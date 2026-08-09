import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { Trophy } from 'lucide-react'

import { cn } from '@/lib/utils'
import { displayName } from '@/lib/chinese'
import { billboardDetailLink } from '@/lib/navigation'
import type {
  BillboardRecords,
  BlockedAlbumInfo,
  BlockedArtistInfo,
  BlockedTrackInfo,
  BlockerKingAlbumRecord,
  BlockerKingArtistRecord,
  BlockerKingRecord,
  ClimbToNo1AlbumRecord,
  ClimbToNo1ArtistRecord,
  ClimbToNo1Record,
  DebutNo1AlbumRecord,
  DebutNo1Record,
  ReturnToNo1AlbumRecord,
  ReturnToNo1ArtistRecord,
  ReturnToNo1Record,
  SelfReplacementAlbumRecord,
  SelfReplacementRecord,
} from '@/types/billboard'
import type { CoverMaps } from './recordsData'
import {
  AlbumCell,
  ArtistCell,
  FeaturedRecord,
  MiniRankTable,
  RankNum,
  RecordCard,
  SectionHeader,
  TrackAlbumToggle,
  TrackCell,
  ValueBar,
  WeekLink,
  type EntityType,
} from './RecordsPrimitives'

export function ChampionshipSection({ rec, covers }: { rec: BillboardRecords; covers: CoverMaps }) {
  const [no1Type, setNo1Type] = useState<EntityType>('track')
  const [debutType, setDebutType] = useState<EntityType>('track')
  const [returnType, setReturnType] = useState<EntityType>('track')
  const [replaceType, setReplaceType] = useState<EntityType>('track')
  const [blockerType, setBlockerType] = useState<EntityType>('track')
  const [climbType, setClimbType] = useState<EntityType>('track')

  const blockerKingSorted = useMemo(() => {
    return [...(rec.blocker_king as BlockerKingRecord[])].sort((a, b) => {
      if (b['阻挡数'] !== a['阻挡数']) return b['阻挡数'] - a['阻挡数']
      return (b['走势评分'] ?? 0) - (a['走势评分'] ?? 0)
    })
  }, [rec.blocker_king])

  const blockerKingAlbumSorted = useMemo(() => {
    return [...(rec.blocker_king_album as BlockerKingAlbumRecord[])].sort((a, b) => {
      if (b['阻挡数'] !== a['阻挡数']) return b['阻挡数'] - a['阻挡数']
      return (b['走势评分'] ?? 0) - (a['走势评分'] ?? 0)
    })
  }, [rec.blocker_king_album])

  const blockerKingArtistSorted = useMemo(() => {
    return [...(rec.blocker_king_artist as BlockerKingArtistRecord[])].sort((a, b) => {
      if (b['阻挡数'] !== a['阻挡数']) return b['阻挡数'] - a['阻挡数']
      return (b['走势评分'] ?? 0) - (a['走势评分'] ?? 0)
    })
  }, [rec.blocker_king_artist])

  type DebutSortMode = 'date' | 'no1weeks' | 'chartweeks'
  const [debutSort, setDebutSort] = useState<{ mode: DebutSortMode; desc: boolean }>({ mode: 'date', desc: true })

  const handleDebutSort = (mode: DebutSortMode) => {
    setDebutSort(prev => prev.mode === mode ? { mode, desc: !prev.desc } : { mode, desc: true })
  }

  const debutTrackSorted = useMemo(() => {
    const rows = [...(rec.debut_no1 as DebutNo1Record[])]
    return rows.sort((a, b) => {
      let cmp = 0
      if (debutSort.mode === 'date') cmp = a.first_week.localeCompare(b.first_week)
      else if (debutSort.mode === 'no1weeks') cmp = (a.weeks_at_no1 ?? 0) - (b.weeks_at_no1 ?? 0)
      else cmp = a.weeks_on_chart - b.weeks_on_chart
      return debutSort.desc ? -cmp : cmp
    })
  }, [rec.debut_no1, debutSort])

  const debutAlbumSorted = useMemo(() => {
    const rows = [...(rec.debut_no1_album as DebutNo1AlbumRecord[])]
    return rows.sort((a, b) => {
      let cmp = 0
      if (debutSort.mode === 'date') cmp = a.first_week.localeCompare(b.first_week)
      else if (debutSort.mode === 'no1weeks') cmp = (a.weeks_at_no1 ?? 0) - (b.weeks_at_no1 ?? 0)
      else cmp = a.weeks_on_chart - b.weeks_on_chart
      return debutSort.desc ? -cmp : cmp
    })
  }, [rec.debut_no1_album, debutSort])

  // 冠单名人堂 toggle: sort by 冠单数 or 冠军专辑数
  const no1Sorted = useMemo(() => {
    if (no1Type === 'album') return [...rec.artist_most_no1].sort((a, b) => (b['冠军专辑数'] ?? 0) - (a['冠军专辑数'] ?? 0))
    return rec.artist_most_no1
  }, [no1Type, rec.artist_most_no1])

  const no1MaxSongs = rec.artist_most_no1[0]?.['冠单数'] ?? 1
  const no1MaxAlbums = Math.max(...rec.artist_most_no1.map(r => r['冠军专辑数'] ?? 0), 1)
  const no1MaxSongWeeks = Math.max(...rec.artist_most_no1.map(r => r['单曲冠军周数'] ?? 0), 1)
  const no1MaxAlbumWeeks = Math.max(...rec.artist_most_no1.map(r => r['专辑冠军周数'] ?? 0), 1)
  const debutTrackMaxNo1Weeks = Math.max(...debutTrackSorted.map(r => r.weeks_at_no1 ?? 0), 1)
  const debutAlbumMaxNo1Weeks = Math.max(...debutAlbumSorted.map(r => r.weeks_at_no1 ?? 0), 1)

  return (
    <div>
      <SectionHeader icon={Trophy} title="冠军圣殿" subtitle="关于 #1 的一切——最罕见、最有分量的荣誉" />

      {/* 冠军名人堂 */}
      <RecordCard title="冠军名人堂" toggle={<TrackAlbumToggle value={no1Type} onChange={setNo1Type} />}>
        {no1Sorted.length > 0 && (
          <div className="mobile-record-podium mb-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
            {no1Sorted.slice(0, 3).map((r, i) => (
              <FeaturedRecord key={r.artist_name}
                label={['冠军之王', '亚军', '季军'][i]}
                value={no1Type === 'album' ? (r['冠军专辑数'] ?? 0) : r['冠单数']}
                unit={no1Type === 'album' ? '张冠军专辑' : '首冠军单曲'}
                caption={`${r.artist_name} · 冠周 ${no1Type === 'album' ? r['专辑冠军周数'] : r['单曲冠军周数']}`}
                coverUrl={covers.artist.get(r.artist_name)}
                linkTo={billboardDetailLink(`/music/artists/${encodeURIComponent(r.artist_name)}`)}
              />
            ))}
          </div>
        )}
        <MiniRankTable rows={no1Sorted} mobileSkip={3} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '艺人', render: (r) => <ArtistCell artistName={r.artist_name} coverUrl={covers.artist.get(r.artist_name)} /> },
          ...(no1Type === 'album'
            ? [
              { header: '冠军专辑', width: '140px', align: 'right' as const, mobileRole: 'primary' as const, render: (r: typeof rec.artist_most_no1[number]) => <ValueBar value={r['冠军专辑数'] ?? 0} max={no1MaxAlbums} suffix="张" /> },
              { header: '专辑冠周', width: '145px', align: 'right' as const, mobileRole: 'secondary' as const, render: (r: typeof rec.artist_most_no1[number]) => <ValueBar value={r['专辑冠军周数'] ?? 0} max={no1MaxAlbumWeeks} suffix="周" /> },
            ]
            : [
              { header: '冠军单曲', width: '140px', align: 'right' as const, mobileRole: 'primary' as const, render: (r: typeof rec.artist_most_no1[number]) => <ValueBar value={r['冠单数']} max={no1MaxSongs} suffix="首" /> },
              { header: '单曲冠周', width: '145px', align: 'right' as const, mobileRole: 'secondary' as const, render: (r: typeof rec.artist_most_no1[number]) => <ValueBar value={r['单曲冠军周数']} max={no1MaxSongWeeks} suffix="周" /> },
            ]
          ),
        ]} />
      </RecordCard>

      {/* 空降冠军 */}
      <RecordCard title="空降冠军 · Debut at #1" subtitle="入榜即夺冠" toggle={<TrackAlbumToggle value={debutType} onChange={setDebutType} />}>
        <div className="mb-3 flex items-center gap-2">
          <span className="font-sans text-[10px] text-muted-foreground">排序：</span>
          <div className="flex items-center rounded-[6px] border border-border bg-muted/30 p-0.5">
            {([
              { key: 'date', label: '空降日期' },
              { key: 'no1weeks', label: '冠军周数' },
              { key: 'chartweeks', label: '在榜周数' },
            ] as { key: DebutSortMode; label: string }[]).map((opt) => {
              const active = debutSort.mode === opt.key
              const arrow = active ? (debutSort.desc ? ' ↓' : ' ↑') : ''
              return (
                <button key={opt.key} onClick={() => handleDebutSort(opt.key)}
                  className={cn('rounded-[4px] px-2.5 py-1 font-sans text-[11px] font-medium transition-colors', active ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')}>
                  {opt.label}{arrow}
                </button>
              )
            })}
          </div>
        </div>
        {debutType === 'track' ? (
          <MiniRankTable rows={debutTrackSorted} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} artistNames={r.artist_names} coverUrl={covers.track.get(r.track_id)} /> },
            { header: '空降日期', width: '110px', render: (r) => <WeekLink date={r.first_week} /> },
            { header: '冠军周数', width: '105px', align: 'right', render: (r) => r.weeks_at_no1 > 0 ? <ValueBar value={r.weeks_at_no1} max={debutTrackMaxNo1Weeks} suffix="周" /> : <span className="text-muted-foreground">—</span> },
            { header: '在榜', width: '140px', align: 'right', render: (r) => <ValueBar value={r.weeks_on_chart} max={debutTrackSorted[0]?.weeks_on_chart ?? 1} suffix="周" /> },
          ]} />
        ) : (
          <MiniRankTable rows={debutAlbumSorted} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '专辑', render: (r) => <AlbumCell albumName={r.album_name} artistName={r.artist_name} coverUrl={covers.album.get(r.album_name)} /> },
            { header: '空降日期', width: '110px', render: (r) => <WeekLink date={r.first_week} /> },
            { header: '冠军周数', width: '105px', align: 'right', render: (r) => r.weeks_at_no1 > 0 ? <ValueBar value={r.weeks_at_no1} max={debutAlbumMaxNo1Weeks} suffix="周" /> : <span className="text-muted-foreground">—</span> },
            { header: '在榜', width: '140px', align: 'right', render: (r) => <ValueBar value={r.weeks_on_chart} max={debutAlbumSorted[0]?.weeks_on_chart ?? 1} suffix="周" /> },
          ]} />
        )}
      </RecordCard>

      {/* 回归冠军 */}
      <RecordCard title="回归冠军 · Return to #1" subtitle="离开冠军位后又重新登顶" toggle={<TrackAlbumToggle value={returnType} onChange={setReturnType} showArtist />}>
        {returnType === 'track' ? (
          <MiniRankTable rows={rec.return_to_no1 as ReturnToNo1Record[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} artistNames={r.artist_names} coverUrl={covers.track.get(r.track_id)} /> },
            { header: '首次夺冠', width: '105px', mobileRole: 'fact', render: (r) => <WeekLink date={r['首次冠单']} /> },
            { header: '回冠周', width: '105px', mobileRole: 'fact', render: (r) => <WeekLink date={r['回冠日期']} /> },
            { header: '间隔', width: '140px', align: 'right', mobileRole: 'primary', render: (r) => <ValueBar value={r['间隔周数']} max={(rec.return_to_no1 as ReturnToNo1Record[])[0]?.['间隔周数'] ?? 1} suffix="周" /> },
          ]} />
        ) : returnType === 'album' ? (
          <MiniRankTable rows={rec.return_to_no1_album as ReturnToNo1AlbumRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '专辑', render: (r) => <AlbumCell albumName={r.album_name} artistName={r.artist_name} coverUrl={covers.album.get(r.album_name)} /> },
            { header: '首次夺冠', width: '105px', mobileRole: 'fact', render: (r) => <WeekLink date={r['首次冠专']} /> },
            { header: '回冠周', width: '105px', mobileRole: 'fact', render: (r) => <WeekLink date={r['回冠日期']} /> },
            { header: '间隔', width: '140px', align: 'right', mobileRole: 'primary', render: (r) => <ValueBar value={r['间隔周数']} max={(rec.return_to_no1_album as ReturnToNo1AlbumRecord[])[0]?.['间隔周数'] ?? 1} suffix="周" /> },
          ]} />
        ) : (
          <MiniRankTable rows={rec.return_to_no1_artist as ReturnToNo1ArtistRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '艺人', render: (r) => <ArtistCell artistName={r.artist_name} coverUrl={covers.artist.get(r.artist_name)} compact /> },
            { header: '首次夺冠', width: '105px', mobileRole: 'fact', render: (r) => <WeekLink date={r['首次夺艺冠']} /> },
            { header: '回冠周', width: '105px', mobileRole: 'fact', render: (r) => <WeekLink date={r['回冠日期']} /> },
            { header: '间隔', width: '140px', align: 'right', mobileRole: 'primary', render: (r) => <ValueBar value={r['间隔周数']} max={(rec.return_to_no1_artist as ReturnToNo1ArtistRecord[])[0]?.['间隔周数'] ?? 1} suffix="周" /> },
          ]} />
        )}
      </RecordCard>

      {/* 冠军传承 */}
      <RecordCard title="冠军传承 · Self-Replacement" subtitle="连续两周不同作品接力夺冠" mobileSubtitle="连续两周由不同作品接力夺冠" toggle={<TrackAlbumToggle value={replaceType} onChange={setReplaceType} />}>
        {replaceType === 'track' ? (
          <MiniRankTable rows={rec.self_replacement_no1 as SelfReplacementRecord[]} mobileRowClassName="mobile-record-replacement-row" columns={[
            { header: '榜单周', width: '105px', render: (r) => <WeekLink date={r['周次']} /> },
            { header: '艺人', render: (r) => <ArtistCell artistName={r['艺人']} coverUrl={covers.artist.get(r['艺人'])} /> },
            { header: '前冠单', render: (r) => <TrackCell trackId={r['前冠单_id']} trackName={r['前冠单']} coverUrl={covers.track.get(r['前冠单_id'])} /> },
            { header: '', width: '32px', align: 'center', render: () => <span className="text-muted-foreground">→</span> },
            { header: '新冠单', render: (r) => <TrackCell trackId={r['新冠单_id']} trackName={r['新冠单']} coverUrl={covers.track.get(r['新冠单_id'])} /> },
          ]} />
        ) : (
          <MiniRankTable rows={rec.self_replacement_no1_album as SelfReplacementAlbumRecord[]} mobileRowClassName="mobile-record-replacement-row" columns={[
            { header: '榜单周', width: '105px', render: (r) => <WeekLink date={r['周次']} /> },
            { header: '艺人', render: (r) => <ArtistCell artistName={r['艺人']} coverUrl={covers.artist.get(r['艺人'])} /> },
            { header: '前冠专', render: (r) => <AlbumCell albumName={r['前冠专']} artistName={r['艺人']} coverUrl={covers.album.get(r['前冠专'])} /> },
            { header: '', width: '32px', align: 'center', render: () => <span className="text-muted-foreground">→</span> },
            { header: '新冠专', render: (r) => <AlbumCell albumName={r['新冠专']} artistName={r['艺人']} coverUrl={covers.album.get(r['新冠专'])} /> },
          ]} />
        )}
      </RecordCard>

      {/* 阻挡王 */}
      <RecordCard title="阻挡王 · Blocker King" subtitle="在 #1 期间阻挡最多 Peak #2 作品" mobileSubtitle="夺冠期间阻挡最多亚军作品" toggle={<TrackAlbumToggle value={blockerType} onChange={setBlockerType} showArtist />}>
        {blockerType === 'track' ? (
          <>
            {blockerKingSorted.length > 0 && (
              <div className="mobile-record-blocker-featured mb-4">
                <FeaturedRecord label="最强阻挡" value={blockerKingSorted[0]['阻挡数']} unit="首 Peak #2 歌曲被挡" caption={`${blockerKingSorted[0].track_name} — ${blockerKingSorted[0].artist_name}`} coverUrl={covers.track.get(blockerKingSorted[0].track_id)} linkTo={billboardDetailLink(`/music/tracks/${blockerKingSorted[0].track_id}`)} />
              </div>
            )}
            <MiniRankTable fixed rows={blockerKingSorted} mobilePreviewCount={4} columns={[
              { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
              { header: '歌曲', width: '280px', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} artistNames={r.artist_names} coverUrl={covers.track.get(r.track_id)} /> },
              { header: '阻挡数', width: '130px', align: 'right', render: (r) => <ValueBar value={r['阻挡数']} max={blockerKingSorted[0]?.['阻挡数'] ?? 1} /> },
              { header: <span className="pl-8">被阻挡歌曲</span>, render: (r) => {
                const blocked: BlockedTrackInfo[] = rec.blocked_tracks_map?.[r.track_id] ?? []
                if (blocked.length === 0) return <span className="text-[11px] text-muted-foreground">—</span>
                return <div className="flex flex-wrap gap-1 pl-8">{blocked.map(b => <Link key={b.track_id} to={billboardDetailLink(`/music/tracks/${b.track_id}`)} className="inline-flex items-center gap-1 rounded-[4px] bg-muted/50 px-1.5 py-0.5 font-sans text-[11px] transition-colors hover:bg-muted hover:text-accent-foreground">{displayName(b.track_name)}</Link>)}</div>
              }},
            ]} />
          </>
        ) : blockerType === 'album' ? (
          <>
            {blockerKingAlbumSorted.length > 0 && (
              <div className="mobile-record-blocker-featured mb-4">
                <FeaturedRecord label="最强阻挡" value={blockerKingAlbumSorted[0]['阻挡数']} unit="张 Peak #2 专辑被挡" caption={`${blockerKingAlbumSorted[0].album_name} — ${blockerKingAlbumSorted[0].artist_name}`} coverUrl={covers.album.get(blockerKingAlbumSorted[0].album_name)} linkTo={billboardDetailLink(`/music/albums/${encodeURIComponent(blockerKingAlbumSorted[0].album_name)}?artist=${encodeURIComponent(blockerKingAlbumSorted[0].artist_name)}`)} />
              </div>
            )}
            <MiniRankTable fixed rows={blockerKingAlbumSorted} mobilePreviewCount={4} columns={[
              { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
              { header: '专辑', width: '280px', render: (r) => <AlbumCell albumName={r.album_name} artistName={r.artist_name} coverUrl={covers.album.get(r.album_name)} /> },
              { header: '阻挡数', width: '130px', align: 'right', render: (r) => <ValueBar value={r['阻挡数']} max={blockerKingAlbumSorted[0]?.['阻挡数'] ?? 1} /> },
              { header: <span className="pl-8">被阻挡专辑</span>, render: (r) => {
                const key = `${r.album_name}||${r.artist_name}`
                const blocked: BlockedAlbumInfo[] = rec.blocked_albums_map?.[key] ?? []
                if (blocked.length === 0) return <span className="text-[11px] text-muted-foreground">—</span>
                return <div className="flex flex-wrap gap-1 pl-8">{blocked.map((b, i) => <Link key={i} to={billboardDetailLink(`/music/albums/${encodeURIComponent(b.album_name)}`)} className="inline-flex items-center gap-1 rounded-[4px] bg-muted/50 px-1.5 py-0.5 font-sans text-[11px] transition-colors hover:bg-muted hover:text-accent-foreground">{displayName(b.album_name)}</Link>)}</div>
              }},
            ]} />
          </>
        ) : (
          <>
            {blockerKingArtistSorted.length > 0 && (
              <div className="mobile-record-blocker-featured mb-4">
                <FeaturedRecord label="最强阻挡" value={blockerKingArtistSorted[0]['阻挡数']} unit="位 Peak #2 艺人被挡" caption={`${blockerKingArtistSorted[0].artist_name}`} coverUrl={covers.artist.get(blockerKingArtistSorted[0].artist_name)} coverRound linkTo={billboardDetailLink(`/music/artists/${encodeURIComponent(blockerKingArtistSorted[0].artist_name)}`)} />
              </div>
            )}
            <MiniRankTable fixed rows={blockerKingArtistSorted} mobilePreviewCount={4} columns={[
              { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
              { header: '艺人', width: '280px', render: (r) => <ArtistCell artistName={r.artist_name} coverUrl={covers.artist.get(r.artist_name)} compact /> },
              { header: '阻挡数', width: '130px', align: 'right', render: (r) => <ValueBar value={r['阻挡数']} max={blockerKingArtistSorted[0]?.['阻挡数'] ?? 1} /> },
              { header: <span className="pl-8">被阻挡艺人</span>, render: (r) => {
                const blocked: BlockedArtistInfo[] = rec.blocked_artists_map?.[r.artist_name] ?? []
                if (blocked.length === 0) return <span className="text-[11px] text-muted-foreground">—</span>
                return <div className="flex flex-wrap gap-1 pl-8">{blocked.map((b, i) => <Link key={i} to={billboardDetailLink(`/music/artists/${encodeURIComponent(b.artist_name)}`)} className="inline-flex items-center gap-1 rounded-[4px] bg-muted/50 px-1.5 py-0.5 font-sans text-[11px] transition-colors hover:bg-muted hover:text-accent-foreground">{displayName(b.artist_name)}</Link>)}</div>
              }},
            ]} />
          </>
        )}
      </RecordCard>

      <RecordCard title="最长登顶路 · Longest Climb to #1" subtitle="首次上榜到首次夺冠之间实际在榜周数" toggle={<TrackAlbumToggle value={climbType} onChange={setClimbType} showArtist />}>
        {climbType === 'track' ? (
          <MiniRankTable rows={rec.longest_to_no1 as ClimbToNo1Record[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} coverUrl={covers.track.get(r.track_id)} /> },
            { header: '首次上榜', width: '105px', mobileRole: 'fact', render: (r) => <WeekLink date={r.first_week} /> },
            { header: '首次夺冠', width: '105px', mobileRole: 'fact', render: (r) => <WeekLink date={r.first_peak_week} /> },
            { header: '登顶周数', width: '130px', align: 'right', mobileRole: 'primary', render: (r) => <ValueBar value={r['登顶周数']} max={rec.longest_to_no1[0]?.['登顶周数'] ?? 1} suffix="周" /> },
          ]} />
        ) : climbType === 'album' ? (
          <MiniRankTable rows={rec.longest_to_no1_album as ClimbToNo1AlbumRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '专辑', render: (r) => <AlbumCell albumName={r.album_name} artistName={r.artist_name} coverUrl={covers.album.get(r.album_name)} /> },
            { header: '首次上榜', width: '105px', mobileRole: 'fact', render: (r) => <WeekLink date={r.first_week} /> },
            { header: '首次夺冠', width: '105px', mobileRole: 'fact', render: (r) => <WeekLink date={r.first_peak_week} /> },
            { header: '登顶周数', width: '130px', align: 'right', mobileRole: 'primary', render: (r) => <ValueBar value={r['登顶周数']} max={rec.longest_to_no1_album[0]?.['登顶周数'] ?? 1} suffix="周" /> },
          ]} />
        ) : (
          <MiniRankTable rows={rec.longest_to_no1_artist as ClimbToNo1ArtistRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '艺人', render: (r) => <ArtistCell artistName={r.artist_name} coverUrl={covers.artist.get(r.artist_name)} compact /> },
            { header: '首次上榜', width: '105px', mobileRole: 'fact', render: (r) => <WeekLink date={r.first_week} /> },
            { header: '首次夺冠', width: '105px', mobileRole: 'fact', render: (r) => <WeekLink date={r.first_peak_week} /> },
            { header: '登顶周数', width: '130px', align: 'right', mobileRole: 'primary', render: (r) => <ValueBar value={r['登顶周数']} max={rec.longest_to_no1_artist[0]?.['登顶周数'] ?? 1} suffix="周" /> },
          ]} />
        )}
      </RecordCard>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════
// Section 2: 持久传奇
// ══════════════════════════════════════════════════════════════
