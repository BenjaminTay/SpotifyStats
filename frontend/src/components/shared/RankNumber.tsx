import { cn } from '@/lib/utils'
import { rankToneClass } from '@/lib/rank-tone'

export function RankNumber({
  rank,
  className,
  highlightTopThree = false,
}: {
  rank: number
  className?: string
  highlightTopThree?: boolean
}) {
  const color = rankToneClass(rank, highlightTopThree)

  return (
    <span className={cn('font-serif font-semibold tabular-nums', color, className)}>
      {String(rank).padStart(2, '0')}
    </span>
  )
}
