import { ChevronLeft, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

interface WeekSelectorProps {
  weekLabel: string
  dateRange?: string
  onPrev: () => void
  onNext: () => void
  disablePrev?: boolean
  disableNext?: boolean
}

export function WeekSelector({
  weekLabel,
  dateRange,
  onPrev,
  onNext,
  disablePrev,
  disableNext,
}: WeekSelectorProps) {
  return (
    <div className="mb-6 flex items-center gap-3.5">
      <button
        onClick={onPrev}
        disabled={disablePrev}
        className={cn(
          'flex h-[34px] w-[34px] items-center justify-center rounded-full border border-border bg-card backdrop-blur-[12px] text-muted-foreground transition-[background,border,color] duration-400',
          disablePrev
            ? 'cursor-not-allowed opacity-40'
            : 'cursor-pointer hover:border-foreground/15 hover:text-foreground',
        )}
      >
        <ChevronLeft className="h-4 w-4" />
      </button>
      <div>
        <div className="font-serif text-[28px] font-semibold leading-[1.1]">
          {weekLabel}
        </div>
        {dateRange && (
          <div className="font-sans text-[13px] text-muted-foreground">
            {dateRange}
          </div>
        )}
      </div>
      <button
        onClick={onNext}
        disabled={disableNext}
        className={cn(
          'flex h-[34px] w-[34px] items-center justify-center rounded-full border border-border bg-card backdrop-blur-[12px] text-muted-foreground transition-[background,border,color] duration-400',
          disableNext
            ? 'cursor-not-allowed opacity-40'
            : 'cursor-pointer hover:border-foreground/15 hover:text-foreground',
        )}
      >
        <ChevronRight className="h-4 w-4" />
      </button>
    </div>
  )
}
