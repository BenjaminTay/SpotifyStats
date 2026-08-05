import { useEffect, useMemo, useState } from 'react'
import { BarChart3, Home, Sparkles, Trophy, Users } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'

import { getMastheadRouteContext, type MobileBottomNavItem } from './routeContext'
import { cn } from '@/lib/utils'

const NAV_ITEMS: Array<{
  id: MobileBottomNavItem
  to: string
  label: string
  icon: typeof Home
}> = [
  { id: 'home', to: '/', label: '首页', icon: Home },
  { id: 'analysis', to: '/analysis/stats', label: '播放', icon: BarChart3 },
  { id: 'billboard', to: '/billboard', label: '榜单', icon: Trophy },
  { id: 'community', to: '/community', label: '社区', icon: Users },
  { id: 'ai', to: '/ai-insights?mode=reports', label: 'AI', icon: Sparkles },
]

function inputModeActive(): boolean {
  const active = document.activeElement
  return active instanceof Element && Boolean(active.closest('[data-mobile-input-mode="true"]'))
}

export function MobileBottomNav() {
  const location = useLocation()
  const [inputFocused, setInputFocused] = useState(false)
  const context = useMemo(
    () => getMastheadRouteContext(location.pathname, location.search),
    [location.pathname, location.search],
  )

  useEffect(() => {
    let frame = 0
    const update = () => setInputFocused(inputModeActive())
    const updateAfterFocus = () => {
      window.cancelAnimationFrame(frame)
      frame = window.requestAnimationFrame(update)
    }
    document.addEventListener('focusin', update)
    document.addEventListener('focusout', updateAfterFocus)
    return () => {
      window.cancelAnimationFrame(frame)
      document.removeEventListener('focusin', update)
      document.removeEventListener('focusout', updateAfterFocus)
    }
  }, [])

  if (!context.showMobileBottomNav || inputFocused) return null

  return (
    <nav className="mobile-bottom-nav" aria-label="移动主导航" data-mobile-shell="bottom-nav">
      <div className="mobile-bottom-nav-inner">
        {NAV_ITEMS.map((item) => {
          const active = context.mobileBottomNavItem === item.id
          const Icon = item.icon
          return (
            <Link
              key={item.id}
              to={item.to}
              aria-current={active ? 'page' : undefined}
              className={cn('mobile-bottom-nav-item', active && 'mobile-bottom-nav-item-active')}
            >
              <span className="mobile-bottom-nav-icon">
                <Icon className="h-[20px] w-[20px]" strokeWidth={active ? 2.2 : 1.8} aria-hidden="true" />
              </span>
              <span>{item.label}</span>
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
