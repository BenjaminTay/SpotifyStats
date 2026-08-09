import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Check, ChevronDown, Disc3, Mic2, Music2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { MobileBottomSheet, MobilePagination } from '@/components/mobile'
import { ChangeCell, type RankChange } from '@/components/shared/ChangeCell'
import { RankNumber } from '@/components/shared/RankNumber'
import { cn } from '@/lib/utils'

export type MobileMusicDetailKind = 'track' | 'album' | 'artist'

export interface MobileMusicDetailFact {
  label: string
  value: string
  accent?: boolean
}

interface MobileMusicDetailHeroProps {
  kind: MobileMusicDetailKind
  title: string
  coverUrl?: string | null
  subtitle?: ReactNode
  meta?: ReactNode
  facts: MobileMusicDetailFact[]
}

function ArtworkFallback({ kind }: { kind: MobileMusicDetailKind }) {
  if (kind === 'artist') return <Mic2 aria-hidden="true" />
  if (kind === 'album') return <Disc3 aria-hidden="true" />
  return <Music2 aria-hidden="true" />
}

export function MobileMusicDetailHero({
  kind,
  title,
  coverUrl,
  subtitle,
  meta,
  facts,
}: MobileMusicDetailHeroProps) {
  const [failed, setFailed] = useState(false)

  return (
    <section className={cn('mobile-music-detail-hero', `mobile-music-detail-hero-${kind}`)}>
      <div className="mobile-music-detail-artwork">
        {coverUrl && !failed
          ? <img src={coverUrl} alt={title} onError={() => setFailed(true)} />
          : <ArtworkFallback kind={kind} />}
      </div>
      <div className="mobile-music-detail-copy">
        <h1>{title}</h1>
        {subtitle && <div className="mobile-music-detail-subtitle">{subtitle}</div>}
        {meta && <div className="mobile-music-detail-meta">{meta}</div>}
      </div>
      <dl className="mobile-music-detail-facts">
        {facts.map((fact) => (
          <div key={`${fact.label}:${fact.value}`} className={cn(fact.accent && 'accent')}>
            <dt>{fact.label}</dt>
            <dd>{fact.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

export interface MobileMusicDetailTab<T extends string> {
  key: T
  label: string
  description?: string
}

interface MobileMusicDetailNavProps<T extends string> {
  activeTab: T
  primaryTabs: MobileMusicDetailTab<T>[]
  moreTabs?: MobileMusicDetailTab<T>[]
  scrollable?: boolean
  onChange: (tab: T) => void
}

export function MobileMusicDetailNav<T extends string>({
  activeTab,
  primaryTabs,
  moreTabs = [],
  scrollable = false,
  onChange,
}: MobileMusicDetailNavProps<T>) {
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const tabRefs = useRef(new Map<T, HTMLButtonElement>())
  const activeMore = moreTabs.find((tab) => tab.key === activeTab)
  const visibleTabs = scrollable ? [...primaryTabs, ...moreTabs] : primaryTabs

  useEffect(() => {
    if (!scrollable) return
    tabRefs.current.get(activeTab)?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest', inline: 'center' })
  }, [activeTab, scrollable])

  return (
    <>
      <nav className={cn('mobile-music-detail-nav', scrollable && 'mobile-music-detail-nav-scroll')} aria-label="详情栏目">
        {visibleTabs.map((tab) => (
          <button
            key={tab.key}
            ref={(node) => {
              if (node) tabRefs.current.set(tab.key, node)
              else tabRefs.current.delete(tab.key)
            }}
            type="button"
            aria-current={activeTab === tab.key ? 'page' : undefined}
            onClick={() => onChange(tab.key)}
          >
            {tab.label}
          </button>
        ))}
        {!scrollable && moreTabs.length > 0 && (
          <button
            ref={triggerRef}
            type="button"
            aria-haspopup="dialog"
            aria-expanded={open}
            aria-current={activeMore ? 'page' : undefined}
            onClick={() => setOpen(true)}
          >
            {activeMore?.label ?? '更多'}
            <ChevronDown aria-hidden="true" />
          </button>
        )}
      </nav>

      {!scrollable && moreTabs.length > 0 && (
        <MobileBottomSheet
          open={open}
          onOpenChange={setOpen}
          title="更多详情栏目"
          eyebrow="Music / Sections"
          description="榜单空态也会保留对应栏目，不影响实体详情资格。"
          triggerRef={triggerRef}
          dataSheet="music-detail-sections"
        >
          <div className="mobile-section-options" role="listbox" aria-label="更多详情栏目">
            {moreTabs.map((tab) => {
              const selected = tab.key === activeTab
              return (
                <button
                  key={tab.key}
                  type="button"
                  role="option"
                  aria-selected={selected}
                  className={cn(selected && 'active')}
                  onClick={() => {
                    onChange(tab.key)
                    setOpen(false)
                  }}
                >
                  <span>
                    <strong>{tab.label}</strong>
                    {tab.description && <small>{tab.description}</small>}
                  </span>
                  {selected && <Check aria-hidden="true" />}
                </button>
              )
            })}
          </div>
        </MobileBottomSheet>
      )}
    </>
  )
}

export interface MobileChartHistoryEntry {
  week: string
  rank: number
  change?: string
  playCount: number
  runningPeak?: number
  runningWeeks?: number
  runningPeakWeeks?: number
}

function parseHistoryChange(value?: string): RankChange {
  if (value === 'NEW') return { type: 'new' }
  if (value === 'RE') return { type: 're' }
  const up = value?.match(/^[▲↑](\d+)$/)
  if (up) return { type: 'up', delta: Number(up[1]) }
  const down = value?.match(/^[▼↓](\d+)$/)
  if (down) return { type: 'down', delta: Number(down[1]) }
  return { type: 'same' }
}

export function MobileChartHistoryList({ entries }: { entries: MobileChartHistoryEntry[] }) {
  const pageSize = 10
  const [pageState, setPageState] = useState({ source: entries, page: 1 })
  const pageCount = Math.max(1, Math.ceil(entries.length / pageSize))
  const page = pageState.source === entries ? Math.min(pageState.page, pageCount) : 1
  const visibleEntries = entries.slice((page - 1) * pageSize, page * pageSize)

  return (
    <div className="mobile-detail-history">
      <div className="mobile-detail-history-list">
        {visibleEntries.map((entry) => (
          <Link key={entry.week} to={`/billboard?week=${entry.week}`} className="mobile-detail-history-row">
            <time>{entry.week.slice(0, 10)}</time>
            <span className="mobile-detail-history-rank">
              <RankNumber rank={entry.rank} highlightTopThree />
              <ChangeCell change={parseHistoryChange(entry.change)} />
            </span>
            <span className="mobile-detail-history-plays">{entry.playCount.toLocaleString('zh-CN')} 次</span>
            <small>
              {entry.runningPeak ? `Peak ${entry.runningPeak}` : 'Peak —'}
              {entry.runningWeeks ? ` · 在榜 ${entry.runningWeeks}周` : ''}
              {entry.runningPeakWeeks != null ? ` · 峰值 ${entry.runningPeakWeeks}周` : ''}
            </small>
          </Link>
        ))}
      </div>
      {pageCount > 1 && (
        <MobilePagination
          mode="pages"
          page={page}
          pageCount={pageCount}
          onPageChange={(nextPage) => setPageState({ source: entries, page: nextPage })}
        />
      )}
    </div>
  )
}
