import { useMemo, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, ListOrdered, X } from 'lucide-react'
import { createPortal } from 'react-dom'

import { useMobileDialog } from '@/components/mobile/useMobileDialog'
import { EntityMediaLink } from '@/features/yearly-review/YearlyReviewPrimitives'
import { ENTITY_LABELS, numberValue, stringValue } from '@/features/yearly-review/yearlyReviewData'
import type { YearlyEntityRef, YearlyReviewResponse } from '@/types/yearly-review-v2'

type AppendixTab = 'play' | 'billboard'
type EntityType = 'track' | 'album' | 'artist'
type PlayMetric = 'plays' | 'hours'

const PAGE_SIZE = 10

function firstText(row: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = stringValue(row, key)
    if (value) return value
  }
  return '—'
}

function rankValue(row: Record<string, unknown>, index: number) {
  return numberValue(row, 'rank') || numberValue(row, 'year_end_rank') || index + 1
}

function rowEntity(row: Record<string, unknown>, entity: EntityType): YearlyEntityRef {
  return {
    entity_type: entity,
    entity_id: (row[entity === 'track' ? 'track_id' : entity === 'album' ? 'album_project_id' : 'artist_id'] as string | number | null | undefined) ?? null,
    name: firstText(row, ['name', 'track_name', 'album_name', 'artist_name']),
    artist_name: entity === 'artist' ? null : stringValue(row, 'artist_name') || null,
    cover_url: stringValue(row, 'cover_url') || null,
    deep_link: stringValue(row, 'deep_link') || null,
  }
}

function metricParts(row: Record<string, unknown>, tab: AppendixTab, metric: PlayMetric) {
  if (tab === 'billboard') {
    return {
      value: numberValue(row, 'year_end_score').toLocaleString('zh-CN', { maximumFractionDigits: 1 }),
      unit: '分',
    }
  }
  if (metric === 'hours') {
    return {
      value: numberValue(row, 'hours').toLocaleString('zh-CN', { maximumFractionDigits: 1 }),
      unit: '小时',
    }
  }
  return { value: numberValue(row, 'plays').toLocaleString('zh-CN'), unit: '次' }
}

function MobileRankRows({
  rows,
  tab,
  entity,
  metric,
  startIndex = 0,
}: {
  rows: Array<Record<string, unknown>>
  tab: AppendixTab
  entity: EntityType
  metric: PlayMetric
  startIndex?: number
}) {
  if (rows.length === 0) return <p className="mobile-yearly-v2-empty">这里还没有榜单记录。</p>

  return (
    <ol className="mobile-yearly-v2-rank-list" start={startIndex + 1}>
      {rows.map((row, index) => {
        const absoluteIndex = startIndex + index
        const itemEntity = rowEntity(row, entity)
        const rowMetric = metricParts(row, tab, metric)
        return (
          <li
            className="mobile-yearly-v2-rank-row"
            key={`${tab}-${entity}-${absoluteIndex}-${itemEntity.name}`}
          >
            <span className="mobile-yearly-v2-rank-number">{rankValue(row, absoluteIndex)}</span>
            <EntityMediaLink entity={itemEntity} className="mobile-yearly-v2-rank-entity" />
            <strong>
              <span>{rowMetric.value}</span>
              <small>{rowMetric.unit}</small>
            </strong>
          </li>
        )
      })}
    </ol>
  )
}

function AppendixControls({
  tab,
  entity,
  metric,
  onTabChange,
  onEntityChange,
  onMetricChange,
  suffix,
}: {
  tab: AppendixTab
  entity: EntityType
  metric: PlayMetric
  onTabChange: (value: AppendixTab) => void
  onEntityChange: (value: EntityType) => void
  onMetricChange: (value: PlayMetric) => void
  suffix: string
}) {
  return (
    <div className={`mobile-yearly-v2-appendix-controls ${suffix ? 'is-preview' : 'is-dialog'}`}>
      <div className="mobile-yearly-v2-appendix-tabs" role="tablist" aria-label={`切换年度榜单${suffix}`}>
        <button type="button" role="tab" aria-selected={tab === 'play'} onClick={() => onTabChange('play')}>播放榜</button>
        <button type="button" role="tab" aria-selected={tab === 'billboard'} onClick={() => onTabChange('billboard')}>个人 Billboard</button>
      </div>
      <div className="mobile-yearly-v2-appendix-filter" aria-label={`切换实体${suffix}`}>
        {(['track', 'album', 'artist'] as EntityType[]).map((value) => (
          <button key={value} type="button" aria-pressed={entity === value} onClick={() => onEntityChange(value)}>
            {ENTITY_LABELS[value]}
          </button>
        ))}
      </div>
      {tab === 'play' && (
        <div className="mobile-yearly-v2-appendix-filter" aria-label={`切换排名方式${suffix}`}>
          <button type="button" aria-pressed={metric === 'plays'} onClick={() => onMetricChange('plays')}>播放次数</button>
          <button type="button" aria-pressed={metric === 'hours'} onClick={() => onMetricChange('hours')}>播放时长</button>
        </div>
      )}
    </div>
  )
}

export function MobileAppendixChapter({ report }: { report: YearlyReviewResponse }) {
  const [tab, setTab] = useState<AppendixTab>('play')
  const [entity, setEntity] = useState<EntityType>('track')
  const [metric, setMetric] = useState<PlayMetric>('plays')
  const [page, setPage] = useState(1)
  const [dialogOpen, setDialogOpen] = useState(false)
  const openerRef = useRef<HTMLButtonElement>(null)
  const dialogRef = useRef<HTMLDivElement>(null)

  const rows = useMemo(() => {
    if (tab === 'play') return report.appendix.play_charts[`${entity}_by_${metric}`] ?? []
    return report.appendix.billboard_charts[entity] ?? []
  }, [entity, metric, report.appendix, tab])
  const totalPages = Math.max(Math.ceil(rows.length / PAGE_SIZE), 1)
  const visibleRows = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  const resetPage = () => setPage(1)
  const changeTab = (value: AppendixTab) => { resetPage(); setTab(value) }
  const changeEntity = (value: EntityType) => { resetPage(); setEntity(value) }
  const changeMetric = (value: PlayMetric) => { resetPage(); setMetric(value) }

  const { close } = useMobileDialog({
    open: dialogOpen,
    onOpenChange: setDialogOpen,
    containerRef: dialogRef,
    triggerRef: openerRef,
  })

  const dialog = dialogOpen ? createPortal(
    <div className="mobile-yearly-v2-dialog-backdrop">
      <div
        ref={dialogRef}
        className="mobile-yearly-v2-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="mobile-yearly-v2-dialog-title"
        tabIndex={-1}
      >
        <header className="mobile-yearly-v2-dialog-header">
          <div>
            <p>{report.year} · THE FULL LISTS</p>
            <h2 id="mobile-yearly-v2-dialog-title">完整榜单</h2>
          </div>
          <button type="button" onClick={close} aria-label="关闭完整榜单" data-mobile-autofocus="true">
            <X aria-hidden="true" />
          </button>
        </header>
        <div className="mobile-yearly-v2-dialog-body">
          <AppendixControls
            tab={tab}
            entity={entity}
            metric={metric}
            onTabChange={changeTab}
            onEntityChange={changeEntity}
            onMetricChange={changeMetric}
            suffix=""
          />
          <MobileRankRows
            rows={visibleRows}
            tab={tab}
            entity={entity}
            metric={metric}
            startIndex={(page - 1) * PAGE_SIZE}
          />
        </div>
        <nav className="mobile-yearly-v2-pagination" aria-label="完整榜单分页">
          <button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>
            <ChevronLeft aria-hidden="true" />上一页
          </button>
          <span>第 {page} / {totalPages} 页 · 共 {rows.length} 条</span>
          <button type="button" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>
            下一页<ChevronRight aria-hidden="true" />
          </button>
        </nav>
      </div>
    </div>,
    document.body,
  ) : null

  return (
    <section className="mobile-yearly-v2-section mobile-yearly-v2-appendix" id="phone-yearly-appendix">
      <header className="mobile-yearly-v2-chapter-heading">
        <span className="mobile-yearly-v2-section-number" aria-hidden="true">08</span>
        <div>
          <p className="mobile-yearly-v2-eyebrow">THE FULL LISTS</p>
          <h2>完整榜单</h2>
        </div>
      </header>
      <AppendixControls
        tab={tab}
        entity={entity}
        metric={metric}
        onTabChange={changeTab}
        onEntityChange={changeEntity}
        onMetricChange={changeMetric}
        suffix="预览"
      />
      <div className="mobile-yearly-v2-appendix-preview">
        <MobileRankRows rows={rows.slice(0, 5)} tab={tab} entity={entity} metric={metric} />
      </div>
      <button
        ref={openerRef}
        type="button"
        className="mobile-yearly-v2-open-list"
        onClick={() => setDialogOpen(true)}
        disabled={rows.length === 0}
      >
        <ListOrdered aria-hidden="true" />
        <span>查看完整榜单</span>
        <strong>{rows.length} 条</strong>
      </button>
      {dialog}
    </section>
  )
}
