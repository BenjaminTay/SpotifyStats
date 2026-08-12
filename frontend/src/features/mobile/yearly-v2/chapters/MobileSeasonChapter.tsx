import { useState } from 'react'
import { ChevronDown } from 'lucide-react'

import { EntityMediaLink } from '@/features/yearly-review/YearlyReviewPrimitives'
import type { YearlyMonthSummary, YearlyReviewResponse } from '@/types/yearly-review-v2'

const EVENT_LABELS: Record<string, string> = {
  listening_peak: '收听高峰',
  leader_change: '榜首更替',
  discovery_peak: '发现时刻',
  return: '旧爱回归',
  obsession_peak: '沉迷时刻',
  sustained_record: '持续纪录',
  listening_pattern: '收听模式',
  record_moment: '年度纪录',
  monthly_shift: '节奏变化',
}

const MONTH_ABBREVIATIONS = [
  'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
  'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC',
]

function MonthPanel({ month }: { month: YearlyMonthSummary }) {
  const leaders = Object.values(month.leaders).filter((entity, index, entities) => (
    entities.findIndex((candidate) => (
      candidate.entity_type === entity.entity_type
      && (candidate.entity_id ?? candidate.name) === (entity.entity_id ?? entity.name)
    )) === index
  ))

  return (
    <article className="mobile-yearly-v2-month-panel" aria-live="polite">
      <header>
        <span>{String(month.month).padStart(2, '0')}</span>
        <div>
          <small>MONTH IN REVIEW</small>
          <strong>{MONTH_ABBREVIATIONS[month.month - 1]}</strong>
        </div>
      </header>
      <div className="mobile-yearly-v2-month-facts">
        <p><strong>{month.plays.toLocaleString('zh-CN')}</strong><span>次播放</span></p>
        <p><strong>{month.hours.toLocaleString('zh-CN', { maximumFractionDigits: 1 })}</strong><span>小时</span></p>
        <p><strong>{month.active_days}</strong><span>个活跃日</span></p>
      </div>
      {leaders.length > 0 && (
        <div className="mobile-yearly-v2-month-leaders">
          {leaders.map((entity) => (
            <EntityMediaLink
              key={`${entity.entity_type}-${entity.entity_id ?? entity.name}`}
              entity={entity}
              className="mobile-yearly-v2-month-leader"
            />
          ))}
        </div>
      )}
    </article>
  )
}

export function MobileSeasonChapter({ report }: { report: YearlyReviewResponse }) {
  const { turning_points: turningPoints, months, stages } = report.season
  const firstRecordedMonth = months.find((month) => month.plays > 0)?.month ?? months[0]?.month ?? 1
  const [selectedMonth, setSelectedMonth] = useState(firstRecordedMonth)
  const activeMonth = months.find((month) => month.month === selectedMonth) ?? months[0]

  return (
    <section
      className="mobile-yearly-v2-section mobile-yearly-v2-season"
      id="phone-yearly-season"
      aria-labelledby="phone-yearly-season-title"
    >
      <header className="mobile-yearly-v2-chapter-heading">
        <span className="mobile-yearly-v2-section-number" aria-hidden="true">02</span>
        <div>
          <p className="mobile-yearly-v2-eyebrow">THE SEASON</p>
          <h2 id="phone-yearly-season-title">这一年如何转弯</h2>
        </div>
      </header>

      {stages.length > 0 && (
        <div className="mobile-yearly-v2-stage-scroller" aria-label="年度阶段">
          {stages.map((stage) => (
            <article key={stage.stage_id} className="mobile-yearly-v2-stage-chip">
              <p>{String(stage.start_month).padStart(2, '0')}—{String(stage.end_month).padStart(2, '0')} 月</p>
              <h3>{stage.label}</h3>
              {stage.entity_refs.map((entity) => (
                <EntityMediaLink
                  key={`${entity.entity_type}-${entity.entity_id ?? entity.name}`}
                  entity={entity}
                  className="mobile-yearly-v2-stage-entity"
                />
              ))}
            </article>
          ))}
        </div>
      )}

      <div className="mobile-yearly-v2-timeline">
        {turningPoints.map((point) => (
          <article key={point.point_id} className="mobile-yearly-v2-timeline-item">
            <div className="mobile-yearly-v2-timeline-marker" aria-hidden="true">
              <span>{String(point.month).padStart(2, '0')}</span>
              <i />
            </div>
            <div className="mobile-yearly-v2-timeline-story">
              <p>{EVENT_LABELS[point.event_type] ?? '年度节点'}{point.date ? ` · ${point.date}` : ''}</p>
              <h3>{point.title}</h3>
              <p>{point.statement}</p>
              {point.entity_refs.length > 0 && (
                <div className="mobile-yearly-v2-timeline-entities">
                  {point.entity_refs.map((entity) => (
                    <EntityMediaLink
                      key={`${entity.entity_type}-${entity.entity_id ?? entity.name}`}
                      entity={entity}
                      className="mobile-yearly-v2-timeline-entity"
                    />
                  ))}
                </div>
              )}
            </div>
          </article>
        ))}
      </div>

      {months.length > 0 && (
        <details className="mobile-yearly-v2-month-ledger">
          <summary>
            <span>
              <small>MONTH BY MONTH</small>
              <strong>十二个月，逐月翻阅</strong>
            </span>
            <em>{months.filter((month) => month.plays > 0).length} / 12</em>
            <ChevronDown aria-hidden="true" />
          </summary>
          <div className="mobile-yearly-v2-month-tabs" role="tablist" aria-label="选择月份">
            {months.map((month) => (
              <button
                key={month.month}
                type="button"
                role="tab"
                aria-selected={activeMonth?.month === month.month}
                aria-controls="phone-yearly-month-panel"
                className={month.plays === 0 ? 'is-empty' : undefined}
                onClick={() => setSelectedMonth(month.month)}
              >
                {String(month.month).padStart(2, '0')}
              </button>
            ))}
          </div>
          {activeMonth && (
            <div id="phone-yearly-month-panel" role="tabpanel">
              <MonthPanel month={activeMonth} />
            </div>
          )}
        </details>
      )}
    </section>
  )
}
