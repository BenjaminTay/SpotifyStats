import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'

const NAV_ITEMS = [
  { to: '/analysis/stats', label: '总体统计' },
  { to: '/analysis/charts', label: '个人排行榜' },
]

export function AnalysisSubNav() {
  return (
    <nav className="mb-7 flex flex-wrap gap-x-6 gap-y-2 border-b border-border" role="tablist">
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
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
          {item.label}
        </NavLink>
      ))}
    </nav>
  )
}
