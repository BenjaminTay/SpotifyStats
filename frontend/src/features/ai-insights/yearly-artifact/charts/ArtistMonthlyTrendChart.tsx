interface TrendPoint {
  month: string
  value: number
}

function monthLabel(value: unknown, fallbackIndex: number): string {
  if (typeof value === 'string') {
    const match = value.match(/^\d{4}-(\d{2})$/)
    if (match) return `${Number(match[1])} 月`
    if (value.trim()) return value
  }
  return `${fallbackIndex + 1} 月`
}

function toRows(data: unknown): Array<{ label: string; points: TrendPoint[] }> {
  if (!data || typeof data !== 'object') return []
  const record = data as Record<string, unknown>
  const months = record.months
  if (Array.isArray(record.entities) && Array.isArray(months)) {
    return record.entities.flatMap((entity) => {
      if (typeof entity !== 'string' || !entity) return []
      const points = months
        .map((month: unknown, index: number) => {
          if (!month || typeof month !== 'object') {
            return { month: monthLabel(null, index), value: 0 }
          }
          const row = month as Record<string, unknown>
          const value = row[entity]
          return {
            month: monthLabel(row.month, index),
            value: typeof value === 'number' ? value : 0,
          }
        })
      return points.some((point) => point.value > 0) ? [{ label: entity, points }] : []
    })
  }
  const rawRows = Array.isArray(record.artists) ? record.artists : Array.isArray(record.rows) ? record.rows : []

  return rawRows.flatMap((item) => {
    if (!item || typeof item !== 'object') return []
    const row = item as Record<string, unknown>
    const label = String(row.artist ?? row.name ?? '')
    const values = Array.isArray(row.monthly_plays)
      ? row.monthly_plays.filter((value): value is number => typeof value === 'number')
      : Array.isArray(row.values)
        ? row.values.filter((value): value is number => typeof value === 'number')
        : []
    const points = values.map((value, index) => ({ month: monthLabel(null, index), value }))
    return label && points.some((point) => point.value > 0) ? [{ label, points }] : []
  })
}

export function ArtistMonthlyTrendChart({ data }: { data: unknown }) {
  const rows = toRows(data).slice(0, 5)
  const max = Math.max(...rows.flatMap((row) => row.points.map((point) => point.value)), 1)

  if (!rows.length) return <p className="text-[12px] text-muted-foreground">艺人月度趋势数据不足</p>

  return (
    <div className="space-y-3">
      {rows.map((row) => (
        <div className="min-w-0" key={row.label}>
          <p className="mb-1 break-words text-[12px] font-semibold text-foreground">{row.label}</p>
          <div className="grid grid-cols-12 gap-1">
            {row.points.slice(0, 12).map((point, index) => (
              <span
                aria-label={`${row.label} ${point.month} ${point.value} 次`}
                className="block rounded-[2px] bg-accent-foreground/70"
                key={`${row.label}-${point.month}-${index}`}
                style={{ height: `${16 + (point.value / max) * 48}px` }}
                title={`${point.month}: ${point.value} 次`}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
