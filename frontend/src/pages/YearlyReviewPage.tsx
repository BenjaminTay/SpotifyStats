import { useState, useEffect, Suspense, lazy, Component } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { queryKeys } from '@/api/query-keys'
import { useYearlyReview } from '@/hooks/useYearlyReview'
import { CustomSummary } from '@/pages/yearly-review/CustomSummary'
import { ShareButton } from '@/pages/yearly-review/ShareButton'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import { AnalysisPageHeader } from '@/components/shared/AnalysisPageHeader'
import { AnalysisSubNav } from '@/components/shared/AnalysisSubNav'
import { MobilePageHeader } from '@/components/mobile'
import { MobileYearlyChapterNav } from '@/features/mobile/yearly/MobileYearlyChapterNav'
import { useViewportMode } from '@/hooks/useViewportMode'

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

export function YearlyReviewPage() {
  const isPhone = useViewportMode() === 'phone'
  const [searchParams, setSearchParams] = useSearchParams()
  const [activeTab, setActiveTab] = useState<TabKey>('custom')
  const playYearsQuery = useQuery({
    queryKey: queryKeys.yearlyReview.availableYears(),
    queryFn: () => api.get<{ years: number[] }>('/wrapped/available-years'),
  })
  const wrappedYearsQuery = useQuery({
    queryKey: queryKeys.yearlyReview.hubAvailableYears(),
    queryFn: () => api.get<{ years: number[] }>('/wrapped-hub/available-years'),
  })

  const playYears = playYearsQuery.data?.years ?? []
  const wrappedYears = wrappedYearsQuery.data?.years ?? []
  const yearsLoading = playYearsQuery.isLoading || wrappedYearsQuery.isLoading
  const yearsError = playYearsQuery.error instanceof Error ? playYearsQuery.error.message : null

  // Per-tab available years
  const displayYears = activeTab === 'custom' ? playYears : wrappedYears
  const yearOptions = isPhone ? [...displayYears].reverse() : displayYears

  // Determine current year: URL param > latest from active tab
  const yearParam = searchParams.get('year')
  const currentYear = yearParam && displayYears.includes(parseInt(yearParam))
    ? parseInt(yearParam)
    : displayYears[displayYears.length - 1] ?? null

  // Keep the URL year valid for the active tab.
  useEffect(() => {
    const parsedYear = yearParam ? parseInt(yearParam) : null
    if (displayYears.length > 0 && (!parsedYear || !displayYears.includes(parsedYear))) {
      setSearchParams({ year: String(displayYears[displayYears.length - 1]) })
    }
  }, [displayYears, setSearchParams, yearParam])

  const { data, loading, error } = useYearlyReview(
    activeTab === 'custom' ? (currentYear ?? 0) : 0,
  )

  return (
    <>
      {!isPhone && <AnalysisPageHeader />}
      {!isPhone && <AnalysisSubNav />}

      {isPhone ? (
        <MobilePageHeader
          eyebrow="Yearly Summary"
          title="年度总结"
          description="沿着章节回看这一年的年度最爱、时间习惯与音乐人格。"
        />
      ) : <section className="mb-8">
        <p className="mb-2 font-sans text-[11px] font-bold uppercase tracking-[1.5px] text-accent-foreground">
          Yearly Summary
        </p>
        <h2 className="font-serif text-[34px] font-bold leading-tight">年度总结</h2>
      </section>}

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
              {y}
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

      {isPhone && activeTab === 'custom' && data && !data.empty && <MobileYearlyChapterNav />}

      {/* 内容区域 */}
      <ErrorBoundary>
        {yearsLoading && <LoadingSkeleton />}
        {yearsError && <ErrorState message={yearsError} />}

        {!yearsLoading && !yearsError && (
          <>
            {loading && <LoadingSkeleton />}
            {error && <ErrorState message={error} />}

            {activeTab === 'custom' && data && !data.empty && (
              <>
                <div className={cn(isPhone && 'mobile-yearly-story')}>
                  <CustomSummary data={data} />
                  <ShareButton />
                </div>
              </>
            )}
            {activeTab === 'official' && (
              <Suspense fallback={<LoadingSkeleton />}>
                <OfficialWrapped />
              </Suspense>
            )}
            {activeTab === 'custom' && data?.empty && <EmptyState year={currentYear ?? 0} />}
          </>
        )}
      </ErrorBoundary>
    </>
  )
}
