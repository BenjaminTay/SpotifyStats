import { STATUS_COPY, formatComparisonWindow, formatMetricComparison } from '@/features/yearly-review/yearlyReviewData'
import type { YearlyReviewResponse } from '@/types/yearly-review-v2'

export function PassportChapter({ report }: { report: YearlyReviewResponse }) {
  const passport = report.passport
  if (!passport) return null
  const status = STATUS_COPY[report.status]
  const periodLabel = passport.observed_end
    ? `截至 ${passport.observed_end.replaceAll('-', '.')}`
    : `${report.year}`
  const comparisonWindow = formatComparisonWindow(report.coverage.comparison)

  return (
    <section className="yearly-v2-cover" aria-labelledby="yearly-v2-cover-title">
      <div className="yearly-v2-cover-orbit" aria-hidden="true" />
      <div className="yearly-v2-cover-kicker">
        <span>PERSONAL LISTENING ANNUAL</span>
        <span>ISSUE {String(report.year).slice(-2)}</span>
      </div>
      <div className="yearly-v2-cover-main">
        <div>
          {report.status !== 'complete' && (
            <p className="yearly-v2-cover-status"><i />{status.label} · {periodLabel}</p>
          )}
          <h1 id="yearly-v2-cover-title"><span>{report.year}</span> 我的音乐年鉴</h1>
        </div>
      </div>
      <div className="yearly-v2-kpi-strip">
        {passport.metrics.map((metric) => {
          const comparison = formatMetricComparison(metric)
          return (
            <div key={metric.key}>
              <span>{metric.label}</span>
              <div className="yearly-v2-kpi-value-row">
                <div>
                  <strong>{typeof metric.value === 'number' ? metric.value.toLocaleString('zh-CN', { maximumFractionDigits: 1 }) : metric.value}</strong>
                  <small>{metric.unit}</small>
                </div>
                {comparison && (
                  <em className={`is-${comparison.direction}`} aria-label={comparison.ariaLabel}>
                    <b aria-hidden="true">{comparison.direction === 'up' ? '↑' : comparison.direction === 'down' ? '↓' : '—'}</b>
                    {comparison.text}
                  </em>
                )}
              </div>
            </div>
          )
        })}
      </div>
      {comparisonWindow && (
        <p className="yearly-v2-comparison-window">
          <span>同期参照</span>{comparisonWindow}
        </p>
      )}
    </section>
  )
}
