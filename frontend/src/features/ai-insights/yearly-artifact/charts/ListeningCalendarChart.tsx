interface CalendarDay {
  date: string
  plays: number
  minutes?: number
}

function isCalendarDay(value: unknown): value is CalendarDay {
  if (!value || typeof value !== 'object') return false
  const record = value as Record<string, unknown>
  return typeof record.date === 'string' && typeof record.plays === 'number'
}

export function ListeningCalendarChart({ data }: { data: unknown }) {
  const record = data as { days?: unknown[]; active_days?: number } | null
  const days = Array.isArray(record?.days) ? record.days.filter(isCalendarDay) : []
  const activeDays = typeof record?.active_days === 'number' ? record.active_days : days.length

  if (!days.length) {
    return (
      <div className="flex min-h-[120px] items-center">
        <p className="text-[12px] font-semibold text-muted-foreground">活跃 {activeDays} 天</p>
      </div>
    )
  }

  const max = Math.max(...days.map((day) => day.plays), 1)

  return (
    <div className="min-w-0">
      <p className="mb-3 text-[12px] font-semibold text-muted-foreground">活跃 {activeDays} 天</p>
      <div
        className="grid min-w-0 gap-1"
        style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(8px, 1fr))' }}
      >
        {days.map((day) => (
          <span
            aria-label={`${day.date} 播放 ${day.plays} 次`}
            className="aspect-square min-w-0 rounded-[3px] bg-accent-foreground"
            key={day.date}
            style={{ opacity: 0.18 + (day.plays / max) * 0.72 }}
            title={`${day.date}: ${day.plays} 次${day.minutes ? ` / ${day.minutes} 分钟` : ''}`}
          />
        ))}
      </div>
    </div>
  )
}
