import { displayName, useChineseTextVersion } from '@/lib/chinese'

interface TimelineHour {
  hour: number
  plays: number
}

interface TimelineTrack {
  key: string
  label: string
}

function isTimelineHour(value: unknown): value is TimelineHour {
  if (!value || typeof value !== 'object') return false
  const record = value as Record<string, unknown>
  return typeof record.hour === 'number' && typeof record.plays === 'number'
}

function toTimelineTrack(value: unknown, index: number): TimelineTrack | null {
  if (typeof value === 'string' && value) return { key: `${value}-${index}`, label: value }
  if (!value || typeof value !== 'object') return null
  const record = value as Record<string, unknown>
  const name = String(record.name ?? record.track_name ?? record.track ?? '')
  if (!name) return null
  const artist = typeof record.artist === 'string' || typeof record.artist_name === 'string'
    ? String(record.artist ?? record.artist_name)
    : ''
  return {
    key: `${name}-${artist}-${index}`,
    label: artist ? `${name} · ${artist}` : name,
  }
}

export function HighlightDayTimeline({ data }: { data: unknown }) {
  useChineseTextVersion()
  const record = data as {
    date?: string
    title?: string
    hours?: unknown[]
    hourly?: unknown[]
    top_tracks?: unknown[]
  } | null
  const rawHours = Array.isArray(record?.hours)
    ? record.hours
    : Array.isArray(record?.hourly)
      ? record.hourly
      : []
  const hours = rawHours.filter(isTimelineHour).slice(0, 24)
  const tracks = Array.isArray(record?.top_tracks)
    ? record.top_tracks.flatMap((item, index) => {
      const track = toTimelineTrack(item, index)
      return track ? [track] : []
    }).slice(0, 4)
    : []
  const max = Math.max(...hours.map((item) => item.plays), 1)

  if (!hours.length && !tracks.length) return <p className="text-[12px] text-muted-foreground">高光日数据不足</p>

  return (
    <div className="space-y-3">
      {(record?.title || record?.date) && (
        <p className="break-words text-[12px] font-semibold text-muted-foreground">
          {[record.title, record.date].filter(Boolean).join(' · ')}
        </p>
      )}
      {hours.length > 0 && (
        <div className="grid grid-cols-12 gap-1 sm:grid-cols-24">
          {hours.map((item) => (
            <span
              aria-label={`${item.hour} 点播放 ${item.plays} 次`}
              className="block rounded-[2px] bg-accent-foreground/70"
              key={item.hour}
              style={{ height: `${14 + (item.plays / max) * 56}px` }}
              title={`${item.hour}:00 ${item.plays} 次`}
            />
          ))}
        </div>
      )}
      {tracks.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {tracks.map((track) => (
            <span className="rounded-full border border-border px-2 py-1 text-[11px] text-muted-foreground" key={track.key}>
              {displayName(track.label)}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
