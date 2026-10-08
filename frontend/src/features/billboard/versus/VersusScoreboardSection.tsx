import { Fragment } from 'react'
import { Link } from 'react-router-dom'
import { coverThumbnailUrl } from '@/lib/cover-thumbnail'
import { GlassCard } from '@/components/shared/GlassCard'
import type { VersusEntityData, EntityListItem } from '@/types/billboard'
import { ENTITY_COLORS, type VersusKind } from './versusData'
import { useViewportMode } from '@/hooks/useViewportMode'
import { MobileVersusScoreboard } from '@/features/mobile/billboard/MobileVersusScoreboard'
import { displayName, useChineseTextVersion } from '@/lib/chinese'
import { buildScoreboard } from './versusScoreboardData'
import type { VersusPersonalState } from './useVersusPersonal'
import { VersusPersonalStatus } from './VersusPersonalStatus'

interface VersusScoreboardSectionProps {
  entities: VersusEntityData[] | null
  kind: VersusKind
  queue: EntityListItem[]
  buildDetailLink: (item: EntityListItem) => string | null
  chartUnavailable?: boolean
  personal: VersusPersonalState
}

export function VersusScoreboardSection({ entities: charts, kind, queue, buildDetailLink, personal, chartUnavailable }: VersusScoreboardSectionProps) {
  useChineseTextVersion()
  const isPhone = useViewportMode() === 'phone'
  const { entities, groups, personalRows, wins, scoreComplete } = buildScoreboard(kind, queue, charts, personal, chartUnavailable)
  const detailLinks = queue.map(buildDetailLink)
  const statuses = <VersusPersonalStatus personal={personal} />
  if (isPhone) return <div>
    {statuses}
    <MobileVersusScoreboard entities={entities} detailLinks={detailLinks} groups={groups}
      personalMetrics={personalRows} wins={wins} scoreComplete={scoreComplete}
      personalLoading={personal.stats.isLoading || personal.ranks.isLoading} />
  </div>
  const sections = [...groups, { label: '个人播放', metrics: personalRows }, {
    label: scoreComplete ? '总分 (胜出指标数)' : '已完成指标得分',
    metrics: [{ label: '胜出次数', values: wins.map(String), winners: scoreComplete && Math.max(...wins) > 0 ? wins.flatMap((win, index) => win === Math.max(...wins) ? [index] : []) : [] }],
  }]
  return <div>
    <h3 className="mb-4 font-serif text-xl font-semibold">对决记分牌</h3>
    {statuses}
    <GlassCard className="overflow-x-auto p-0">
      <table className="w-full min-w-[300px] border-collapse" aria-label="对决指标矩阵">
        <thead><tr className="border-b border-border">
          <th scope="col" className="sticky left-0 w-[140px] bg-card py-2.5 pl-4 text-left text-[10px] font-bold text-muted-foreground">指标</th>
          {entities.map((entity, index) => {
            const [title, subtitle] = (entity.name ?? '').split(' — ')
            const renderedTitle = displayName(title)
            return <th scope="col" key={index} className="py-3 pr-4 text-center align-top" style={{ color: ENTITY_COLORS[index] }}>
              {entity.cover_url && <img src={coverThumbnailUrl(entity.cover_url)} alt="" loading="lazy" className="mx-auto mb-1.5 h-10 w-10 rounded-lg object-cover" />}
              {detailLinks[index] ? <Link to={detailLinks[index]!} className="block truncate font-serif text-[13px] font-semibold hover:underline" title={renderedTitle}>{renderedTitle}</Link>
                : <span className="block truncate font-serif text-[13px] font-semibold" title={renderedTitle}>{renderedTitle}</span>}
              {subtitle && <span className="mt-0.5 block font-sans text-[12px] italic">{displayName(subtitle)}</span>}
            </th>
          })}
        </tr></thead>
        <tbody>{sections.map((section) => <Fragment key={section.label}>
          <tr><th scope="colgroup" colSpan={queue.length + 1} className="border-b border-border bg-accent/12 py-2 pl-4 text-left text-[11px] font-bold tracking-[1.4px] text-accent-foreground">{section.label}</th></tr>
          {section.metrics.map((metric) => <tr key={metric.label} className="border-b border-border/40 hover:bg-muted/30">
            <th scope="row" className="sticky left-0 w-[140px] bg-card py-2.5 pl-4 text-left text-[13px] font-normal text-muted-foreground"><span title={'description' in metric ? metric.description : undefined}>{metric.label}</span></th>
            {metric.values.map((value, index) => <td key={index} className="py-2.5 pr-4 text-right text-[14px] font-semibold tabular-nums"
              style={metric.winners.includes(index) ? { color: ENTITY_COLORS[index], backgroundColor: `${ENTITY_COLORS[index]}14` } : undefined}>{value}</td>)}
          </tr>)}
        </Fragment>)}</tbody>
      </table>
    </GlassCard>
  </div>
}
