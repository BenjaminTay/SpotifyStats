import { useEffect, useMemo, useState } from 'react'

import { BillboardSubNav } from '@/components/shared/BillboardSubNav'
import { useBillboardAllTime } from '@/hooks/useBillboard'
import { cn } from '@/lib/utils'
import { AlbumsNumberOnesSection } from './AlbumsNumberOnesSection'
import { ArtistsNumberOnesSection } from './ArtistsNumberOnesSection'
import { ErrorState, SkeletonBlock } from './NumberOnesPrimitives'
import { TracksNumberOnesSection } from './TracksNumberOnesSection'
import {
  SUB_TABS,
  availableYearsForTab,
  buildNumberOnes,
  filterNumberOnesByYear,
  type SubTabKey,
} from './numberOnesData'

let cachedSubTab: SubTabKey = 'tracks'
let cachedYear = 0

export function NumberOnesExperience({ mergeLevel = 2 }: { mergeLevel?: number }) {
  const { data, loading, error } = useBillboardAllTime(mergeLevel)
  const [activeTab, setActiveTab] = useState<SubTabKey>(cachedSubTab)
  const [selectedYear, setSelectedYear] = useState(cachedYear)

  const computed = useMemo(() => buildNumberOnes(data), [data])
  const availableYears = useMemo(
    () => availableYearsForTab(computed, activeTab),
    [activeTab, computed],
  )

  useEffect(() => {
    if (availableYears.length === 0) return
    if (!availableYears.includes(selectedYear)) {
      cachedYear = availableYears[0]
      setSelectedYear(availableYears[0])
    }
  }, [availableYears, selectedYear])

  const yearFiltered = useMemo(
    () => filterNumberOnesByYear(computed, selectedYear),
    [computed, selectedYear],
  )

  function handleTabChange(tab: SubTabKey) {
    cachedSubTab = tab
    setActiveTab(tab)
  }

  function handleYearChange(year: number) {
    cachedYear = year
    setSelectedYear(year)
  }

  if (loading) return <SkeletonBlock />
  if (error) return <ErrorState error={error} />
  if (!data) return null

  return (
    <>
      <BillboardSubNav active="number-ones" />

      <section className="mt-6 mb-6">
        <p className="mb-4 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
          Chart / Number Ones
        </p>
        <h1 className="font-serif text-[44px] font-bold leading-[1.06] tracking-[-1.2px]">
          每周榜首
        </h1>
      </section>

      <div className="mb-8 flex gap-7 border-b border-border">
        {SUB_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => handleTabChange(tab.key)}
            className={cn(
              '-mb-px cursor-pointer border-none bg-transparent px-0 pb-2.5 font-sans text-[13px] font-medium transition-[color,border] duration-200',
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

      {activeTab === 'tracks' && (
        <TracksNumberOnesSection
          computed={computed}
          yearFiltered={yearFiltered}
          availableYears={availableYears}
          selectedYear={selectedYear}
          onYearChange={handleYearChange}
        />
      )}

      {activeTab === 'albums' && (
        <AlbumsNumberOnesSection
          computed={computed}
          yearFiltered={yearFiltered}
          availableYears={availableYears}
          selectedYear={selectedYear}
          onYearChange={handleYearChange}
        />
      )}

      {activeTab === 'artists' && (
        <ArtistsNumberOnesSection
          computed={computed}
          yearFiltered={yearFiltered}
          availableYears={availableYears}
          selectedYear={selectedYear}
          onYearChange={handleYearChange}
        />
      )}
    </>
  )
}
