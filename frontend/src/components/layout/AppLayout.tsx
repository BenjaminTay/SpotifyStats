import { useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import { Masthead } from './Masthead'
import { NoiseOverlay } from '@/components/shared/NoiseOverlay'
import { preloadWeeklyData, preloadAllTimeData } from '@/hooks/useBillboard'
import { preloadDashboardData } from '@/hooks/useDashboard'
import { useChineseTextVersion } from '@/lib/chinese'
import { useBillboardNameVersion } from '@/lib/billboard-name'

export function AppLayout() {
  useChineseTextVersion()
  useBillboardNameVersion()

  useEffect(() => {
    const timer = window.setTimeout(() => {
      preloadDashboardData()
      preloadWeeklyData()
      preloadAllTimeData()
    }, 600)

    return () => window.clearTimeout(timer)
  }, [])

  return (
    <div className="relative flex min-h-screen flex-col overflow-x-clip">
      <NoiseOverlay />

      {/* Dark mode ambient gradients */}
      <div className="pointer-events-none fixed inset-0 z-0 hidden opacity-50 dark:block">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_60%_50%_at_20%_30%,oklch(0.563_0.18_28.2/0.06),transparent)]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_50%_40%_at_70%_60%,oklch(0.697_0.125_73.5/0.04),transparent)]" />
      </div>

      <Masthead />

      <main className="relative z-1 mx-auto w-full max-w-[1200px] flex-1 px-5 py-8 sm:px-10 sm:py-10">
        <Outlet />
      </main>
    </div>
  )
}
