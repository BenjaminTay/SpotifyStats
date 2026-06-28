import { Outlet } from 'react-router-dom'
import { AnalysisPageHeader } from '@/components/shared/AnalysisPageHeader'
import { AnalysisSubNav } from '@/components/shared/AnalysisSubNav'
import { AnalysisTimeRangeSelector } from '@/components/shared/AnalysisTimeRangeSelector'
import { useAnalysisQueryState } from '@/components/shared/AnalysisControls'

export function AnalysisLayout() {
  const { period, periodValue, startDate, endDate, setQuery } = useAnalysisQueryState()

  return (
    <>
      <AnalysisPageHeader />
      <AnalysisSubNav
        right={
          <AnalysisTimeRangeSelector
            period={period}
            periodValue={periodValue}
            startDate={startDate}
            endDate={endDate}
            onChange={setQuery}
          />
        }
      />
      <Outlet />
    </>
  )
}
