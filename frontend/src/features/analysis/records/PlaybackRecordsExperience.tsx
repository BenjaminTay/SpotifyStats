/** Playback Records Experience — section tab management + lazy loading, aligned with Billboard RecordsPage. */

import { Suspense, lazy, useState } from 'react'
import { cn } from '@/lib/utils'
import type { PlaybackRecordsData } from '@/types/analysis'
import { SectionFallback } from './PlaybackRecordsPrimitives'

const ObsessionSection = lazy(() => import('./ObsessionSection').then((m) => ({ default: m.ObsessionSection })))
const LongevitySection = lazy(() => import('./LongevitySection').then((m) => ({ default: m.LongevitySection })))
const ReignsSection = lazy(() => import('./ReignsSection').then((m) => ({ default: m.ReignsSection })))
const TimePatternsSection = lazy(() => import('./TimePatternsSection').then((m) => ({ default: m.TimePatternsSection })))
const DiscoverySection = lazy(() => import('./DiscoverySection').then((m) => ({ default: m.DiscoverySection })))
const BehaviorSection = lazy(() => import('./BehaviorSection').then((m) => ({ default: m.BehaviorSection })))

type SectionKey = 'obsession' | 'longevity' | 'reigns' | 'timePatterns' | 'discovery' | 'behavior'

const SECTIONS: { key: SectionKey; label: string }[] = [
  { key: 'obsession', label: '狂热时刻' },
  { key: 'longevity', label: '长线陪伴' },
  { key: 'reigns', label: '个人王朝' },
  { key: 'timePatterns', label: '时间密码' },
  { key: 'discovery', label: '探索发现' },
  { key: 'behavior', label: '行为奇观' },
]

interface Props {
  data: PlaybackRecordsData
}

export function PlaybackRecordsExperience({ data }: Props) {
  const [activeSection, setActiveSection] = useState<SectionKey>('obsession')

  return (
    <div>
      {/* Section tabs — matches Billboard RecordsPage tab style */}
      <nav className="mb-8 flex gap-7 border-b border-border" role="tablist" aria-label="播放记录分类">
        {SECTIONS.map((s) => (
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
      </nav>

      {/* Section content */}
      <Suspense fallback={<SectionFallback />}>
        {activeSection === 'obsession' && <ObsessionSection data={data.obsession} />}
        {activeSection === 'longevity' && <LongevitySection data={data.longevity} />}
        {activeSection === 'reigns' && <ReignsSection data={data.reigns} />}
        {activeSection === 'timePatterns' && <TimePatternsSection data={data.time_patterns} />}
        {activeSection === 'discovery' && <DiscoverySection data={data.discovery} />}
        {activeSection === 'behavior' && <BehaviorSection data={data.behavior} />}
      </Suspense>
    </div>
  )
}
