import { useState, useEffect, useMemo, createContext, useContext } from 'react'
import { createPortal } from 'react-dom'
import { Link, useNavigate } from 'react-router-dom'
import { useBillboard } from '@/hooks/useBillboard'
import { GlassCard } from '@/components/shared/GlassCard'
import { BillboardSubNav } from '@/components/shared/BillboardSubNav'
import { Skeleton } from '@/components/ui/skeleton'
import { AlertCircle, Trophy, Clock, Zap, Crown, Sparkles, BarChart3, TrendingUp, TrendingDown, ChevronLeft, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { displayName } from '@/lib/chinese'
import type {
  BillboardRecords, BlockedTrackInfo, BlockedAlbumInfo, TrackSummary, ArtistTrackCounts, BillboardDataResponse,
  DebutNo1Record, DebutNo1AlbumRecord,
  ReturnToNo1Record, ReturnToNo1AlbumRecord,
  SelfReplacementRecord, SelfReplacementAlbumRecord,
  BlockerKingRecord, BlockerKingAlbumRecord,
  LongestChartingRecord, LongestChartingAlbumRecord,
  LongestStreakRecord, LongestStreakAlbumRecord,
  LongestNoTop5Record, LongestNoTop5AlbumRecord,
  MostWeeksNo2Record, MostWeeksNo2AlbumRecord,
  MostReentriesRecord, MostReentriesAlbumRecord,
  LongestSameRankRecord, LongestSameRankAlbumRecord,
  DecadeBestRecord,
} from '@/types/billboard'

// ── helpers ──────────────────────────────────────────────────

function fmtNum(n: number): string { return new Intl.NumberFormat('zh-CN').format(n) }
function fmtDate(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso + 'T00:00:00')
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`
}

// ── shared sub-components ────────────────────────────────────

function CoverImg({ url }: { url?: string | null }) {
  const [imgError, setImgError] = useState(false)
  useEffect(() => { setImgError(false) }, [url])
  if (url && !imgError) return <img src={url} alt="" className="h-10 w-10 shrink-0 rounded-[8px] object-cover" onError={() => setImgError(true)} loading="lazy" />
  return <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[8px] bg-muted text-base">🎵</div>
}

function ArtistCoverImg({ url, size }: { url?: string | null; size?: 'sm' | 'md' }) {
  const [imgError, setImgError] = useState(false)
  useEffect(() => { setImgError(false) }, [url])
  const cls = size === 'sm' ? 'h-10 w-10' : 'h-14 w-14'
  if (url && !imgError) return <img src={url} alt="" className={cn(cls, 'shrink-0 rounded-full object-cover')} onError={() => setImgError(true)} loading="lazy" />
  return <div className={cn(cls, 'flex shrink-0 items-center justify-center rounded-full bg-muted text-base')}>🎤</div>
}

function ValueBar({ value, max, suffix }: { value: number; max: number; suffix?: string }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <span className="inline-flex items-center gap-2">
      <span className="inline-block w-[52px] text-right font-sans text-[14px] font-semibold tabular-nums">
        {fmtNum(value)}{suffix && <span className="ml-0.5 text-[11px] font-normal text-muted-foreground">{suffix}</span>}
      </span>
      <span className="inline-block h-[3px] w-[56px] rounded-[2px] bg-muted">
        <span className="block h-full rounded-[2px] bg-accent-foreground transition-[width] duration-300" style={{ width: `${pct}%` }} />
      </span>
    </span>
  )
}

function SectionHeader({ icon: Icon, title, subtitle }: { icon: React.ComponentType<{ className?: string }>; title: string; subtitle: string }) {
  return (
    <div className="mb-6">
      <div className="mb-1 flex items-center gap-2">
        <Icon className="h-5 w-5 text-accent-foreground" />
        <h2 className="font-serif text-[28px] font-bold tracking-[-0.5px]">{title}</h2>
      </div>
      <p className="font-sans text-[13px] text-muted-foreground">{subtitle}</p>
    </div>
  )
}

type EntityType = 'track' | 'album'

function TrackAlbumToggle({ value, onChange }: { value: EntityType; onChange: (v: EntityType) => void }) {
  return (
    <div className="flex items-center rounded-[6px] border border-border bg-muted/30 p-0.5">
      <button onClick={() => onChange('track')} className={cn('rounded-[4px] px-2.5 py-1 font-sans text-[11px] font-medium transition-colors', value === 'track' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')}>单曲</button>
      <button onClick={() => onChange('album')} className={cn('rounded-[4px] px-2.5 py-1 font-sans text-[11px] font-medium transition-colors', value === 'album' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')}>专辑</button>
    </div>
  )
}

const PaginationPortalCtx = createContext<HTMLDivElement | null>(null)

function RecordCard({ title, subtitle, toggle, children }: { title: string; subtitle?: string; toggle?: React.ReactNode; children: React.ReactNode }) {
  const [portalEl, setPortalEl] = useState<HTMLDivElement | null>(null)
  return (
    <PaginationPortalCtx.Provider value={portalEl}>
      <GlassCard className="mb-5 p-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="font-serif text-[18px] font-bold tracking-[-0.3px]">{title}</h3>
            {subtitle && <p className="mt-0.5 font-sans text-[11px] text-muted-foreground">{subtitle}</p>}
          </div>
          <div className="flex items-center gap-3">
            <div ref={setPortalEl} />
            {toggle}
          </div>
        </div>
        {children}
      </GlassCard>
    </PaginationPortalCtx.Provider>
  )
}

function FeaturedRecord({ label, value, unit, caption, linkTo, coverUrl }: {
  label: string; value: string | number; unit?: string; caption?: string; linkTo?: string; coverUrl?: string | null
}) {
  const content = (
    <div className={cn('rounded-[12px] border border-border bg-muted/20 p-5', linkTo && 'transition-colors hover:bg-muted/40')}>
      <div className="flex items-start gap-4">
        {coverUrl && <img src={coverUrl} alt="" className="h-14 w-14 shrink-0 rounded-[10px] object-cover" />}
        <div className="min-w-0">
          <p className="mb-1 font-sans text-[11px] font-semibold uppercase tracking-[1.2px] text-muted-foreground">{label}</p>
          <p className="font-serif text-[40px] font-bold leading-[1.1] tracking-[-1px] tabular-nums">
            {typeof value === 'number' ? fmtNum(value) : value}
            {unit && <span className="ml-1 font-sans text-[16px] font-normal text-muted-foreground">{unit}</span>}
          </p>
          {caption && <p className="mt-2 font-sans text-[12px] text-muted-foreground">{displayName(caption)}</p>}
        </div>
      </div>
    </div>
  )
  if (linkTo) return <Link to={linkTo}>{content}</Link>
  return content
}

// ── Paginated Table ──────────────────────────────────────────

function Pagination({ page, totalPages, startIdx, endIdx, totalItems, onPageChange }: {
  page: number; totalPages: number; startIdx: number; endIdx: number; totalItems: number; onPageChange: (p: number) => void
}) {
  if (totalPages <= 1) return null
  return (
    <div className="flex items-center gap-0.5">
      <span className="mr-1.5 font-sans text-[10px] text-muted-foreground">{startIdx}—{endIdx} / {totalItems}</span>
      <button onClick={() => onPageChange(1)} disabled={page <= 1} className="rounded p-1 text-muted-foreground hover:text-foreground disabled:opacity-25 transition-colors"><ChevronLeft className="h-3 w-3 rotate-180" /></button>
      <button onClick={() => onPageChange(page - 1)} disabled={page <= 1} className="rounded p-1 text-muted-foreground hover:text-foreground disabled:opacity-25 transition-colors"><ChevronLeft className="h-3 w-3" /></button>
      <span className="px-0.5 font-sans text-[10px] tabular-nums text-muted-foreground">{page}/{totalPages}</span>
      <button onClick={() => onPageChange(page + 1)} disabled={page >= totalPages} className="rounded p-1 text-muted-foreground hover:text-foreground disabled:opacity-25 transition-colors"><ChevronRight className="h-3 w-3" /></button>
      <button onClick={() => onPageChange(totalPages)} disabled={page >= totalPages} className="rounded p-1 text-muted-foreground hover:text-foreground disabled:opacity-25 transition-colors"><ChevronRight className="h-3 w-3 rotate-180" /></button>
    </div>
  )
}

function MiniRankTable<T extends object>({ rows, columns, emptyText = '暂无数据', fixed }: {
  rows: T[]; columns: { header: React.ReactNode; width?: string; align?: 'left' | 'right' | 'center'; render: (row: T, idx: number) => React.ReactNode }[]; emptyText?: string; fixed?: boolean
}) {
  const PAGE_SIZE = 10
  const [page, setPage] = useState(1)
  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE))
  const safePage = Math.min(page, totalPages)
  useEffect(() => { setPage(1) }, [rows])

  const portalTarget = useContext(PaginationPortalCtx)

  if (rows.length === 0) return <p className="py-4 text-center font-sans text-[12px] text-muted-foreground">{emptyText}</p>

  const displayRows = rows.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE)
  const startIdx = (safePage - 1) * PAGE_SIZE + 1
  const endIdx = Math.min(safePage * PAGE_SIZE, rows.length)

  return (
    <div>
      {totalPages > 1 && !portalTarget && (
        <div className="mb-2 flex items-center justify-end">
          <Pagination page={safePage} totalPages={totalPages} startIdx={startIdx} endIdx={endIdx} totalItems={rows.length} onPageChange={setPage} />
        </div>
      )}
      {totalPages > 1 && portalTarget && createPortal(
        <Pagination page={safePage} totalPages={totalPages} startIdx={startIdx} endIdx={endIdx} totalItems={rows.length} onPageChange={setPage} />,
        portalTarget
      )}
      <div className="overflow-x-auto">
        <table className={cn('w-full', fixed && 'table-fixed')}>
          <thead>
            <tr className="border-b border-border">
              {columns.map((col, i) => (
                <th key={i} className={cn('pb-2 font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground', col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left')} style={col.width ? { width: col.width } : undefined}>{col.header}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {displayRows.map((row, idx) => (
              <tr key={idx} className="border-b border-border/50 transition-colors hover:bg-muted/30">
                {columns.map((col, colIdx) => (
                  <td key={colIdx} className={cn('py-2.5', col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left')} style={col.width ? { width: col.width } : undefined}>{col.render(row, (safePage - 1) * PAGE_SIZE + idx)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function RankNum({ rank }: { rank: number }) { return <span className="font-serif text-[20px] font-semibold tabular-nums">{String(rank).padStart(2, '0')}</span> }

function PeakNum({ rank }: { rank: number }) {
  const colorCls = rank === 1 ? 'text-accent-foreground'
    : rank === 2 ? 'text-muted-foreground'
    : rank === 3 ? 'text-[#C17A4E] dark:text-[#C97B6B]'
    : 'text-muted-foreground'
  return <span className={cn('font-serif text-[22px] font-semibold tabular-nums', colorCls)}>{String(rank).padStart(2, '0')}</span>
}

function TrackCell({ trackId, trackName, artistName, coverUrl }: { trackId?: number; trackName: string; artistName?: string; coverUrl?: string | null }) {
  const link = trackId != null ? `/music/tracks/${trackId}` : '#'
  return (
    <div className="flex items-center gap-3">
      <CoverImg url={coverUrl} />
      <div className="min-w-0">
        <Link to={link} className="block truncate font-sans text-[13px] font-semibold transition-colors hover:text-accent-foreground">{displayName(trackName)}</Link>
        {artistName && (
          <Link to={`/music/artists/${encodeURIComponent(artistName)}`} className="block truncate font-sans text-[11px] italic text-muted-foreground transition-colors hover:text-accent-foreground">{displayName(artistName)}</Link>
        )}
      </div>
    </div>
  )
}

function ArtistCell({ artistName, coverUrl }: { artistName: string; coverUrl?: string | null }) {
  return (
    <div className="flex items-center gap-3">
      <ArtistCoverImg url={coverUrl} />
      <Link to={`/music/artists/${encodeURIComponent(artistName)}`} className="font-sans text-[13px] font-semibold transition-colors hover:text-accent-foreground">{displayName(artistName)}</Link>
    </div>
  )
}

function AlbumCell({ albumName, artistName, coverUrl }: { albumName: string; artistName: string; coverUrl?: string | null }) {
  return (
    <div className="flex items-center gap-3">
      <CoverImg url={coverUrl} />
      <div className="min-w-0">
        <Link to={`/music/albums/${encodeURIComponent(albumName)}`} className="block truncate font-sans text-[13px] font-semibold transition-colors hover:text-accent-foreground">{displayName(albumName)}</Link>
        <Link to={`/music/artists/${encodeURIComponent(artistName)}`} className="block truncate font-sans text-[11px] italic text-muted-foreground transition-colors hover:text-accent-foreground">{displayName(artistName)}</Link>
      </div>
    </div>
  )
}

// ── Sub-Tabs ─────────────────────────────────────────────────

const RECORD_TABS = [
  { key: 'championship', label: '冠军圣殿', icon: Trophy },
  { key: 'longevity', label: '持久传奇', icon: Clock },
  { key: 'breakthrough', label: '爆发时刻', icon: Zap },
  { key: 'halloffame', label: '名人堂', icon: Crown },
  { key: 'curiosities', label: '奇趣纪录', icon: Sparkles },
  { key: 'market', label: '每周大盘', icon: BarChart3 },
] as const
type TabKey = typeof RECORD_TABS[number]['key']

function LoadingSkeleton() {
  return (
    <div className="mx-auto max-w-[1200px]">
      <Skeleton className="mb-4 h-3 w-32" />
      <Skeleton className="mb-8 h-[44px] w-48" />
      <Skeleton className="mb-6 h-[40px] w-full rounded-[12px]" />
      {[1,2,3].map(i => <Skeleton key={i} className="mb-5 h-[200px] w-full rounded-[16px]" />)}
    </div>
  )
}

// ══════════════════════════════════════════════════════════════
// Section 1: 冠军圣殿
// ══════════════════════════════════════════════════════════════

function ChampionshipSection({ rec, covers, onWeekClick }: { rec: BillboardRecords; covers: CoverMaps; onWeekClick: (week: string) => void }) {
  const [no1Type, setNo1Type] = useState<EntityType>('track')
  const [debutType, setDebutType] = useState<EntityType>('track')
  const [returnType, setReturnType] = useState<EntityType>('track')
  const [replaceType, setReplaceType] = useState<EntityType>('track')
  const [blockerType, setBlockerType] = useState<EntityType>('track')

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

  return (
    <div>
      <SectionHeader icon={Trophy} title="冠军圣殿" subtitle="关于 #1 的一切——最罕见、最有分量的荣誉" />

      {/* 冠军名人堂 */}
      <RecordCard title="冠军名人堂" toggle={<TrackAlbumToggle value={no1Type} onChange={setNo1Type} />}>
        {no1Sorted.length > 0 && (
          <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
            {no1Sorted.slice(0, 3).map((r, i) => (
              <FeaturedRecord key={r.artist_name}
                label={['冠军之王', '亚军', '季军'][i]}
                value={no1Type === 'album' ? (r['冠军专辑数'] ?? 0) : r['冠单数']}
                unit={no1Type === 'album' ? '张冠军专辑' : '首冠军单曲'}
                caption={`${r.artist_name} · 冠周 ${no1Type === 'album' ? r['专辑冠军周数'] : r['单曲冠军周数']}`}
                coverUrl={covers.artist.get(r.artist_name)}
                linkTo={`/music/artists/${encodeURIComponent(r.artist_name)}`}
              />
            ))}
          </div>
        )}
        <MiniRankTable rows={no1Sorted} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '艺人', render: (r) => <ArtistCell artistName={r.artist_name} coverUrl={covers.artist.get(r.artist_name)} /> },
          ...(no1Type === 'album'
            ? [
              { header: '冠军专辑', width: '140px', align: 'right' as const, render: (r: typeof rec.artist_most_no1[number]) => <ValueBar value={r['冠军专辑数'] ?? 0} max={no1MaxAlbums} /> },
              { header: '专辑冠周', width: '145px', align: 'right' as const, render: (r: typeof rec.artist_most_no1[number]) => <ValueBar value={r['专辑冠军周数'] ?? 0} max={no1MaxAlbumWeeks} suffix="周" /> },
            ]
            : [
              { header: '冠军单曲', width: '140px', align: 'right' as const, render: (r: typeof rec.artist_most_no1[number]) => <ValueBar value={r['冠单数']} max={no1MaxSongs} /> },
              { header: '单曲冠周', width: '145px', align: 'right' as const, render: (r: typeof rec.artist_most_no1[number]) => <ValueBar value={r['单曲冠军周数']} max={no1MaxSongWeeks} suffix="周" /> },
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
            { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} coverUrl={covers.track.get(r.track_id)} /> },
            { header: '空降日期', width: '110px', render: (r) => <button onClick={() => onWeekClick(r.first_week)} className="font-sans text-[12px] tabular-nums text-muted-foreground transition-colors hover:text-foreground hover:underline">{fmtDate(r.first_week)}</button> },
            { header: '冠军周数', width: '105px', align: 'right', render: (r) => <span className="font-sans text-[13px] tabular-nums text-muted-foreground">{r.weeks_at_no1 > 0 ? `${r.weeks_at_no1} 周` : '—'}</span> },
            { header: '在榜', width: '140px', align: 'right', render: (r) => <ValueBar value={r.weeks_on_chart} max={debutTrackSorted[0]?.weeks_on_chart ?? 1} suffix="周" /> },
          ]} />
        ) : (
          <MiniRankTable rows={debutAlbumSorted} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '专辑', render: (r) => <AlbumCell albumName={r.album_name} artistName={r.artist_name} coverUrl={covers.album.get(r.album_name)} /> },
            { header: '空降日期', width: '110px', render: (r) => <button onClick={() => onWeekClick(r.first_week)} className="font-sans text-[12px] tabular-nums text-muted-foreground transition-colors hover:text-foreground hover:underline">{fmtDate(r.first_week)}</button> },
            { header: '冠军周数', width: '105px', align: 'right', render: (r) => <span className="font-sans text-[13px] tabular-nums text-muted-foreground">{r.weeks_at_no1 > 0 ? `${r.weeks_at_no1} 周` : '—'}</span> },
            { header: '在榜', width: '140px', align: 'right', render: (r) => <ValueBar value={r.weeks_on_chart} max={debutAlbumSorted[0]?.weeks_on_chart ?? 1} suffix="周" /> },
          ]} />
        )}
      </RecordCard>

      {/* 回归冠军 */}
      <RecordCard title="回归冠军 · Return to #1" subtitle="离开冠军位后又重新登顶" toggle={<TrackAlbumToggle value={returnType} onChange={setReturnType} />}>
        {returnType === 'track' ? (
          <MiniRankTable rows={rec.return_to_no1 as ReturnToNo1Record[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} coverUrl={covers.track.get(r.track_id)} /> },
            { header: '首次夺冠', width: '105px', render: (r) => <span className="font-sans text-[12px] tabular-nums text-muted-foreground">{fmtDate(r['首次冠单'])}</span> },
            { header: '回归日期', width: '105px', render: (r) => <span className="font-sans text-[12px] tabular-nums text-muted-foreground">{fmtDate(r['回冠日期'])}</span> },
            { header: '间隔', width: '140px', align: 'right', render: (r) => <ValueBar value={r['间隔周数']} max={(rec.return_to_no1 as ReturnToNo1Record[])[0]?.['间隔周数'] ?? 1} suffix="周" /> },
          ]} />
        ) : (
          <MiniRankTable rows={rec.return_to_no1_album as ReturnToNo1AlbumRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '专辑', render: (r) => <AlbumCell albumName={r.album_name} artistName={r.artist_name} coverUrl={covers.album.get(r.album_name)} /> },
            { header: '首次夺冠', width: '105px', render: (r) => <span className="font-sans text-[12px] tabular-nums text-muted-foreground">{fmtDate(r['首次冠专'])}</span> },
            { header: '回归日期', width: '105px', render: (r) => <span className="font-sans text-[12px] tabular-nums text-muted-foreground">{fmtDate(r['回冠日期'])}</span> },
            { header: '间隔', width: '140px', align: 'right', render: (r) => <ValueBar value={r['间隔周数']} max={(rec.return_to_no1_album as ReturnToNo1AlbumRecord[])[0]?.['间隔周数'] ?? 1} suffix="周" /> },
          ]} />
        )}
      </RecordCard>

      {/* 冠军传承 */}
      <RecordCard title="冠军传承 · Self-Replacement" subtitle="连续两周不同作品接力夺冠" toggle={<TrackAlbumToggle value={replaceType} onChange={setReplaceType} />}>
        {replaceType === 'track' ? (
          <MiniRankTable rows={rec.self_replacement_no1 as SelfReplacementRecord[]} columns={[
            { header: '日期', width: '105px', render: (r) => <span className="font-sans text-[12px] tabular-nums text-muted-foreground">{fmtDate(r['周次'])}</span> },
            { header: '艺人', render: (r) => <ArtistCell artistName={r['艺人']} coverUrl={covers.artist.get(r['艺人'])} /> },
            { header: '前冠单', render: (r) => <TrackCell trackId={r['前冠单_id']} trackName={r['前冠单']} coverUrl={covers.track.get(r['前冠单_id'])} /> },
            { header: '', width: '32px', align: 'center', render: () => <span className="text-muted-foreground">→</span> },
            { header: '新冠单', render: (r) => <TrackCell trackId={r['新冠单_id']} trackName={r['新冠单']} coverUrl={covers.track.get(r['新冠单_id'])} /> },
          ]} />
        ) : (
          <MiniRankTable rows={rec.self_replacement_no1_album as SelfReplacementAlbumRecord[]} columns={[
            { header: '日期', width: '105px', render: (r) => <span className="font-sans text-[12px] tabular-nums text-muted-foreground">{fmtDate(r['周次'])}</span> },
            { header: '艺人', render: (r) => <ArtistCell artistName={r['艺人']} coverUrl={covers.artist.get(r['艺人'])} /> },
            { header: '前冠专', render: (r) => <AlbumCell albumName={r['前冠专']} artistName={r['艺人']} coverUrl={covers.album.get(r['前冠专'])} /> },
            { header: '', width: '32px', align: 'center', render: () => <span className="text-muted-foreground">→</span> },
            { header: '新冠专', render: (r) => <AlbumCell albumName={r['新冠专']} artistName={r['艺人']} coverUrl={covers.album.get(r['新冠专'])} /> },
          ]} />
        )}
      </RecordCard>

      {/* 阻挡王 */}
      <RecordCard title="阻挡王 · Blocker King" subtitle="在 #1 期间阻挡最多 Peak #2 作品" toggle={<TrackAlbumToggle value={blockerType} onChange={setBlockerType} />}>
        {blockerType === 'track' ? (
          <>
            {blockerKingSorted.length > 0 && (
              <div className="mb-4">
                <FeaturedRecord label="最强阻挡" value={blockerKingSorted[0]['阻挡数']} unit="首 Peak #2 歌曲被挡" caption={`${blockerKingSorted[0].track_name} — ${blockerKingSorted[0].artist_name}`} coverUrl={covers.track.get(blockerKingSorted[0].track_id)} linkTo={`/music/tracks/${blockerKingSorted[0].track_id}`} />
              </div>
            )}
            <MiniRankTable fixed rows={blockerKingSorted} columns={[
              { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
              { header: '歌曲', width: '280px', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} coverUrl={covers.track.get(r.track_id)} /> },
              { header: '阻挡数', width: '130px', align: 'right', render: (r) => <ValueBar value={r['阻挡数']} max={blockerKingSorted[0]?.['阻挡数'] ?? 1} /> },
              { header: <span className="pl-8">被阻挡歌曲</span>, render: (r) => {
                const blocked: BlockedTrackInfo[] = rec.blocked_tracks_map?.[r.track_id] ?? []
                if (blocked.length === 0) return <span className="text-[11px] text-muted-foreground">—</span>
                return <div className="flex flex-wrap gap-1 pl-8">{blocked.map(b => <Link key={b.track_id} to={`/music/tracks/${b.track_id}`} className="inline-flex items-center gap-1 rounded-[4px] bg-muted/50 px-1.5 py-0.5 font-sans text-[11px] transition-colors hover:bg-muted hover:text-accent-foreground">{displayName(b.track_name)}</Link>)}</div>
              }},
            ]} />
          </>
        ) : (
          <>
            {blockerKingAlbumSorted.length > 0 && (
              <div className="mb-4">
                <FeaturedRecord label="最强阻挡" value={blockerKingAlbumSorted[0]['阻挡数']} unit="张 Peak #2 专辑被挡" caption={`${blockerKingAlbumSorted[0].album_name} — ${blockerKingAlbumSorted[0].artist_name}`} linkTo={`/music/albums/${encodeURIComponent(blockerKingAlbumSorted[0].album_name)}`} />
              </div>
            )}
            <MiniRankTable fixed rows={blockerKingAlbumSorted} columns={[
              { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
              { header: '专辑', width: '280px', render: (r) => <AlbumCell albumName={r.album_name} artistName={r.artist_name} coverUrl={covers.album.get(r.album_name)} /> },
              { header: '阻挡数', width: '130px', align: 'right', render: (r) => <ValueBar value={r['阻挡数']} max={blockerKingAlbumSorted[0]?.['阻挡数'] ?? 1} /> },
              { header: <span className="pl-8">被阻挡专辑</span>, render: (r) => {
                const key = `${r.album_name}||${r.artist_name}`
                const blocked: BlockedAlbumInfo[] = rec.blocked_albums_map?.[key] ?? []
                if (blocked.length === 0) return <span className="text-[11px] text-muted-foreground">—</span>
                return <div className="flex flex-wrap gap-1 pl-8">{blocked.map((b, i) => <Link key={i} to={`/music/albums/${encodeURIComponent(b.album_name)}`} className="inline-flex items-center gap-1 rounded-[4px] bg-muted/50 px-1.5 py-0.5 font-sans text-[11px] transition-colors hover:bg-muted hover:text-accent-foreground">{displayName(b.album_name)}</Link>)}</div>
              }},
            ]} />
          </>
        )}
      </RecordCard>

      {/* 最长/最快登顶 */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        <RecordCard title="最长登顶路 · Longest Climb to #1">
          {rec.longest_to_no1.length > 0 && <FeaturedRecord label="马拉松冠军" value={rec.longest_to_no1[0]['登顶周数']} unit="周登顶" caption={`${rec.longest_to_no1[0].track_name} — ${rec.longest_to_no1[0].artist_name}`} linkTo={`/music/tracks/${rec.longest_to_no1[0].track_id}`} />}
        </RecordCard>
        <RecordCard title="最快登顶 · Fastest Climb to #1" subtitle="非空降歌曲（排除入榜即夺冠）">
          {rec.fastest_to_no1.length > 0 && <FeaturedRecord label="闪电战冠军" value={rec.fastest_to_no1[0]['登顶周数']} unit="周登顶" caption={`${rec.fastest_to_no1[0].track_name} — ${rec.fastest_to_no1[0].artist_name}`} linkTo={`/music/tracks/${rec.fastest_to_no1[0].track_id}`} />}
        </RecordCard>
      </div>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════
// Section 2: 持久传奇
// ══════════════════════════════════════════════════════════════

function LongevitySection({ rec, covers }: { rec: BillboardRecords; covers: CoverMaps }) {
  const [chartingType, setChartingType] = useState<EntityType>('track')
  const [streakType, setStreakType] = useState<EntityType>('track')
  const [noTop5Type, setNoTop5Type] = useState<EntityType>('track')
  const [no2Type, setNo2Type] = useState<EntityType>('track')
  const [reentryType, setReentryType] = useState<EntityType>('track')
  const [sameRankType, setSameRankType] = useState<EntityType>('track')

  return (
    <div>
      <SectionHeader icon={Clock} title="持久传奇" subtitle="时间是最严苛的裁判——那些经得起岁月考验的纪录" />

      <RecordCard title="最长在榜 · Longest Charting" subtitle="在榜周数最多" toggle={<TrackAlbumToggle value={chartingType} onChange={setChartingType} />}>
        {chartingType === 'track' ? (
          <MiniRankTable rows={rec.longest_charting as LongestChartingRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} coverUrl={covers.track.get(r.track_id)} /> },
            { header: '在榜周数', width: '145px', align: 'right', render: (r) => <ValueBar value={r.weeks_on_chart} max={(rec.longest_charting as LongestChartingRecord[])[0]?.weeks_on_chart ?? 1} suffix="周" /> },
            { header: 'Peak', width: '55px', align: 'center', render: (r) => <PeakNum rank={r.peak_position} /> },
            { header: '冠周', width: '110px', align: 'right', render: (r) => <span className="font-sans text-[13px] tabular-nums text-muted-foreground">{r.weeks_at_no1 > 0 ? `${r.weeks_at_no1} 周` : '—'}</span> },
          ]} />
        ) : (
          <MiniRankTable rows={rec.longest_charting_album as LongestChartingAlbumRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '专辑', render: (r) => <AlbumCell albumName={r.album_name} artistName={r.artist_name} coverUrl={covers.album.get(r.album_name)} /> },
            { header: '在榜周数', width: '145px', align: 'right', render: (r) => <ValueBar value={r.weeks_on_chart} max={(rec.longest_charting_album as LongestChartingAlbumRecord[])[0]?.weeks_on_chart ?? 1} suffix="周" /> },
            { header: 'Peak', width: '55px', align: 'center', render: (r) => <PeakNum rank={r.peak_position} /> },
            { header: '冠周', width: '110px', align: 'right', render: (r) => <span className="font-sans text-[13px] tabular-nums text-muted-foreground">{r.weeks_at_no1 > 0 ? `${r.weeks_at_no1} 周` : '—'}</span> },
          ]} />
        )}
      </RecordCard>

      <RecordCard title="最长连续在榜 · Longest Consecutive Streak" subtitle="无断档连续在榜纪录" toggle={<TrackAlbumToggle value={streakType} onChange={setStreakType} />}>
        {streakType === 'track' ? (
          <MiniRankTable rows={rec.longest_streak as LongestStreakRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} coverUrl={covers.track.get(r.track_id)} /> },
            { header: '连续周数', width: '145px', align: 'right', render: (r) => <ValueBar value={r['连续周数']} max={(rec.longest_streak as LongestStreakRecord[])[0]?.['连续周数'] ?? 1} suffix="周" /> },
            { header: '时间区间', width: '190px', render: (r) => <span className="font-sans text-[12px] tabular-nums text-muted-foreground">{fmtDate(r['起始周'])} — {fmtDate(r['结束周'])}</span> },
          ]} />
        ) : (
          <MiniRankTable rows={rec.longest_streak_album as LongestStreakAlbumRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '专辑', render: (r) => <AlbumCell albumName={r.album_name} artistName={r.artist_name} coverUrl={covers.album.get(r.album_name)} /> },
            { header: '连续周数', width: '145px', align: 'right', render: (r) => <ValueBar value={r['连续周数']} max={(rec.longest_streak_album as LongestStreakAlbumRecord[])[0]?.['连续周数'] ?? 1} suffix="周" /> },
            { header: '时间区间', width: '190px', render: (r) => <span className="font-sans text-[12px] tabular-nums text-muted-foreground">{fmtDate(r['起始周'])} — {fmtDate(r['结束周'])}</span> },
          ]} />
        )}
      </RecordCard>

      <RecordCard title="隐形冠军 · Longest Without Top 5" subtitle="在榜最久但从未来到 Top 5" toggle={<TrackAlbumToggle value={noTop5Type} onChange={setNoTop5Type} />}>
        {noTop5Type === 'track' ? (
          <MiniRankTable rows={rec.longest_no_top5 as LongestNoTop5Record[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} coverUrl={covers.track.get(r.track_id)} /> },
            { header: '在榜周数', width: '145px', align: 'right', render: (r) => <ValueBar value={r.weeks_on_chart} max={(rec.longest_no_top5 as LongestNoTop5Record[])[0]?.weeks_on_chart ?? 1} suffix="周" /> },
            { header: 'Peak', width: '55px', align: 'center', render: (r) => <PeakNum rank={r.peak_position} /> },
          ]} />
        ) : (
          <MiniRankTable rows={rec.longest_no_top5_album as LongestNoTop5AlbumRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '专辑', render: (r) => <AlbumCell albumName={r.album_name} artistName={r.artist_name} coverUrl={covers.album.get(r.album_name)} /> },
            { header: '在榜周数', width: '145px', align: 'right', render: (r) => <ValueBar value={r.weeks_on_chart} max={(rec.longest_no_top5_album as LongestNoTop5AlbumRecord[])[0]?.weeks_on_chart ?? 1} suffix="周" /> },
            { header: 'Peak', width: '55px', align: 'center', render: (r) => <PeakNum rank={r.peak_position} /> },
          ]} />
        )}
      </RecordCard>

      <RecordCard title="万年老二 · Most Weeks at #2 Without #1" subtitle="在 #2 停留最久但从未夺冠" toggle={<TrackAlbumToggle value={no2Type} onChange={setNo2Type} />}>
        {no2Type === 'track' ? (
          <MiniRankTable rows={rec.most_weeks_no2_no_no1 as MostWeeksNo2Record[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} coverUrl={covers.track.get(r.track_id)} /> },
            { header: '#2 周数', width: '145px', align: 'right', render: (r) => <ValueBar value={r.weeks_at_no2} max={(rec.most_weeks_no2_no_no1 as MostWeeksNo2Record[])[0]?.weeks_at_no2 ?? 1} suffix="周" /> },
            { header: 'Peak', width: '55px', align: 'center', render: () => <PeakNum rank={2} /> },
          ]} />
        ) : (
          <MiniRankTable rows={rec.most_weeks_no2_no_no1_album as MostWeeksNo2AlbumRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '专辑', render: (r) => <AlbumCell albumName={r.album_name} artistName={r.artist_name} coverUrl={covers.album.get(r.album_name)} /> },
            { header: '#2 周数', width: '145px', align: 'right', render: (r) => <ValueBar value={r.weeks_at_no2} max={(rec.most_weeks_no2_no_no1_album as MostWeeksNo2AlbumRecord[])[0]?.weeks_at_no2 ?? 1} suffix="周" /> },
            { header: 'Peak', width: '55px', align: 'center', render: () => <PeakNum rank={2} /> },
          ]} />
        )}
      </RecordCard>

      <RecordCard title="回榜王 · Most Re-entries" subtitle="出榜后重新入榜次数最多" toggle={<TrackAlbumToggle value={reentryType} onChange={setReentryType} />}>
        {reentryType === 'track' ? (
          <MiniRankTable rows={rec.most_reentries as MostReentriesRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} coverUrl={covers.track.get(r.track_id)} /> },
            { header: '回榜次数', width: '145px', align: 'right', render: (r) => <ValueBar value={r['回榜次数']} max={(rec.most_reentries as MostReentriesRecord[])[0]?.['回榜次数'] ?? 1} suffix="次" /> },
            { header: '在榜周数', width: '110px', align: 'right', render: (r) => <span className="font-sans text-[13px] tabular-nums text-muted-foreground">{r['在榜周数']} 周</span> },
          ]} />
        ) : (
          <MiniRankTable rows={rec.most_reentries_album as MostReentriesAlbumRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '专辑', render: (r) => <AlbumCell albumName={r.album_name} artistName={r.artist_name} coverUrl={covers.album.get(r.album_name)} /> },
            { header: '回榜次数', width: '145px', align: 'right', render: (r) => <ValueBar value={r['回榜次数']} max={(rec.most_reentries_album as MostReentriesAlbumRecord[])[0]?.['回榜次数'] ?? 1} suffix="次" /> },
            { header: '在榜周数', width: '110px', align: 'right', render: (r) => <span className="font-sans text-[13px] tabular-nums text-muted-foreground">{r['在榜周数']} 周</span> },
          ]} />
        )}
      </RecordCard>

      <RecordCard title="稳如磐石 · Longest Consecutive Same Rank" subtitle="在同一排名连续停留最久" toggle={<TrackAlbumToggle value={sameRankType} onChange={setSameRankType} />}>
        {sameRankType === 'track' ? (
          <MiniRankTable rows={rec.longest_consecutive_same_rank as LongestSameRankRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} coverUrl={covers.track.get(r.track_id)} /> },
            { header: '排名', width: '55px', align: 'center', render: (r) => <PeakNum rank={r['停留排名']} /> },
            { header: '连续周数', width: '145px', align: 'right', render: (r) => <ValueBar value={r['连续周数']} max={(rec.longest_consecutive_same_rank as LongestSameRankRecord[])[0]?.['连续周数'] ?? 1} suffix="周" /> },
            { header: '时间区间', width: '190px', render: (r) => <span className="font-sans text-[12px] tabular-nums text-muted-foreground">{fmtDate(r['起始周'])} — {fmtDate(r['结束周'])}</span> },
          ]} />
        ) : (
          <MiniRankTable rows={rec.longest_consecutive_same_rank_album as LongestSameRankAlbumRecord[]} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '专辑', render: (r) => <AlbumCell albumName={r.album_name} artistName={r.artist_name} coverUrl={covers.album.get(r.album_name)} /> },
            { header: '排名', width: '55px', align: 'center', render: (r) => <PeakNum rank={r['停留排名']} /> },
            { header: '连续周数', width: '145px', align: 'right', render: (r) => <ValueBar value={r['连续周数']} max={(rec.longest_consecutive_same_rank_album as LongestSameRankAlbumRecord[])[0]?.['连续周数'] ?? 1} suffix="周" /> },
            { header: '时间区间', width: '190px', render: (r) => <span className="font-sans text-[12px] tabular-nums text-muted-foreground">{fmtDate(r['起始周'])} — {fmtDate(r['结束周'])}</span> },
          ]} />
        )}
      </RecordCard>

      <RecordCard title="最长艺人生涯 · Longest Artist Chart Span" subtitle="首次上榜到最近上榜跨度最大">
        <MiniRankTable rows={rec.longest_artist_span} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '艺人', render: (r) => <ArtistCell artistName={r.artist_name} coverUrl={covers.artist.get(r.artist_name)} /> },
          { header: '生涯跨度', width: '145px', align: 'right', render: (r) => <ValueBar value={r['跨度天数']} max={rec.longest_artist_span[0]?.['跨度天数'] ?? 1} suffix="天" /> },
          { header: '时间区间', width: '190px', render: (r) => <span className="font-sans text-[12px] tabular-nums text-muted-foreground">{fmtDate(r['首次上榜'])} — {fmtDate(r['最近上榜'])}</span> },
          { header: '歌曲数', width: '60px', align: 'center', render: (r) => <span className="font-sans text-[13px] tabular-nums text-muted-foreground">{r['上榜歌曲数']}</span> },
        ]} />
      </RecordCard>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════
// Sections 3-6 (no toggle needed, keep as-is but with new structure)
// ══════════════════════════════════════════════════════════════

function BreakthroughSection({ rec, covers }: { rec: BillboardRecords; covers: CoverMaps }) {
  return (
    <div>
      <SectionHeader icon={Zap} title="爆发时刻" subtitle="那些让人瞠目结舌的瞬间——榜单上最极致的爆发力" />

      <RecordCard title="艺人霸榜 · Most Simultaneous Chart Entries" subtitle="单周同一艺人上榜歌曲数最多">
        {rec.artist_simul && (
          <div className="mb-4">
            <FeaturedRecord label="艺人霸榜纪录" value={rec.artist_simul.count} unit="首歌曲同时在榜" caption={`${rec.artist_simul.artist} · ${fmtDate(rec.artist_simul.week)}`} coverUrl={covers.artist.get(rec.artist_simul.artist)} linkTo={`/music/artists/${encodeURIComponent(rec.artist_simul.artist || '')}`} />
          </div>
        )}
        {rec.artist_simul_list?.length > 0 && (
          <MiniRankTable rows={rec.artist_simul_list} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '艺人', render: (r) => <ArtistCell artistName={r.artist_name} coverUrl={covers.artist.get(r.artist_name)} /> },
            { header: '日期', width: '110px', render: (r) => <span className="font-sans text-[12px] tabular-nums text-muted-foreground">{fmtDate(r.billboard_week)}</span> },
            { header: '上榜数', width: '145px', align: 'right', render: (r) => <ValueBar value={r.track_count} max={rec.artist_simul_list[0]?.track_count ?? 1} suffix="首" /> },
          ]} />
        )}
      </RecordCard>

      <RecordCard title="专辑霸榜 · Most Simultaneous Album Entries" subtitle="单周同一专辑上榜歌曲数最多">
        {rec.album_simul && (
          <div className="mb-4">
            <FeaturedRecord label="专辑霸榜纪录" value={rec.album_simul.count} unit="首歌曲同时在榜" caption={`${rec.album_simul.album} · ${rec.album_simul.artist} · ${fmtDate(rec.album_simul.week)}`} coverUrl={covers.album.get(rec.album_simul.album)} linkTo={`/music/albums/${encodeURIComponent(rec.album_simul.album || '')}`} />
          </div>
        )}
        {rec.album_simul_list?.length > 0 && (
          <MiniRankTable rows={rec.album_simul_list} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '专辑', render: (r) => <AlbumCell albumName={r.album_name} artistName={r.artist_name} coverUrl={covers.album.get(r.album_name)} /> },
            { header: '日期', width: '110px', render: (r) => <span className="font-sans text-[12px] tabular-nums text-muted-foreground">{fmtDate(r.billboard_week)}</span> },
            { header: '上榜数', width: '145px', align: 'right', render: (r) => <ValueBar value={r.track_count} max={rec.album_simul_list[0]?.track_count ?? 1} suffix="首" /> },
          ]} />
        )}
      </RecordCard>

      <RecordCard title="Top 10 屠榜 · Most Simultaneous Top 10" subtitle="单周同一艺人 Top 10 歌曲数最多">
        {rec.most_top10_simul ? (
          <FeaturedRecord label="Top 10 屠榜纪录" value={rec.most_top10_simul.count} unit="首进入 Top 10" caption={`${rec.most_top10_simul.artist} · ${fmtDate(rec.most_top10_simul.week)}`} coverUrl={covers.artist.get(rec.most_top10_simul.artist)} linkTo={`/music/artists/${encodeURIComponent(rec.most_top10_simul.artist || '')}`} />
        ) : (
          <p className="py-4 text-center font-sans text-[12px] text-muted-foreground">暂无数据</p>
        )}
      </RecordCard>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        <RecordCard title="最大跃升 · Biggest Jump" subtitle="单周排名上升最多">
          <MiniRankTable rows={rec.biggest_jump} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} coverUrl={covers.track.get(r.track_id)} /> },
            { header: '变化', width: '160px', align: 'right', render: (r) => <span className="inline-flex items-center gap-1 font-sans text-[14px] font-bold tabular-nums text-emerald-600 dark:text-emerald-400"><TrendingUp className="h-3.5 w-3.5" />▲{Math.abs(r['变化'])}</span> },
          ]} />
        </RecordCard>
        <RecordCard title="最大跌幅 · Biggest Drop" subtitle="单周排名下降最多">
          <MiniRankTable rows={rec.biggest_drop} columns={[
            { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
            { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} coverUrl={covers.track.get(r.track_id)} /> },
            { header: '变化', width: '160px', align: 'right', render: (r) => <span className="inline-flex items-center gap-1 font-sans text-[14px] font-bold tabular-nums text-red-600 dark:text-red-400"><TrendingDown className="h-3.5 w-3.5" />▼{Math.abs(r['变化'])}</span> },
          ]} />
        </RecordCard>
      </div>

      <RecordCard title="最快出榜 · Fastest Exit After #1" subtitle="夺冠后最快跌出榜单">
        <MiniRankTable rows={rec.fastest_exit_after_no1} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} coverUrl={covers.track.get(r.track_id)} /> },
          { header: '夺冠日期', width: '110px', render: (r) => <span className="font-sans text-[12px] tabular-nums text-muted-foreground">{fmtDate(r.first_peak_week)}</span> },
          { header: '出榜日期', width: '110px', render: (r) => <span className="font-sans text-[12px] tabular-nums text-muted-foreground">{fmtDate(r.last_week)}</span> },
          { header: '巅后周数', width: '145px', align: 'right', render: (r) => <ValueBar value={r['巅峰后周数']} max={rec.fastest_exit_after_no1[0]?.['巅峰后周数'] ?? 1} suffix="周" /> },
        ]} />
      </RecordCard>

      <RecordCard title="最强单周 · Strongest Week" subtitle="总播放量最高的单周">
        {rec.strongest_week ? <FeaturedRecord label="最强单周" value={fmtNum(rec.strongest_week.total_plays)} unit="次播放" caption={fmtDate(rec.strongest_week.week)} /> : <p className="py-4 text-center font-sans text-[12px] text-muted-foreground">暂无数据</p>}
      </RecordCard>
    </div>
  )
}

function DecadeBestCard({ covers, decadeGroups }: { covers: CoverMaps; decadeGroups: Map<string, DecadeBestRecord[]> }) {
  const decades = useMemo(() => Array.from(decadeGroups.keys()).sort(), [decadeGroups])
  const [activeDecade, setActiveDecade] = useState<string>(decades[decades.length - 1] ?? '')

  useEffect(() => {
    if (decades.length > 0 && !decades.includes(activeDecade)) {
      setActiveDecade(decades[decades.length - 1])
    }
  }, [decades, activeDecade])

  const tracks = decadeGroups.get(activeDecade) ?? []

  return (
    <RecordCard title="年代之王 · Decade Best" toggle={
      <div className="flex items-center rounded-[6px] border border-border bg-muted/30 p-0.5">
        {decades.map((d) => (
          <button key={d} onClick={() => setActiveDecade(d)}
            className={cn('rounded-[4px] px-3 py-1 font-sans text-[11px] font-medium transition-colors', activeDecade === d ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')}>
            {d}
          </button>
        ))}
      </div>
    }>
      {tracks.length > 0 ? (
        <MiniRankTable rows={tracks} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} coverUrl={covers.track.get(r.track_id)} /> },
          { header: '走势评分', width: '130px', align: 'right', render: (r) => <ValueBar value={r['走势评分']} max={tracks[0]?.['走势评分'] ?? 1} /> },
          { header: 'Peak', width: '55px', align: 'center', render: (r) => <PeakNum rank={r.peak} /> },
          { header: '在榜', width: '100px', align: 'right', render: (r) => <span className="font-sans text-[13px] tabular-nums text-muted-foreground">{r.weeks_on_chart} 周</span> },
        ]} />
      ) : (
        <p className="py-4 text-center font-sans text-[12px] text-muted-foreground">暂无数据</p>
      )}
    </RecordCard>
  )
}

function HallOfFameSection({ rec, covers }: { rec: BillboardRecords; covers: CoverMaps }) {
  const decadeGroups = useMemo(() => {
    const map = new Map<string, typeof rec.decade_best>()
    for (const r of rec.decade_best) { const key = r['年代']; if (!map.has(key)) map.set(key, []); map.get(key)!.push(r) }
    return map
  }, [rec.decade_best])

  const songScoreMax = rec.all_time_greatest[0]?.['走势评分'] ?? 1
  const albumScoreMax = rec.album_power_ranking[0]?.['走势评分'] ?? 1
  const artistScoreMax = rec.artist_power_ranking[0]?.['走势评分'] ?? 1

  return (
    <div>
      <SectionHeader icon={Crown} title="名人堂" subtitle="走势评分最高的歌曲、专辑与艺人——各年代的传奇之作" />

      {/* 歌曲走势总榜 */}
      <RecordCard title="歌曲走势总榜 · All-Time Greatest Songs">
        {rec.all_time_greatest.length > 0 && (
          <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
            {rec.all_time_greatest.slice(0, 3).map((r, i) => (
              <FeaturedRecord key={r.track_id}
                label={['走势之王', '亚军', '季军'][i]}
                value={r['走势评分'].toFixed(0)}
                unit="走势评分"
                caption={`${r.track_name} — ${r.artist_name}`}
                coverUrl={covers.track.get(r.track_id)}
                linkTo={`/music/tracks/${r.track_id}`}
              />
            ))}
          </div>
        )}
        <MiniRankTable rows={rec.all_time_greatest} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '歌曲', render: (r) => <TrackCell trackId={r.track_id} trackName={r.track_name} artistName={r.artist_name} coverUrl={covers.track.get(r.track_id)} /> },
          { header: '走势评分', width: '145px', align: 'right', render: (r) => <ValueBar value={r['走势评分']} max={songScoreMax} /> },
          { header: 'Peak', width: '55px', align: 'center', render: (r) => <PeakNum rank={r.peak_position} /> },
          { header: '在榜', width: '110px', align: 'right', render: (r) => <span className="font-sans text-[13px] tabular-nums text-muted-foreground">{r.weeks_on_chart} 周</span> },
        ]} />
      </RecordCard>

      {/* 专辑走势总榜 */}
      <RecordCard title="专辑走势总榜 · All-Time Greatest Albums">
        {rec.album_power_ranking.length > 0 && (
          <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
            {rec.album_power_ranking.slice(0, 3).map((r, i) => (
              <FeaturedRecord key={`${r.album_name}-${r.artist_name}`}
                label={['走势之王', '亚军', '季军'][i]}
                value={r['走势评分'].toFixed(0)}
                unit="走势评分"
                caption={`${r.album_name} — ${r.artist_name}`}
                coverUrl={covers.album.get(r.album_name)}
                linkTo={`/music/albums/${encodeURIComponent(r.album_name)}`}
              />
            ))}
          </div>
        )}
        <MiniRankTable rows={rec.album_power_ranking} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '专辑', render: (r) => <AlbumCell albumName={r.album_name} artistName={r.artist_name} coverUrl={covers.album.get(r.album_name)} /> },
          { header: '走势评分', width: '145px', align: 'right', render: (r) => <ValueBar value={r['走势评分']} max={albumScoreMax} /> },
          { header: 'Peak', width: '55px', align: 'center', render: (r) => <PeakNum rank={r.peak_position} /> },
          { header: '在榜', width: '110px', align: 'right', render: (r) => <span className="font-sans text-[13px] tabular-nums text-muted-foreground">{r.weeks_on_chart} 周</span> },
        ]} />
      </RecordCard>

      {/* 艺人走势总榜 */}
      <RecordCard title="艺人走势总榜 · All-Time Greatest Artists">
        {rec.artist_power_ranking.length > 0 && (
          <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
            {rec.artist_power_ranking.slice(0, 3).map((r, i) => (
              <FeaturedRecord key={r.artist_name}
                label={['走势之王', '亚军', '季军'][i]}
                value={r['走势评分'].toFixed(0)}
                unit="走势评分"
                caption={r.artist_name}
                coverUrl={covers.artist.get(r.artist_name)}
                linkTo={`/music/artists/${encodeURIComponent(r.artist_name)}`}
              />
            ))}
          </div>
        )}
        <MiniRankTable rows={rec.artist_power_ranking} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '艺人', render: (r) => <ArtistCell artistName={r.artist_name} coverUrl={covers.artist.get(r.artist_name)} /> },
          { header: '走势评分', width: '145px', align: 'right', render: (r) => <ValueBar value={r['走势评分']} max={artistScoreMax} /> },
          { header: 'Peak', width: '55px', align: 'center', render: (r) => <PeakNum rank={r.peak_position as number} /> },
          { header: '在榜', width: '110px', align: 'right', render: (r) => <span className="font-sans text-[13px] tabular-nums text-muted-foreground">{r.weeks_on_chart} 周</span> },
        ]} />
      </RecordCard>

      {/* 年度之歌 */}
      <RecordCard title="年度之歌 · Year-End #1">
        {rec.year_end_no1.length > 0 ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-5">
            {rec.year_end_no1.map((r) => (
              <Link key={r.year} to={`/music/tracks/${r.track_id}`} className="group rounded-[10px] border border-border bg-muted/20 p-4 transition-colors hover:bg-muted/40">
                <CoverImg url={covers.track.get(r.track_id)} />
                <p className="mt-2 font-serif text-[28px] font-bold leading-none tracking-[-0.5px]">{r.year}</p>
                <p className="mt-2 truncate font-sans text-[12px] font-semibold group-hover:text-accent-foreground">{displayName(r.track_name)}</p>
                <p className="truncate font-sans text-[11px] italic text-muted-foreground">{displayName(r.artist_name)}</p>
                <p className="mt-1 font-sans text-[11px] text-muted-foreground">Peak #{r.peak} · {r.weeks_on_chart} 周</p>
              </Link>
            ))}
          </div>
        ) : <p className="py-4 text-center font-sans text-[12px] text-muted-foreground">暂无数据</p>}
      </RecordCard>

      {/* 年代之王 */}
      <DecadeBestCard covers={covers} decadeGroups={decadeGroups} />
    </div>
  )
}

function CuriositiesSection({ rec, covers, trackSummary, artistTrackCounts }: {
  rec: BillboardRecords; covers: CoverMaps; trackSummary: TrackSummary[]; artistTrackCounts: ArtistTrackCounts[]
}) {
  const oneHitWonders = useMemo(() => artistTrackCounts.filter(a => a.total_tracks === 1 && a.top1 >= 1).sort((a, b) => b.weeks_at_no1 - a.weeks_at_no1), [artistTrackCounts])
  const prolificArtists = useMemo(() => [...artistTrackCounts].sort((a, b) => b.total_tracks - a.total_tracks).slice(0, 20), [artistTrackCounts])
  const sameNameDiffArtist = useMemo(() => {
    const groups = new Map<string, TrackSummary[]>()
    for (const t of trackSummary) { const name = t.track_name.toLowerCase(); if (!groups.has(name)) groups.set(name, []); groups.get(name)!.push(t) }
    return Array.from(groups.values()).filter(g => { const artists = new Set(g.map(t => t.artist_name)); return artists.size >= 2 }).sort((a, b) => b.length - a.length).slice(0, 10)
  }, [trackSummary])
  const oldestTrack = useMemo(() => [...trackSummary].filter(t => t.first_week).sort((a, b) => a.first_week.localeCompare(b.first_week))[0] ?? null, [trackSummary])
  const newestTrack = useMemo(() => [...trackSummary].filter(t => t.first_week).sort((a, b) => b.first_week.localeCompare(a.first_week))[0] ?? null, [trackSummary])
  const longestName = useMemo(() => [...trackSummary].sort((a, b) => b.track_name.length - a.track_name.length)[0] ?? null, [trackSummary])
  const shortestName = useMemo(() => [...trackSummary].sort((a, b) => a.track_name.length - b.track_name.length)[0] ?? null, [trackSummary])

  return (
    <div>
      <SectionHeader icon={Sparkles} title="奇趣纪录" subtitle="那些让人会心一笑的冷知识——数据里的彩蛋" />

      <RecordCard title="双空冠 · Double Debut" subtitle="同一张专辑有两首歌空降入榜">
        <MiniRankTable rows={rec.double_debut} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '歌曲', render: (r) => <TrackCell trackId={r.debut_track_id} trackName={r.debut_track} artistName={r.debut_artist} coverUrl={covers.track.get(r.debut_track_id)} /> },
          { header: '空降日期', width: '110px', render: (r) => <span className="font-sans text-[12px] tabular-nums text-muted-foreground">{fmtDate(r.debut_week)}</span> },
          { header: '所属专辑', render: (r) => <Link to={`/music/albums/${encodeURIComponent(r.debut_album)}`} className="font-sans text-[12px] transition-colors hover:text-accent-foreground">{displayName(r.debut_album)}</Link> },
        ]} />
      </RecordCard>

      <RecordCard title="全榜单制霸 · Triple #1" subtitle="同一周单曲榜、专辑榜、艺人榜三榜 #1 同属一人">
        <MiniRankTable rows={rec.triple_no1} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '艺人', render: (r) => <ArtistCell artistName={r['艺人']} coverUrl={covers.artist.get(r['艺人'])} /> },
          { header: '日期', width: '110px', render: (r) => <span className="font-sans text-[12px] tabular-nums text-muted-foreground">{fmtDate(r.billboard_week)}</span> },
        ]} />
      </RecordCard>

      <RecordCard title="一曲成名 · One-Hit Wonder" subtitle="仅一首歌上榜且直接夺冠">
        {oneHitWonders.length > 0 ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
            {oneHitWonders.slice(0, 9).map((a) => (
              <Link key={a.artist_name} to={`/music/artists/${encodeURIComponent(a.artist_name)}`} className="flex items-center gap-3 rounded-[10px] border border-border bg-muted/20 p-3 transition-colors hover:bg-muted/40">
                <ArtistCoverImg url={covers.artist.get(a.artist_name)} />
                <div className="min-w-0">
                  <p className="truncate font-sans text-[13px] font-semibold">{displayName(a.artist_name)}</p>
                  <p className="font-sans text-[11px] text-muted-foreground">{a.best_peak_track} · 冠周 {a.weeks_at_no1}</p>
                </div>
              </Link>
            ))}
          </div>
        ) : <p className="py-4 text-center font-sans text-[12px] text-muted-foreground">暂无数据</p>}
      </RecordCard>

      <RecordCard title="劳模歌手 · Most Prolific Artists" subtitle="上榜歌曲数最多的艺人">
        <MiniRankTable rows={prolificArtists} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '艺人', render: (r) => <ArtistCell artistName={r.artist_name} coverUrl={covers.artist.get(r.artist_name)} /> },
          { header: '上榜歌曲', width: '145px', align: 'right', render: (r) => <ValueBar value={r.total_tracks} max={prolificArtists[0]?.total_tracks ?? 1} suffix="首" /> },
          { header: '最佳Peak', width: '55px', align: 'center', render: (r) => <PeakNum rank={r.best_peak as number} /> },
          { header: '冠单数', width: '60px', align: 'center', render: (r) => <span className="font-sans text-[13px] tabular-nums text-muted-foreground">{r.top1}</span> },
          { header: '总周数', width: '110px', align: 'right', render: (r) => <span className="font-sans text-[13px] tabular-nums text-muted-foreground">{r.total_weeks} 周</span> },
        ]} />
      </RecordCard>

      <RecordCard title="同名异曲 · Same Name, Different Song" subtitle="相同歌名、不同艺人的歌曲">
        {sameNameDiffArtist.length > 0 ? (
          <div className="space-y-3">
            {sameNameDiffArtist.slice(0, 5).map((group) => (
              <div key={group[0].track_name} className="rounded-[10px] border border-border bg-muted/20 p-4">
                <p className="mb-2 font-sans text-[14px] font-bold">"{displayName(group[0].track_name)}"</p>
                <div className="flex flex-wrap gap-2">
                  {group.map((t) => (
                    <Link key={t.track_id} to={`/music/tracks/${t.track_id}`} className="inline-flex items-center gap-1.5 rounded-[6px] bg-background px-2.5 py-1 font-sans text-[12px] transition-colors hover:bg-muted">{displayName(t.artist_name)}<span className="text-[10px] text-muted-foreground">Peak #{t.peak_position}</span></Link>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : <p className="py-4 text-center font-sans text-[12px] text-muted-foreground">暂无数据</p>}
      </RecordCard>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        <RecordCard title="最早上榜 · Oldest Chart Entry">
          {oldestTrack && <FeaturedRecord label="最早入榜" value={fmtDate(oldestTrack.first_week)} caption={`${oldestTrack.track_name} — ${oldestTrack.artist_name}`} linkTo={`/music/tracks/${oldestTrack.track_id}`} />}
        </RecordCard>
        <RecordCard title="最新上榜 · Newest Chart Entry">
          {newestTrack && <FeaturedRecord label="最新入榜" value={fmtDate(newestTrack.first_week)} caption={`${newestTrack.track_name} — ${newestTrack.artist_name}`} linkTo={`/music/tracks/${newestTrack.track_id}`} />}
        </RecordCard>
      </div>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        <RecordCard title="最长歌名 · Longest Track Name">
          {longestName && <FeaturedRecord label="最长歌名" value={longestName.track_name.length} unit="字" caption={`${longestName.track_name} — ${longestName.artist_name}`} linkTo={`/music/tracks/${longestName.track_id}`} />}
        </RecordCard>
        <RecordCard title="最短歌名 · Shortest Track Name">
          {shortestName && <FeaturedRecord label="最短歌名" value={shortestName.track_name.length} unit="字" caption={`${shortestName.track_name} — ${shortestName.artist_name}`} linkTo={`/music/tracks/${shortestName.track_id}`} />}
        </RecordCard>
      </div>
    </div>
  )
}

function MarketSection({ rec, covers, onWeekClick }: { rec: BillboardRecords; covers: CoverMaps; onWeekClick: (week: string) => void }) {
  return (
    <div>
      <SectionHeader icon={BarChart3} title="每周大盘" subtitle="榜单整体走势——每周的竞争格局与新歌活力" />

      <RecordCard title="每周播放量排行 · Weekly Total Plays">
        <MiniRankTable rows={rec.week_total_plays} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '周次', render: (r) => <button onClick={() => onWeekClick(r.billboard_week)} className="font-sans text-[13px] font-semibold tabular-nums transition-colors hover:text-accent-foreground hover:underline">{fmtDate(r.billboard_week)}</button> },
          { header: '总播放', width: '165px', align: 'right', render: (r) => <ValueBar value={r.total_plays} max={rec.week_total_plays[0]?.total_plays ?? 1} /> },
          { header: <span className="pl-6">#1 歌曲</span>, render: (r) => r.no1_track ? <div className="pl-6"><TrackCell trackId={r.no1_track_id ?? undefined} trackName={r.no1_track} artistName={r.no1_track_artist ?? undefined} coverUrl={covers.track.get(r.no1_track_id ?? -1)} /></div> : <span className="pl-6 text-muted-foreground">—</span> },
          { header: <span className="pl-6">#1 专辑</span>, render: (r) => r.no1_album ? <div className="pl-6"><AlbumCell albumName={r.no1_album} artistName={r.no1_album_artist ?? ''} coverUrl={covers.album.get(r.no1_album)} /></div> : <span className="pl-6 text-muted-foreground">—</span> },
        ]} />
      </RecordCard>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        <RecordCard title="最激烈竞争 · Closest #1 vs #2" subtitle="冠亚军差距最小的周">
          {rec.closest_no1_vs_no2 && 'week' in rec.closest_no1_vs_no2 ? <FeaturedRecord label="毫厘之差" value={rec.closest_no1_vs_no2.gap_pct.toFixed(2)} unit="%" caption={`#1 ${rec.closest_no1_vs_no2.no1_track} vs #2 ${rec.closest_no1_vs_no2.no2_track} · ${fmtDate(rec.closest_no1_vs_no2.week)}`} /> : <p className="py-4 text-center font-sans text-[12px] text-muted-foreground">暂无数据</p>}
        </RecordCard>
        <RecordCard title="最悬殊碾压 · Largest #1 vs #2" subtitle="冠亚军差距最大的周">
          {rec.largest_no1_vs_no2 && 'week' in rec.largest_no1_vs_no2 ? <FeaturedRecord label="断层领先" value={rec.largest_no1_vs_no2.gap_pct.toFixed(2)} unit="%" caption={`#1 ${rec.largest_no1_vs_no2.no1_track} vs #2 ${rec.largest_no1_vs_no2.no2_track} · ${fmtDate(rec.largest_no1_vs_no2.week)}`} /> : <p className="py-4 text-center font-sans text-[12px] text-muted-foreground">暂无数据</p>}
        </RecordCard>
      </div>

      <RecordCard title="新歌活跃度 · New Entry Ratio" subtitle="每周新入榜歌曲占比趋势">
        <MiniRankTable rows={rec.new_entry_ratio} columns={[
          { header: '#', width: '48px', align: 'center', render: (_, idx) => <RankNum rank={idx + 1} /> },
          { header: '周次', render: (r) => <button onClick={() => onWeekClick(r.billboard_week)} className="font-sans text-[13px] font-semibold tabular-nums transition-colors hover:text-accent-foreground hover:underline">{fmtDate(r.billboard_week)}</button> },
          { header: '新入榜', width: '80px', align: 'center', render: (r) => <span className="font-sans text-[13px] tabular-nums text-muted-foreground">{r['新入榜歌曲数']}</span> },
          { header: '新歌占比', width: '145px', align: 'right', render: (r) => <ValueBar value={Math.round(r['新歌占比'])} max={100} suffix="%" /> },
        ]} />
      </RecordCard>
    </div>
  )
}

// ── Cover Maps ───────────────────────────────────────────────

interface CoverMaps { track: Map<number, string | null>; artist: Map<string, string | null>; album: Map<string, string | null> }

function buildCoverMaps(data: BillboardDataResponse): CoverMaps {
  const track = new Map<number, string | null>()
  const artist = new Map<string, string | null>()
  const album = new Map<string, string | null>()
  for (const e of data.weekly) { if (!track.has(e.track_id) && e.cover_url) track.set(e.track_id, e.cover_url) }
  for (const e of data.weekly_artist) { if (!artist.has(e.artist_name) && e.cover_url) artist.set(e.artist_name, e.cover_url) }
  for (const e of data.weekly) { if (!artist.has(e.artist_name) && e.cover_url) artist.set(e.artist_name, e.cover_url) }
  for (const e of data.weekly_album) { if (!album.has(e.album_name) && e.cover_url) album.set(e.album_name, e.cover_url) }
  return { track, artist, album }
}

// ══════════════════════════════════════════════════════════════
// Main Page
// ══════════════════════════════════════════════════════════════

export function RecordsPage() {
  const { data, loading, error, goToWeek } = useBillboard()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<TabKey>('championship')

  const covers = useMemo(() => {
    if (!data) return { track: new Map(), artist: new Map(), album: new Map() }
    return buildCoverMaps(data)
  }, [data])

  if (loading) return <LoadingSkeleton />

  if (error) {
    return (
      <div className="flex flex-col items-center gap-4 py-20 text-center">
        <AlertCircle className="h-8 w-8 text-accent-foreground" />
        <p className="font-sans text-[13px] text-muted-foreground">{error}</p>
      </div>
    )
  }

  if (!data) return null

  const rec: BillboardRecords = data.records

  const handleWeekClick = (week: string) => {
    goToWeek(week)
    navigate('/billboard')
  }

  return (
    <div className="mx-auto max-w-[1200px]">
      <BillboardSubNav active="records" />

      <section className="mt-6 mb-6">
        <p className="mb-4 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">Chart / Hall of Fame</p>
        <h1 className="font-serif text-[44px] font-bold leading-[1.06] tracking-[-1.2px]">榜单记录</h1>
      </section>

      <nav className="mb-8 flex gap-7 border-b border-border" role="tablist">
        {RECORD_TABS.map((tab) => (
          <button key={tab.key} role="tab" aria-selected={activeTab === tab.key} onClick={() => setActiveTab(tab.key)}
            className={cn('-mb-px border-none bg-transparent px-0 pb-2.5 font-sans text-[13px] font-medium transition-[color,border] duration-200 border-b-2', activeTab === tab.key ? 'border-accent-foreground font-semibold text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground')}>
            {tab.label}
          </button>
        ))}
      </nav>

      {activeTab === 'championship' && <ChampionshipSection rec={rec} covers={covers} onWeekClick={handleWeekClick} />}
      {activeTab === 'longevity' && <LongevitySection rec={rec} covers={covers} />}
      {activeTab === 'breakthrough' && <BreakthroughSection rec={rec} covers={covers} />}
      {activeTab === 'halloffame' && <HallOfFameSection rec={rec} covers={covers} />}
      {activeTab === 'curiosities' && <CuriositiesSection rec={rec} covers={covers} trackSummary={data.track_summary} artistTrackCounts={data.artist_track_counts} />}
      {activeTab === 'market' && <MarketSection rec={rec} covers={covers} onWeekClick={handleWeekClick} />}
    </div>
  )
}
