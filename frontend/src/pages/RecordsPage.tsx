import { lazy, Suspense, useEffect, useMemo, useRef } from 'react'
import { AlertCircle } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'

import { getDefaultMergeLevel, normalizeMergeLevel } from '@/lib/merge-level'
import { BillboardSubNav } from '@/components/shared/BillboardSubNav'
import { Skeleton } from '@/components/ui/skeleton'
import { useBillboard } from '@/hooks/useBillboard'
import { useAnalysisFilters } from '@/hooks/useAnalysis'
import { cn } from '@/lib/utils'
import type { BillboardRecords } from '@/types/billboard'
import { buildBillboardContextParams } from '@/features/billboard/billboardContext'
import { buildCoverMaps } from '@/features/billboard/records/recordsData'
import { ChampionshipSection } from '@/features/billboard/records/ChampionshipSection'
import { useViewportMode } from '@/hooks/useViewportMode'

const LongevitySection = lazy(() =>
  import('@/features/billboard/records/LongevitySection').then((m) => ({
    default: m.LongevitySection,
  })),
)
const BreakthroughSection = lazy(() =>
  import('@/features/billboard/records/BreakthroughSection').then((m) => ({
    default: m.BreakthroughSection,
  })),
)
const HallOfFameSection = lazy(() =>
  import('@/features/billboard/records/HallOfFameSection').then((m) => ({
    default: m.HallOfFameSection,
  })),
)
const CuriositiesSection = lazy(() =>
  import('@/features/billboard/records/CuriositiesSection').then((m) => ({
    default: m.CuriositiesSection,
  })),
)
const MarketSection = lazy(() =>
  import('@/features/billboard/records/MarketSection').then((m) => ({
    default: m.MarketSection,
  })),
)

const RECORD_TABS = [
  { key: 'championship', label: '冠军圣殿' },
  { key: 'longevity', label: '持久传奇' },
  { key: 'breakthrough', label: '爆发时刻' },
  { key: 'halloffame', label: '名人堂' },
  { key: 'curiosities', label: '奇趣纪录' },
  { key: 'market', label: '每周大盘' },
] as const

type TabKey = typeof RECORD_TABS[number]['key']

function MobileRecordFamilyTabs({ value, onChange }: {
  value: TabKey
  onChange: (value: TabKey) => void
}) {
  const tabRefs = useRef(new Map<TabKey, HTMLButtonElement>())

  useEffect(() => {
    tabRefs.current.get(value)?.scrollIntoView({ block: 'nearest', inline: 'center' })
  }, [value])

  return (
    <nav className="mobile-record-family-tabs" role="tablist" aria-label="榜单记录分类">
      {RECORD_TABS.map((tab) => (
        <button
          key={tab.key}
          ref={(node) => {
            if (node) tabRefs.current.set(tab.key, node)
            else tabRefs.current.delete(tab.key)
          }}
          type="button"
          role="tab"
          aria-selected={value === tab.key}
          className={cn(value === tab.key && 'active')}
          onClick={() => onChange(tab.key)}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  )
}

function LoadingSkeleton() {
  return (
    <div className="mx-auto max-w-[1200px]">
      <Skeleton className="mb-4 h-3 w-32" />
      <Skeleton className="mb-8 h-[44px] w-48" />
      <Skeleton className="mb-6 h-[40px] w-full rounded-[12px]" />
      {[1, 2, 3].map((i) => <Skeleton key={i} className="mb-5 h-[200px] w-full rounded-[16px]" />)}
    </div>
  )
}

function SectionFallback() {
  return (
    <div className="space-y-4">
      {[1, 2, 3].map((i) => (
        <Skeleton key={i} className="h-[200px] w-full rounded-[16px]" />
      ))}
    </div>
  )
}

export function RecordsPage() {
  const isPhone = useViewportMode() === 'phone'
  const [searchParams, setSearchParams] = useSearchParams()
  const mergeLevel = normalizeMergeLevel(searchParams.get('merge_level') ?? getDefaultMergeLevel())
  const { filters, loading: filtersLoading } = useAnalysisFilters()
  const billboardParams = useMemo(
    () => buildBillboardContextParams({ ...filters, merge_level: mergeLevel }),
    [filters, mergeLevel],
  )
  const { data, loading, error } = useBillboard(
    billboardParams,
    undefined,
    !filtersLoading,
  )
  const requestedFamily = searchParams.get('family')
  const activeTab: TabKey = RECORD_TABS.some((tab) => tab.key === requestedFamily)
    ? requestedFamily as TabKey
    : 'championship'
  const handleFamilyChange = (family: TabKey) => {
    const next = new URLSearchParams(searchParams)
    next.set('family', family)
    next.delete('record')
    setSearchParams(next)
    window.requestAnimationFrame(() => {
      window.scrollTo({ top: 0, behavior: 'smooth' })
    })
  }

  const covers = useMemo(() => {
    if (!data) return { track: new Map(), artist: new Map(), album: new Map() }
    return buildCoverMaps(data)
  }, [data])

  if (filtersLoading || loading) return <LoadingSkeleton />

  if (error) {
    return (
      <div className="flex flex-col items-center gap-4 py-20 text-center">
        <AlertCircle className="h-8 w-8 text-accent-foreground" />
        <p className="font-sans text-[13px] text-muted-foreground">{error}</p>
      </div>
    )
  }

  if (!data) return null

  const rec: BillboardRecords = data.records

  return (
    <div className={isPhone ? 'mobile-m4-page' : 'mx-auto max-w-[1200px]'} data-mobile-page={isPhone ? 'billboard-records' : undefined}>
      {!isPhone && <BillboardSubNav active="records" />}

      {!isPhone && <section className="mt-6 mb-6">
        <p className="mb-4 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">Chart / Hall of Fame</p>
        <h1 className="font-serif text-[44px] font-bold leading-[1.06] tracking-[-1.2px]">榜单记录</h1>
      </section>}

      {isPhone ? (
        <MobileRecordFamilyTabs value={activeTab} onChange={handleFamilyChange} />
      ) : <nav className="mb-8 flex gap-7 border-b border-border" role="tablist">
        {RECORD_TABS.map((tab) => (
          <button
            key={tab.key}
            role="tab"
            aria-selected={activeTab === tab.key}
            onClick={() => handleFamilyChange(tab.key)}
            className={cn(
              '-mb-px border-none bg-transparent px-0 pb-2.5 font-sans text-[13px] font-medium transition-[color,border] duration-200 border-b-2',
              activeTab === tab.key
                ? 'border-accent-foreground font-semibold text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            {tab.label}
          </button>
        ))}
      </nav>}

      <div className={cn(isPhone && 'mobile-records-stack')}>
      <Suspense fallback={<SectionFallback />}>
        {activeTab === 'championship' && <ChampionshipSection rec={rec} covers={covers} />}
        {activeTab === 'longevity' && <LongevitySection rec={rec} covers={covers} />}
        {activeTab === 'breakthrough' && <BreakthroughSection rec={rec} covers={covers} />}
        {activeTab === 'halloffame' && <HallOfFameSection rec={rec} covers={covers} />}
        {activeTab === 'curiosities' && (
          <CuriositiesSection
            rec={rec}
            covers={covers}
            trackSummary={data.track_summary}
            artistTrackCounts={data.artist_track_counts}
          />
        )}
        {activeTab === 'market' && <MarketSection rec={rec} covers={covers} />}
      </Suspense>
      </div>
    </div>
  )
}
