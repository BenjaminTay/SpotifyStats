import { Link, useLocation } from 'react-router-dom'
import { useEffect, useMemo, useRef } from 'react'
import { ThemeToggle } from './ThemeToggle'
import { cn } from '@/lib/utils'
import { getBillboardName, useBillboardNameVersion } from '@/lib/billboard-name'
import { getMastheadRouteContext, type MastheadNavTo } from './routeContext'

type NavItem = {
  to: MastheadNavTo
  label: string
  disabled?: boolean
}

export function Masthead() {
  const version = useBillboardNameVersion()
  const location = useLocation()
  const activeNavRef = useRef<HTMLAnchorElement | null>(null)
  const routeContext = useMemo(
    () => getMastheadRouteContext(location.pathname, location.search),
    [location.pathname, location.search],
  )

  const navItems = useMemo<NavItem[]>(() => [
    { to: '/', label: '总览' },
    { to: '/analysis', label: '分析' },
    { to: '/yearly-review', label: '年度回顾' },
    { to: '/billboard', label: getBillboardName() },
    { to: '/community', label: '社区' },
    { to: '/ai-insights', label: 'AI 洞察' },
    { to: '/account', label: '账户' },
    { to: '/settings', label: '设置' },
  ], [version])

  useEffect(() => {
    const isMobile = window.matchMedia('(max-width: 639px)').matches
    if (!isMobile) return
    activeNavRef.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'nearest',
      inline: 'center',
    })
  }, [routeContext.activeNavTo])

  const isNavActive = (to: MastheadNavTo) => {
    if (routeContext.activeNavTo) return routeContext.activeNavTo === to
    return to === '/' && location.pathname === '/'
  }

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-card/45 backdrop-blur-[12px] transition-[background,border] duration-400">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 sm:flex-nowrap sm:gap-8 sm:px-10 sm:py-4">
        <div className="shrink-0 font-serif text-[22px] font-bold tracking-[-0.3px]">
          Spotify{' '}
          <span className="italic text-accent-foreground transition-colors duration-400">
            Stats
          </span>
        </div>
        <nav className="order-3 flex w-full min-w-0 max-w-full basis-full gap-2 overflow-x-auto whitespace-nowrap pb-1 sm:order-none sm:w-auto sm:max-w-none sm:basis-auto sm:gap-6 sm:pb-0">
          {navItems.map((item) => {
            const active = isNavActive(item.to)
            return item.disabled ? (
              <span
                key={item.to}
                className="cursor-not-allowed pb-0.5 text-[12px] font-semibold uppercase tracking-[1.2px] text-muted-foreground/40"
              >
                {item.label}
              </span>
            ) : (
              <Link
                key={item.to}
                to={item.to}
                ref={active ? activeNavRef : undefined}
                aria-current={active ? 'page' : undefined}
                className={cn(
                  'rounded-[7px] border px-2.5 py-1.5 text-[12px] font-semibold uppercase tracking-[1.2px] transition-colors duration-200 sm:border-0 sm:px-0 sm:py-0.5',
                  active
                    ? 'border-accent-foreground/20 bg-accent-foreground/10 text-foreground sm:border-b-2 sm:border-accent-foreground sm:bg-transparent'
                    : 'border-transparent text-muted-foreground hover:bg-muted/70 hover:text-foreground sm:hover:bg-transparent',
                )}
              >
                {item.label}
              </Link>
            )
          })}
        </nav>
        <div className="shrink-0 sm:order-none">
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
