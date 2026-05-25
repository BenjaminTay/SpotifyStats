import type { PlatformDist } from '@/types/dashboard'

interface PlatformDistChartProps {
  data: PlatformDist[]
}

const PLATFORM_LABELS: Record<string, string> = {
  ios: 'iOS',
  android: 'Android',
  desktop: 'Desktop',
  web: 'Web',
}

const BAR_COLORS = [
  'bg-accent-foreground',
  'bg-[#C17A4E] dark:bg-[#C97B6B]',
  'bg-[#B8860B] dark:bg-[#D4A24E]',
  'bg-[#3B5998] dark:bg-[#7B9CC8]',
]

export function PlatformDistChart({ data }: PlatformDistChartProps) {
  const sorted = [...data].sort((a, b) => b.count - a.count)
  const total = sorted.reduce((sum, d) => sum + d.count, 0)
  const maxPct = sorted.length > 0 ? sorted[0].count / total : 1

  return (
    <div className="space-y-3">
      {sorted.map((d, i) => {
        const pct = total > 0 ? d.count / total : 0
        const barWidth = maxPct > 0 ? (pct / maxPct) * 100 : 0
        return (
          <div key={d.platform} className="space-y-1">
            <div className="flex justify-between font-sans text-[13px] font-medium">
              <span>{PLATFORM_LABELS[d.platform] || d.platform}</span>
              <span className="font-semibold tabular-nums">
                {Math.round(pct * 100)}%
              </span>
            </div>
            <div className="h-[5px] w-full rounded-[3px] bg-border overflow-hidden">
              <div
                className={`h-full rounded-[3px] transition-all duration-500 ${BAR_COLORS[i % BAR_COLORS.length]}`}
                style={{ width: `${barWidth}%` }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}
