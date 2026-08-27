import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AlertCircle } from 'lucide-react'

import { Skeleton } from '@/components/ui/skeleton'
import { MobileStatePanel } from '@/components/mobile'
import { DesktopBillboardWeekly } from '@/features/billboard/weekly/DesktopBillboardWeekly'
import {
  buildWeeklySummary,
  isBillboardWeeklyTab,
  type BillboardWeeklyEntry,
  type BillboardWeeklyTab,
} from '@/features/billboard/weekly/weeklyPresentation'
import { MobileBillboardWeekly } from '@/features/mobile/billboard/MobileBillboardWeekly'
import { useBillboardWeekly } from '@/hooks/useBillboard'
import { useSettings } from '@/hooks/useSettings'
import { useViewportMode } from '@/hooks/useViewportMode'
import { getDefaultMergeLevel, normalizeMergeLevel } from '@/lib/merge-level'
import type { BillboardWeeklyResponse } from '@/types/billboard'

const PAGE_SIZE = 50

function entriesForTab(data: BillboardWeeklyResponse, tab: BillboardWeeklyTab): BillboardWeeklyEntry[] {
  if (tab === 'tracks') return data.weekly
  if (tab === 'albums') return data.weekly_album
  return data.weekly_artist
}

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
  const { settings, loading: settingsLoading } = useSettings()
  const includeCompilations = settings?.include_compilations ?? false

  const {
    data,
    loading,
    error,
    refetch,
    selectedWeek,
    currentWeekData,
    currentIndex,
    totalWeeks,
    goToWeek,
  } = useBillboardWeekly(initialWeek, mergeLevel, includeCompilations, !settingsLoading)

  const entries = currentWeekData[activeTab] as BillboardWeeklyEntry[]
  const previousWeek = data?.meta.all_weeks_desc[currentIndex + 1]
  const previousEntries = useMemo(() => {
    if (!data || !previousWeek) return []
    return entriesForTab(data, activeTab).filter((entry) => entry.billboard_week === previousWeek)
  }, [activeTab, data, previousWeek])
  const historicalEntries = useMemo(() => {
    if (!data) return []
    const historicalWeeks = new Set(data.meta.all_weeks_desc.slice(currentIndex + 1))
    return entriesForTab(data, activeTab).filter((entry) => historicalWeeks.has(entry.billboard_week))
  }, [activeTab, currentIndex, data])
  const summary = useMemo(
    () => buildWeeklySummary(entries, previousEntries, historicalEntries, activeTab),
    [activeTab, entries, historicalEntries, previousEntries],
  )

  const paginationKey = `${activeTab}:${selectedWeek}`
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
    goToWeek(week)
    updateQuery('week', week)
  }
  const selectPage = (nextPage: number) => setPagination({ key: paginationKey, page: nextPage })

  if (loading || settingsLoading) {
    return viewportMode === 'phone'
      ? <div className="mobile-m3-page"><MobileStatePanel variant="loading" /></div>
      : <BillboardSkeleton />
  }

  if (error) {
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
    activeTab,
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

  return viewportMode === 'phone'
    ? <MobileBillboardWeekly {...presentationProps} />
    : <DesktopBillboardWeekly {...presentationProps} />
}
