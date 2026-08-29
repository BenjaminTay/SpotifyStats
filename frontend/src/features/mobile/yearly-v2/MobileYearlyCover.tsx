import { STATUS_COPY, formatComparisonWindow, formatMetricComparison } from '@/features/yearly-review/yearlyReviewData'
import type { YearlyReviewResponse } from '@/types/yearly-review-v2'

export function MobileYearlyCover({ report }: { report: YearlyReviewResponse }) {
  const passport = report.passport
  if (!passport) return null

  const periodLabel = passport.observed_end
    ? `截至 ${passport.observed_end.replaceAll('-', '.')}`
    : `${report.year}`
  const comparisonWindow = formatComparisonWindow(report.coverage.comparison)

  return (
    <section className="mobile-yearly-v2-cover" aria-labelledby="mobile-yearly-v2-title">
      <div className="mobile-yearly-v2-cover-rings" aria-hidden="true"><i /></div>
      <header className="mobile-yearly-v2-mastline">
        <span>PERSONAL LISTENING ANNUAL</span>
        <span>ISSUE {String(report.year).slice(-2)}</span>
      </header>
      <div className="mobile-yearly-v2-cover-title">
        {report.status !== 'complete' && (
          <p><i aria-hidden="true" />{STATUS_COPY[report.status].label} · {periodLabel}</p>
        )}
        <h1 id="mobile-yearly-v2-title"><span>{report.year}</span>我的音乐年鉴</h1>
      </div>
      <div className="mobile-yearly-v2-kpis" aria-label={`${report.year} 年度数据`}>
        {passport.metrics.slice(0, 6).map((metric) => {
          const comparison = formatMetricComparison(metric)
          return (
            <div key={metric.key} className="mobile-yearly-v2-kpi">
              <span>{metric.label}</span>
              <div>
                <strong>
                  {typeof metric.value === 'number'
                    ? metric.value.toLocaleString('zh-CN', { maximumFractionDigits: 1 })
                    : metric.value}
                  {metric.unit && <small>{metric.unit}</small>}
                </strong>
                {comparison && (
                  <em className={`is-${comparison.direction}`} aria-label={comparison.ariaLabel}>
                    <b aria-hidden="true">
                      {comparison.direction === 'up' ? '↑' : comparison.direction === 'down' ? '↓' : '—'}
                    </b>
                    {comparison.text}
                  </em>
                )}
              </div>
            </div>
          )
        })}
      </div>
      {comparisonWindow && (
        <p className="mobile-yearly-v2-comparison-window">
          <span>同期参照</span>{comparisonWindow}
        </p>
      )}
    </section>
  )
}
