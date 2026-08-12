import { useState } from 'react'
import { ArrowDownRight, ArrowUpRight } from 'lucide-react'

import { EntityMediaLink } from '@/features/yearly-review/YearlyReviewPrimitives'
import { numberValue, stringValue } from '@/features/yearly-review/yearlyReviewData'
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

export function MobileTasteMigrationChapter({ report }: { report: YearlyReviewResponse }) {
  const [axis, setAxis] = useState<TasteAxis>('style')
  const availableAxes = AXES.filter((item) => ['core', 'secondary'].includes(report.coverage.taste[item.key].level))
  const currentAxis = availableAxes.some((item) => item.key === axis) ? axis : availableAxes[0]?.key

  if (!currentAxis) return null

  const rows = report.taste_migration.distributions[currentAxis] ?? []
  const changes = report.taste_migration.changes[currentAxis] ?? []
  const observation = report.taste_migration.observations.find(
    (item) => item.headline_id === `taste_migration_${currentAxis}`,
  )
  const comparison = report.taste_migration.comparison
  const currentAxisLabel = AXES.find((item) => item.key === currentAxis)?.label ?? '品味'

  return (
    <section className="mobile-yearly-v2-section mobile-yearly-v2-taste" id="phone-yearly-taste">
      <header className="mobile-yearly-v2-chapter-heading">
        <span className="mobile-yearly-v2-section-number" aria-hidden="true">06</span>
        <div>
          <p className="mobile-yearly-v2-eyebrow">TASTE MIGRATION</p>
          <h2>品味并非静止不动</h2>
        </div>
      </header>

      <div className="mobile-yearly-v2-taste-tabs" role="tablist" aria-label="切换品味维度">
        {availableAxes.map((item) => (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={currentAxis === item.key}
            onClick={() => setAxis(item.key)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="mobile-yearly-v2-taste-distribution">
        <header>
          <strong>{currentAxisLabel}</strong>
          <span>全年占比</span>
        </header>
        {rows.slice(0, 10).map((row) => {
          const share = Math.max(0, Math.min(numberValue(row, 'share_pct'), 100))
          const label = rowLabel(row)
          return (
            <div className="mobile-yearly-v2-taste-row" key={`${currentAxis}-${label}`}>
              <div>
                <span>{label}</span>
                <strong>{share.toFixed(1)}%</strong>
              </div>
              <div
                className="mobile-yearly-v2-taste-bar"
                role="progressbar"
                aria-label={`${label}占比`}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={share}
              >
                <i style={{ width: `${share}%` }} />
              </div>
            </div>
          )
        })}
        {rows.length === 0 && <p className="mobile-yearly-v2-empty">这一维度还没有可展示的分布。</p>}
      </div>

      {comparison.status === 'available' && changes.length > 0 && (
        <aside className="mobile-yearly-v2-taste-change">
          <p className="mobile-yearly-v2-taste-period">
            {comparison.from_label} <span aria-hidden="true">→</span> {comparison.to_label}
          </p>
          {observation && (
            <div className="mobile-yearly-v2-taste-story">
              <h3>{observation.title}</h3>
              <p>{observation.statement}</p>
              {observation.entity_refs.map((entity) => (
                <EntityMediaLink
                  key={`${entity.entity_type}-${entity.entity_id}-${entity.name}`}
                  entity={entity}
                  className="mobile-yearly-v2-taste-entity"
                />
              ))}
            </div>
          )}
          <div className="mobile-yearly-v2-taste-change-list">
            {changes.slice(0, 6).map((row) => {
              const delta = numberValue(row, 'delta_pct')
              const label = stringValue(row, 'label') || stringValue(row, 'key') || '其他'
              return (
                <div key={`${currentAxis}-${stringValue(row, 'key') || label}`}>
                  <span>{label}</span>
                  <small>{numberValue(row, 'from_pct').toFixed(1)}% → {numberValue(row, 'to_pct').toFixed(1)}%</small>
                  <strong className={delta >= 0 ? 'is-up' : 'is-down'} aria-label={`${label}${delta >= 0 ? '上升' : '下降'} ${Math.abs(delta).toFixed(1)}%`}>
                    {delta >= 0 ? <ArrowUpRight aria-hidden="true" /> : <ArrowDownRight aria-hidden="true" />}
                    {Math.abs(delta).toFixed(1)}%
                  </strong>
                </div>
              )
            })}
          </div>
        </aside>
      )}
    </section>
  )
}
