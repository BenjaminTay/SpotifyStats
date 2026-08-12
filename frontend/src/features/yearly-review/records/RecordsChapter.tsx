import { useState } from 'react'
import { ArrowLeft, ArrowRight, BookOpen, ExternalLink } from 'lucide-react'
import { Link } from 'react-router-dom'

import { EntityLink, EmptyChapter, MetricLine, SectionHeading } from '@/features/yearly-review/YearlyReviewPrimitives'
import { useYearlyReviewV2Records } from '@/hooks/useYearlyReviewV2'
import type { AnalysisFilters } from '@/types/analysis'
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
      <header>
        <span>{CATEGORY_LABELS[record.category] ?? '年度纪录'}</span>
      </header>
      <p>{record.title}</p>
      <h3>{record.statement}</h3>
      {record.entity_refs.length > 0 && (
        <div className="yearly-v2-record-entities">
          {record.entity_refs.slice(0, 3).map((entity) => (
            <EntityLink
              key={`${entity.entity_type}-${entity.entity_id}-${entity.name}`}
              entity={entity}
              className="yearly-v2-inline-entity"
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
        <Link to={record.deep_link} className="yearly-v2-record-external" aria-label={`查看纪录：${record.title}`}>
          <ExternalLink aria-hidden="true" />
        </Link>
      )}
    </article>
  )
}

export function RecordsChapter({ report, filters }: { report: YearlyReviewResponse; filters: AnalysisFilters }) {
  const [catalogOpen, setCatalogOpen] = useState(false)
  const [page, setPage] = useState(1)
  const catalog = useYearlyReviewV2Records(report.year, filters, page, 20, catalogOpen)

  return (
    <section className="yearly-v2-section" id="yearly-v2-records">
      <SectionHeading
        number="05"
        eyebrow="THE RECORD BOOK"
        title="今年被你打破的纪录"
        description="高峰、连胜、耐久、回归与怪趣事实不再散落在播放记录页，而是成为这本年鉴的正式档案。"
      />
      {report.records.featured.length === 0 ? (
        <EmptyChapter>当前年度没有达到展示阈值的纪录。</EmptyChapter>
      ) : (
        <div className="yearly-v2-featured-records">
          {report.records.featured.map((record, index) => (
            <RecordCard key={record.record_id} record={record} featured={index === 0} />
          ))}
        </div>
      )}

      <div className="yearly-v2-catalog-toggle">
        <div>
          <BookOpen aria-hidden="true" />
          <span><strong>公开年度纪录目录</strong><small>仅收录具备正式文案与可核验证据的纪录，服务端分页加载</small></span>
        </div>
        <button type="button" aria-expanded={catalogOpen} onClick={() => { setPage(1); setCatalogOpen((open) => !open) }}>
          {catalogOpen ? '收起目录' : '打开目录'}
        </button>
      </div>

      {catalogOpen && (
        <div className="yearly-v2-record-catalog" aria-live="polite">
          {catalog.isLoading && <p className="yearly-v2-catalog-state">正在调取纪录目录…</p>}
          {catalog.error && <p className="yearly-v2-catalog-state is-error">纪录目录加载失败：{catalog.error instanceof Error ? catalog.error.message : '未知错误'}</p>}
          {catalog.data && (
            <>
              <div className="yearly-v2-catalog-grid">
                {catalog.data.items.map((record) => <RecordCard key={record.record_id} record={record} />)}
              </div>
              <nav className="yearly-v2-pagination" aria-label="年度纪录分页">
                <button type="button" disabled={page <= 1 || catalog.isFetching} onClick={() => setPage((value) => value - 1)}><ArrowLeft aria-hidden="true" />上一页</button>
                <span>第 {catalog.data.page} / {Math.max(catalog.data.total_pages, 1)} 页 · 共 {catalog.data.total} 条</span>
                <button type="button" disabled={page >= catalog.data.total_pages || catalog.isFetching} onClick={() => setPage((value) => value + 1)}>下一页<ArrowRight aria-hidden="true" /></button>
              </nav>
            </>
          )}
        </div>
      )}
    </section>
  )
}
