/** Playback Records page — route container for /analysis/records, aligned with Billboard RecordsPage. */

import { useAnalysisFilters, analysisApi } from '@/hooks/useAnalysis'
import { useAnalysisQueryState } from '@/components/shared/AnalysisControls'
import { useQuery } from '@tanstack/react-query'
import { queryKeys } from '@/api/query-keys'
import { Skeleton } from '@/components/ui/skeleton'
import { AlertCircle } from 'lucide-react'
import { PlaybackRecordsExperience } from '@/features/analysis/records/PlaybackRecordsExperience'
import { MobilePageHeader } from '@/components/mobile'
import { useViewportMode } from '@/hooks/useViewportMode'

function LoadingSkeleton() {
  return (
    <div className="mx-auto max-w-[1200px]">
      <Skeleton className="mb-4 h-3 w-32" />
      <Skeleton className="mb-8 h-[44px] w-48" />
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
  const { apiParams } = useAnalysisQueryState()

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

  const { data, isLoading, error } = useQuery({
    queryKey: queryKeys.analysis.records(params),
    queryFn: () =>
      analysisApi.records(filters, {
        period: (apiParams.period as 'lifetime') || 'lifetime',
        start_date: (apiParams as Record<string, string>).start_date,
        end_date: (apiParams as Record<string, string>).end_date,
        merge_level: filters.merge_level,
        include_compilations: false,
      }),
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  })

  if (filtersLoading || isLoading) return <LoadingSkeleton />

  if (error) {
    return (
      <div className="mx-auto max-w-[1200px] py-16 text-center">
        <AlertCircle className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
        <p className="font-sans text-[14px] text-muted-foreground">加载播放记录失败</p>
        <p className="mt-1 font-sans text-[12px] text-muted-foreground/60">{String(error)}</p>
      </div>
    )
  }

  if (!data) return null

  return (
    <div className={isPhone ? 'mobile-m4-page' : 'mx-auto max-w-[1200px]'} data-mobile-page={isPhone ? 'playback-records' : undefined}>
      {/* Page header — matches Billboard RecordsPage style */}
      {isPhone ? (
        <MobilePageHeader
          eyebrow="Playback Records"
          title="播放记录"
          description="从强烈高光到长线陪伴，用五个栏目回看个人听歌纪录。"
        />
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
