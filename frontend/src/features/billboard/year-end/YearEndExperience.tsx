import { useEffect, useMemo, useState } from 'react'
import { AlertCircle } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'

import { BillboardSubNav } from '@/components/shared/BillboardSubNav'
import { Skeleton } from '@/components/ui/skeleton'
import { useBillboardYearEnd } from '@/hooks/useBillboard'
import { getBillboardName } from '@/lib/billboard-name'
import { getDefaultMergeLevel } from '@/lib/merge-level'
import { cn } from '@/lib/utils'
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

export function YearEndExperience() {
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedYear = parseYear(searchParams.get('year'))
  const mergeLevel = parseMergeLevel(searchParams.get('merge_level'))
  const includeCompilations = searchParams.get('include_compilations') === 'true'
  const { data, loading, error, refetch } = useBillboardYearEnd(requestedYear, mergeLevel, includeCompilations)
  const [activeTab, setActiveTab] = useState<YearEndTab>(cachedTab)
  const [page, setPage] = useState(cachedPage)
  const [sortKey, setSortKey] = useState<YearEndSortKey>(cachedSortKey)
  const [sortDir, setSortDir] = useState<YearEndSortDir>(cachedSortDir)

  const selectedYear = data?.meta.year ?? requestedYear
  const availableYears = data?.meta.available_years ?? []

  useEffect(() => { cachedTab = activeTab }, [activeTab])
  useEffect(() => { cachedPage = page }, [page])
  useEffect(() => { cachedSortKey = sortKey }, [sortKey])
  useEffect(() => { cachedSortDir = sortDir }, [sortDir])
  useEffect(() => { setPage(1) }, [activeTab, requestedYear, sortKey, sortDir])

  const rows = useMemo(() => rowsForTab(data, activeTab), [activeTab, data])
  const sortedRows = useMemo(
    () => sortYearEndRows(rows, sortKey, sortDir),
    [rows, sortDir, sortKey],
  )

  function handleYearChange(year: number) {
    const next = new URLSearchParams(searchParams)
    next.set('year', String(year))
    setSearchParams(next)
  }

  function handleTabChange(tab: YearEndTab) {
    const nextSort = defaultSortForTab(tab)
    setActiveTab(tab)
    setSortKey(nextSort.key)
    setSortDir(nextSort.dir)
  }

  function handleSortChange(key: YearEndSortKey) {
    const nextDir = nextSortDir(sortKey, sortDir, key)
    setSortKey(key)
    setSortDir(nextDir)
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
          {availableYears.length === 0 ? (
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

      {loading && !data && <SkeletonBlock />}
      {error && !data && <ErrorState error={error} refetch={refetch} />}

      {data && (
        <>
          <YearEndHonors honors={data.honors} />

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
