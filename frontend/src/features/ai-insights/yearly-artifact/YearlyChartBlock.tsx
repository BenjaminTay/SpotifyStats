import { AlbumDualityCompare } from './charts/AlbumDualityCompare'
import { ArtistMonthlyTrendChart } from './charts/ArtistMonthlyTrendChart'
import { DiscoveryTimeline } from './charts/DiscoveryTimeline'
import { GenreLanguageMixChart } from './charts/GenreLanguageMixChart'
import { HighlightDayTimeline } from './charts/HighlightDayTimeline'
import { ListeningCalendarChart } from './charts/ListeningCalendarChart'
import type { YearlyChartSpec } from './yearlyArtifactTypes'

type MatrixItemType = 'track' | 'album' | 'artist'

interface MatrixDisplayItem {
  artist?: string
  name: string
  peak_rank?: number
  plays?: number
  type: MatrixItemType
  typeLabel: string
  weeks_on_chart?: number
}

const matrixTypeLabels: Record<MatrixItemType, string> = {
  track: '单曲',
  album: '专辑',
  artist: '艺人',
}

const placeholderText = /^(unknown|undefined|null|nan)$/i
const unsafeText = /\b(unknown|undefined|null|nan)\b/i

function cleanText(value: unknown): string | null {
  if (value == null) return null
  const text = String(value).trim()
  if (!text || placeholderText.test(text)) return null
  return text
}

function cleanObservation(value: unknown): string | null {
  if (typeof value !== 'string') return null
  const text = value.trim()
  if (!text || unsafeText.test(text)) return null
  return text
}

function cleanNumber(value: unknown): number | undefined {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : undefined
  }
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : undefined
  }
  return undefined
}

function matrixItemType(value: unknown): MatrixItemType | null {
  const type = cleanText(value)?.toLowerCase()
  if (type === 'track' || type === 'song' || type === 'single') return 'track'
  if (type === 'album') return 'album'
  if (type === 'artist') return 'artist'
  return null
}

function matrixItemName(row: Record<string, unknown>, type: MatrixItemType): string | null {
  const candidates = type === 'track'
    ? [row.name, row.track_name, row.track]
    : type === 'album'
      ? [row.name, row.album_name, row.album]
      : [row.name, row.artist_name, row.artist]
  for (const candidate of candidates) {
    const text = cleanText(candidate)
    if (text) return text
  }
  return null
}

function toMatrixDisplayItems(data: unknown): MatrixDisplayItem[] {
  if (!data || typeof data !== 'object') return []
  const record = data as Record<string, unknown>
  const rawItems = Array.isArray(record.items)
    ? record.items
    : Array.isArray(record.rows)
      ? record.rows
      : []

  return rawItems.flatMap((item) => {
    if (!item || typeof item !== 'object') return []
    const row = item as Record<string, unknown>
    const type = matrixItemType(row.type)
    if (!type) return []
    const name = matrixItemName(row, type)
    if (!name) return []

    const artist = type === 'artist' ? null : cleanText(row.artist_name) ?? cleanText(row.artist)
    return [{
      artist: artist && artist !== name ? artist : undefined,
      name,
      peak_rank: cleanNumber(row.peak_rank) ?? cleanNumber(row.peak_position) ?? cleanNumber(row.peak),
      plays: cleanNumber(row.plays),
      type,
      typeLabel: matrixTypeLabels[type],
      weeks_on_chart: cleanNumber(row.weeks_on_chart),
    }]
  })
}

function chartObservations(data: unknown): string[] {
  if (!data || typeof data !== 'object') return []
  const observations = (data as Record<string, unknown>).observations
  if (!Array.isArray(observations)) return []
  return observations.flatMap((item) => {
    const text = cleanObservation(item)
    return text ? [text] : []
  }).slice(0, 2)
}

function PlaybackBillboardMatrixChart({ data }: { data: unknown }) {
  const items = toMatrixDisplayItems(data).slice(0, 6)

  if (!items.length) return <p className="text-[12px] text-muted-foreground">播放与榜单矩阵数据不足</p>

  return (
    <div className="grid min-w-0 gap-2 sm:grid-cols-2">
      {items.map((item) => {
        const metrics = [
          item.plays != null ? `${item.plays} 次播放` : null,
          item.weeks_on_chart != null ? `${item.weeks_on_chart} 周在榜` : null,
          item.peak_rank != null ? `PK #${item.peak_rank}` : null,
        ].filter(Boolean)

        return (
          <div
            className="min-w-0 rounded-[8px] border border-border/70 p-3"
            key={`${item.type}-${item.name}-${item.artist ?? ''}`}
          >
            <span className="inline-flex rounded-full border border-border bg-card/60 px-2 py-0.5 text-[11px] font-semibold text-muted-foreground">
              {item.typeLabel}
            </span>
            <p className="mt-2 break-words text-[13px] font-semibold text-foreground">{item.name}</p>
            {item.artist && <p className="mt-1 text-[12px] text-muted-foreground">{item.artist}</p>}
            {metrics.length > 0 && (
              <p className="mt-2 text-[11px] text-muted-foreground">
                {metrics.join(' · ')}
              </p>
            )}
          </div>
        )
      })}
    </div>
  )
}

function ChartBody({ spec, data }: { spec: YearlyChartSpec; data: unknown }) {
  switch (spec.chart_type) {
    case 'listening_calendar_heatmap':
      return <ListeningCalendarChart data={data} />
    case 'artist_monthly_trend':
      return <ArtistMonthlyTrendChart data={data} />
    case 'album_duality_compare':
      return <AlbumDualityCompare data={data} />
    case 'highlight_day_timeline':
      return <HighlightDayTimeline data={data} />
    case 'genre_language_mix':
      return <GenreLanguageMixChart data={data} />
    case 'discovery_timeline':
      return <DiscoveryTimeline data={data} />
    case 'playback_billboard_matrix':
      return <PlaybackBillboardMatrixChart data={data} />
    default:
      return <p className="text-[12px] text-muted-foreground">{cleanText(spec.fallback) ?? '图表数据不足'}</p>
  }
}

export function YearlyChartBlock({
  spec,
  chartData,
}: {
  spec: YearlyChartSpec | null
  chartData: unknown
}) {
  if (!spec) return null

  const insight = cleanText(spec.insight)
  const fallback = cleanText(spec.fallback) ?? '图表数据不足'
  const observations = chartObservations(chartData)

  return (
    <figure className="min-w-0 rounded-[8px] border border-border bg-card/35 p-4">
      <figcaption>
        <p className="break-words font-serif text-[18px] font-semibold text-foreground">{spec.title}</p>
        {insight && <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">{insight}</p>}
      </figcaption>
      <div className="mt-4 min-h-[160px] min-w-0 overflow-hidden rounded-[6px] bg-muted/20 p-4">
        {chartData ? <ChartBody data={chartData} spec={spec} /> : (
          <p className="text-[12px] text-muted-foreground">{fallback}</p>
        )}
      </div>
      {observations.length > 0 && (
        <ul className="mt-3 space-y-1.5" aria-label={`${spec.title} 观察`}>
          {observations.map((observation) => (
            <li
              className="grid grid-cols-[auto_1fr] gap-2 text-[12px] leading-relaxed text-muted-foreground"
              key={observation}
            >
              <span className="mt-2 h-1.5 w-1.5 rounded-full bg-accent-foreground/70" />
              <span>{observation}</span>
            </li>
          ))}
        </ul>
      )}
    </figure>
  )
}
