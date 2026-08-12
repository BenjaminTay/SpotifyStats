import { useEffect, useRef, Component } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAnalysisFilters } from '@/hooks/useAnalysis'
import {
  usePrewarmYearlyReviews,
  useYearlyReviewGenerationStatus,
  useYearlyReviewV2,
  useYearlyReviewV2AvailableYears,
} from '@/hooks/useYearlyReviewV2'
import { cn } from '@/lib/utils'
import { AnalysisPageHeader } from '@/components/shared/AnalysisPageHeader'
import { AnalysisSubNav } from '@/components/shared/AnalysisSubNav'
import { YearlyReviewPhoneExperience } from '@/features/mobile/yearly-v2/YearlyReviewPhoneExperience'
import { useViewportMode } from '@/hooks/useViewportMode'
import { YearlyReviewDesktopExperience } from '@/features/yearly-review/YearlyReviewDesktopExperience'
import { YearlyReviewV2Empty, YearlyReviewV2Error, YearlyReviewV2Loading } from '@/features/yearly-review/YearlyReviewStates'

class ErrorBoundary extends Component<{ children: React.ReactNode }, { error: Error | null }> {
  constructor(props: { children: React.ReactNode }) {
    super(props)
    this.state = { error: null }
  }
  static getDerivedStateFromError(error: Error) {
    return { error }
  }
  render() {
    if (this.state.error) {
      if (import.meta.env.DEV) {
        console.error('YearlyReview ErrorBoundary caught:', this.state.error)
      }
      return (
        <div className="py-16 text-center">
          <p className="font-serif text-[28px] font-bold mb-3">页面渲染错误</p>
          {import.meta.env.DEV && (
            <p className="font-sans text-[13px] text-muted-foreground mb-4 font-mono whitespace-pre-wrap break-all max-w-lg mx-auto">
              {this.state.error.message}
            </p>
          )}
          <p className="font-sans text-[13px] text-muted-foreground/60">
            请刷新页面后重试。如问题持续，请联系管理员。
          </p>
        </div>
      )
    }
    return this.props.children
  }
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <div className="h-64 animate-pulse rounded-2xl bg-muted" />
      <div className="grid grid-cols-3 gap-6">
        <div className="h-48 animate-pulse rounded-xl bg-muted" />
        <div className="h-48 animate-pulse rounded-xl bg-muted" />
        <div className="h-48 animate-pulse rounded-xl bg-muted" />
      </div>
    </div>
  )
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="py-16 text-center">
      <p className="font-sans text-[14px] text-muted-foreground mb-2">加载失败</p>
      <p className="font-sans text-[13px] text-muted-foreground/60">{message}</p>
    </div>
  )
}

const EMPTY_YEARS: number[] = []

export function YearlyReviewPage() {
  const isPhone = useViewportMode() === 'phone'
  const [searchParams, setSearchParams] = useSearchParams()
  const { filters, loading: filtersLoading } = useAnalysisFilters()
  const v2YearsQuery = useYearlyReviewV2AvailableYears(true)
  const v2Years = v2YearsQuery.data?.years ?? EMPTY_YEARS

  const yearOptions = [...v2Years].sort((left, right) => left - right)
  const yearsLoading = v2YearsQuery.isLoading
  const yearsError = v2YearsQuery.error instanceof Error ? v2YearsQuery.error.message : null

  // Determine current year: valid URL param > newest available year.
  const yearParam = searchParams.get('year')
  const latestYear = v2Years.length > 0 ? Math.max(...v2Years) : null
  const currentYear = yearParam && v2Years.includes(parseInt(yearParam))
    ? parseInt(yearParam)
    : latestYear

  // Keep the URL year valid for the annual report.
  useEffect(() => {
    const parsedYear = yearParam ? parseInt(yearParam) : null
    if (v2Years.length > 0 && (!parsedYear || !v2Years.includes(parsedYear))) {
      setSearchParams({ year: String(latestYear) })
    }
  }, [latestYear, setSearchParams, v2Years, yearParam])

  const v2Review = useYearlyReviewV2(
    currentYear ?? 0,
    filters,
    !filtersLoading,
  )
  const generationEnabled = !filtersLoading
    && currentYear != null
    && v2Years.length > 0
  const generationStatus = useYearlyReviewGenerationStatus(v2Years, filters, generationEnabled)
  const { mutate: prewarmYearlyReviews } = usePrewarmYearlyReviews(filters)
  const lastPrewarmRequestRef = useRef<string | null>(null)
  useEffect(() => {
    if (!generationEnabled || currentYear == null) return
    const years = [...v2Years].sort((left, right) => left - right)
    const requestKey = `${generationStatus.filterKey}|${years.join(',')}|${currentYear}`
    if (lastPrewarmRequestRef.current === requestKey) return
    lastPrewarmRequestRef.current = requestKey
    prewarmYearlyReviews(
      { years, foreground_year: currentYear },
      {
        onError: () => {
          if (lastPrewarmRequestRef.current === requestKey) lastPrewarmRequestRef.current = null
        },
      },
    )
  }, [currentYear, generationEnabled, generationStatus.filterKey, prewarmYearlyReviews, v2Years])
  const v2Data = v2Review.data?.year === currentYear ? v2Review.data : null
  const currentGenerationTask = generationStatus.tasks.find(task => task.year === currentYear) ?? null
  const currentTaskIsActive = currentGenerationTask?.state === 'queued'
    || currentGenerationTask?.state === 'running'
  const refetchV2Review = v2Review.refetch
  const previousTaskStateRef = useRef<Record<number, string | undefined>>({})
  useEffect(() => {
    if (currentYear == null || currentGenerationTask == null) return
    const previousState = previousTaskStateRef.current[currentYear]
    previousTaskStateRef.current[currentYear] = currentGenerationTask.state
    if (
      currentGenerationTask.state === 'ready'
      && (
        previousState === 'queued'
        || previousState === 'running'
        || (previousState == null && v2Review.isError)
      )
      && !v2Data
    ) {
      void refetchV2Review()
    }
  }, [currentGenerationTask, currentYear, refetchV2Review, v2Data, v2Review.isError])
  const v2Pending = filtersLoading
    || currentTaskIsActive
    || v2Review.isLoading
    || v2Review.isPlaceholderData
    || (!v2Data && v2Review.isFetching)

  return (
    <>
      {!isPhone && <AnalysisPageHeader />}
      {!isPhone && <AnalysisSubNav />}

      {/* 年份选择器 */}
      <div className={cn('flex items-center', isPhone ? 'mobile-yearly-controls' : 'mb-8')}>
        <div className="flex max-w-full gap-2 overflow-x-auto pb-1">
          {yearOptions.map(y => (
            <button
              key={y}
              onClick={() => setSearchParams({ year: String(y) })}
              className={cn(
                'px-4 py-1.5 rounded-full font-sans text-[13px] font-medium transition-colors',
                y === currentYear
                  ? 'bg-accent-foreground text-card'
                  : 'bg-muted text-muted-foreground hover:text-foreground',
              )}
            >
              {y}
            </button>
          ))}
        </div>
      </div>

      {/* 内容区域 */}
      <ErrorBoundary>
        {yearsLoading && <LoadingSkeleton />}
        {yearsError && <ErrorState message={yearsError} />}

        {!yearsLoading && !yearsError && (
          <>
            {v2Pending && (
              <YearlyReviewV2Loading
                year={currentYear ?? new Date().getFullYear()}
                task={currentGenerationTask}
              />
            )}
            {!v2Pending && v2Review.error && (
              <YearlyReviewV2Error
                message={v2Review.error instanceof Error ? v2Review.error.message : '未知错误'}
                onRetry={() => void v2Review.refetch()}
              />
            )}

            {isPhone && v2Data && v2Data.status !== 'empty' && (
              <YearlyReviewPhoneExperience
                key={`${v2Data.year}-${v2Data.filter_context.filter_fingerprint}`}
                report={v2Data}
              />
            )}
            {!isPhone && v2Data && v2Data.status !== 'empty' && (
              <YearlyReviewDesktopExperience report={v2Data} />
            )}
            {v2Data?.status === 'empty' && <YearlyReviewV2Empty year={currentYear ?? 0} />}
          </>
        )}
      </ErrorBoundary>
    </>
  )
}
