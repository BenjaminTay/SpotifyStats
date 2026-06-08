import { createContext, useContext, useEffect, useState } from 'react'
import type { ComponentType, ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router-dom'
import { ChevronLeft, ChevronRight } from 'lucide-react'

import { GlassCard } from '@/components/shared/GlassCard'
import { cn } from '@/lib/utils'
import { displayName } from '@/lib/chinese'

// ── helpers ──────────────────────────────────────────────────

export function fmtNum(n: number): string { return new Intl.NumberFormat('zh-CN').format(n) }
export function fmtDate(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso + 'T00:00:00')
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`
}

// ── shared sub-components ────────────────────────────────────

export function CoverImg({ url }: { url?: string | null }) {
  const [imgError, setImgError] = useState(false)
  useEffect(() => { setImgError(false) }, [url])
  if (url && !imgError) return <img src={url} alt="" className="h-10 w-10 shrink-0 rounded-[8px] object-cover" onError={() => setImgError(true)} loading="lazy" />
  return <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[8px] bg-muted text-base">🎵</div>
}

export function ArtistCoverImg({ url, size }: { url?: string | null; size?: 'sm' | 'md' }) {
  const [imgError, setImgError] = useState(false)
  useEffect(() => { setImgError(false) }, [url])
  const cls = size === 'sm' ? 'h-10 w-10' : 'h-14 w-14'
  if (url && !imgError) return <img src={url} alt="" className={cn(cls, 'shrink-0 rounded-full object-cover')} onError={() => setImgError(true)} loading="lazy" />
  return <div className={cn(cls, 'flex shrink-0 items-center justify-center rounded-full bg-muted text-base')}>🎤</div>
}

export function ValueBar({ value, max, suffix }: { value: number; max: number; suffix?: string }) {
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

export function SectionHeader({ icon: Icon, title, subtitle }: { icon: ComponentType<{ className?: string }>; title: string; subtitle: string }) {
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

export type EntityType = 'track' | 'album'

export function TrackAlbumToggle({ value, onChange }: { value: EntityType; onChange: (v: EntityType) => void }) {
  return (
    <div className="flex items-center rounded-[6px] border border-border bg-muted/30 p-0.5">
      <button onClick={() => onChange('track')} className={cn('rounded-[4px] px-2.5 py-1 font-sans text-[11px] font-medium transition-colors', value === 'track' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')}>单曲</button>
      <button onClick={() => onChange('album')} className={cn('rounded-[4px] px-2.5 py-1 font-sans text-[11px] font-medium transition-colors', value === 'album' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')}>专辑</button>
    </div>
  )
}

const PaginationPortalCtx = createContext<HTMLDivElement | null>(null)

export function RecordCard({ title, subtitle, toggle, children }: { title: string; subtitle?: string; toggle?: ReactNode; children: ReactNode }) {
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

export function FeaturedRecord({ label, value, unit, caption, linkTo, coverUrl }: {
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

export function MiniRankTable<T extends object>({ rows, columns, emptyText = '暂无数据', fixed }: {
  rows: T[]; columns: { header: ReactNode; width?: string; align?: 'left' | 'right' | 'center'; render: (row: T, idx: number) => ReactNode }[]; emptyText?: string; fixed?: boolean
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

export function RankNum({ rank }: { rank: number }) { return <span className="font-serif text-[20px] font-semibold tabular-nums">{String(rank).padStart(2, '0')}</span> }

export function PeakNum({ rank }: { rank: number }) {
  const colorCls = rank === 1 ? 'text-accent-foreground'
    : rank === 2 ? 'text-muted-foreground'
    : rank === 3 ? 'text-[#C17A4E] dark:text-[#C97B6B]'
    : 'text-muted-foreground'
  return <span className={cn('font-serif text-[22px] font-semibold tabular-nums', colorCls)}>{String(rank).padStart(2, '0')}</span>
}

export function TrackCell({ trackId, trackName, artistName, coverUrl }: { trackId?: number; trackName: string; artistName?: string; coverUrl?: string | null }) {
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

export function ArtistCell({ artistName, coverUrl }: { artistName: string; coverUrl?: string | null }) {
  return (
    <div className="flex items-center gap-3">
      <ArtistCoverImg url={coverUrl} />
      <Link to={`/music/artists/${encodeURIComponent(artistName)}`} className="font-sans text-[13px] font-semibold transition-colors hover:text-accent-foreground">{displayName(artistName)}</Link>
    </div>
  )
}

export function AlbumCell({ albumName, artistName, coverUrl }: { albumName: string; artistName: string; coverUrl?: string | null }) {
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
