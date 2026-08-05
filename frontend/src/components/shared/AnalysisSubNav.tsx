import type { ReactNode } from 'react'
import { NavLink, useSearchParams } from 'react-router-dom'
import { cn } from '@/lib/utils'

const NAV_ITEMS = [
  { to: '/analysis/stats', label: '播放统计', preserveTimeRange: true },
  { to: '/analysis/charts', label: '播放排行', preserveTimeRange: true },
  { to: '/yearly-review', label: '年度总结', preserveTimeRange: false },
  { to: '/analysis/records', label: '播放记录', preserveTimeRange: true },
  { to: '/account', label: '账号中心', preserveTimeRange: false },
]

const TIME_RANGE_PARAMS = ['period', 'period_value', 'start', 'end']

function usePreservedTo(path: string, preserveTimeRange: boolean): string {
  const [searchParams] = useSearchParams()
  if (!preserveTimeRange) return path

  const preserved = new URLSearchParams()
  TIME_RANGE_PARAMS.forEach((key) => {
    const val = searchParams.get(key)
    if (val) preserved.set(key, val)
  })
  const qs = preserved.toString()
  return qs ? `${path}?${qs}` : path
}

function TabLink({
  to,
  label,
  preserveTimeRange,
}: {
  to: string
  label: string
  preserveTimeRange: boolean
}) {
  const preservedTo = usePreservedTo(to, preserveTimeRange)
  return (
    <NavLink
      to={preservedTo}
      end
      role="tab"
      className={({ isActive }) =>
        cn(
          'shrink-0 pb-2.5 font-sans text-[13px] font-medium border-b-2 transition-colors -mb-[1px]',
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
    <>
      {right && <div className="mb-4 flex justify-end md:hidden">{right}</div>}
      <nav className="mb-7 hidden min-h-9 min-w-0 flex-wrap items-end gap-x-6 gap-y-2 border-b border-border md:flex">
      <div className="flex min-w-0 max-w-full gap-x-6 overflow-x-auto whitespace-nowrap" role="tablist">
        {NAV_ITEMS.map((item) => (
          <TabLink
            key={item.to}
            to={item.to}
            label={item.label}
            preserveTimeRange={item.preserveTimeRange}
          />
        ))}
      </div>
      {right ? (
        <div className="ml-auto -mb-px -translate-y-[3px]">{right}</div>
      ) : (
        <div aria-hidden="true" className="basis-full h-9 sm:hidden" />
      )}
      </nav>
    </>
  )
}
