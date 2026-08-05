import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'

const NAV_ITEMS = [
  { to: '/billboard', label: '周榜', active: 'weekly' as const },
  { to: '/billboard/number-ones', label: '每周榜首', active: 'number-ones' as const },
  { to: '/billboard/year-end', label: '年榜', active: 'year-end' as const },
  { to: '/billboard/all-time', label: '总榜', active: 'all-time' as const },
  { to: '/billboard/records', label: '榜单记录', active: 'records' as const },
  { to: '/billboard/versus', label: '对决', active: 'versus' as const },
]

interface BillboardSubNavProps {
  active: 'weekly' | 'number-ones' | 'all-time' | 'year-end' | 'records' | 'versus'
}

export function BillboardSubNav({ active }: BillboardSubNavProps) {
  return (
    <nav className="hidden max-w-full gap-6 overflow-x-auto border-b border-border md:flex" role="tablist">
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === '/billboard'}
          role="tab"
          aria-selected={active === item.active}
          className={cn(
            'shrink-0 pb-2.5 font-sans text-[13px] font-medium border-b-2 transition-colors -mb-[1px]',
            active === item.active
              ? 'border-accent-foreground text-foreground font-semibold'
              : 'border-transparent text-muted-foreground hover:text-foreground',
          )}
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  )
}
