import { displayName, useChineseTextVersion } from '@/lib/chinese'

interface MatrixItem {
  name: string
  artist?: string
  plays?: number
  weeks_on_chart?: number
  peak_rank?: number
}

function toMatrixItems(data: unknown): MatrixItem[] {
  if (!data || typeof data !== 'object') return []
  const record = data as Record<string, unknown>
  const rawItems = Array.isArray(record.items) ? record.items : Array.isArray(record.rows) ? record.rows : []

  return rawItems.flatMap((item) => {
    if (!item || typeof item !== 'object') return []
    const row = item as Record<string, unknown>
    const name = String(row.name ?? row.track ?? row.album ?? '')
    if (!name) return []
    return [{
      name,
      artist: typeof row.artist === 'string' ? row.artist : undefined,
      plays: typeof row.plays === 'number' ? row.plays : undefined,
      weeks_on_chart: typeof row.weeks_on_chart === 'number' ? row.weeks_on_chart : undefined,
      peak_rank: typeof row.peak_rank === 'number'
        ? row.peak_rank
        : typeof row.peak_position === 'number'
          ? row.peak_position
          : typeof row.peak === 'number'
            ? row.peak
            : undefined,
    }]
  })
}

export function PlaybackBillboardMatrix({ data }: { data: unknown }) {
  useChineseTextVersion()
  const items = toMatrixItems(data).slice(0, 6)

  if (!items.length) return <p className="text-[12px] text-muted-foreground">播放与榜单矩阵数据不足</p>

  return (
    <div className="grid min-w-0 gap-2 sm:grid-cols-2">
      {items.map((item) => (
        <div className="min-w-0 rounded-[8px] border border-border/70 p-3" key={`${item.name}-${item.artist ?? ''}`}>
          <p className="break-words text-[13px] font-semibold text-foreground">{displayName(item.name)}</p>
          {item.artist && <p className="mt-1 text-[12px] text-muted-foreground">{displayName(item.artist)}</p>}
          <p className="mt-2 text-[11px] text-muted-foreground">
            {[
              item.plays != null ? `${item.plays} 次播放` : null,
              item.weeks_on_chart != null ? `${item.weeks_on_chart} 周在榜` : null,
              item.peak_rank != null ? `PK #${item.peak_rank}` : null,
            ].filter(Boolean).join(' · ')}
          </p>
        </div>
      ))}
    </div>
  )
}
