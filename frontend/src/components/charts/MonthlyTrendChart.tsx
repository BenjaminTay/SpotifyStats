import { useTheme } from '@/hooks/useTheme'
import { getChartColors } from '@/lib/theme'
import type { MonthlyTrendPoint } from '@/types/dashboard'

interface MonthlyTrendChartProps {
  data: MonthlyTrendPoint[]
}

export function MonthlyTrendChart({ data }: MonthlyTrendChartProps) {
  const { isDark } = useTheme()
  const colors = [...getChartColors(isDark)]
  const maxValue = Math.max(...data.map((d) => d.plays), 1)
  const numberFormatter = new Intl.NumberFormat('zh-CN')

  const points = data.map((d) => {
    const [, month] = d.period.split('-')
    return {
      label: `${parseInt(month, 10)}月`,
      value: d.plays,
      height: `${Math.max((d.plays / maxValue) * 100, d.plays > 0 ? 3 : 0)}%`,
    }
  })

  if (points.length === 0) {
    return (
      <div className="flex h-[240px] items-center justify-center rounded-lg border border-dashed border-border/70 font-sans text-[13px] text-muted-foreground">
        暂无月度趋势数据
      </div>
    )
  }

  return (
    <div
      className="h-[240px]"
      role="img"
      aria-label={`月度播放趋势，最高月播放 ${numberFormatter.format(maxValue)} 次`}
    >
      <div className="relative h-[204px] overflow-hidden rounded-[8px] border-b border-border/80">
        <div className="pointer-events-none absolute inset-0 grid grid-rows-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <div
              key={index}
              className="border-t border-dashed border-border/50 first:border-border/70"
            />
          ))}
        </div>
        <div className="relative z-1 flex h-full items-end gap-2 px-1 pt-3 sm:gap-3">
          {points.map((point, index) => (
            <div key={`${point.label}-${index}`} className="flex h-full min-w-0 flex-1 items-end">
              <div
                className="w-full rounded-t-[5px] transition-opacity duration-150 hover:opacity-80"
                style={{
                  height: point.height,
                  backgroundColor: colors[index % colors.length],
                  boxShadow: isDark ? '0 0 18px rgba(255,255,255,0.04)' : '0 8px 18px rgba(45,36,32,0.08)',
                }}
                title={`${point.label}: ${numberFormatter.format(point.value)} 次播放`}
                aria-label={`${point.label}: ${numberFormatter.format(point.value)} 次播放`}
              />
            </div>
          ))}
        </div>
      </div>
      <div className="mt-3 grid gap-2" style={{ gridTemplateColumns: `repeat(${points.length}, minmax(0, 1fr))` }}>
        {points.map((point, index) => (
          <span
            key={`${point.label}-${index}`}
            className="truncate text-center font-sans text-[11px] font-medium text-muted-foreground"
          >
            {point.label}
          </span>
        ))}
      </div>
    </div>
  )
}
