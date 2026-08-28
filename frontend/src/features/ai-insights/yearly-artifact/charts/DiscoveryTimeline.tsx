import { displayName, useChineseTextVersion } from '@/lib/chinese'

interface DiscoveryItem {
  name: string
  first_seen?: string
  plays?: number
}

function toDiscoveryItems(data: unknown): DiscoveryItem[] {
  if (!data || typeof data !== 'object') return []
  const record = data as Record<string, unknown>
  const rawItems = Array.isArray(record.items)
    ? record.items
    : Array.isArray(record.discoveries)
      ? record.discoveries
      : Array.isArray(record.artists)
        ? record.artists
        : Array.isArray(record.new_artists)
          ? record.new_artists
          : []

  return rawItems.flatMap((item) => {
    if (!item || typeof item !== 'object') return []
    const row = item as Record<string, unknown>
    const name = String(row.name ?? row.artist ?? '')
    if (!name) return []
    return [{
      name,
      first_seen: typeof row.first_seen === 'string'
        ? row.first_seen
        : typeof row.first_date === 'string'
          ? row.first_date
          : undefined,
      plays: typeof row.plays === 'number' ? row.plays : undefined,
    }]
  })
}

export function DiscoveryTimeline({ data }: { data: unknown }) {
  useChineseTextVersion()
  const items = toDiscoveryItems(data).slice(0, 8)

  if (!items.length) return <p className="text-[12px] text-muted-foreground">新发现时间线数据不足</p>

  return (
    <ol className="space-y-2">
      {items.map((item) => (
        <li className="grid min-w-0 grid-cols-[auto_1fr] gap-3" key={`${item.name}-${item.first_seen ?? ''}`}>
          <span className="mt-1 h-2 w-2 rounded-full bg-accent-foreground" />
          <div className="min-w-0">
            <p className="break-words text-[13px] font-semibold text-foreground">{displayName(item.name)}</p>
            <p className="text-[12px] text-muted-foreground">
              {[item.first_seen, item.plays != null ? `${item.plays} 次` : null].filter(Boolean).join(' · ')}
            </p>
          </div>
        </li>
      ))}
    </ol>
  )
}
