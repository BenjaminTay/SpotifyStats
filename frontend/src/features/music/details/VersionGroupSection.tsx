import { useState } from 'react'
import { Link } from 'react-router'
import { ChevronDown, ChevronUp, Disc, Layers } from 'lucide-react'
import { GlassCard } from '@/components/shared/GlassCard'
import type { TrackVersionGroup, AlbumVersionGroup, AlbumSourceBreakdownItem } from '@/types/billboard'
import { VersionCoverageMatrix } from './VersionCoverageMatrix'

interface Props {
  kind: 'track' | 'album'
  data: TrackVersionGroup | AlbumVersionGroup
  /** Per-bucket source breakdown from album project (album kind only). */
  sourceBreakdown?: AlbumSourceBreakdownItem[] | null
  /** Keep advanced source details collapsed on compact presentations. */
  collapsible?: boolean
}

const SCOPE_LABELS: Record<string, string> = {
  recording: '同录音',
  release: '同发行组',
  composition: '同作品',
}

const RECORDING_KIND_LABELS: Record<string, string> = {
  remastered: 'Remastered',
  acoustic: 'Acoustic',
  live: 'Live',
  remix: 'Remix',
  instrumental: 'Instrumental',
  radio_edit: 'Radio Edit',
  demo: 'Demo',
  clean_explicit: 'Clean/Explicit',
  deluxe: 'Deluxe',
}

const BUCKET_LABELS: Record<string, string> = {
  original_album: '原版专辑',
  deluxe: '豪华版/扩展版',
  single: '单曲版',
  compilation: '精选集/合辑',
  live_acoustic_remix: 'Live / Acoustic / Remix',
  rerecord: '重录版本',
  other: '其他来源',
  inferred: '推断来源',
}

export function VersionGroupSection({ kind, data, sourceBreakdown, collapsible = false }: Props) {
  const [open, setOpen] = useState(false)

  const hasSourceBreakdown = kind === 'album' && sourceBreakdown && sourceBreakdown.length > 0
  const scopeLabel = SCOPE_LABELS[data.scope] ?? data.scope
  const Chevron = open ? ChevronUp : ChevronDown
  const albumData = kind === 'album' ? (data as AlbumVersionGroup) : null
  const isAlbum = kind === 'album'

  // Build unified table rows (album: enriched from sourceBreakdown; track: from versions)
  interface Row {
    key: string
    name: string | null
    artist: string | null
    cover: string | null
    plays: number
    albumId: number | null
    bucket: string | null
    uniqueTracks: number | null
    releaseDate: string | null
    isPrimary: boolean
    trackId: number | null
    recordingKind: string | null
  }
  const rows: Row[] = (() => {
    if (kind === 'album' && sourceBreakdown && sourceBreakdown.length > 0) {
      const versionById = new Map<number, (typeof data.versions)[number]>()
      for (const v of data.versions) {
        if (v.album_id != null) versionById.set(v.album_id, v)
      }
      return sourceBreakdown.map((item) => {
        const v = item.source_album_id != null ? versionById.get(item.source_album_id) : undefined
        return {
          key: `${item.source_bucket}-${item.source_album_id ?? 'none'}`,
          name: item.source_album_name,
          artist: v?.artist_name ?? null,
          cover: item.album_cover_url ?? v?.album_cover_url ?? null,
          plays: item.play_count,
          albumId: item.source_album_id,
          bucket: item.source_bucket,
          uniqueTracks: item.track_count ?? v?.unique_tracks ?? null,
          releaseDate: item.release_date ?? v?.release_date ?? null,
          isPrimary: v?.is_primary ?? false,
          trackId: null,
          recordingKind: null,
        }
      })
    }
    // Track mode or no sourceBreakdown: use raw versions
    return data.versions.map((v) => ({
      key: String(v.album_id ?? v.track_id ?? ''),
      name: v.album_name ?? v.track_name ?? '',
      artist: v.artist_name ?? null,
      cover: v.album_cover_url ?? null,
      plays: v.plays,
      albumId: v.album_id ?? null,
      bucket: null,
      uniqueTracks: v.unique_tracks ?? null,
      releaseDate: v.release_date ?? null,
      isPrimary: v.is_primary ?? false,
      trackId: v.track_id ?? null,
      recordingKind: v.recording_kind ?? null,
    }))
  })()

  const totalPlays = rows.reduce((s, r) => s + r.plays, 0) || data.total_plays || data.versions.reduce((s, v) => s + v.plays, 0)

  if (!hasSourceBreakdown && (!data.versions || data.versions.length < 2)) return null

  const tableContent = (
    <div className={isAlbum ? 'px-4 py-3' : ''}>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-muted-foreground text-xs border-b border-border/30">
              <th className="text-left py-2 pr-4 font-medium">版本</th>
              <th className="text-right py-2 pr-3 font-medium">播放</th>
              <th className="text-right py-2 pr-3 font-medium w-[80px]">占比</th>
              {isAlbum && (
                <th className="text-right py-2 pr-4 font-medium">曲目</th>
              )}
              <th className="text-center py-2 font-medium w-16">标记</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const ratio = totalPlays > 0 ? (row.plays / totalPlays) * 100 : 0
              return (
                <tr
                  key={row.key}
                  className="border-b border-border/20 last:border-0 hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                >
                  <td className="py-2 pr-4">
                    <div className="flex items-center gap-2">
                      {row.cover && (
                        <img
                          src={row.cover}
                          alt=""
                          className="w-8 h-8 rounded object-cover flex-shrink-0"
                          loading="lazy"
                        />
                      )}
                      <div className="min-w-0">
                        {isAlbum && row.albumId != null && row.name ? (
                          <Link
                            to={`/music/albums/${encodeURIComponent(row.name)}?artist=${encodeURIComponent(row.artist ?? '')}`}
                            className="text-primary hover:underline block truncate"
                          >
                            {row.name}
                          </Link>
                        ) : !isAlbum && row.trackId != null ? (
                          <Link
                            to={`/music/tracks/${row.trackId}`}
                            className="text-primary hover:underline block truncate"
                          >
                            {row.name ?? `Track #${row.trackId}`}
                          </Link>
                        ) : (
                          <span className="text-muted-foreground truncate block">{row.name ?? '—'}</span>
                        )}
                        {!isAlbum && row.recordingKind && (
                          <span className="inline-block mt-0.5 text-[10px] text-muted-foreground bg-muted/40 rounded px-1 py-px">
                            {RECORDING_KIND_LABELS[row.recordingKind] ?? row.recordingKind}
                          </span>
                        )}
                        {row.releaseDate && (
                          <span className="block text-[11px] text-muted-foreground/70 mt-0.5">
                            {row.releaseDate}
                          </span>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums font-mono text-xs">
                    {row.plays.toLocaleString()}
                  </td>
                  <td className="py-2 pr-3 text-right w-[80px]">
                    <div className="flex items-center gap-1.5">
                      <div className="flex-1 h-1.5 rounded-full bg-muted/30 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-primary/60"
                          style={{ width: `${Math.min(ratio, 100)}%` }}
                        />
                      </div>
                      <span className="text-[11px] tabular-nums font-mono text-muted-foreground w-9 text-right">
                        {ratio.toFixed(0)}%
                      </span>
                    </div>
                  </td>
                  {isAlbum && (
                    <td className="py-2 pr-4 text-right tabular-nums font-mono text-xs">
                      {row.uniqueTracks != null ? row.uniqueTracks : '—'}
                    </td>
                  )}
                  <td className="py-2 text-center">
                    {isAlbum && row.bucket ? (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-muted/40 text-muted-foreground">
                        {BUCKET_LABELS[row.bucket] ?? row.bucket}
                      </span>
                    ) : row.isPrimary ? (
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-primary/10 text-primary">
                        <Disc className="w-2.5 h-2.5" />
                        主版本
                      </span>
                    ) : null}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <VersionCoverageMatrix albumData={albumData} compact={isAlbum} />
    </div>
  )

  if (isAlbum) {
    return (
      <GlassCard className="mb-6">
        {collapsible ? (
          <button
            type="button"
            className="flex w-full items-center justify-between rounded-xl px-4 py-3 text-left transition-colors hover:bg-black/5 dark:hover:bg-white/5"
            aria-expanded={open}
            onClick={() => setOpen(!open)}
          >
            <span className="flex items-center gap-2.5">
              <Layers className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">版本与来源</span>
              <small className="text-xs text-muted-foreground">按需查看</small>
            </span>
            <Chevron className="h-4 w-4 text-muted-foreground" />
          </button>
        ) : (
          <div className="flex items-center gap-2.5 px-4 py-3">
            <Layers className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">版本来源拆分</span>
          </div>
        )}
        {(!collapsible || open) && tableContent}
      </GlassCard>
    )
  }

  return (
    <GlassCard className="mb-6">
      <button
        type="button"
        className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-black/5 dark:hover:bg-white/5 rounded-xl transition-colors"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-2.5">
          <Layers className="w-4 h-4 text-muted-foreground" />
          <span className="font-medium text-sm">{data.canonical_name}</span>
          <span className="text-xs text-muted-foreground">
            · {data.versions.length} 个版本 · {scopeLabel}
          </span>
        </div>
        <Chevron className="w-4 h-4 text-muted-foreground" />
      </button>

      {open && tableContent}
    </GlassCard>
  )
}
