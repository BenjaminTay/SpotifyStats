interface MixItem {
  label: string
  mode: 'count' | 'percent'
  value: number
}

function toMixItems(data: unknown): MixItem[] {
  if (!data || typeof data !== 'object') return []
  const record = data as Record<string, unknown>
  const rawItems = Array.isArray(record.items)
    ? record.items
    : Array.isArray(record.genres)
      ? record.genres
      : Array.isArray(record.languages)
        ? record.languages
        : []

  return rawItems.flatMap((item): MixItem[] => {
    if (!item || typeof item !== 'object') return []
    const row = item as Record<string, unknown>
    const label = String(row.label ?? row.name ?? row.genre ?? row.language ?? '')
    if (typeof row.percent === 'number') return label && row.percent > 0 ? [{ label, mode: 'percent', value: row.percent }] : []
    if (typeof row.share === 'number') return label && row.share > 0 ? [{ label, mode: 'percent', value: row.share }] : []
    if (typeof row.value === 'number') return label && row.value > 0 ? [{ label, mode: 'percent', value: row.value }] : []
    if (typeof row.plays === 'number') return label && row.plays > 0 ? [{ label, mode: 'count', value: row.plays }] : []
    return []
  })
}

export function GenreLanguageMixChart({ data }: { data: unknown }) {
  const items = toMixItems(data).slice(0, 8)
  const countTotal = items
    .filter((item) => item.mode === 'count')
    .reduce((sum, item) => sum + item.value, 0)

  if (!items.length) return <p className="text-[12px] text-muted-foreground">曲风或语种占比数据不足</p>

  return (
    <div className="space-y-2">
      {items.map((item) => {
        const percent = item.mode === 'count' && countTotal > 0
          ? Math.round((item.value / countTotal) * 100)
          : Math.round(item.value)
        return (
          <div className="min-w-0" key={item.label}>
            <div className="mb-1 flex items-center justify-between gap-3 text-[12px]">
              <span className="min-w-0 break-words text-foreground">{item.label}</span>
              <span className="shrink-0 tabular-nums text-muted-foreground">{percent}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-muted/40">
              <div className="h-full rounded-full bg-accent-foreground" style={{ width: `${Math.min(100, percent)}%` }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}
