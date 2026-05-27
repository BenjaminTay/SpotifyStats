import { cn } from '@/lib/utils'
import type { ChartEntry } from '@/types/billboard'
import { Crown } from 'lucide-react'

interface ChartBarsProps {
  charts: ChartEntry[]
  className?: string
}

function barStyle(peak: number): { bg: string; text: string } {
  if (peak === 1) return { bg: 'bg-gradient-to-r from-amber-500 to-amber-400', text: 'text-amber-600 dark:text-amber-400' }
  if (peak <= 5) return { bg: 'bg-gradient-to-r from-amber-500/70 to-amber-400/50', text: 'text-amber-500' }
  if (peak <= 10) return { bg: 'bg-gradient-to-r from-foreground/50 to-foreground/30', text: 'text-foreground/70' }
  if (peak <= 20) return { bg: 'bg-gradient-to-r from-muted-foreground/50 to-muted-foreground/30', text: 'text-muted-foreground' }
  return { bg: 'bg-muted-foreground/30', text: 'text-muted-foreground/70' }
}

export function ChartBars({ charts, className }: ChartBarsProps) {
  if (!charts.length) return null
  const maxPeak = Math.max(...charts.map(c => c.peak), 1)
  return (
    <div className={cn('space-y-3', className)}>
      {charts.map((c) => {
        const style = barStyle(c.peak)
        return (
          <div key={c.region} className="group flex items-center gap-3">
            <span className="w-32 shrink-0 font-sans text-[12px] leading-snug text-muted-foreground">{c.region}</span>
            <div className="flex flex-1 items-center gap-2.5">
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted/60">
                <div
                  className={cn('h-full rounded-full transition-all duration-500', style.bg)}
                  style={{ width: `${Math.max(100 - ((c.peak - 1) / maxPeak) * 90, 6)}%` }}
                />
              </div>
              <span className={cn(
                'flex items-center gap-1 font-sans text-[12px] font-bold tabular-nums min-w-[2rem]',
                style.text,
              )}>
                {c.peak === 1 && <Crown className="h-3 w-3 shrink-0 text-amber-500" />}
                #{c.peak}
              </span>
            </div>
            {c.detail && (
              <span className="hidden font-sans text-[11px] leading-snug text-muted-foreground sm:inline">{c.detail}</span>
            )}
          </div>
        )
      })}
    </div>
  )
}
