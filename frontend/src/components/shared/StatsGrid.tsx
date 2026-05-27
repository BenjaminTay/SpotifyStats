import { cn } from '@/lib/utils'
import type { StatItem } from '@/types/billboard'

const GRADIENTS = [
  'from-amber-500/10 to-orange-500/5',
  'from-rose-500/10 to-pink-500/5',
  'from-sky-500/10 to-cyan-500/5',
  'from-violet-500/10 to-purple-500/5',
  'from-emerald-500/10 to-teal-500/5',
  'from-fuchsia-500/10 to-rose-500/5',
]

const ACCENTS = [
  'text-amber-600 dark:text-amber-400',
  'text-rose-600 dark:text-rose-400',
  'text-sky-600 dark:text-sky-400',
  'text-violet-600 dark:text-violet-400',
  'text-emerald-600 dark:text-emerald-400',
  'text-fuchsia-600 dark:text-fuchsia-400',
]

interface StatsGridProps {
  stats: StatItem[]
  className?: string
}

export function StatsGrid({ stats, className }: StatsGridProps) {
  if (!stats.length) return null
  return (
    <div className={cn('grid grid-cols-2 gap-3', className)}>
      {stats.map((s, i) => {
        const gradient = GRADIENTS[i % GRADIENTS.length]
        const accent = ACCENTS[i % ACCENTS.length]
        // If value is a long string (not just a number), use smaller font
        const isLong = s.value.length > 8 && !/^\d/.test(s.value)
        return (
          <div
            key={s.label}
            className={cn(
              'relative overflow-hidden rounded-xl bg-gradient-to-br p-4',
              gradient,
            )}
          >
            {/* Decorative corner accent */}
            <div className={cn('absolute -right-2 -top-2 h-8 w-8 rounded-full opacity-20', accent.replace('text-', 'bg-'))} aria-hidden />
            <p className={cn(
              'relative font-serif font-semibold leading-none',
              isLong ? 'text-[14px]' : 'text-[24px]',
              accent,
            )}>
              {s.value}
            </p>
            <p className="relative mt-2 font-sans text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground">{s.label}</p>
          </div>
        )
      })}
    </div>
  )
}
