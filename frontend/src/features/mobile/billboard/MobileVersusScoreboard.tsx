import { Link } from 'react-router-dom'
import { Crown } from 'lucide-react'

import { ENTITY_COLORS } from '@/features/billboard/versus/versusData'
import type { VersusEntityData } from '@/types/billboard'

export interface MobileVersusMetric {
  label: string
  description?: string
  values: string[]
  winners: number[]
}

export interface MobileVersusMetricGroup {
  label: string
  metrics: MobileVersusMetric[]
}

interface MobileVersusScoreboardProps {
  entities: VersusEntityData[]
  detailLinks: (string | null)[]
  groups: MobileVersusMetricGroup[]
  personalMetrics: MobileVersusMetric[]
  wins: number[]
  personalLoading: boolean
}

export function MobileVersusScoreboard({
  entities,
  detailLinks,
  groups,
  personalMetrics,
  wins,
  personalLoading,
}: MobileVersusScoreboardProps) {
  const maxWins = Math.max(...wins)
  const winnerIndices = wins.map((value, index) => value === maxWins ? index : -1).filter((index) => index >= 0)
  const winnerLabel = winnerIndices.length === 1 ? entities[winnerIndices[0]]?.name : '并列胜出'

  return (
    <section className="mobile-versus-scoreboard">
      <header className="mobile-versus-winner">
        <Crown aria-hidden="true" />
        <div><p>对决结果</p><h2>{winnerLabel}</h2><span>{maxWins > 0 ? `在 ${maxWins} 项指标中胜出` : '当前数据暂无明确胜者'}</span></div>
      </header>

      <div className="mobile-versus-entity-cards">
        {entities.map((entity, entityIndex) => (
          <article key={`${entity.name}:${entityIndex}`} style={{ '--entity-color': ENTITY_COLORS[entityIndex % ENTITY_COLORS.length] } as React.CSSProperties}>
            <header>
              {entity.cover_url && <img src={entity.cover_url} alt="" loading="lazy" />}
              <div>
                <span>对决 {String(entityIndex + 1).padStart(2, '0')}</span>
                {detailLinks[entityIndex] ? <Link to={detailLinks[entityIndex] ?? '#'}>{entity.name}</Link> : <strong>{entity.name}</strong>}
              </div>
              <em>{wins[entityIndex]} 胜</em>
            </header>

            {groups.map((group) => (
              <details key={group.label} open={group.label === '榜单成绩'}>
                <summary>{group.label}<span>{group.metrics.length} 项</span></summary>
                <dl>
                  {group.metrics.map((metric) => (
                    <div key={metric.label} className={metric.winners.includes(entityIndex) ? 'winner' : undefined} title={metric.description}>
                      <dt>{metric.label}</dt><dd>{metric.values[entityIndex] ?? '—'}</dd>
                    </div>
                  ))}
                </dl>
              </details>
            ))}

            {(personalMetrics.length > 0 || personalLoading) && (
              <details>
                <summary>个人播放<span>{personalLoading ? '加载中' : `${personalMetrics.length} 项`}</span></summary>
                <dl>
                  {personalMetrics.map((metric) => (
                    <div key={metric.label} className={metric.winners.includes(entityIndex) ? 'winner' : undefined}>
                      <dt>{metric.label}</dt><dd>{metric.values[entityIndex] ?? '—'}</dd>
                    </div>
                  ))}
                </dl>
              </details>
            )}
          </article>
        ))}
      </div>
    </section>
  )
}
