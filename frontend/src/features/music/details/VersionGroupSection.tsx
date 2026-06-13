import { useState } from 'react'
import { Link } from 'react-router'
import { ChevronDown, ChevronUp, Disc, Layers, Star } from 'lucide-react'
import { GlassCard } from '@/components/shared/GlassCard'
import type { TrackVersionGroup, AlbumVersionGroup } from '@/types/billboard'
import { cn } from '@/lib/utils'

interface Props {
  kind: 'track' | 'album'
  data: TrackVersionGroup | AlbumVersionGroup
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

export function VersionGroupSection({ kind, data }: Props) {
  const [open, setOpen] = useState(false)

  if (!data.versions || data.versions.length < 2) return null

  const scopeLabel = SCOPE_LABELS[data.scope] ?? data.scope
  const Chevron = open ? ChevronUp : ChevronDown
  const totalPlays = data.total_plays || data.versions.reduce((s, v) => s + v.plays, 0)
  const albumData = kind === 'album' ? (data as AlbumVersionGroup) : null

  return (
    <GlassCard className="mb-6">
      <button
        type="button"
        className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-black/5 dark:hover:bg-white/5 rounded-xl transition-colors"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-2.5">
          <Layers className="w-4 h-4 text-muted-foreground" />
          <span className="font-medium text-sm">
            {data.canonical_name}
          </span>
          <span className="text-xs text-muted-foreground">
            · {data.versions.length} 个版本 · {scopeLabel}
          </span>
        </div>
        <Chevron className="w-4 h-4 text-muted-foreground" />
      </button>

      {open && (
        <div className="border-t border-border/50 px-4 py-3">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-muted-foreground text-xs border-b border-border/30">
                  <th className="text-left py-2 pr-4 font-medium">版本</th>
                  {kind === 'track' && (
                    <th className="text-left py-2 pr-4 font-medium">所属专辑</th>
                  )}
                  {kind === 'album' && (
                    <th className="text-left py-2 pr-4 font-medium">艺人</th>
                  )}
                  <th className="text-right py-2 pr-3 font-medium">播放</th>
                  <th className="text-right py-2 pr-3 font-medium w-[80px]">占比</th>
                  {kind === 'album' && (
                    <th className="text-right py-2 pr-4 font-medium">曲目</th>
                  )}
                  <th className="text-center py-2 font-medium w-16">标记</th>
                </tr>
              </thead>
              <tbody>
                {data.versions.map((v, i) => {
                  const ratio = totalPlays > 0 ? (v.plays / totalPlays) * 100 : 0
                  return (
                    <tr
                      key={i}
                      className="border-b border-border/20 last:border-0 hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                    >
                      <td className="py-2 pr-4">
                        <div className="flex items-center gap-2">
                          {v.album_cover_url && (
                            <img
                              src={v.album_cover_url}
                              alt=""
                              className="w-8 h-8 rounded object-cover flex-shrink-0"
                              loading="lazy"
                            />
                          )}
                          <div className="min-w-0">
                            {kind === 'track' && v.track_id ? (
                              <Link
                                to={`/music/tracks/${v.track_id}`}
                                className="text-primary hover:underline block truncate"
                              >
                                {v.track_name ?? `Track #${v.track_id}`}
                              </Link>
                            ) : kind === 'album' && v.album_name ? (
                              <Link
                                to={`/music/albums/${encodeURIComponent(v.album_name)}?artist=${encodeURIComponent(v.artist_name ?? '')}`}
                                className="text-primary hover:underline block truncate"
                              >
                                {v.album_name}
                              </Link>
                            ) : (
                              <span className="text-muted-foreground">—</span>
                            )}
                            {v.recording_kind && (
                              <span className="inline-block mt-0.5 text-[10px] text-muted-foreground bg-muted/40 rounded px-1 py-px">
                                {RECORDING_KIND_LABELS[v.recording_kind] ?? v.recording_kind}
                              </span>
                            )}
                            {v.release_date && (
                              <span className="block text-[11px] text-muted-foreground/70 mt-0.5">
                                {v.release_date}
                              </span>
                            )}
                          </div>
                        </div>
                      </td>
                      {kind === 'track' && (
                        <td className="py-2 pr-4 text-muted-foreground text-xs">{v.album_name ?? '—'}</td>
                      )}
                      {kind === 'album' && (
                        <td className="py-2 pr-4 text-muted-foreground text-xs">{v.artist_name ?? '—'}</td>
                      )}
                      <td className="py-2 pr-3 text-right tabular-nums font-mono text-xs">
                        {v.plays.toLocaleString()}
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
                      {kind === 'album' && v.unique_tracks != null && (
                        <td className="py-2 pr-4 text-right tabular-nums font-mono text-xs">
                          {v.unique_tracks}
                        </td>
                      )}
                      <td className="py-2 text-center">
                        {v.is_primary ? (
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

          {/* Track coverage matrix — album only (R30.3 / R30.4) */}
          {albumData?.track_coverage && albumData.track_coverage.length > 0 && (
            <div className="border-t border-border/50 px-4 py-3">
              <h4 className="mb-2.5 font-sans text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                曲目覆盖对比
              </h4>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-muted-foreground text-[11px] border-b border-border/30">
                      <th className="text-left py-1.5 pr-4 font-medium">曲目</th>
                      {albumData.versions.map((v) => (
                        <th key={v.album_id ?? v.album_name} className="text-center py-1.5 px-2 font-medium w-[72px]">
                          {v.is_primary ? '标准版' : (v.album_name ?? '').slice(0, 6)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {albumData.track_coverage.map((tc) => (
                      <tr
                        key={tc.track_id}
                        className={cn(
                          'border-b border-border/20 last:border-0',
                          tc.is_exclusive && 'bg-amber-50/30 dark:bg-amber-950/10',
                        )}
                      >
                        <td className="py-1.5 pr-4">
                          <span className="flex items-center gap-1.5">
                            {tc.track_name}
                            {tc.is_exclusive && (
                              <Star className="w-3 h-3 text-amber-600 dark:text-amber-400 flex-shrink-0" />
                            )}
                          </span>
                        </td>
                        {albumData.versions.map((v) => {
                          const hasTrack = tc.album_ids.includes(v.album_id!)
                          return (
                            <td key={v.album_id ?? v.album_name} className="text-center py-1.5 px-2">
                              {hasTrack ? (
                                <span className="inline-block w-3 h-3 rounded-full bg-primary/60" />
                              ) : (
                                <span className="text-[11px] text-muted-foreground/30">—</span>
                              )}
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-2 text-[11px] text-muted-foreground">
                <Star className="inline w-2.5 h-2.5 text-amber-600 dark:text-amber-400 mr-1" />
                独占曲目 — 仅在某一个版本中出现，其他版本没有
              </p>
            </div>
          )}
        </div>
      )}
    </GlassCard>
  )
}
