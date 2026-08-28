import { useEffect, useMemo, useState } from 'react'
import { AlertCircle } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'

import { getDefaultMergeLevel, normalizeMergeLevel } from '@/lib/merge-level'
import { getBillboardName } from '@/lib/billboard-name'
import { BillboardSubNav } from '@/components/shared/BillboardSubNav'
import { Skeleton } from '@/components/ui/skeleton'
import { AllTimeTable, Pagination } from '@/features/billboard/all-time/AllTimeTable'
import { AllTimeControls } from '@/features/billboard/all-time/AllTimeControls'
import { AllTimeToolbar } from '@/features/billboard/all-time/AllTimeToolbar'
import {
  ALL_TIME_PAGE_SIZE,
  EMPTY_ALL_TIME_ROWS,
  PEAK_FILTER_OPTIONS,
  TABS,
  buildAllTimeRows,
  getMaxBarValue,
  getColumnsForTab,
  getRowsForTab,
  loadVisibleColumnIds,
  recommendedVisibleColumnIds,
  saveVisibleColumnIds,
  selectAllTimeRows,
  visibleColumnsForTab,
  type ColumnDef,
  type AllTimeRow,
  type EntityTab,
  type PeakFilter,
} from '@/features/billboard/all-time/allTimeData'
import { useBillboardAllTime } from '@/hooks/useBillboard'
import { useAnalysisFilters } from '@/hooks/useAnalysis'
import { buildBillboardContextParams } from '@/features/billboard/billboardContext'
import { cn } from '@/lib/utils'
import { useViewportMode } from '@/hooks/useViewportMode'
import { MobileAllTime } from '@/features/mobile/billboard/MobileAllTime'
import { useChineseTextVersion } from '@/lib/chinese'

let cachedEntityTab: EntityTab = 'tracks'
let cachedPeakFilter: PeakFilter = 'all'
let cachedPage = 1
let cachedSortKeyTrack = 'power_score'
let cachedSortDirTrack: 'asc' | 'desc' = 'desc'
let cachedSortKeyAlbum = 'power_score'
let cachedSortDirAlbum: 'asc' | 'desc' = 'desc'
let cachedSortKeyArtist = 'power_score'
let cachedSortDirArtist: 'asc' | 'desc' = 'desc'

function SkeletonBlock() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-9 w-48" />
      <div className="flex gap-4">
        <Skeleton className="h-8 w-16" />
        <Skeleton className="h-8 w-16" />
        <Skeleton className="h-8 w-16" />
      </div>
      <Skeleton className="h-10 w-40" />
      <Skeleton className="h-[400px] w-full rounded-2xl" />
    </div>
  )
}

function ErrorState({ error, refetch }: { error: string; refetch: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-24">
      <AlertCircle className="h-10 w-10 text-muted-foreground" />
      <p className="text-base text-muted-foreground">{error}</p>
      <button
        onClick={refetch}
        className="rounded-lg bg-accent-foreground px-5 py-2 text-sm font-medium text-primary-foreground hover:opacity-80"
      >
        重新加载
      </button>
    </div>
  )
}

export function AllTimeChartsPage() {
  const chineseTextVersion = useChineseTextVersion()
  const isPhone = useViewportMode() === 'phone'
  const [searchParams, setSearchParams] = useSearchParams()
  const mergeLevel = normalizeMergeLevel(searchParams.get('merge_level') ?? getDefaultMergeLevel())
  const searchQuery = searchParams.get('q') ?? ''
  const { filters, loading: filtersLoading } = useAnalysisFilters()
  const billboardParams = buildBillboardContextParams({ ...filters, merge_level: mergeLevel })
  const { data, loading, error, refetch } = useBillboardAllTime(mergeLevel, filters.include_compilations, billboardParams, !filtersLoading)
  const [activeTab, setActiveTab] = useState<EntityTab>(cachedEntityTab)
  const [peakFilter, setPeakFilter] = useState<PeakFilter>(cachedPeakFilter)
  const [page, setPage] = useState(cachedPage)
  const [sortKeyTrack, setSortKeyTrack] = useState(cachedSortKeyTrack)
  const [sortDirTrack, setSortDirTrack] = useState<'asc' | 'desc'>(cachedSortDirTrack)
  const [sortKeyAlbum, setSortKeyAlbum] = useState(cachedSortKeyAlbum)
  const [sortDirAlbum, setSortDirAlbum] = useState<'asc' | 'desc'>(cachedSortDirAlbum)
  const [sortKeyArtist, setSortKeyArtist] = useState(cachedSortKeyArtist)
  const [sortDirArtist, setSortDirArtist] = useState<'asc' | 'desc'>(cachedSortDirArtist)
  const [visibleColumnsByTab, setVisibleColumnsByTab] = useState<Record<EntityTab, string[]>>(() => ({
    tracks: loadVisibleColumnIds('tracks'),
    albums: loadVisibleColumnIds('albums'),
    artists: loadVisibleColumnIds('artists'),
  }))

  const sortKey = activeTab === 'tracks' ? sortKeyTrack : activeTab === 'albums' ? sortKeyAlbum : sortKeyArtist
  const sortDir = activeTab === 'tracks' ? sortDirTrack : activeTab === 'albums' ? sortDirAlbum : sortDirArtist
  const setSortKey = activeTab === 'tracks' ? setSortKeyTrack : activeTab === 'albums' ? setSortKeyAlbum : setSortKeyArtist
  const setSortDir = activeTab === 'tracks' ? setSortDirTrack : activeTab === 'albums' ? setSortDirAlbum : setSortDirArtist

  useEffect(() => { cachedEntityTab = activeTab }, [activeTab])
  useEffect(() => { cachedPeakFilter = peakFilter }, [peakFilter])
  useEffect(() => { cachedPage = page }, [page])
  useEffect(() => { cachedSortKeyTrack = sortKeyTrack }, [sortKeyTrack])
  useEffect(() => { cachedSortDirTrack = sortDirTrack }, [sortDirTrack])
  useEffect(() => { cachedSortKeyAlbum = sortKeyAlbum }, [sortKeyAlbum])
  useEffect(() => { cachedSortDirAlbum = sortDirAlbum }, [sortDirAlbum])
  useEffect(() => { cachedSortKeyArtist = sortKeyArtist }, [sortKeyArtist])
  useEffect(() => { cachedSortDirArtist = sortDirArtist }, [sortDirArtist])

  const allTimeRows = useMemo(() => data ? buildAllTimeRows(data) : EMPTY_ALL_TIME_ROWS, [data])
  const displayRows = useMemo(
    () => selectAllTimeRows(allTimeRows, activeTab, peakFilter, sortKey, sortDir, searchQuery),
    [activeTab, allTimeRows, chineseTextVersion, peakFilter, searchQuery, sortDir, sortKey],
  )
  const visibleColumns = useMemo(
    () => visibleColumnsForTab(activeTab, visibleColumnsByTab[activeTab]),
    [activeTab, visibleColumnsByTab],
  )
  const maxBarValue = useMemo(
    () => getMaxBarValue(getRowsForTab(allTimeRows, activeTab), activeTab),
    [activeTab, allTimeRows],
  )

  function handleColumnClick(column: ColumnDef<AllTimeRow>) {
    if (!column.sortable) return
    setPage(1)
    if (sortKey === column.key) {
      setSortDir(sortDir === 'desc' ? 'asc' : 'desc')
    } else {
      setSortKey(column.key)
      setSortDir('desc')
    }
  }

  function updateSearchQuery(value: string) {
    setPage(1)
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      if (value) next.set('q', value)
      else next.delete('q')
      return next
    }, { replace: true })
  }

  function updateVisibleColumns(ids: string[]) {
    saveVisibleColumnIds(activeTab, ids)
    setVisibleColumnsByTab((current) => ({ ...current, [activeTab]: ids }))
  }

  function restoreRecommendedColumns() {
    updateVisibleColumns(recommendedVisibleColumnIds(activeTab))
  }

  if (loading || filtersLoading) return <SkeletonBlock />
  if (error) return <ErrorState error={error} refetch={refetch} />
  if (!data) return null

  if (isPhone) {
    return (
      <MobileAllTime
        activeTab={activeTab}
        rows={displayRows.rows}
        total={displayRows.total}
        searchQuery={searchQuery}
        peakFilter={peakFilter}
        sortKey={sortKey}
        sortDir={sortDir}
        visibleColumnIds={visibleColumnsByTab[activeTab]}
        page={page}
        pageSize={20}
        onTabChange={(tab) => {
          cachedEntityTab = tab
          setActiveTab(tab)
          setPage(1)
          updateSearchQuery('')
        }}
        onSearchChange={updateSearchQuery}
        onPeakFilterChange={(filter) => { setPeakFilter(filter); setPage(1) }}
        onSortChange={handleColumnClick}
        onVisibleColumnsChange={updateVisibleColumns}
        onPageChange={setPage}
      />
    )
  }

  return (
    <>
      <BillboardSubNav active="all-time" />

      <section className="mt-6 mb-6">
        <p className="mb-4 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
          Chart / All-Time
        </p>
        <h1 className="font-serif text-[44px] font-bold leading-[1.06] tracking-[-1.2px]">
          {getBillboardName()} 总榜
        </h1>
      </section>

      <div className="mb-5 flex gap-7 border-b border-border" role="tablist">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            role="tab"
            aria-selected={activeTab === tab.key}
            onClick={() => {
              cachedEntityTab = tab.key
              setActiveTab(tab.key)
              setPage(1)
              updateSearchQuery('')
            }}
            className={cn(
              '-mb-px border-none bg-transparent px-0 pb-2.5 font-sans text-[13px] font-medium transition-[color,border] duration-200',
              'border-b-2',
              activeTab === tab.key
                ? 'border-accent-foreground font-semibold text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <AllTimeToolbar
        filters={(
          <>
          <span className="font-sans text-[12px] font-medium uppercase tracking-[1px] text-muted-foreground">
            筛选
          </span>
          <div className="flex gap-1.5">
            {PEAK_FILTER_OPTIONS.map((option) => (
              <button
                key={option.value}
                onClick={() => {
                  setPeakFilter(option.value)
                  setPage(1)
                }}
                className={cn(
                  'rounded-full px-3.5 py-1.5 font-sans text-[12px] font-medium transition-colors',
                  peakFilter === option.value
                    ? 'bg-accent-foreground text-primary-foreground'
                    : 'bg-muted/60 text-muted-foreground hover:bg-muted hover:text-foreground',
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
          </>
        )}
        fieldsSearch={(
          <AllTimeControls
            query={searchQuery}
            onQueryChange={updateSearchQuery}
            columns={getColumnsForTab(activeTab)}
            visibleColumnIds={visibleColumnsByTab[activeTab]}
            onVisibleColumnIdsChange={updateVisibleColumns}
            onRestoreRecommended={restoreRecommendedColumns}
          />
        )}
        pagination={(
          <Pagination
            page={Math.min(page, Math.max(1, Math.ceil(displayRows.rows.length / ALL_TIME_PAGE_SIZE)))}
            totalPages={Math.max(1, Math.ceil(displayRows.rows.length / ALL_TIME_PAGE_SIZE))}
            onPageChange={setPage}
          />
        )}
      />

      <AllTimeTable
        activeTab={activeTab}
        rows={displayRows.rows}
        columns={visibleColumns}
        total={displayRows.total}
        sortKey={sortKey}
        sortDir={sortDir}
        page={page}
        pageSize={ALL_TIME_PAGE_SIZE}
        maxBarValue={maxBarValue}
        onColumnClick={handleColumnClick}
        onPageChange={setPage}
        emptyMessage={searchQuery ? '没有匹配当前搜索的结果' : '暂无数据'}
      />
    </>
  )
}
