import { Outlet } from 'react-router-dom'
import { AnalysisSubNav } from '@/components/shared/AnalysisSubNav'
import { AnalysisTimeRangeSelector } from '@/components/shared/AnalysisTimeRangeSelector'
import { useAnalysisQueryState } from '@/components/shared/AnalysisControls'

export function AnalysisLayout() {
  const { period, periodValue, startDate, endDate, setQuery } = useAnalysisQueryState()

  return (
    <>
      <section className="mb-9">
        <p className="mb-4 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
          Playback / Analysis
        </p>
        <h1 className="mb-3 font-serif text-[48px] font-bold leading-[1.06] tracking-[-1.2px]">
          播放分析
        </h1>
      </section>

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
