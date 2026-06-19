import { Link } from 'react-router-dom'

import { CoverCell } from '@/components/shared/CoverCell'
import { GlassCard } from '@/components/shared/GlassCard'
import { displayName } from '@/lib/chinese'
import type { ReleaseCycleArtistOverviewResponse } from '@/types/billboard'
import { formatDateShort, formatOptionalRank } from './MusicDetailPrimitives'

type ArtistReleaseCycle = ReleaseCycleArtistOverviewResponse['cycles'][number]

type ReleaseCoverSource = {
  cover_url?: string | null
  db_album_id?: number | null
}

function releaseCoverUrl(item: ReleaseCoverSource): string | null {
  if (item.cover_url) return item.cover_url
  if (item.db_album_id != null) return `/covers/albums/${item.db_album_id}.jpg`
  return null
}

function formatReleaseType(type: string): string {
  if (type === 'album') return '专辑'
  if (type === 'single') return '单曲'
  return type
}

function MiniReleaseStat({
  label,
  value,
  accent,
}: {
  label: string
  value: string
  accent?: boolean
}) {
  return (
    <div>
      <p className="font-sans text-[9px] font-bold uppercase tracking-[1px] text-muted-foreground">
        {label}
      </p>
      <p
        className="mt-1 font-serif text-[22px] font-bold leading-none"
        style={accent ? { color: 'var(--accent-foreground)' } : undefined}
      >
        {value}
      </p>
    </div>
  )
}

export function ReleaseCycleSection({
  title,
  cycles,
  artistName,
  startIndex = 0,
}: {
  title: string
  cycles: ArtistReleaseCycle[]
  artistName: string
  startIndex?: number
}) {
  return (
    <div className="mb-5 last:mb-0">
      <div className="mb-3 flex items-end justify-between border-b border-border pb-2">
        <p className="font-sans text-[11px] font-bold uppercase tracking-[1.4px] text-muted-foreground">
          {title}
        </p>
        <p className="font-sans text-[11px] text-muted-foreground">{cycles.length} 个发行</p>
      </div>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {cycles.map((cycle, index) => (
          <GlassCard key={`${cycle.album_name}-${cycle.release_date}`} className="p-5">
            <div className="flex items-start gap-4">
              <CoverCell index={startIndex + index} coverUrl={releaseCoverUrl(cycle)} label={displayName(cycle.album_name)} />
              <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <p className="truncate font-sans text-[14px] font-semibold">
                      {displayName(cycle.album_name)}
                    </p>
                    <p className="mt-1 font-sans text-[12px] text-muted-foreground">
                      {formatDateShort(cycle.release_date)} · {formatReleaseType(cycle.album_type)}
                    </p>
                  </div>
                  <Link
                    to={`/music/albums/${encodeURIComponent(cycle.album_name)}?artist=${encodeURIComponent(artistName)}`}
                    className="shrink-0 font-sans text-[12px] font-semibold text-accent-foreground transition-opacity hover:opacity-80"
                  >
                    查看
                  </Link>
                </div>
                <div className="mt-4 grid grid-cols-4 gap-3">
                  <MiniReleaseStat label="空降" value={formatOptionalRank(cycle.metrics.debut_rank)} />
                  <MiniReleaseStat
                    label="Peak"
                    value={formatOptionalRank(cycle.metrics.peak_rank)}
                    accent={cycle.metrics.peak_rank === 1}
                  />
                  <MiniReleaseStat label="在榜" value={`${cycle.metrics.weeks_on_chart || 0}`} />
                  <MiniReleaseStat
                    label="冲击"
                    value={cycle.metrics.artist_impact_fmt ?? (cycle.metrics.artist_impact != null ? cycle.metrics.artist_impact.toFixed(2) : '—')}
                  />
                </div>
                {cycle.sub_albums && (
                  <p className="mt-3 line-clamp-2 font-sans text-[11px] text-muted-foreground">
                    含合并子版本
                  </p>
                )}
              </div>
            </div>
          </GlassCard>
        ))}
      </div>
    </div>
  )
}
