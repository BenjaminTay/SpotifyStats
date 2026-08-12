import { ExternalLink } from 'lucide-react'
import { Link } from 'react-router-dom'

import { EntityMediaLink, EmptyChapter, MetricLine, SectionHeading } from '@/features/yearly-review/YearlyReviewPrimitives'
import { displayYearlyText } from '@/features/yearly-review/yearlyReviewData'
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

function RecordCard({ record, featured = false }: { record: YearlyFeaturedRecord; featured?: boolean }) {
  const content = (
    <>
      {record.entity_refs[0] && (
        <EntityMediaLink
          entity={record.entity_refs[0]}
          size="medium"
          className="yearly-v2-record-hero-entity"
        />
      )}
      <header>
        <span>{CATEGORY_LABELS[record.category] ?? '年度纪录'}</span>
      </header>
      <p>{displayYearlyText(record.title)}</p>
      <h3>{displayYearlyText(record.statement)}</h3>
      {record.entity_refs.length > 0 && (
        <div className="yearly-v2-record-entities">
          {record.entity_refs.slice(record.entity_refs[0] ? 1 : 0, 3).map((entity) => (
            <EntityMediaLink
              key={`${entity.entity_type}-${entity.entity_id}-${entity.name}`}
              entity={entity}
              className="yearly-v2-record-entity"
            />
          ))}
        </div>
      )}
      <div className="yearly-v2-record-metrics">
        {record.metrics.slice(0, 3).map((metric) => <MetricLine key={metric.key} metric={metric} compact />)}
      </div>
    </>
  )

  return (
    <article className={featured ? 'yearly-v2-record-card is-featured' : 'yearly-v2-record-card'}>
      {content}
      {record.deep_link && (
        <Link to={record.deep_link} className="yearly-v2-record-external" aria-label={`查看纪录：${displayYearlyText(record.title)}`}>
          <ExternalLink aria-hidden="true" />
        </Link>
      )}
    </article>
  )
}

export function RecordsChapter({ report }: { report: YearlyReviewResponse }) {
  return (
    <section className="yearly-v2-section" id="yearly-v2-records">
      <SectionHeading
        number="05"
        eyebrow="THE RECORD BOOK"
        title="今年被你打破的纪录"
      />
      {report.records.featured.length === 0 ? (
        <EmptyChapter>这一年还没有特别突出的纪录。</EmptyChapter>
      ) : (
        <div className="yearly-v2-featured-records">
          {report.records.featured.map((record, index) => (
            <RecordCard key={record.record_id} record={record} featured={index === 0} />
          ))}
        </div>
      )}

    </section>
  )
}
