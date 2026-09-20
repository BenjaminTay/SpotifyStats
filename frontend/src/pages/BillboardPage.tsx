import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AlertCircle } from 'lucide-react'

import { Skeleton } from '@/components/ui/skeleton'
import { SnapshotStatusNotice } from '@/components/shared/SnapshotStatusNotice'
import { MobileStatePanel } from '@/components/mobile'
import { DesktopBillboardWeekly } from '@/features/billboard/weekly/DesktopBillboardWeekly'
import {
  buildWeeklySummary,
  isBillboardWeeklyTab,
  type BillboardWeeklyEntry,
  type BillboardWeeklyTab,
} from '@/features/billboard/weekly/weeklyPresentation'
import { MobileBillboardWeekly } from '@/features/mobile/billboard/MobileBillboardWeekly'
import { useWeeklyProjection } from '@/hooks/useBillboard'
import { useAnalysisFilters } from '@/hooks/useAnalysis'
import { buildBillboardContextParams } from '@/features/billboard/billboardContext'
import { useViewportMode } from '@/hooks/useViewportMode'
import { getDefaultMergeLevel, normalizeMergeLevel } from '@/lib/merge-level'
import type { BillboardWeeklyResponse } from '@/types/billboard'

const PAGE_SIZE = 50
const EMPTY_WEEKLY_ENTRIES: BillboardWeeklyEntry[] = []

function BillboardSkeleton() {
  return (
    <>
      <div className="mb-6">
        <Skeleton className="mb-3 h-3 w-24" />
        <Skeleton className="h-[44px] w-64" />
      </div>
      <div className="mb-5 flex gap-7">
        {Array.from({ length: 3 }).map((_, index) => <Skeleton key={index} className="h-6 w-16" />)}
      </div>
      <div className="mb-6 flex gap-3.5">
        <Skeleton className="h-[34px] w-[34px] rounded-full" />
        <Skeleton className="h-[50px] w-48" />
        <Skeleton className="h-[34px] w-[34px] rounded-full" />
      </div>
      <Skeleton className="mb-6 h-12 w-full rounded-[16px]" />
      <Skeleton className="h-[600px] w-full rounded-[16px]" />
    </>
  )
}

export function BillboardPage() {
  const viewportMode = useViewportMode()
  const [searchParams, setSearchParams] = useSearchParams()
  const initialWeek = searchParams.get('week')
  const tabParam = searchParams.get('tab')
  const activeTab: BillboardWeeklyTab = isBillboardWeeklyTab(tabParam) ? tabParam : 'tracks'
  const mergeLevel = normalizeMergeLevel(searchParams.get('merge_level') ?? getDefaultMergeLevel())
  const { filters, loading: settingsLoading } = useAnalysisFilters()
  const params = buildBillboardContextParams({ ...filters, merge_level: mergeLevel })
  const { data: projection, loading, switching, error, refetch } = useWeeklyProjection(params, initialWeek, activeTab, !settingsLoading)
  const data = useMemo(() => projection ? { ...projection, weekly: [], weekly_album: [], weekly_artist: [] } as BillboardWeeklyResponse : null, [projection])
  const displayTab: BillboardWeeklyTab = projection?.entity && isBillboardWeeklyTab(projection.entity)
    ? projection.entity
    : activeTab
  const selectedWeek = projection?.selected_week ?? ''
  const currentIndex = data?.meta.all_weeks_desc.indexOf(selectedWeek) ?? 0
  const totalWeeks = data?.meta.all_weeks_desc.length ?? 0
  const entries = (projection?.current as BillboardWeeklyEntry[] | undefined) ?? EMPTY_WEEKLY_ENTRIES
  const previousEntries = (projection?.previous as BillboardWeeklyEntry[] | undefined) ?? EMPTY_WEEKLY_ENTRIES
  const historicalEntries = (projection?.historical as BillboardWeeklyEntry[] | undefined) ?? EMPTY_WEEKLY_ENTRIES
  const summary = useMemo(
    () => buildWeeklySummary(entries, previousEntries, historicalEntries, displayTab),
    [displayTab, entries, historicalEntries, previousEntries],
  )

  const paginationKey = `${displayTab}:${selectedWeek}`
  const [pagination, setPagination] = useState({ key: paginationKey, page: 1 })
  const requestedPage = pagination.key === paginationKey ? pagination.page : 1
  const totalPages = Math.max(1, Math.ceil(entries.length / PAGE_SIZE))
  const page = Math.min(requestedPage, totalPages)

  const updateQuery = (key: 'tab' | 'week', value: string) => {
    const next = new URLSearchParams(searchParams)
    next.set(key, value)
    setSearchParams(next, { replace: false })
  }
  const selectTab = (tab: BillboardWeeklyTab) => updateQuery('tab', tab)
  const selectWeek = (week: string | undefined) => {
    if (!week) return
    updateQuery('week', week)
  }
  const selectPage = (nextPage: number) => setPagination({ key: paginationKey, page: nextPage })

  if (loading || settingsLoading) {
    return viewportMode === 'phone'
      ? <div className="mobile-m3-page"><MobileStatePanel variant="loading" /></div>
      : <BillboardSkeleton />
  }

  if (error && !projection) {
    return viewportMode === 'phone' ? (
      <div className="mobile-m3-page">
        <MobileStatePanel variant="error" description={`榜单加载失败：${error}`} actionLabel="重新加载" onAction={refetch} />
      </div>
    ) : (
      <div className="flex flex-col items-center gap-4 py-20 text-center">
        <AlertCircle className="h-8 w-8 text-accent-foreground" />
        <p className="text-muted-foreground">加载失败：{error}</p>
        <button
          type="button"
          onClick={refetch}
          className="rounded-full bg-accent-foreground px-6 py-2 text-[13px] font-semibold text-primary-foreground transition-opacity hover:opacity-85"
        >
          重新加载
        </button>
      </div>
    )
  }

  if (!data) return null

  const presentationProps = {
    data,
    activeTab: displayTab,
    onTabChange: selectTab,
    selectedWeek,
    currentIndex,
    totalWeeks,
    onPreviousWeek: () => selectWeek(data.meta.all_weeks_desc[currentIndex + 1]),
    onNextWeek: () => selectWeek(data.meta.all_weeks_desc[currentIndex - 1]),
    onGoToWeek: selectWeek,
    entries,
    previousEntries,
    historicalEntries,
    summary,
    page,
    totalPages,
    pageSize: PAGE_SIZE,
    onPageChange: selectPage,
  }

  return (
    <div className="relative" aria-busy={switching}>
      <SnapshotStatusNotice snapshot={projection?.snapshot} />
      {switching && (
        <p
          role="status"
          className="sticky top-3 z-20 ml-auto mb-3 w-fit rounded-full border border-border bg-background/90 px-3 py-1.5 text-xs text-muted-foreground shadow-sm backdrop-blur"
        >
          正在切换榜单，当前内容会在新数据就绪后更新…
        </p>
      )}
      {viewportMode === 'phone'
        ? <MobileBillboardWeekly {...presentationProps} />
        : <DesktopBillboardWeekly {...presentationProps} />}
    </div>
  )
}
