import { cn } from '@/lib/utils'

export function RankNumber({ rank, className }: { rank: number; className?: string }) {
  const color = rank === 1
    ? 'text-accent-foreground'
    : rank === 3
      ? 'text-[#C17A4E] dark:text-[#C97B6B]'
      : 'text-muted-foreground'

  return (
    <span className={cn('font-serif font-semibold tabular-nums', color, className)}>
      {String(rank).padStart(2, '0')}
    </span>
  )
}
