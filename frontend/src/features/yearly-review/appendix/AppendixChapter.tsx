import { useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'

import { SectionHeading } from '@/features/yearly-review/YearlyReviewPrimitives'
import { ENTITY_LABELS, numberValue, stringValue } from '@/features/yearly-review/yearlyReviewData'
import type { YearlyReviewResponse } from '@/types/yearly-review-v2'

type AppendixTab = 'play' | 'billboard' | 'months' | 'method'
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

export function AppendixChapter({ report }: { report: YearlyReviewResponse }) {
  const [tab, setTab] = useState<AppendixTab>('play')
  const [entity, setEntity] = useState<EntityType>('track')
  const [metric, setMetric] = useState<PlayMetric>('plays')
  const [page, setPage] = useState(1)

  const rows = useMemo(() => {
    if (tab === 'play') return report.appendix.play_charts[`${entity}_by_${metric}`] ?? []
    if (tab === 'billboard') return report.appendix.billboard_charts[entity] ?? []
    if (tab === 'months') return report.appendix.monthly_champions
    return []
  }, [entity, metric, report.appendix, tab])
  const totalPages = Math.max(Math.ceil(rows.length / PAGE_SIZE), 1)
  const visibleRows = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  return (
    <section className="yearly-v2-section yearly-v2-appendix" id="yearly-v2-appendix">
      <SectionHeading
        number="08"
        eyebrow="INDEX & METHOD"
        title="完整榜单与口径索引"
        description="故事到此结束，事实继续保留。所有长榜与月度冠军在一个附录中分页查阅。"
      />
      <div className="yearly-v2-appendix-tabs" role="tablist" aria-label="切换年度附录">
        {([
          ['play', '播放榜'],
          ['billboard', '个人 Billboard'],
          ['months', '月度冠军'],
          ['method', '方法与限制'],
        ] as Array<[AppendixTab, string]>).map(([key, label]) => (
          <button key={key} type="button" role="tab" aria-selected={tab === key} onClick={() => { setPage(1); setTab(key) }}>{label}</button>
        ))}
      </div>

      {tab !== 'method' && (
        <>
          {tab !== 'months' && (
            <div className="yearly-v2-appendix-filters">
              <div>{(['track', 'album', 'artist'] as EntityType[]).map((type) => <button key={type} type="button" aria-pressed={entity === type} onClick={() => { setPage(1); setEntity(type) }}>{ENTITY_LABELS[type]}</button>)}</div>
              {tab === 'play' && <div>{(['plays', 'hours'] as PlayMetric[]).map((value) => <button key={value} type="button" aria-pressed={metric === value} onClick={() => { setPage(1); setMetric(value) }}>{value === 'plays' ? '按播放次数' : '按有效时长'}</button>)}</div>}
            </div>
          )}
          <div className="yearly-v2-table-wrap">
            <table>
              <thead><tr><th>排名</th><th>{tab === 'months' ? '月份' : '名称'}</th><th>{tab === 'months' ? '月度冠军' : '艺人 / 类型'}</th><th>{tab === 'billboard' ? '年榜积分' : metric === 'hours' ? '有效时长' : '播放次数'}</th></tr></thead>
              <tbody>
                {visibleRows.map((row, index) => {
                  const absoluteIndex = (page - 1) * PAGE_SIZE + index
                  if (tab === 'months') {
                    const leaders = row.leaders && typeof row.leaders === 'object' ? row.leaders as Record<string, Record<string, unknown>> : {}
                    const leader = leaders.play_track ?? leaders.billboard_track
                    return <tr key={`month-${numberValue(row, 'month')}`}><td>{absoluteIndex + 1}</td><td>{numberValue(row, 'month')} 月</td><td>{leader ? (stringValue(leader, 'deep_link') ? <Link to={stringValue(leader, 'deep_link')}>{firstText(leader, ['name', 'track_name'])}</Link> : firstText(leader, ['name', 'track_name'])) : '—'}</td><td>{numberValue(row, 'plays').toLocaleString()} 次</td></tr>
                  }
                  return (
                    <tr key={`${tab}-${entity}-${absoluteIndex}-${firstText(row, ['name', 'track_name', 'album_name', 'artist_name'])}`}>
                      <td>{rankValue(row, absoluteIndex)}</td>
                      <td>{stringValue(row, 'deep_link') ? <Link to={stringValue(row, 'deep_link')}>{firstText(row, ['name', 'track_name', 'album_name', 'artist_name'])}</Link> : firstText(row, ['name', 'track_name', 'album_name', 'artist_name'])}</td>
                      <td>{firstText(row, ['artist_name', 'entity_type'])}</td>
                      <td>{tab === 'billboard' ? numberValue(row, 'year_end_score').toLocaleString(undefined, { maximumFractionDigits: 1 }) : metric === 'hours' ? `${numberValue(row, 'hours').toLocaleString(undefined, { maximumFractionDigits: 1 })} 小时` : `${numberValue(row, 'plays').toLocaleString()} 次`}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {visibleRows.length === 0 && <p className="yearly-v2-table-empty">该索引当前没有可展示条目。</p>}
          </div>
          <nav className="yearly-v2-pagination" aria-label="年度附录分页">
            <button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}><ChevronLeft aria-hidden="true" />上一页</button>
            <span>第 {page} / {totalPages} 页 · 共 {rows.length} 条</span>
            <button type="button" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>下一页<ChevronRight aria-hidden="true" /></button>
          </nav>
        </>
      )}

      {tab === 'method' && (
        <div className="yearly-v2-method-grid">
          <article><p>有效播放</p><h3>{report.filter_context.dynamic_threshold ? '按歌曲动态判断' : `${report.filter_context.min_ms / 1000} 秒固定阈值`}</h3><span>{report.methodology.metric_definitions['有效播放']}</span></article>
          <article><p>同期比较</p><h3>{report.coverage.comparison.comparable ? '同日起止窗口' : '本年不展示同比'}</h3><span>{report.methodology.comparison_periods.current_start ?? '—'} 至 {report.methodology.comparison_periods.current_end ?? '—'}<br />基线 {report.methodology.comparison_periods.baseline_start ?? '—'} 至 {report.methodology.comparison_periods.baseline_end ?? '—'}</span></article>
          <article className="is-wide"><p>实体口径</p><ul>{Object.entries(report.methodology.entity_grains).map(([label, value]) => <li key={label}><strong>{label}：</strong>{value}</li>)}</ul></article>
          <article className="is-wide"><p>方法说明</p><ul>{report.methodology.notes.map((note) => <li key={note}>{note}</li>)}</ul></article>
          <article className="is-wide"><p>覆盖与限制</p>{report.methodology.coverage_caveats.length > 0 ? <ul>{report.methodology.coverage_caveats.map((limit) => <li key={limit}>{limit}</li>)}</ul> : <span>当前未发现需要额外披露的覆盖限制。</span>}</article>
        </div>
      )}
    </section>
  )
}
