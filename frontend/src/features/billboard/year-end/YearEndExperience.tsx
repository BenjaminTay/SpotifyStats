import { useEffect, useMemo, useState } from 'react'
import { AlertCircle } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'

import { BillboardSubNav } from '@/components/shared/BillboardSubNav'
import { Skeleton } from '@/components/ui/skeleton'
import { useBillboardYearEnd } from '@/hooks/useBillboard'
import { useSettings } from '@/hooks/useSettings'
import { getBillboardName } from '@/lib/billboard-name'
import { getDefaultMergeLevel } from '@/lib/merge-level'
import { cn } from '@/lib/utils'
import type { BillboardYearEndMeta } from '@/types/billboard'
import { YearEndHonors } from './YearEndHonors'
import { YearEndTable } from './YearEndTable'
import {
  YEAR_END_PAGE_SIZE,
  YEAR_END_TABS,
  defaultSortForTab,
  nextSortDir,
  rowsForTab,
  sortYearEndRows,
  type YearEndSortDir,
  type YearEndSortKey,
  type YearEndTab,
} from './yearEndData'
import { useViewportMode } from '@/hooks/useViewportMode'
import { MobileYearEnd } from '@/features/mobile/billboard/MobileYearEnd'

let cachedTab: YearEndTab = 'tracks'
let cachedPage = 1
let cachedSortKey: YearEndSortKey = 'year_end_score'
let cachedSortDir: YearEndSortDir = 'desc'

function parseYear(value: string | null): number | null {
  if (!value) return null
  const year = Number(value)
  return Number.isInteger(year) ? year : null
}

function parseMergeLevel(value: string | null): number {
  const level = Number(value ?? getDefaultMergeLevel())
  return level === 1 || level === 2 || level === 3 ? level : 2
}

function parseTab(value: string | null): YearEndTab | null {
  return YEAR_END_TABS.some((tab) => tab.key === value) ? value as YearEndTab : null
}

function SkeletonBlock() {
  return (
    <div className="space-y-5 py-6">
      <Skeleton className="h-14 w-full rounded-[16px]" />
      <Skeleton className="h-[560px] w-full rounded-[16px]" />
    </div>
  )
}

function ErrorState({ error, refetch }: { error: string; refetch: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-20">
      <AlertCircle className="h-10 w-10 text-muted-foreground" />
      <p className="max-w-xl text-center text-sm text-muted-foreground">{error}</p>
      <button
        type="button"
        onClick={refetch}
        className="rounded-lg bg-accent-foreground px-5 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-80"
      >
        重新加载
      </button>
    </div>
  )
}

function formatCoverageDate(value: string | null): string {
  if (!value) return '未知日期'
  const [year, month, day] = value.slice(0, 10).split('-')
  return `${year}年${Number(month)}月${Number(day)}日`
}

function coverageMessage(meta: BillboardYearEndMeta): string | null {
  if (meta.is_complete_year) return null
  const period = `${formatCoverageDate(meta.period_start)}至${formatCoverageDate(meta.period_end)}`
  if (meta.coverage_status === 'year_to_date') {
    return `本页是截至 ${formatCoverageDate(meta.period_end)} 的阶段年榜，后续榜单周会继续改变排名与荣誉。`
  }
  if (meta.coverage_status === 'partial_start') {
    return `该年份的本地数据从 ${formatCoverageDate(meta.period_start)} 开始，仅覆盖 ${period}，不能视为完整年度结论。`
  }
  if (meta.coverage_status === 'incomplete' || meta.has_internal_gaps) {
    return `该年份覆盖 ${period}，但榜单周存在缺口，排名与荣誉仅供阶段性参考。`
  }
  if (meta.coverage_status === 'empty') return '该年份没有可计算的个人榜单数据。'
  return `该年份仅覆盖 ${period}，排名与荣誉是阶段结果。`
}

export function YearEndExperience() {
  const isPhone = useViewportMode() === 'phone'
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedYear = parseYear(searchParams.get('year'))
  const requestedTab = parseTab(searchParams.get('tab'))
  const mergeLevel = parseMergeLevel(searchParams.get('merge_level'))
  const { settings, loading: settingsLoading } = useSettings()
  const includeCompilationsParam = searchParams.get('include_compilations')
  const includeCompilations = includeCompilationsParam === null
    ? settings?.include_compilations ?? false
    : includeCompilationsParam === 'true'
  const { data, loading, fetching, placeholder, error, refetch } = useBillboardYearEnd(
    requestedYear,
    mergeLevel,
    includeCompilations,
    !settingsLoading,
  )
  const [activeTab, setActiveTab] = useState<YearEndTab>(requestedTab ?? cachedTab)
  const [page, setPage] = useState(cachedPage)
  const [sortKey, setSortKey] = useState<YearEndSortKey>(cachedSortKey)
  const [sortDir, setSortDir] = useState<YearEndSortDir>(cachedSortDir)

  const visibleData = data &&
    !settingsLoading &&
    !placeholder &&
    (requestedYear === null || data.meta.year === requestedYear)
    ? data
    : null
  const selectedYear = requestedYear ?? data?.meta.year
  const availableYears = data?.meta.available_years ?? []
  const isTransitioning = !visibleData && (settingsLoading || loading || fetching || placeholder)
  const areYearOptionsLoading =
    availableYears.length === 0 && (settingsLoading || loading || fetching || placeholder)

  useEffect(() => { cachedTab = activeTab }, [activeTab])
  useEffect(() => { cachedPage = page }, [page])
  useEffect(() => { cachedSortKey = sortKey }, [sortKey])
  useEffect(() => { cachedSortDir = sortDir }, [sortDir])
  useEffect(() => {
    if (requestedTab === null || requestedTab === activeTab) return
    const nextSort = defaultSortForTab(requestedTab)
    setActiveTab(requestedTab)
    setPage(1)
    setSortKey(nextSort.key)
    setSortDir(nextSort.dir)
  }, [activeTab, requestedTab])

  const rows = useMemo(() => rowsForTab(visibleData, activeTab), [activeTab, visibleData])
  const sortedRows = useMemo(
    () => sortYearEndRows(rows, sortKey, sortDir),
    [rows, sortDir, sortKey],
  )

  function handleYearChange(year: number) {
    setPage(1)
    const next = new URLSearchParams(searchParams)
    next.set('year', String(year))
    setSearchParams(next)
  }

  function handleTabChange(tab: YearEndTab) {
    const nextSort = defaultSortForTab(tab)
    setActiveTab(tab)
    setPage(1)
    setSortKey(nextSort.key)
    setSortDir(nextSort.dir)
    const next = new URLSearchParams(searchParams)
    next.set('tab', tab)
    setSearchParams(next)
  }

  function handleSortChange(key: YearEndSortKey) {
    const nextDir = nextSortDir(sortKey, sortDir, key)
    setSortKey(key)
    setSortDir(nextDir)
    setPage(1)
  }

  if (isPhone && visibleData) {
    return (
      <MobileYearEnd
        data={visibleData}
        selectedYear={selectedYear}
        availableYears={availableYears}
        coverageMessage={coverageMessage(visibleData.meta)}
        activeTab={activeTab}
        rows={sortedRows}
        sortKey={sortKey}
        sortDir={sortDir}
        page={page}
        pageSize={20}
        onYearChange={handleYearChange}
        onTabChange={handleTabChange}
        onSortChange={handleSortChange}
        onPageChange={setPage}
      />
    )
  }

  return (
    <>
      <BillboardSubNav active="year-end" />

      <section className="mt-6 mb-6">
        <p className="mb-4 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
          Chart / Year-End
        </p>
        <h1 className="font-serif text-[44px] font-bold leading-[1.06] tracking-[-1.2px]">
          {getBillboardName()} 年榜
        </h1>
        <div
          className="mt-5 flex max-w-full gap-2 overflow-x-auto pb-0.5"
          aria-label="切换年榜年份"
        >
          {areYearOptionsLoading ? (
            <Skeleton
              className="h-8 w-[76px] shrink-0 rounded-full"
              aria-label="正在加载可用年份"
            />
          ) : availableYears.length === 0 && !error ? (
            <span className="rounded-full bg-muted px-4 py-1.5 font-sans text-[13px] font-medium text-muted-foreground">
              无数据
            </span>
          ) : (
            availableYears.map((year) => (
              <button
                key={year}
                type="button"
                onClick={() => handleYearChange(year)}
                aria-pressed={year === selectedYear}
                className={cn(
                  'shrink-0 rounded-full px-4 py-1.5 font-sans text-[13px] font-medium transition-colors',
                  year === selectedYear
                    ? 'bg-accent-foreground text-card'
                    : 'bg-muted text-muted-foreground hover:text-foreground',
                )}
              >
                {year}
              </button>
            ))
          )}
        </div>
      </section>

      {isTransitioning && <SkeletonBlock />}
      {error && !visibleData && !isTransitioning && <ErrorState error={error} refetch={refetch} />}

      {visibleData && (
        <>
          {coverageMessage(visibleData.meta) && (
            <div
              className="mb-5 flex gap-3 rounded-[12px] border border-amber-500/30 bg-amber-500/[0.08] px-4 py-3 text-sm text-muted-foreground"
              role="status"
            >
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
              <p>{coverageMessage(visibleData.meta)}</p>
            </div>
          )}
          <p className="mb-4 font-sans text-[12px] text-muted-foreground">
            已统计 {visibleData.meta.observed_weeks}/{visibleData.meta.expected_weeks} 个榜单周
            {' · '}周榜入榜线：单曲 Top {visibleData.meta.weekly_top_n}、专辑 Top {visibleData.meta.weekly_album_top_n}、艺人 Top {visibleData.meta.weekly_artist_top_n}
          </p>

          <YearEndHonors
            honors={visibleData.honors}
            isCompleteYear={visibleData.meta.is_complete_year}
          />

          <div className="mb-6 border-b border-border">
            <div className="flex gap-7 overflow-x-auto" role="tablist">
              {YEAR_END_TABS.map((tab) => (
                <button
                  key={tab.key}
                  type="button"
                  role="tab"
                  aria-selected={activeTab === tab.key}
                  onClick={() => handleTabChange(tab.key)}
                  className={cn(
                    '-mb-px shrink-0 border-b-2 bg-transparent px-0 pb-2.5 font-sans text-[13px] font-medium transition-colors',
                    activeTab === tab.key
                      ? 'border-accent-foreground font-semibold text-foreground'
                      : 'border-transparent text-muted-foreground hover:text-foreground',
                  )}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          <YearEndTable
            tab={activeTab}
            rows={sortedRows}
            page={page}
            pageSize={YEAR_END_PAGE_SIZE}
            sortKey={sortKey}
            sortDir={sortDir}
            onSortChange={handleSortChange}
            onPageChange={setPage}
          />
        </>
      )}
    </>
  )
}
