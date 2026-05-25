import { cn } from '@/lib/utils'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

interface KpiCardProps {
  label: string
  value: string
  trend?: 'up' | 'down' | 'neutral'
  trendLabel?: string
}

const trendIcon = {
  up: TrendingUp,
  down: TrendingDown,
  neutral: Minus,
}

const trendColor = {
  up: 'text-[#4A6B4F] dark:text-[#7D9B76]',
  down: 'text-accent-foreground',
  neutral: 'text-muted-foreground',
}

export function KpiCard({ label, value, trend, trendLabel }: KpiCardProps) {
  const Icon = trend ? trendIcon[trend] : null

  return (
    <div>
      <p className="mb-1.5 font-sans text-[12px] font-semibold uppercase tracking-[1px] text-muted-foreground">
        {label}
      </p>
      <p className="mb-2 font-serif text-[44px] font-bold leading-none tracking-[-1px]">
        {value}
      </p>
      {trend && Icon && (
        <p
          className={cn(
            'flex items-center gap-1 font-sans text-[12px] font-semibold',
            trendColor[trend],
          )}
        >
          <Icon className="h-3 w-3" />
          {trendLabel}
        </p>
      )}
    </div>
  )
}
