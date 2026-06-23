import { Star } from 'lucide-react'
import type { AlbumVersionGroup } from '@/types/billboard'
import { cn } from '@/lib/utils'

interface VersionCoverageMatrixProps {
  albumData: AlbumVersionGroup | null
  compact?: boolean
}

export function VersionCoverageMatrix({
  albumData,
  compact = false,
}: VersionCoverageMatrixProps) {
  if (!albumData?.track_coverage?.length) return null

  return (
    <div className={compact ? 'border-t border-border/50 pt-3 mt-3' : 'border-t border-border/50 px-4 py-3'}>
      <h4 className="mb-2.5 font-sans text-xs font-semibold text-muted-foreground uppercase tracking-wider">
        曲目覆盖对比
      </h4>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-muted-foreground text-[11px] border-b border-border/30">
              <th className="text-left py-1.5 pr-4 font-medium">曲目</th>
              {albumData.versions.map((version) => (
                <th
                  key={version.album_id ?? version.album_name}
                  className="text-center py-1.5 px-2 font-medium w-[72px]"
                >
                  {version.is_primary ? '标准版' : (version.album_name ?? '').slice(0, 6)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {albumData.track_coverage.map((track) => (
              <tr
                key={track.track_id}
                className={cn(
                  'border-b border-border/20 last:border-0',
                  track.is_exclusive && 'bg-amber-50/30 dark:bg-amber-950/10',
                )}
              >
                <td className="py-1.5 pr-4">
                  <span className="flex items-center gap-1.5">
                    {track.track_name}
                    {track.is_exclusive && (
                      <Star className="w-3 h-3 text-amber-600 dark:text-amber-400 flex-shrink-0" />
                    )}
                  </span>
                </td>
                {albumData.versions.map((version) => {
                  const hasTrack = track.album_ids.includes(version.album_id!)
                  return (
                    <td key={version.album_id ?? version.album_name} className="text-center py-1.5 px-2">
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
  )
}
