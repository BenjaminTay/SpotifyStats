import { cn } from '@/lib/utils'
import { GlassCard } from '@/components/shared/GlassCard'
import { useTheme } from '@/hooks/useTheme'
import type { CollectionInsights } from '@/types/account'

function RingMetric({
  label,
  value,
  max,
  unit,
  isDark,
}: {
  label: string
  value: number
  max: number
  unit: string
  isDark: boolean
}) {
  const pct = Math.min((value / max) * 100, 100)

  const fgColor = isDark ? 'rgba(255,255,255,0.85)' : 'rgba(0,0,0,0.55)'
  const bgColor = isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.08)'

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div
        className="relative flex h-20 w-20 items-center justify-center rounded-full"
        style={{
          background: `conic-gradient(${fgColor} ${pct * 3.6}deg, ${bgColor} ${pct * 3.6}deg)`,
        }}
      >
        <div className={cn(
          'absolute inset-[6px] flex flex-col items-center justify-center rounded-full',
          'bg-[#e8d5c4] dark:bg-[#0f3460]',
        )}>
          <span className="font-serif text-lg font-bold leading-none">
            {value.toFixed(0)}
          </span>
          <span className="-mt-0.5 font-sans text-[10px] text-muted-foreground dark:text-white/60">
            {unit}
          </span>
        </div>
      </div>
      <p className="font-sans text-[11px] font-medium text-muted-foreground dark:text-white/70">{label}</p>
    </div>
  )
}

export function PersonalityHero({ insights }: { insights: CollectionInsights }) {
  const { personality } = insights
  const { metrics } = personality
  const { isDark } = useTheme()

  return (
    <GlassCard className="overflow-hidden p-0">
      <div className={cn(
        'flex flex-col gap-0 bg-gradient-to-br',
        'from-[#f5f0eb] via-[#ede4db] to-[#e8d5c4] text-foreground',
        'dark:from-[#1a1a2e] dark:via-[#16213e] dark:to-[#0f3460] dark:text-white',
      )}>
        <div className="flex flex-col gap-6 p-8 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex-1 space-y-3">
            <span className="text-5xl">{personality.icon}</span>
            <h2 className="font-serif text-4xl font-bold tracking-[-0.5px]">
              {personality.type}
            </h2>
            <p className="max-w-lg font-sans text-sm leading-relaxed text-muted-foreground dark:text-white/70">
              {personality.description}
            </p>
          </div>

          <div className="flex gap-8 lg:gap-12">
            <RingMetric
              label="慢热指数"
              value={metrics.avg_plays_before_save}
              max={20}
              unit="次"
              isDark={isDark}
            />
            <RingMetric
              label="留存率"
              value={metrics.retention_pct}
              max={100}
              unit="%"
              isDark={isDark}
            />
            <RingMetric
              label="冲动收藏"
              value={metrics.impulsive_pct}
              max={100}
              unit="%"
              isDark={isDark}
            />
          </div>
        </div>

        <div className="grid grid-cols-3 border-t border-black/10 dark:border-white/10">
          <div className="px-8 py-4 text-center">
            <p className="font-serif text-2xl font-bold">
              {metrics.avg_plays_before_save.toFixed(1)}
            </p>
            <p className="font-sans text-xs text-muted-foreground dark:text-white/50">收藏前平均播放</p>
          </div>
          <div className="border-x border-black/10 px-8 py-4 text-center dark:border-white/10">
            <p className="font-serif text-2xl font-bold">
              {metrics.retention_pct.toFixed(0)}%
            </p>
            <p className="font-sans text-xs text-muted-foreground dark:text-white/50">长期留存率</p>
          </div>
          <div className="px-8 py-4 text-center">
            <p className="font-serif text-2xl font-bold">
              {metrics.impulsive_pct.toFixed(0)}%
            </p>
            <p className="font-sans text-xs text-muted-foreground dark:text-white/50">冲动收藏比例</p>
          </div>
        </div>
      </div>
    </GlassCard>
  )
}
