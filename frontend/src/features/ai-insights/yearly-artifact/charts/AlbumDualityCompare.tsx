import { displayName, useChineseTextVersion } from '@/lib/chinese'

function readField(value: unknown, field: string): string {
  if (!value || typeof value !== 'object') return ''
  const raw = (value as Record<string, unknown>)[field]
  return raw == null ? '' : String(raw)
}

export function AlbumDualityCompare({ data }: { data: unknown }) {
  useChineseTextVersion()
  const record = data as {
    playback_leader?: unknown
    chart_leader?: unknown
    interpretation?: string
  } | null
  const playback = readField(record?.playback_leader, 'name')
  const playbackArtist = readField(record?.playback_leader, 'artist')
  const chart = readField(record?.chart_leader, 'name')
  const chartArtist = readField(record?.chart_leader, 'artist')

  if (!playback || !chart) {
    return <p className="text-[12px] text-muted-foreground">专辑对照数据不足</p>
  }

  return (
    <div className="space-y-3">
      <div className="grid min-w-0 gap-3 sm:grid-cols-2">
        <div className="min-w-0 rounded-[8px] border border-border/70 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.8px] text-muted-foreground">
            最常播放
          </p>
          <p className="mt-2 break-words font-serif text-[18px] text-foreground">{displayName(playback)}</p>
          {playbackArtist && <p className="mt-1 text-[12px] text-muted-foreground">{displayName(playbackArtist)}</p>}
        </div>
        <div className="min-w-0 rounded-[8px] border border-border/70 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.8px] text-muted-foreground">
            最稳定在榜
          </p>
          <p className="mt-2 break-words font-serif text-[18px] text-foreground">{displayName(chart)}</p>
          {chartArtist && <p className="mt-1 text-[12px] text-muted-foreground">{displayName(chartArtist)}</p>}
        </div>
      </div>
      {record?.interpretation && (
        <p className="text-[12px] leading-relaxed text-muted-foreground">{record.interpretation}</p>
      )}
    </div>
  )
}
