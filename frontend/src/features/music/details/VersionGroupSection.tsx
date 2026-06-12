import { useState } from 'react'
import { Link } from 'react-router'
import { ChevronDown, ChevronUp, Disc, Layers } from 'lucide-react'
import { GlassCard } from '@/components/shared/GlassCard'
import type { TrackVersionGroup, AlbumVersionGroup } from '@/types/billboard'

interface Props {
  kind: 'track' | 'album'
  data: TrackVersionGroup | AlbumVersionGroup
}

const SCOPE_LABELS: Record<string, string> = {
  recording: '同录音',
  release: '同发行组',
  composition: '同作品',
}

export function VersionGroupSection({ kind, data }: Props) {
  const [open, setOpen] = useState(false)

  if (!data.versions || data.versions.length < 2) return null

  const scopeLabel = SCOPE_LABELS[data.scope] ?? data.scope
  const Chevron = open ? ChevronUp : ChevronDown

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
                  <th className="text-left py-2 pr-4 font-medium">版本名称</th>
                  {kind === 'track' && (
                    <th className="text-left py-2 pr-4 font-medium">所属专辑</th>
                  )}
                  {kind === 'album' && (
                    <th className="text-left py-2 pr-4 font-medium">艺人</th>
                  )}
                  <th className="text-right py-2 pr-4 font-medium">播放次数</th>
                  {kind === 'track' && (
                    <th className="text-right py-2 pr-4 font-medium">时长</th>
                  )}
                  {kind === 'album' && (
                    <th className="text-right py-2 pr-4 font-medium">独有曲目</th>
                  )}
                  <th className="text-center py-2 font-medium w-16">标记</th>
                </tr>
              </thead>
              <tbody>
                {data.versions.map((v, i) => (
                  <tr
                    key={i}
                    className="border-b border-border/20 last:border-0 hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                  >
                    <td className="py-2 pr-4">
                      {kind === 'track' && v.track_id ? (
                        <Link
                          to={`/music/tracks/${v.track_id}`}
                          className="text-primary hover:underline"
                        >
                          {v.track_name ?? `Track #${v.track_id}`}
                        </Link>
                      ) : kind === 'album' && v.album_name ? (
                        <Link
                          to={`/music/albums/${encodeURIComponent(v.album_name)}?artist=${encodeURIComponent(v.artist_name ?? '')}`}
                          className="text-primary hover:underline"
                        >
                          {v.album_name}
                        </Link>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                    {kind === 'track' && (
                      <td className="py-2 pr-4 text-muted-foreground">{v.album_name ?? '—'}</td>
                    )}
                    {kind === 'album' && (
                      <td className="py-2 pr-4 text-muted-foreground">{v.artist_name ?? '—'}</td>
                    )}
                    <td className="py-2 pr-4 text-right tabular-nums font-mono">
                      {v.plays.toLocaleString()}
                    </td>
                    {kind === 'track' && v.total_ms != null && (
                      <td className="py-2 pr-4 text-right text-muted-foreground tabular-nums font-mono">
                        {(v.total_ms / 3_600_000).toFixed(1)}h
                      </td>
                    )}
                    {kind === 'album' && v.unique_tracks != null && (
                      <td className="py-2 pr-4 text-right tabular-nums font-mono">
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
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </GlassCard>
  )
}
