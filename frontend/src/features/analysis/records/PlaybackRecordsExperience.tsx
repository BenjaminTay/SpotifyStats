/** Playback Records Experience — section tab management + lazy loading, aligned with Billboard RecordsPage. */

import { Suspense, lazy, useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { useViewportMode } from '@/hooks/useViewportMode'
import type { PlaybackRecordsData } from '@/types/analysis'
import { SectionFallback } from './PlaybackRecordsPrimitives'
import { PLAYBACK_RECORD_SECTIONS, type PlaybackRecordSectionKey } from './recordsArchitecture'

const ObsessionSection = lazy(() => import('./ObsessionSection').then((m) => ({ default: m.ObsessionSection })))
const LongevitySection = lazy(() => import('./LongevitySection').then((m) => ({ default: m.LongevitySection })))
const ReignsSection = lazy(() => import('./ReignsSection').then((m) => ({ default: m.ReignsSection })))
const TimePatternsSection = lazy(() => import('./TimePatternsSection').then((m) => ({ default: m.TimePatternsSection })))
const DiscoverySection = lazy(() => import('./DiscoverySection').then((m) => ({ default: m.DiscoverySection })))

interface Props {
  data: PlaybackRecordsData
}

export function PlaybackRecordsExperience({ data }: Props) {
  const isPhone = useViewportMode() === 'phone'
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedFamily = searchParams.get('family')
  const activeSection: PlaybackRecordSectionKey = PLAYBACK_RECORD_SECTIONS.some(
    (section) => section.key === requestedFamily,
  ) ? requestedFamily as PlaybackRecordSectionKey : 'highlights'
  const tabRefs = useRef(new Map<PlaybackRecordSectionKey, HTMLButtonElement>())

  const handleSectionChange = (section: PlaybackRecordSectionKey) => {
    const next = new URLSearchParams(searchParams)
    next.set('family', section)
    next.delete('record')
    setSearchParams(next, { replace: true })
  }

  useEffect(() => {
    tabRefs.current.get(activeSection)?.scrollIntoView?.({ block: 'nearest', inline: 'center' })
  }, [activeSection])

  return (
    <div className={cn(isPhone && 'mobile-playback-records-experience')}>
      {isPhone ? (
        <nav className="mobile-record-family-tabs" role="tablist" aria-label="播放记录分类">
          {PLAYBACK_RECORD_SECTIONS.map((section) => (
            <button
              key={section.key}
              ref={(node) => {
                if (node) tabRefs.current.set(section.key, node)
                else tabRefs.current.delete(section.key)
              }}
              type="button"
              role="tab"
              aria-selected={activeSection === section.key}
              className={cn(activeSection === section.key && 'active')}
              onClick={() => handleSectionChange(section.key)}
            >
              {section.label}
            </button>
          ))}
        </nav>
      ) : <nav className="mb-8 flex gap-7 border-b border-border" role="tablist" aria-label="播放记录分类">
        {PLAYBACK_RECORD_SECTIONS.map((s) => (
          <button
            key={s.key}
            type="button"
            role="tab"
            aria-selected={activeSection === s.key}
            onClick={() => handleSectionChange(s.key)}
            className={cn(
              '-mb-px border-none bg-transparent px-0 pb-2.5 font-sans text-[13px] font-medium transition-[color,border] duration-200 border-b-2',
              activeSection === s.key
                ? 'border-accent-foreground font-semibold text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            {s.label}
          </button>
        ))}
      </nav>}

      {/* Section content */}
      <div className={cn(isPhone && 'mobile-records-stack')}>
      <Suspense fallback={<SectionFallback />}>
        {activeSection === 'highlights' && <ObsessionSection data={data.obsession} reigns={data.reigns} behavior={data.behavior} />}
        {activeSection === 'reigns' && <ReignsSection data={data.reigns} />}
        {activeSection === 'longevity' && <LongevitySection data={data.longevity} />}
        {activeSection === 'timePatterns' && <TimePatternsSection data={data.time_patterns} />}
        {activeSection === 'discovery' && <DiscoverySection data={data.discovery} />}
      </Suspense>
      </div>
    </div>
  )
}
