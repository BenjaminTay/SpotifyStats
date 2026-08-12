import { ExternalLink } from 'lucide-react'
import { Link } from 'react-router-dom'

import { EntityMediaLink } from '@/features/yearly-review/YearlyReviewPrimitives'
import { displayYearlyText, formatMetric } from '@/features/yearly-review/yearlyReviewData'
import type { YearlyFeaturedRecord, YearlyReviewResponse } from '@/types/yearly-review-v2'

const CATEGORY_LABELS: Record<string, string> = {
  obsession: '沉迷高峰',
  championship: '冠军时刻',
  discovery: '发现与回归',
  market: '榜单占位',
  behavior: '播放行为',
  time_patterns: '时间模式',
  longevity: '长久陪伴',
  movement: '榜单变化',
}

function MobileRecordCard({ record, featured }: { record: YearlyFeaturedRecord; featured: boolean }) {
  const primaryEntity = record.entity_refs[0]

  return (
    <article className={`mobile-yearly-v2-record-card${featured ? ' is-featured' : ''}`}>
      <div className="mobile-yearly-v2-record-index" aria-hidden="true">
        {featured ? 'RECORD OF THE YEAR' : CATEGORY_LABELS[record.category] ?? '年度纪录'}
      </div>
      {primaryEntity && (
        <EntityMediaLink
          entity={primaryEntity}
          size={featured ? 'medium' : 'small'}
          className="mobile-yearly-v2-record-primary"
        />
      )}
      <div className="mobile-yearly-v2-record-copy">
        <p>{featured ? CATEGORY_LABELS[record.category] ?? '年度纪录' : displayYearlyText(record.title)}</p>
        <h3>{displayYearlyText(record.statement)}</h3>
        {featured && <span>{displayYearlyText(record.title)}</span>}
      </div>
      {record.entity_refs.length > 1 && (
        <div className="mobile-yearly-v2-record-entities">
          {record.entity_refs.slice(1, 3).map((entity) => (
            <EntityMediaLink
              key={`${entity.entity_type}-${entity.entity_id}-${entity.name}`}
              entity={entity}
              className="mobile-yearly-v2-record-entity"
            />
          ))}
        </div>
      )}
      {record.metrics.length > 0 && (
        <dl className="mobile-yearly-v2-record-metrics">
          {record.metrics.slice(0, 3).map((metric) => (
            <div key={metric.key}>
              <dt>{displayYearlyText(metric.label)}</dt>
              <dd>{displayYearlyText(formatMetric(metric))}</dd>
            </div>
          ))}
        </dl>
      )}
      {record.deep_link && (
        <Link
          to={record.deep_link}
          className="mobile-yearly-v2-record-link"
          aria-label={`查看纪录：${displayYearlyText(record.title)}`}
        >
          <span>查看相关记录</span>
          <ExternalLink aria-hidden="true" />
        </Link>
      )}
    </article>
  )
}

export function MobileRecordsChapter({ report }: { report: YearlyReviewResponse }) {
  return (
    <section className="mobile-yearly-v2-section mobile-yearly-v2-records" id="phone-yearly-records">
      <header className="mobile-yearly-v2-chapter-heading">
        <span className="mobile-yearly-v2-section-number" aria-hidden="true">05</span>
        <div>
          <p className="mobile-yearly-v2-eyebrow">THE RECORD BOOK</p>
          <h2>今年被你打破的纪录</h2>
        </div>
      </header>
      {report.records.featured.length > 0 ? (
        <div className="mobile-yearly-v2-record-list">
          {report.records.featured.map((record, index) => (
            <MobileRecordCard key={record.record_id} record={record} featured={index === 0} />
          ))}
        </div>
      ) : (
        <p className="mobile-yearly-v2-empty">这一年还没有特别突出的纪录。</p>
      )}
    </section>
  )
}
