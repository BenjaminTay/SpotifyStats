import { useState, useEffect, useRef, Suspense, lazy, Component } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { queryKeys } from '@/api/query-keys'
import { useAnalysisFilters } from '@/hooks/useAnalysis'
import { useYearlyReview } from '@/hooks/useYearlyReview'
import {
  usePrewarmYearlyReviews,
  useYearlyReviewGenerationStatus,
  useYearlyReviewV2,
  useYearlyReviewV2AvailableYears,
} from '@/hooks/useYearlyReviewV2'
import { CustomSummary } from '@/pages/yearly-review/CustomSummary'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import { AnalysisPageHeader } from '@/components/shared/AnalysisPageHeader'
import { AnalysisSubNav } from '@/components/shared/AnalysisSubNav'
import { MobileYearlyChapterNav } from '@/features/mobile/yearly/MobileYearlyChapterNav'
import { YearlyPeriodNotice } from '@/features/mobile/yearly/YearlyPeriodNotice'
import { useViewportMode } from '@/hooks/useViewportMode'
import { YearlyReviewDesktopExperience } from '@/features/yearly-review/YearlyReviewDesktopExperience'
import { YearlyReviewV2Empty, YearlyReviewV2Error, YearlyReviewV2Loading } from '@/features/yearly-review/YearlyReviewStates'

// OfficialWrapped 懒加载
const OfficialWrapped = lazy(() => import('@/pages/yearly-review/OfficialWrapped').then(m => ({ default: m.OfficialWrapped })))

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

function EmptyState({ year }: { year: number }) {
  return (
    <div className="py-16 text-center">
      <p className="font-serif text-[28px] font-bold mb-3">{year} 年暂无数据</p>
      <p className="font-sans text-[14px] text-muted-foreground">换个年份试试</p>
    </div>
  )
}

type TabKey = 'custom' | 'official'
const EMPTY_YEARS: number[] = []

export function YearlyReviewPage() {
  const isPhone = useViewportMode() === 'phone'
  const [searchParams, setSearchParams] = useSearchParams()
  const [activeTab, setActiveTab] = useState<TabKey>('custom')
  const { filters, loading: filtersLoading } = useAnalysisFilters()
  const playYearsQuery = useQuery({
    queryKey: queryKeys.yearlyReview.availableYears(),
    queryFn: () => api.get<{ years: number[] }>('/wrapped/available-years'),
    enabled: isPhone && activeTab === 'custom',
  })
  const wrappedYearsQuery = useQuery({
    queryKey: queryKeys.yearlyReview.hubAvailableYears(),
    queryFn: () => api.get<{ years: number[] }>('/wrapped-hub/available-years'),
    enabled: activeTab === 'official',
  })
  const v2YearsQuery = useYearlyReviewV2AvailableYears(!isPhone && activeTab === 'custom')

  const playYears = playYearsQuery.data?.years ?? []
  const wrappedYears = wrappedYearsQuery.data?.years ?? []
  const v2Years = v2YearsQuery.data?.years ?? EMPTY_YEARS

  // Per-tab available years
  const displayYears = activeTab === 'custom' ? (isPhone ? playYears : v2Years) : wrappedYears
  const yearOptions = [...displayYears].sort((left, right) => left - right)
  const activeYearsQuery = activeTab === 'official' ? wrappedYearsQuery : isPhone ? playYearsQuery : v2YearsQuery
  const yearsLoading = activeYearsQuery.isLoading
  const yearsError = activeYearsQuery.error instanceof Error ? activeYearsQuery.error.message : null

  // Determine current year: URL param > latest from active tab
  const yearParam = searchParams.get('year')
  const latestYear = displayYears.length > 0 ? Math.max(...displayYears) : null
  const latestCompleteYear = latestYear === new Date().getFullYear() && displayYears.includes(latestYear - 1)
    ? latestYear - 1
    : latestYear
  const preferredYear = !isPhone && activeTab === 'custom' ? latestCompleteYear : latestYear
  const currentYear = yearParam && displayYears.includes(parseInt(yearParam))
    ? parseInt(yearParam)
    : preferredYear

  // Keep the URL year valid for the active tab.
  useEffect(() => {
    const parsedYear = yearParam ? parseInt(yearParam) : null
    if (displayYears.length > 0 && (!parsedYear || !displayYears.includes(parsedYear))) {
      setSearchParams({ year: String(preferredYear) })
    }
  }, [displayYears, preferredYear, setSearchParams, yearParam])

  const legacyReview = useYearlyReview(
    activeTab === 'custom' ? (currentYear ?? 0) : 0,
    isPhone && activeTab === 'custom',
  )
  const v2Review = useYearlyReviewV2(
    activeTab === 'custom' ? (currentYear ?? 0) : 0,
    filters,
    !isPhone && activeTab === 'custom' && !filtersLoading,
  )
  const generationEnabled = !isPhone
    && activeTab === 'custom'
    && !filtersLoading
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
  const data = legacyReview.data
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

      {/* 年份选择器 + Tab 导航 */}
      <div className={cn('mb-8 flex items-center justify-between', isPhone && 'mobile-yearly-controls')}>
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
              {y === new Date().getFullYear() && activeTab === 'custom' ? `${y} · 进行中` : y}
            </button>
          ))}
        </div>
        <div className="flex gap-6 border-b border-border">
          {[
            { key: 'custom' as TabKey, label: '年度总结' },
            { key: 'official' as TabKey, label: '官方 Wrapped' },
          ].map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                'pb-2.5 font-sans text-[13px] font-medium border-b-2 transition-colors -mb-[1px]',
                activeTab === tab.key
                  ? 'border-accent-foreground text-foreground font-semibold'
                  : 'border-transparent text-muted-foreground hover:text-foreground',
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {isPhone && activeTab === 'custom' && data?.reporting_period && (
        <YearlyPeriodNotice period={data.reporting_period} />
      )}

      {isPhone && activeTab === 'custom' && data && !data.empty && <MobileYearlyChapterNav />}

      {/* 内容区域 */}
      <ErrorBoundary>
        {yearsLoading && <LoadingSkeleton />}
        {yearsError && <ErrorState message={yearsError} />}

        {!yearsLoading && !yearsError && (
          <>
            {isPhone && legacyReview.loading && <LoadingSkeleton />}
            {isPhone && legacyReview.error && <ErrorState message={legacyReview.error} />}
            {!isPhone && activeTab === 'custom' && v2Pending && (
              <YearlyReviewV2Loading
                year={currentYear ?? new Date().getFullYear()}
                task={currentGenerationTask}
              />
            )}
            {!isPhone && activeTab === 'custom' && !v2Pending && v2Review.error && (
              <YearlyReviewV2Error
                message={v2Review.error instanceof Error ? v2Review.error.message : '未知错误'}
                onRetry={() => void v2Review.refetch()}
              />
            )}

            {isPhone && activeTab === 'custom' && data && !data.empty && (
              <div className={cn(isPhone && 'mobile-yearly-story')}>
                <CustomSummary data={data} />
              </div>
            )}
            {!isPhone && activeTab === 'custom' && v2Data && v2Data.status !== 'empty' && (
              <YearlyReviewDesktopExperience report={v2Data} />
            )}
            {activeTab === 'official' && (
              <Suspense fallback={<LoadingSkeleton />}>
                <OfficialWrapped />
              </Suspense>
            )}
            {isPhone && activeTab === 'custom' && data?.empty && <EmptyState year={currentYear ?? 0} />}
            {!isPhone && activeTab === 'custom' && v2Data?.status === 'empty' && <YearlyReviewV2Empty year={currentYear ?? 0} />}
          </>
        )}
      </ErrorBoundary>
    </>
  )
}
