import { useState } from 'react'
import { ArrowDownRight, ArrowUpRight } from 'lucide-react'

import { EntityMediaLink, SectionHeading } from '@/features/yearly-review/YearlyReviewPrimitives'
import { displayYearlyText, numberValue, stringValue } from '@/features/yearly-review/yearlyReviewData'
import type { YearlyReviewResponse } from '@/types/yearly-review-v2'

type TasteAxis = 'style' | 'scene' | 'language' | 'release_era'

const AXES: Array<{ key: TasteAxis; label: string }> = [
  { key: 'style', label: '主曲风' },
  { key: 'scene', label: '地区流行' },
  { key: 'language', label: '语言' },
  { key: 'release_era', label: '发行年代' },
]

function rowLabel(row: Record<string, unknown>) {
  const label = stringValue(row, 'label') || stringValue(row, 'key') || '其他'
  return label === '尚未归类' || label === 'unknown' ? '其他' : label
}

export function TasteMigrationChapter({ report }: { report: YearlyReviewResponse }) {
  const [axis, setAxis] = useState<TasteAxis>('style')
  const availableAxes = AXES.filter((item) => ['core', 'secondary'].includes(report.coverage.taste[item.key].level))
  const activeAxis = availableAxes.some((item) => item.key === axis) ? axis : availableAxes[0]?.key
  if (!activeAxis) return null
  const currentAxis = activeAxis
  const rows = report.taste_migration.distributions[currentAxis] ?? []
  const changes = report.taste_migration.changes[currentAxis] ?? []
  const maxShare = Math.max(...rows.map((row) => numberValue(row, 'share_pct')), 1)
  const observation = report.taste_migration.observations.find((item) => item.headline_id === `taste_migration_${currentAxis}`)
  const comparison = report.taste_migration.comparison
  const comparisonLabel = comparison.status === 'available'
    ? `${comparison.from_label} → ${comparison.to_label}`
    : '仅展示年度分布'

  return (
    <section className="yearly-v2-section" id="yearly-v2-taste">
      <SectionHeading number="06" eyebrow="TASTE MIGRATION" title="品味并非静止不动" />
      <div className="yearly-v2-taste-tabs" role="tablist" aria-label="切换品味维度">
        {availableAxes.map((item) => (
          <button key={item.key} type="button" role="tab" aria-selected={currentAxis === item.key} onClick={() => setAxis(item.key)}>{item.label}</button>
        ))}
      </div>

      {rows.length > 0 && (
        <div className="yearly-v2-taste-layout">
          <div className="yearly-v2-taste-distribution">
            {rows.slice(0, 10).map((row) => {
              const share = numberValue(row, 'share_pct')
              return (
                <div key={`${currentAxis}-${rowLabel(row)}`}>
                  <span>{rowLabel(row)}</span>
                  <i><b style={{ width: `${Math.max(share / maxShare * 100, share > 0 ? 2 : 0)}%` }} /></i>
                  <strong>{share.toFixed(1)}%</strong>
                </div>
              )
            })}
          </div>
          {comparison.status === 'available' && changes.length > 0 && <aside className="yearly-v2-taste-change">
            <p>{comparisonLabel}</p>
            {observation ? (
              <div className="yearly-v2-taste-story">
                <h3>{displayYearlyText(observation.title)}</h3>
                <span>{displayYearlyText(observation.statement)}</span>
                {observation.entity_refs.map((entity) => <EntityMediaLink key={`${entity.entity_type}-${entity.entity_id}`} entity={entity} className="yearly-v2-taste-entity" />)}
              </div>
            ) : null}
            <div className="yearly-v2-change-list">
              {changes.slice(0, 6).map((row) => {
                const delta = numberValue(row, 'delta_pct')
                return (
                  <div key={`${currentAxis}-${stringValue(row, 'key')}`}>
                    <span>{stringValue(row, 'label') || stringValue(row, 'key')}</span>
                    <small>{numberValue(row, 'from_pct').toFixed(1)}% → {numberValue(row, 'to_pct').toFixed(1)}%</small>
                    <strong className={delta >= 0 ? 'is-up' : 'is-down'}>{delta >= 0 ? <ArrowUpRight aria-hidden="true" /> : <ArrowDownRight aria-hidden="true" />}{Math.abs(delta).toFixed(1)} 个百分点</strong>
                  </div>
                )
              })}
            </div>
          </aside>}
        </div>
      )}
    </section>
  )
}
