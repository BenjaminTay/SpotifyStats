import { cn } from '@/lib/utils'
import type { CareerEvent } from '@/types/billboard'

interface CareerTimelineProps {
  events: CareerEvent[]
  className?: string
}

export function CareerTimeline({ events, className }: CareerTimelineProps) {
  if (!events.length) return null
  return (
    <div className={cn('space-y-0', className)}>
      {events.map((ev, i) => {
        const isFirst = i === 0
        const isLast = i === events.length - 1
        const dotColor = isFirst
          ? 'bg-amber-500 ring-amber-500/20'
          : isLast
            ? 'bg-rose-400 ring-rose-400/20'
            : 'bg-muted-foreground/30 ring-muted-foreground/10'

        return (
          <div key={i} className="flex gap-4">
            {/* Year + dot + line */}
            <div className="flex w-[52px] flex-col items-center shrink-0">
              <span className="font-sans text-[12px] font-bold tabular-nums text-muted-foreground">
                {ev.year}
              </span>
              <div className={cn(
                'mt-1.5 h-2.5 w-2.5 rounded-full ring-2',
                dotColor,
              )} />
              {!isLast && (
                <div className="mt-0.5 w-px flex-1 bg-gradient-to-b from-border to-transparent" />
              )}
            </div>
            {/* Event content */}
            <div className={cn('pb-6 flex-1', isLast && 'pb-0')}>
              <div className={cn(
                'rounded-lg px-3 py-2 -ml-1',
                isFirst && 'bg-amber-500/5 border border-amber-500/10',
              )}>
                <p className="font-sans text-[13px] font-semibold leading-snug text-foreground/85">{ev.event}</p>
                {ev.detail && (
                  <p className="mt-0.5 font-sans text-[12px] leading-snug text-muted-foreground">{ev.detail}</p>
                )}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
