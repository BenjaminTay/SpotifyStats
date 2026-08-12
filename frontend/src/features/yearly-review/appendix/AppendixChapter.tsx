import { useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

import { EntityMediaLink, SectionHeading } from '@/features/yearly-review/YearlyReviewPrimitives'
import { ENTITY_LABELS, numberValue, stringValue } from '@/features/yearly-review/yearlyReviewData'
import type { YearlyEntityRef, YearlyReviewResponse } from '@/types/yearly-review-v2'

type AppendixTab = 'play' | 'billboard'
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

function rowEntity(row: Record<string, unknown>, entity: EntityType): YearlyEntityRef {
  const name = firstText(row, ['name', 'track_name', 'album_name', 'artist_name'])
  return {
    entity_type: entity,
    entity_id: (row[entity === 'track' ? 'track_id' : entity === 'album' ? 'album_project_id' : 'artist_id'] as string | number | null | undefined) ?? null,
    name,
    artist_name: entity === 'artist' ? null : stringValue(row, 'artist_name') || null,
    cover_url: stringValue(row, 'cover_url') || null,
    deep_link: stringValue(row, 'deep_link') || null,
  }
}

export function AppendixChapter({ report }: { report: YearlyReviewResponse }) {
  const [tab, setTab] = useState<AppendixTab>('play')
  const [entity, setEntity] = useState<EntityType>('track')
  const [metric, setMetric] = useState<PlayMetric>('plays')
  const [page, setPage] = useState(1)

  const rows = useMemo(() => {
    if (tab === 'play') return report.appendix.play_charts[`${entity}_by_${metric}`] ?? []
    if (tab === 'billboard') return report.appendix.billboard_charts[entity] ?? []
    return []
  }, [entity, metric, report.appendix, tab])
  const totalPages = Math.max(Math.ceil(rows.length / PAGE_SIZE), 1)
  const visibleRows = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  return (
    <section className="yearly-v2-section yearly-v2-appendix" id="yearly-v2-appendix">
      <SectionHeading number="08" eyebrow="THE FULL LISTS" title="完整榜单" />
      <div className="yearly-v2-appendix-tabs" role="tablist" aria-label="切换年度附录">
        {([
          ['play', '播放榜'],
          ['billboard', '个人 Billboard'],
        ] as Array<[AppendixTab, string]>).map(([key, label]) => (
          <button key={key} type="button" role="tab" aria-selected={tab === key} onClick={() => { setPage(1); setTab(key) }}>{label}</button>
        ))}
      </div>

      <>
        <div className="yearly-v2-appendix-filters">
              <div>{(['track', 'album', 'artist'] as EntityType[]).map((type) => <button key={type} type="button" aria-pressed={entity === type} onClick={() => { setPage(1); setEntity(type) }}>{ENTITY_LABELS[type]}</button>)}</div>
          {tab === 'play' && <div>{(['plays', 'hours'] as PlayMetric[]).map((value) => <button key={value} type="button" aria-pressed={metric === value} onClick={() => { setPage(1); setMetric(value) }}>{value === 'plays' ? '按播放次数' : '按播放时长'}</button>)}</div>}
            </div>
          <div className="yearly-v2-table-wrap">
            <table>
              <thead><tr><th>排名</th><th>歌曲 / 专辑 / 艺人</th><th>{tab === 'billboard' ? '年度积分' : metric === 'hours' ? '播放时长' : '播放次数'}</th></tr></thead>
              <tbody>
                {visibleRows.map((row, index) => {
                  const absoluteIndex = (page - 1) * PAGE_SIZE + index
                  return (
                    <tr key={`${tab}-${entity}-${absoluteIndex}-${firstText(row, ['name', 'track_name', 'album_name', 'artist_name'])}`}>
                      <td>{rankValue(row, absoluteIndex)}</td>
                      <td><EntityMediaLink entity={rowEntity(row, entity)} /></td>
                      <td>{tab === 'billboard' ? numberValue(row, 'year_end_score').toLocaleString(undefined, { maximumFractionDigits: 1 }) : metric === 'hours' ? `${numberValue(row, 'hours').toLocaleString(undefined, { maximumFractionDigits: 1 })} 小时` : `${numberValue(row, 'plays').toLocaleString()} 次`}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {visibleRows.length === 0 && <p className="yearly-v2-table-empty">这里还没有榜单记录。</p>}
          </div>
          <nav className="yearly-v2-pagination" aria-label="年度附录分页">
            <button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}><ChevronLeft aria-hidden="true" />上一页</button>
            <span>第 {page} / {totalPages} 页 · 共 {rows.length} 条</span>
            <button type="button" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>下一页<ChevronRight aria-hidden="true" /></button>
          </nav>
      </>
    </section>
  )
}
