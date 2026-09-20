import { SnapshotUnavailableError } from '@/api/errors'
/** Playback Records page — route container for /analysis/records, aligned with Billboard RecordsPage. */

import { useAnalysisFilters, analysisApi, usePreparedAnalysisData } from '@/hooks/useAnalysis'
import { useAnalysisQueryState } from '@/components/shared/AnalysisControls'
import { Skeleton } from '@/components/ui/skeleton'
import { AlertCircle } from 'lucide-react'
import { PlaybackRecordsExperience } from '@/features/analysis/records/PlaybackRecordsExperience'
import { MobileAnalysisTimeControl } from '@/features/mobile/analysis/MobileAnalysisTimeControl'
import { useViewportMode } from '@/hooks/useViewportMode'
import { SnapshotStatusNotice } from '@/components/shared/SnapshotStatusNotice'

function LoadingSkeleton({ isPhone = false }: { isPhone?: boolean }) {
  return (
    <div className="mx-auto max-w-[1200px]">
      {!isPhone && (
        <>
          <Skeleton className="mb-4 h-3 w-32" />
          <Skeleton className="mb-8 h-[44px] w-48" />
        </>
      )}
      <Skeleton className="mb-6 h-[40px] w-full rounded-[12px]" />
      {[1, 2, 3].map((i) => (
        <Skeleton key={i} className="mb-5 h-[200px] w-full rounded-[16px]" />
      ))}
    </div>
  )
}

export function AnalysisRecordsPage() {
  const isPhone = useViewportMode() === 'phone'
  const { filters, loading: filtersLoading } = useAnalysisFilters()
  const { period, periodValue, startDate, endDate, setQuery, apiParams } = useAnalysisQueryState()

  const params: Record<string, unknown> = {
    min_ms: filters.min_ms,
    music_only: filters.music_only,
    merge_enabled: filters.merge_enabled,
    dynamic_threshold: filters.dynamic_threshold,
    merge_level: filters.merge_level,
    period: apiParams.period || 'lifetime',
    start_date: (apiParams as Record<string, string>).start_date || undefined,
    end_date: (apiParams as Record<string, string>).end_date || undefined,
  }
  if (filters.max_merge_gap_minutes != null) {
    params.max_merge_gap_minutes = filters.max_merge_gap_minutes
  }

  const { data, loading: isLoading, switching, error, errorObject, refetch } = usePreparedAnalysisData(
    'analysis_records',
    () =>
      analysisApi.records(filters, {
        period: apiParams.period || 'lifetime',
        start_date: (apiParams as Record<string, string>).start_date,
        end_date: (apiParams as Record<string, string>).end_date,
        merge_level: filters.merge_level,
        include_compilations: false,
      }),
    () => analysisApi.prepareSnapshot('analysis_records', filters, {
      ...apiParams,
      merge_level: filters.merge_level,
      include_compilations: false,
    }),
    [params],
    !filtersLoading,
  )

  if (filtersLoading || isLoading) return <LoadingSkeleton isPhone={isPhone} />

  if (error) {
    return (
      <div role={switching ? 'status' : 'alert'} className="mx-auto max-w-[1200px] py-16 text-center">
        <AlertCircle className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
        <p className="font-sans text-[14px] text-muted-foreground">{switching ? '正在准备这个时间范围的数据' : errorObject instanceof SnapshotUnavailableError ? '当前时间范围暂不可用' : '加载播放记录失败'}</p>
        <p className="mt-1 font-sans text-[12px] text-muted-foreground/60">{switching ? '可以停留在当前页面，准备完成后会自动显示。' : error}</p>
        {!switching && <button type="button" className="mt-4 text-sm underline" onClick={refetch}>重试</button>}
      </div>
    )
  }

  if (!data) return null

  return (
    <div className={isPhone ? 'mobile-m4-page' : 'mx-auto max-w-[1200px]'} data-mobile-page={isPhone ? 'playback-records' : undefined}>
      <SnapshotStatusNotice snapshot={data.snapshot} />
      {switching && <p role="status" className="mb-3 text-sm text-muted-foreground">正在切换时间范围…</p>}
      {isPhone ? (
        <div className="mobile-analysis-floating-time-control">
          <MobileAnalysisTimeControl
            compact
            period={period}
            periodValue={periodValue}
            startDate={startDate}
            endDate={endDate}
            onChange={setQuery}
          />
        </div>
      ) : <section className="mt-6 mb-6">
        <p className="mb-2 font-sans text-[11px] font-bold uppercase tracking-[1.5px] text-accent-foreground">Playback Records</p>
        <h2 className="font-serif text-[34px] font-bold leading-tight">
          播放记录
        </h2>
      </section>}

      <PlaybackRecordsExperience data={data.records} />
    </div>
  )
}
