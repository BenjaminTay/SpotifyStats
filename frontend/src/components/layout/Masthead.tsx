import { NavLink } from 'react-router-dom'
import { ThemeToggle } from './ThemeToggle'
import { cn } from '@/lib/utils'

type NavItem = {
  to: string
  label: string
  disabled?: boolean
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', label: '总览' },
  { to: '/analysis', label: '分析' },
  { to: '/yearly-review', label: '年度回顾' },
  { to: '/billboard', label: 'Billboard' },
  { to: '/settings', label: '设置' },
]

export function Masthead() {
  return (
    <header className="sticky top-0 z-50 border-b border-border bg-card/45 backdrop-blur-[12px] transition-[background,border] duration-400">
      <div className="flex items-center justify-between px-10 py-4">
        <div className="flex items-center gap-8">
          <div className="flex items-baseline gap-0.5 font-serif text-[22px] font-bold tracking-[-0.3px]">
            Spotify{' '}
            <span className="italic text-accent-foreground transition-colors duration-400">
              Stats
            </span>
          </div>
          <nav className="flex gap-6">
            {NAV_ITEMS.map((item) =>
              item.disabled ? (
                <span
                  key={item.to}
                  className="cursor-not-allowed pb-0.5 text-[12px] font-semibold uppercase tracking-[1.2px] text-muted-foreground/40"
                >
                  {item.label}
                </span>
              ) : (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    cn(
                      'pb-0.5 text-[12px] font-semibold uppercase tracking-[1.2px] transition-colors duration-200',
                      'border-b-2',
                      isActive
                        ? 'border-accent-foreground text-foreground'
                        : 'border-transparent text-muted-foreground hover:text-foreground',
                    )
                  }
                >
                  {item.label}
                </NavLink>
              ),
            )}
          </nav>
        </div>
        <ThemeToggle />
      </div>
    </header>
  )
}
