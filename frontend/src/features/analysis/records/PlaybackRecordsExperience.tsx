/** Playback Records Experience — section tab management + lazy loading, aligned with Billboard RecordsPage. */

import { Suspense, lazy, useState } from 'react'
import { cn } from '@/lib/utils'
import { MobileSectionSwitcher } from '@/components/mobile'
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
  const [activeSection, setActiveSection] = useState<PlaybackRecordSectionKey>('highlights')

  return (
    <div>
      {isPhone ? (
        <MobileSectionSwitcher
          value={activeSection}
          options={PLAYBACK_RECORD_SECTIONS.map((section) => ({
            value: section.key,
            label: section.label,
            description: `${section.modules.length} 组纪录`,
          }))}
          onChange={setActiveSection}
          title="选择播放记录栏目"
        />
      ) : <nav className="mb-8 flex gap-7 border-b border-border" role="tablist" aria-label="播放记录分类">
        {PLAYBACK_RECORD_SECTIONS.map((s) => (
          <button
            key={s.key}
            role="tab"
            aria-selected={activeSection === s.key}
            onClick={() => setActiveSection(s.key)}
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
