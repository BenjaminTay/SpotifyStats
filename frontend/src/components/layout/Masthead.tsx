import { Link, useLocation } from 'react-router-dom'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Search, Settings } from 'lucide-react'
import { ThemeToggle } from './ThemeToggle'
import { cn } from '@/lib/utils'
import { getMastheadRouteContext, type MastheadNavTo } from './routeContext'
import { MusicSearchDialog } from '@/features/music/search/MusicSearchDialog'
import { useRuntimeCapabilities } from '@/hooks/useRuntimeCapabilities'

type NavItem = {
  to: MastheadNavTo
  label: string
}

const primaryNavItems: NavItem[] = [
  { to: '/', label: '首页' },
  { to: '/analysis', label: '播放分析' },
  { to: '/billboard', label: '榜单' },
  { to: '/community', label: '社区' },
  { to: '/ai-insights', label: 'AI' },
]

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  return target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)
}

export function Masthead() {
  const { capabilities } = useRuntimeCapabilities()
  const location = useLocation()
  const activeNavRef = useRef<HTMLElement | null>(null)
  const searchTriggerRef = useRef<HTMLButtonElement | null>(null)
  const restoreSearchFocusRef = useRef(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const routeContext = useMemo(
    () => getMastheadRouteContext(location.pathname, location.search),
    [location.pathname, location.search],
  )

  const setActiveNavElement = useCallback((node: HTMLElement | null) => {
    activeNavRef.current = node
  }, [])

  useEffect(() => {
    const isMobile = window.matchMedia('(max-width: 639px)').matches
    if (!isMobile) return
    activeNavRef.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'nearest',
      inline: 'center',
    })
  }, [routeContext.activeNavTo])

  useEffect(() => {
    const handleShortcut = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() !== 'k' || (!event.metaKey && !event.ctrlKey)) return
      if (event.altKey || isEditableTarget(event.target)) return
      event.preventDefault()
      setSearchOpen(true)
    }
    window.addEventListener('keydown', handleShortcut)
    return () => window.removeEventListener('keydown', handleShortcut)
  }, [])

  useEffect(() => {
    if (searchOpen || !restoreSearchFocusRef.current) return
    restoreSearchFocusRef.current = false
    searchTriggerRef.current?.focus()
  }, [searchOpen])

  const handleSearchOpenChange = useCallback((open: boolean) => {
    if (!open) restoreSearchFocusRef.current = true
    setSearchOpen(open)
  }, [])

  const isNavActive = (to: MastheadNavTo) => {
    if (routeContext.activeNavTo) return routeContext.activeNavTo === to
    return to === '/' && location.pathname === '/'
  }

  const navItemClassName = (active: boolean) => cn(
    'inline-flex items-center rounded-[7px] border px-2.5 py-1.5 text-[12px] font-semibold uppercase tracking-[1.2px] transition-colors duration-200 sm:border-0 sm:px-0 sm:py-0.5',
    active
      ? 'border-accent-foreground/20 bg-accent-foreground/10 text-foreground sm:border-b-2 sm:border-accent-foreground sm:bg-transparent'
      : 'border-transparent text-muted-foreground hover:bg-muted/70 hover:text-foreground sm:hover:bg-transparent',
  )

  const utilityLinkClassName = (active: boolean) => cn(
    'inline-flex size-9 items-center justify-center rounded-full border border-border bg-card text-muted-foreground transition-colors duration-200 hover:bg-muted/70 hover:text-foreground',
    active && 'border-accent-foreground/20 bg-accent-foreground/10 text-foreground',
  )

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-card/45 backdrop-blur-[12px] transition-[background,border] duration-400">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 sm:flex-nowrap sm:gap-8 sm:px-10 sm:py-4">
        <div className="flex shrink-0 items-center gap-2 font-serif text-[22px] font-bold tracking-[-0.3px]">
          <span>
            Spotify{' '}
            <span className="italic text-accent-foreground transition-colors duration-400">
              Stats
            </span>
          </span>
          {capabilities.surface === 'public-readonly' && (
            <span className="rounded-full border border-accent-foreground/25 bg-accent-foreground/8 px-2 py-0.5 font-sans text-[9px] font-bold uppercase tracking-[1px] text-accent-foreground">
              公开展示
            </span>
          )}
        </div>
        <nav
          aria-label="主导航"
          className="order-3 flex w-full min-w-0 max-w-full basis-full gap-2 overflow-x-auto whitespace-nowrap pb-1 sm:order-none sm:w-auto sm:max-w-none sm:basis-auto sm:gap-5 sm:pb-0"
        >
          {primaryNavItems.filter((item) => item.to !== '/ai-insights' || capabilities.ai).map((item) => {
            const active = isNavActive(item.to)
            return (
              <Link
                key={item.to}
                to={item.to}
                ref={active ? setActiveNavElement : undefined}
                aria-current={active ? 'page' : undefined}
                className={navItemClassName(active)}
              >
                {item.label}
              </Link>
            )
          })}
        </nav>
        <div className="flex shrink-0 items-center gap-2 sm:order-none">
          <button
            ref={searchTriggerRef}
            type="button"
            aria-label="搜索音乐详情"
            aria-keyshortcuts="Meta+K Control+K"
            onClick={() => setSearchOpen(true)}
            className={utilityLinkClassName(location.pathname === '/music/search')}
          >
            <Search className="h-4.5 w-4.5" aria-hidden="true" />
          </button>
          <ThemeToggle />
          {capabilities.settings && (
            <Link
              to="/settings"
              aria-label="偏好设置"
              className={utilityLinkClassName(routeContext.activeNavTo === '/settings')}
            >
              <Settings className="h-4.5 w-4.5" aria-hidden="true" />
            </Link>
          )}
        </div>
      </div>
      {searchOpen && <MusicSearchDialog open onOpenChange={handleSearchOpenChange} />}
    </header>
  )
}
