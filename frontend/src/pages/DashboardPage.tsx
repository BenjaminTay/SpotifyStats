import { HomeDesktopExperience } from '@/features/home/HomeDesktopExperience'
import { HomeEmpty, HomeError, HomeLoading } from '@/features/home/HomeStates'
import { HomePhoneExperience } from '@/features/home/HomePhoneExperience'
import { useAnalysisFilters } from '@/hooks/useAnalysis'
import { useHomeOverview } from '@/hooks/useHome'
import { useViewportMode } from '@/hooks/useViewportMode'

import '@/features/home/home.css'

export function DashboardPage() {
  const isPhone = useViewportMode() === 'phone'
  const { filters, loading: filtersLoading } = useAnalysisFilters()
  const query = useHomeOverview(filters, !filtersLoading)

  if (filtersLoading || query.isLoading) return <HomeLoading phone={isPhone} />
  if (query.error || !query.data) return <HomeError phone={isPhone} onRetry={() => void query.refetch()} />
  if (query.data.state === 'empty') return <HomeEmpty phone={isPhone} />

  return isPhone
    ? <HomePhoneExperience data={query.data} />
    : <HomeDesktopExperience data={query.data} />
}
