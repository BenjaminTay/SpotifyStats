/** Shared UI primitives for Playback Records — aligned with Billboard RecordsPrimitives. */

import { createContext, type ReactNode, useCallback, useContext, useState } from 'react'
import { createPortal } from 'react-dom'
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { GlassCard } from '@/components/shared/GlassCard'
import { displayName } from '@/lib/chinese'
import { cn } from '@/lib/utils'
import type { EntityRecordType, PlaybackRecordRow } from '@/types/analysis'

// ═══════════════════════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════════════════════

const fmtNum = (n: number) => new Intl.NumberFormat('zh-CN').format(n)

// ═══════════════════════════════════════════════════════════════════════════
// CoverImg
// ═══════════════════════════════════════════════════════════════════════════

function CoverImg({ url, size = 'sm' }: { url?: string | null; size?: 'sm' | 'md' }) {
  const dims = size === 'md' ? 'h-14 w-14' : 'h-10 w-10'
  if (url) {
    return (
      <img
        src={url}
        alt=""
        className={`${dims} shrink-0 rounded-[8px] object-cover`}
        loading="lazy"
        decoding="async"
      />
    )
  }
  return (
    <div className={`${dims} flex shrink-0 items-center justify-center rounded-[8px] bg-muted text-[18px]`}>
      🎵
    </div>
  )
}

function ArtistCoverImg({ url, size = 'sm' }: { url?: string | null; size?: 'sm' | 'md' }) {
  const dims = size === 'md' ? 'h-14 w-14' : 'h-10 w-10'
  if (url) {
    return (
      <img
        src={url}
        alt=""
        className={`${dims} shrink-0 rounded-full object-cover`}
        loading="lazy"
        decoding="async"
      />
    )
  }
  return (
    <div className={`${dims} flex shrink-0 items-center justify-center rounded-full bg-muted text-[18px]`}>
      🎤
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// Pagination Portal
// ═══════════════════════════════════════════════════════════════════════════

const PaginationPortalContext = createContext<HTMLElement | null>(null)

// ═══════════════════════════════════════════════════════════════════════════
// SectionHeader
// ═══════════════════════════════════════════════════════════════════════════

export function SectionHeader({
  icon: Icon,
  title,
  subtitle,
}: {
  icon: React.ElementType
  title: string
  subtitle?: string
}) {
  return (
    <div className="mb-6">
      <div className="mb-1 flex items-center gap-2">
        <Icon className="h-5 w-5 text-accent-foreground" />
        <h2 className="font-serif text-[28px] font-bold tracking-[-0.5px]">{title}</h2>
      </div>
      {subtitle && <p className="font-sans text-[13px] text-muted-foreground">{subtitle}</p>}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// EntityRecordToggle — matches Billboard's TrackAlbumToggle
// ═══════════════════════════════════════════════════════════════════════════

const ENTITY_LABELS: Record<EntityRecordType, string> = {
  track: '单曲',
  album: '专辑',
  artist: '艺人',
}

export function EntityRecordToggle({
  value,
  available,
  onChange,
}: {
  value: EntityRecordType
  available: EntityRecordType[]
  onChange: (v: EntityRecordType) => void
}) {
  if (available.length <= 1) return null
  return (
    <div className="flex items-center rounded-[6px] border border-border bg-muted/30 p-0.5">
      {available.map((et) => (
        <button
          key={et}
          onClick={() => onChange(et)}
          className={cn(
            'rounded-[4px] px-2.5 py-1 font-sans text-[11px] font-medium transition-colors',
            value === et
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground',
          )}
        >
          {ENTITY_LABELS[et]}
        </button>
      ))}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// RecordCard — matches Billboard's RecordCard
// ═══════════════════════════════════════════════════════════════════════════

export function RecordCard({
  title,
  subtitle,
  toggle,
  children,
}: {
  title: string
  subtitle?: string
  toggle?: ReactNode
  children: ReactNode
}) {
  const [portalTarget, setPortalTarget] = useState<HTMLDivElement | null>(null)
  const portalRef = useCallback((el: HTMLDivElement | null) => {
    setPortalTarget(el)
  }, [])

  return (
    <PaginationPortalContext.Provider value={portalTarget}>
      <GlassCard className="mb-5 p-5">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h3 className="font-serif text-[18px] font-bold tracking-[-0.3px]">{title}</h3>
            {subtitle && (
              <p className="mt-0.5 font-sans text-[11px] text-muted-foreground">{subtitle}</p>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-3">
            {toggle}
            <div ref={portalRef} />
          </div>
        </div>
        {children}
      </GlassCard>
    </PaginationPortalContext.Provider>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// FeaturedRecord — matches Billboard's FeaturedRecord
// ═══════════════════════════════════════════════════════════════════════════

export function FeaturedRecord({
  label,
  value,
  unit,
  caption,
  linkTo,
  coverUrl,
  coverRound,
}: {
  label: string
  value: string | number
  unit?: string
  caption?: string
  linkTo?: string
  coverUrl?: string | null
  coverRound?: boolean
}) {
  const content = (
    <div
      className={cn(
        'flex items-start gap-4 rounded-[12px] border border-border bg-muted/20 p-5',
        linkTo && 'transition-colors hover:bg-muted/40',
      )}
    >
      {coverRound ? (
        <ArtistCoverImg url={coverUrl} size="md" />
      ) : (
        <CoverImg url={coverUrl} size="md" />
      )}
      <div className="min-w-0">
        <p className="mb-1 font-sans text-[11px] font-semibold uppercase tracking-[1.2px] text-muted-foreground">
          {label}
        </p>
        <p className="font-serif text-[40px] font-bold leading-[1.1] tracking-[-1px] tabular-nums">
          {typeof value === 'number' ? fmtNum(value) : value}
          {unit && (
            <span className="ml-1 font-sans text-[16px] font-normal text-muted-foreground">
              {unit}
            </span>
          )}
        </p>
        {caption && (
          <p className="mt-2 font-sans text-[12px] text-muted-foreground">{caption}</p>
        )}
      </div>
    </div>
  )

  if (linkTo) {
    return <Link to={linkTo}>{content}</Link>
  }
  return content
}

// ═══════════════════════════════════════════════════════════════════════════
// MiniRankTable — matches Billboard's MiniRankTable
// ═══════════════════════════════════════════════════════════════════════════

interface ColumnDef {
  header: string
  width?: string
  align?: 'left' | 'right' | 'center'
  render: (row: PlaybackRecordRow, idx: number) => ReactNode
}

export function MiniRankTable({
  rows,
  columns,
  emptyText = '暂无数据',
  fixed,
}: {
  rows: PlaybackRecordRow[]
  columns: ColumnDef[]
  emptyText?: string
  fixed?: boolean
}) {
  const [page, setPage] = useState(0)
  const perPage = 10
  const totalPages = Math.max(1, Math.ceil(rows.length / perPage))
  const start = page * perPage
  const pageRows = rows.slice(start, start + perPage)
  const minTableWidth = columns.every((col) => col.width?.endsWith('px'))
    ? `${columns.reduce((sum, col) => sum + Number.parseInt(col.width ?? '0', 10), 0)}px`
    : undefined

  if (rows.length === 0) {
    return <p className="py-4 text-center font-sans text-[12px] text-muted-foreground">{emptyText}</p>
  }

  const paginationBar = (
    <div className="flex items-center gap-1.5 font-sans text-[12px] tabular-nums text-muted-foreground">
      <span>
        {rows.length === 0 ? '0' : fmtNum(start + 1)}—{fmtNum(Math.min(start + perPage, rows.length))}{' '}
        / {fmtNum(rows.length)}
      </span>
      <button
        onClick={() => setPage(0)}
        disabled={page === 0}
        className="p-0.5 disabled:opacity-30"
        aria-label="第一页"
      >
        <ChevronsLeft className="h-3 w-3" />
      </button>
      <button
        onClick={() => setPage((p) => Math.max(0, p - 1))}
        disabled={page === 0}
        className="p-0.5 disabled:opacity-30"
        aria-label="上一页"
      >
        <ChevronLeft className="h-3 w-3" />
      </button>
      <button
        onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
        disabled={page >= totalPages - 1}
        className="p-0.5 disabled:opacity-30"
        aria-label="下一页"
      >
        <ChevronRight className="h-3 w-3" />
      </button>
      <button
        onClick={() => setPage(totalPages - 1)}
        disabled={page >= totalPages - 1}
        className="p-0.5 disabled:opacity-30"
        aria-label="最后一页"
      >
        <ChevronsRight className="h-3 w-3" />
      </button>
    </div>
  )

  const portalTarget = useContext(PaginationPortalContext)
  const pagination = totalPages > 1 ? (
    portalTarget ? (
      createPortal(paginationBar, portalTarget)
    ) : (
      <div className="mb-3 flex justify-end">{paginationBar}</div>
    )
  ) : null

  return (
    <div>
      {!portalTarget && pagination}
      <div className="overflow-x-auto">
        <table className={cn('w-full', fixed && 'table-fixed')} style={minTableWidth ? { minWidth: minTableWidth } : undefined}>
          <thead>
            <tr className="border-b border-border">
              {columns.map((col, i) => (
                <th
                  key={i}
                  className={cn(
                    'whitespace-nowrap pb-2 font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground',
                    col.align === 'right' && 'text-right',
                    col.align === 'center' && 'text-center',
                  )}
                  style={col.width ? { width: col.width } : undefined}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageRows.map((row, i) => (
              <tr
                key={start + i}
                className="border-b border-border/50 transition-colors hover:bg-muted/30"
              >
                {columns.map((col, j) => (
                  <td
                    key={j}
                    className={cn(
                      'py-2.5',
                      col.align === 'right' && 'text-right',
                      col.align === 'center' && 'text-center',
                    )}
                  >
                    {col.render(row, start + i)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {portalTarget && pagination}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// Cell renderers
// ═══════════════════════════════════════════════════════════════════════════

export function RankNum({ rank }: { rank: number }) {
  return (
    <span className="font-serif text-[20px] font-semibold tabular-nums">
      {String(rank).padStart(2, '0')}
    </span>
  )
}

export function TrackCell({
  trackId,
  name,
  artistName,
  coverUrl,
}: {
  trackId?: string | null
  name: string
  artistName?: string | null
  coverUrl?: string | null
}) {
  return (
    <div className="flex items-center gap-2.5 min-w-0">
      <CoverImg url={coverUrl} />
      <div className="min-w-0 truncate">
        {trackId ? (
          <Link
            to={`/music/tracks/${encodeURIComponent(trackId)}`}
            className="block truncate font-sans text-[14px] font-medium text-foreground hover:text-accent-foreground"
          >
            {displayName(name)}
          </Link>
        ) : (
          <span className="block truncate font-sans text-[14px] font-medium">{displayName(name)}</span>
        )}
        {artistName && (
          <p className="truncate font-sans text-[11px] italic text-muted-foreground">{displayName(artistName)}</p>
        )}
      </div>
    </div>
  )
}

export function ArtistCell({ name, coverUrl }: { name: string; coverUrl?: string | null }) {
  return (
    <div className="flex items-center gap-2.5 min-w-0">
      <ArtistCoverImg url={coverUrl} />
      <Link
        to={`/music/artists/${encodeURIComponent(name)}`}
        className="truncate font-sans text-[14px] font-medium text-foreground hover:text-accent-foreground"
      >
        {displayName(name)}
      </Link>
    </div>
  )
}

export function AlbumCell({
  name,
  artistName,
  coverUrl,
}: {
  name: string
  artistName?: string | null
  coverUrl?: string | null
}) {
  return (
    <div className="flex items-center gap-2.5 min-w-0">
      <CoverImg url={coverUrl} />
      <div className="min-w-0 truncate">
        <span className="block truncate font-sans text-[14px] font-medium">{displayName(name)}</span>
        {artistName && (
          <p className="truncate font-sans text-[11px] italic text-muted-foreground">{displayName(artistName)}</p>
        )}
      </div>
    </div>
  )
}

export function ValueBar({ value, max, suffix }: { value: number; max: number; suffix?: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="inline-block w-[52px] text-right font-sans text-[14px] font-semibold tabular-nums">
        {typeof value === 'number' && value % 1 !== 0 ? value.toFixed(1) : fmtNum(value)}
      </span>
      <span className="inline-block h-[3px] w-[56px] rounded-[2px] bg-muted">
        <span
          className="block h-full rounded-[2px] bg-accent-foreground transition-[width]"
          style={{ width: `${pct}%` }}
        />
      </span>
      {suffix && (
        <span className="font-sans text-[11px] font-normal text-muted-foreground">{suffix}</span>
      )}
    </span>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// EntityRecordCard — combined RecordCard + toggle + table
// ═══════════════════════════════════════════════════════════════════════════

export function EntityRecordCard({
  title,
  subtitle,
  recordsByEntity,
  defaultEntity = 'track',
  columns,
  emptyText = '暂无数据',
}: {
  title: string
  subtitle?: string
  recordsByEntity: Partial<Record<EntityRecordType, PlaybackRecordRow[]>>
  defaultEntity?: EntityRecordType
  columns: (entity: EntityRecordType) => ColumnDef[]
  emptyText?: string
}) {
  const allAvailable = (Object.keys(recordsByEntity) as EntityRecordType[]).filter(
    (k) => recordsByEntity[k] !== undefined,
  )
  const available = allAvailable.filter(
    (k) => recordsByEntity[k] && recordsByEntity[k]!.length > 0,
  )
  const initial = available.includes(defaultEntity) ? defaultEntity : available[0] ?? allAvailable[0] ?? 'track'
  const [entity, setEntity] = useState<EntityRecordType>(initial)

  const rows = recordsByEntity[entity] ?? []

  return (
    <RecordCard
      title={title}
      subtitle={subtitle}
      toggle={
        <EntityRecordToggle
          value={entity}
          available={allAvailable}
          onChange={setEntity}
        />
      }
    >
      <MiniRankTable rows={rows} columns={columns(entity)} emptyText={emptyText} />
    </RecordCard>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// Section fallback (skeleton)
// ═══════════════════════════════════════════════════════════════════════════

export function SectionFallback() {
  return (
    <div className="space-y-5">
      {[1, 2, 3].map((i) => (
        <div key={i} className="glass-card animate-pulse rounded-[16px] p-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <div className="mb-1 h-[22px] w-48 rounded bg-muted/50" />
              <div className="h-3 w-64 rounded bg-muted/30" />
            </div>
            <div className="h-7 w-28 rounded-[6px] bg-muted/30" />
          </div>
          <div className="space-y-2.5">
            {[1, 2, 3].map((j) => (
              <div key={j} className="h-10 w-full rounded bg-muted/20" />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
