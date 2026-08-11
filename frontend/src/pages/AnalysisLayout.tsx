import { Outlet } from 'react-router-dom'
import { AnalysisPageHeader } from '@/components/shared/AnalysisPageHeader'
import { AnalysisSubNav } from '@/components/shared/AnalysisSubNav'
import { AnalysisTimeRangeSelector } from '@/components/shared/AnalysisTimeRangeSelector'
import { useAnalysisQueryState } from '@/components/shared/AnalysisControls'
import { useViewportMode } from '@/hooks/useViewportMode'

export function AnalysisLayout() {
  const { period, periodValue, startDate, endDate, setQuery } = useAnalysisQueryState()
  const isPhone = useViewportMode() === 'phone'

  return (
    <>
      <AnalysisPageHeader />
      <AnalysisSubNav
        right={!isPhone ? (
          <AnalysisTimeRangeSelector
            period={period}
            periodValue={periodValue}
            startDate={startDate}
            endDate={endDate}
            onChange={setQuery}
          />
          ) : undefined}
      />
      <Outlet />
    </>
  )
}
