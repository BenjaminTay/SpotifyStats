import type { ReactNode } from 'react'
import { NavLink, useSearchParams } from 'react-router-dom'
import { cn } from '@/lib/utils'

const NAV_ITEMS = [
  { to: '/analysis/stats', label: '总体统计' },
  { to: '/analysis/charts', label: '个人排行榜' },
  { to: '/analysis/records', label: '播放记录' },
]

const TIME_RANGE_PARAMS = ['period', 'period_value', 'start', 'end']

function usePreservedTo(path: string): string {
  const [searchParams] = useSearchParams()
  const preserved = new URLSearchParams()
  TIME_RANGE_PARAMS.forEach((key) => {
    const val = searchParams.get(key)
    if (val) preserved.set(key, val)
  })
  const qs = preserved.toString()
  return qs ? `${path}?${qs}` : path
}

function TabLink({ to, label }: { to: string; label: string }) {
  const preservedTo = usePreservedTo(to)
  return (
    <NavLink
      to={preservedTo}
      end
      role="tab"
      className={({ isActive }) =>
        cn(
          'pb-2.5 font-sans text-[13px] font-medium border-b-2 transition-colors -mb-[1px]',
          isActive
            ? 'border-accent-foreground text-foreground font-semibold'
            : 'border-transparent text-muted-foreground hover:text-foreground',
        )
      }
    >
      {label}
    </NavLink>
  )
}

export function AnalysisSubNav({ right }: { right?: ReactNode }) {
  return (
    <nav className="mb-7 flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-border">
      <div className="flex gap-x-6" role="tablist">
        {NAV_ITEMS.map((item) => (
          <TabLink key={item.to} to={item.to} label={item.label} />
        ))}
      </div>
      {right && <div className="ml-auto pb-2.5 -mb-[1px]">{right}</div>}
    </nav>
  )
}
