import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useViewportMode } from '@/hooks/useViewportMode'
import { displayName } from '@/lib/chinese'
import type { EntityRecordFamily, EntityRecordType, PlaybackRecordRow } from '@/types/analysis'
import { EntityRecordToggle, RecordCard } from './PlaybackRecordsPrimitives'

const SEGMENTS = [
  { label: '0:00-7:00', start: 0, end: 7 },
  { label: '8:00-15:00', start: 8, end: 15 },
  { label: '16:00-23:00', start: 16, end: 23 },
] as const

const ENTITY_HEADERS: Record<EntityRecordType, string> = {
  track: '歌曲',
  album: '专辑',
  artist: '艺人',
}

function hourOf(row: PlaybackRecordRow) {
  const hour = Number.parseInt(row.date ?? '', 10)
  return Number.isFinite(hour) ? hour : -1
}

function EntityName({ row, entity }: { row: PlaybackRecordRow; entity: EntityRecordType }) {
  const name = displayName(row.name)
  const className = 'font-sans text-[12px] font-medium leading-[1.35] text-foreground break-words hover:text-accent-foreground'
  if (entity === 'artist') {
    return <Link to={`/music/artists/${encodeURIComponent(row.name)}`} className={className}>{name}</Link>
  }
  if (entity === 'album') {
    const query = row.artist_name ? `?artist=${encodeURIComponent(row.artist_name)}` : ''
    return (
      <div className="min-w-0">
        <Link to={`/music/albums/${encodeURIComponent(row.name)}${query}`} className={className}>{name}</Link>
        {row.artist_name && <p className="mt-0.5 font-sans text-[10px] italic leading-tight text-muted-foreground break-words">{displayName(row.artist_name)}</p>}
      </div>
    )
  }
  return (
    <div className="min-w-0">
      {row.entity_id ? (
        <Link to={`/music/tracks/${encodeURIComponent(row.entity_id)}`} className={className}>{name}</Link>
      ) : <span className={className}>{name}</span>}
      {row.artist_name && <p className="mt-0.5 font-sans text-[10px] italic leading-tight text-muted-foreground break-words">{displayName(row.artist_name)}</p>}
    </div>
  )
}

function EntityArtwork({ row, entity }: { row: PlaybackRecordRow; entity: EntityRecordType }) {
  const round = entity === 'artist' ? 'rounded-full' : 'rounded-[7px]'
  return (
    <span aria-hidden="true" className={`relative flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden border border-border/70 bg-muted text-[13px] ${round}`}>
      {entity === 'artist' ? '🎤' : '🎵'}
      {row.cover_url && (
        <img
          src={row.cover_url}
          alt=""
          className="absolute inset-0 h-full w-full object-cover"
          loading="lazy"
          decoding="async"
          onError={(event) => { event.currentTarget.style.display = 'none' }}
        />
      )}
    </span>
  )
}

function HourEntity({ row, entity }: { row?: PlaybackRecordRow; entity: EntityRecordType }) {
  if (!row) return <span className="text-muted-foreground">—</span>
  return (
    <div className="flex min-w-0 items-center gap-2">
      <EntityArtwork row={row} entity={entity} />
      <div className="min-w-0 flex-1"><EntityName row={row} entity={entity} /></div>
    </div>
  )
}

export function HourlySegmentsCard({ records }: { records: EntityRecordFamily }) {
  const isPhone = useViewportMode() === 'phone'
  const available = (['track', 'album', 'artist'] as EntityRecordType[]).filter((key) => records[key]?.length > 0)
  const [selected, setSelected] = useState<EntityRecordType>(available[0] ?? 'track')
  const [segmentIndex, setSegmentIndex] = useState(0)
  const active = available.includes(selected) ? selected : (available[0] ?? 'track')
  const byHour = useMemo(() => new Map((records[active] ?? []).map((row) => [hourOf(row), row])), [active, records])
  const displayedSegments = isPhone ? [SEGMENTS[segmentIndex]] : SEGMENTS

  return (
    <RecordCard
      title="时段统计 · Hourly Patterns"
      subtitle="每小时播放冠军；按一天的三个八小时区段并排对照"
      toggle={<EntityRecordToggle value={active} available={available} onChange={setSelected} />}
    >
      {available.length === 0 ? (
        <p className="py-6 text-center font-sans text-[12px] text-muted-foreground">暂无时段统计</p>
      ) : (
        <>
          {isPhone && (
            <div className="mobile-record-time-segments" role="tablist" aria-label="选择八小时时段">
              {SEGMENTS.map((segment, index) => (
                <button
                  key={segment.label}
                  type="button"
                  role="tab"
                  aria-selected={segmentIndex === index}
                  onClick={() => setSegmentIndex(index)}
                >
                  {segment.label}
                </button>
              ))}
            </div>
          )}
          <div
            role="table"
            aria-label={`${ENTITY_HEADERS[active]}每小时时段冠军`}
            className="hidden grid-cols-3 gap-x-4 lg:grid"
          >
            {SEGMENTS.map((segment) => (
              <div key={`${segment.label}-header`} role="row" className="grid min-w-0 grid-cols-[52px_minmax(0,1fr)_52px] rounded-t-[12px] border border-border/70 bg-muted/10 font-sans text-[9px] font-bold uppercase tracking-[0.9px] text-muted-foreground">
                <span role="columnheader" className="px-2 py-2">时段</span>
                <span role="columnheader" className="px-1 py-2">{ENTITY_HEADERS[active]}</span>
                <span role="columnheader" className="px-2 py-2 text-right">次数</span>
              </div>
            ))}
            {Array.from({ length: 8 }, (_, offset) => offset).flatMap((offset) =>
              SEGMENTS.map((segment) => {
                const hour = segment.start + offset
                const row = byHour.get(hour)
                return (
                  <div
                    key={hour}
                    role="row"
                    data-hour-offset={offset}
                    className={`grid min-w-0 grid-cols-[52px_minmax(0,1fr)_52px] items-center border-x border-b border-border/70 bg-muted/10 ${offset === 7 ? 'rounded-b-[12px]' : ''}`}
                  >
                    <span role="cell" className="px-2 py-2.5 font-sans text-[11px] font-medium tabular-nums text-muted-foreground">{String(hour).padStart(2, '0')}:00</span>
                    <span role="cell" className="min-w-0 px-1 py-2.5"><HourEntity row={row} entity={active} /></span>
                    <span role="cell" className="px-2 py-2.5 text-right font-serif text-[16px] font-semibold tabular-nums">{row?.value ?? '—'}</span>
                  </div>
                )
              }),
            )}
          </div>
          <div className="grid grid-cols-1 gap-4 lg:hidden">
          {displayedSegments.map((segment) => (
            <section key={segment.label} aria-label={`${segment.label} ${ENTITY_HEADERS[active]}时段冠军`} className="min-w-0 overflow-hidden rounded-[12px] border border-border/70 bg-muted/10">
              <table className="w-full table-fixed">
                <colgroup><col className="w-[52px]" /><col /><col className="w-[44px]" /></colgroup>
                <thead>
                  <tr className="border-b border-border/50 font-sans text-[9px] font-bold uppercase tracking-[0.9px] text-muted-foreground">
                    <th className="px-2 py-2 text-left">时段</th>
                    <th className="px-1 py-2 text-left">{ENTITY_HEADERS[active]}</th>
                    <th className="px-2 py-2 text-right">次数</th>
                  </tr>
                </thead>
                <tbody>
                  {Array.from({ length: 8 }, (_, offset) => segment.start + offset).map((hour) => {
                    const row = byHour.get(hour)
                    return (
                      <tr key={hour} className="border-b border-border/40 last:border-0 align-middle">
                        <td className="px-2 py-2.5 align-middle font-sans text-[11px] font-medium tabular-nums text-muted-foreground">{String(hour).padStart(2, '0')}:00</td>
                        <td className="min-w-0 px-1 py-2.5 align-middle"><HourEntity row={row} entity={active} /></td>
                        <td className="px-2 py-2.5 align-middle text-right font-serif text-[16px] font-semibold tabular-nums">{row?.value ?? '—'}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </section>
          ))}
          </div>
        </>
      )}
    </RecordCard>
  )
}
