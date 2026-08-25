import { cn } from '@/lib/utils'

export interface RankChange {
  type: 'up' | 'down' | 'same' | 'new' | 're'
  delta?: number
}

export const CHART_MOVEMENT_LABEL_CLASS = 'font-sans text-[10px] font-bold uppercase tracking-[1px]'

export function ChangeCell({ change }: { change: RankChange }) {
  if (change.type === 'new') {
    return (
      <span className={cn(CHART_MOVEMENT_LABEL_CLASS, 'text-[#3B5998] dark:text-[#7B9CC8]')}>
        NEW
      </span>
    )
  }
  if (change.type === 're') {
    return (
      <span className={cn(CHART_MOVEMENT_LABEL_CLASS, 'text-[#B8860B] dark:text-[#D4A24E]')}>
        RE
      </span>
    )
  }
  if (change.type === 'same') {
    return <span className="text-[11px] text-muted-foreground">—</span>
  }
  const arrow = change.type === 'up' ? '↑' : '↓'
  const color =
    change.type === 'up'
      ? 'text-[#4A6B4F] dark:text-[#7D9B76]'
      : 'text-accent-foreground'
  return <span className={cn('text-[11px] font-bold', color)}>{arrow} {change.delta}</span>
}
