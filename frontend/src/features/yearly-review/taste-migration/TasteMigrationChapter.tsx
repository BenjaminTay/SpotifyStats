import { useState } from 'react'
import { ArrowDownRight, ArrowUpRight } from 'lucide-react'

import { EntityLink, EmptyChapter, SectionHeading } from '@/features/yearly-review/YearlyReviewPrimitives'
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
  return stringValue(row, 'label') || stringValue(row, 'key') || '尚未归类'
}

export function TasteMigrationChapter({ report }: { report: YearlyReviewResponse }) {
  const [axis, setAxis] = useState<TasteAxis>('style')
  const coverage = report.coverage.taste[axis]
  const rows = report.taste_migration.distributions[axis] ?? []
  const changes = report.taste_migration.changes[axis] ?? []
  const maxShare = Math.max(...rows.map((row) => numberValue(row, 'share_pct')), 1)
  const observation = report.taste_migration.observations.find((item) => item.headline_id === `taste_migration_${axis}`)
  const comparison = report.taste_migration.comparison
  const comparisonLabel = comparison.status === 'available'
    ? `${comparison.from_label} → ${comparison.to_label}`
    : '仅展示年度分布'

  return (
    <section className="yearly-v2-section" id="yearly-v2-taste">
      <SectionHeading
        number="06"
        eyebrow="TASTE MIGRATION"
        title="品味并非静止不动"
        description="年度分布回答你听了什么；仅在两个完整且可比较的阶段之间解释品味变化。"
      />
      <div className="yearly-v2-taste-tabs" role="tablist" aria-label="切换品味维度">
        {AXES.map((item) => (
          <button key={item.key} type="button" role="tab" aria-selected={axis === item.key} onClick={() => setAxis(item.key)}>{item.label}</button>
        ))}
      </div>
      <div className="yearly-v2-taste-coverage">
        <span>已知覆盖率 <strong>{coverage.known_pct.toFixed(1)}%</strong></span>
        <span>{report.taste_migration.coverage_notes[axis] ?? '暂无法判断'}</span>
        {coverage.unknown_hours > 0 && <span>尚未归类 {coverage.unknown_hours.toFixed(1)} 小时</span>}
      </div>

      {rows.length === 0 ? (
        <EmptyChapter>这一维度的已知元数据不足，年鉴不会据此补写结论。</EmptyChapter>
      ) : (
        <div className="yearly-v2-taste-layout">
          <div className="yearly-v2-taste-distribution">
            {rows.slice(0, 10).map((row) => {
              const share = numberValue(row, 'share_pct')
              return (
                <div key={`${axis}-${rowLabel(row)}`}>
                  <span>{rowLabel(row)}</span>
                  <i><b style={{ width: `${Math.max(share / maxShare * 100, share > 0 ? 2 : 0)}%` }} /></i>
                  <strong>{share.toFixed(1)}%</strong>
                </div>
              )
            })}
          </div>
          <aside className="yearly-v2-taste-change">
            <p>{comparisonLabel}</p>
            {observation ? (
              <div className="yearly-v2-taste-story">
                <h3>{observation.title}</h3>
                <span>{observation.statement}</span>
                {observation.entity_refs.map((entity) => <EntityLink key={`${entity.entity_type}-${entity.entity_id}`} entity={entity} className="yearly-v2-inline-entity" />)}
              </div>
            ) : <small>{comparison.status === 'available' ? '变化未达到结论门槛，以下仅列事实差值。' : '当前尚无两个完整的可比阶段，不计算迁移差值。'}</small>}
            <div className="yearly-v2-change-list">
              {changes.slice(0, 6).map((row) => {
                const delta = numberValue(row, 'delta_pct')
                return (
                  <div key={`${axis}-${stringValue(row, 'key')}`}>
                    <span>{stringValue(row, 'label') || stringValue(row, 'key')}</span>
                    <small>{numberValue(row, 'from_pct').toFixed(1)}% → {numberValue(row, 'to_pct').toFixed(1)}%</small>
                    <strong className={delta >= 0 ? 'is-up' : 'is-down'}>{delta >= 0 ? <ArrowUpRight aria-hidden="true" /> : <ArrowDownRight aria-hidden="true" />}{Math.abs(delta).toFixed(1)}pp</strong>
                  </div>
                )
              })}
            </div>
          </aside>
        </div>
      )}
    </section>
  )
}
