import { Fragment, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { Crown } from 'lucide-react'

import { ENTITY_COLORS } from '@/features/billboard/versus/versusData'
import type { VersusEntityData } from '@/types/billboard'
import { displayName, useChineseTextVersion } from '@/lib/chinese'

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

function entityStyle(index: number): CSSProperties {
  return { '--entity-color': ENTITY_COLORS[index % ENTITY_COLORS.length] } as CSSProperties
}

function splitEntityName(name: string) {
  const separatorIndex = name.indexOf(' — ')
  if (separatorIndex < 0) return { title: name, subtitle: null }
  return {
    title: name.slice(0, separatorIndex),
    subtitle: name.slice(separatorIndex + 3),
  }
}

function MetricRows({ metrics, entityCount }: { metrics: MobileVersusMetric[]; entityCount: number }) {
  return (
    <>
      {metrics.map((metric) => (
        <tr key={metric.label} className="mobile-versus-matrix-row">
          <th scope="row" className="mobile-versus-matrix-label">
            <span title={metric.description}>{metric.label}</span>
          </th>
          {Array.from({ length: entityCount }, (_, index) => {
            const isWinner = metric.winners.includes(index)
            return (
              <td
                key={index}
                className={`mobile-versus-matrix-value${isWinner ? ' winner' : ''}`}
                style={entityStyle(index)}
              >
                {metric.values[index] ?? '—'}
              </td>
            )
          })}
        </tr>
      ))}
    </>
  )
}

export function MobileVersusScoreboard({
  entities,
  detailLinks,
  groups,
  personalMetrics,
  wins,
  personalLoading,
}: MobileVersusScoreboardProps) {
  useChineseTextVersion()
  const maxWins = Math.max(...wins)
  const winnerIndices = wins.map((value, index) => value === maxWins ? index : -1).filter((index) => index >= 0)
  const winnerLabel = winnerIndices.length === 1 ? displayName(entities[winnerIndices[0]]?.name ?? '') : '并列胜出'
  const totalWinners = maxWins > 0 ? winnerIndices : []

  return (
    <section className="mobile-versus-scoreboard" aria-label="移动端对决结果">
      <header className="mobile-versus-winner">
        <Crown aria-hidden="true" />
        <div><p>对决结果</p><h2>{winnerLabel}</h2><span>{maxWins > 0 ? `在 ${maxWins} 项指标中胜出` : '当前数据暂无明确胜者'}</span></div>
      </header>

      <section className="mobile-versus-matrix-shell" aria-label="对决指标矩阵">
        <div className="mobile-versus-matrix-scroll">
          <table className="mobile-versus-matrix" aria-label="移动端对决指标矩阵">
            <thead>
              <tr>
                <th scope="col" className="mobile-versus-matrix-label mobile-versus-matrix-corner">指标</th>
                {entities.map((entity, index) => {
                  const split = splitEntityName(entity.name ?? '未命名实体')
                  const title = displayName(split.title)
                  const subtitle = split.subtitle ? displayName(split.subtitle) : null
                  return (
                    <th key={`${entity.name}:${index}`} scope="col" className="mobile-versus-matrix-entity" style={entityStyle(index)}>
                      <span className="mobile-versus-matrix-entity-index">对决 {String(index + 1).padStart(2, '0')}</span>
                      <div className="mobile-versus-matrix-entity-main">
                        {entity.cover_url && <img src={entity.cover_url} alt="" loading="lazy" />}
                        <div>
                          {detailLinks[index] ? <Link to={detailLinks[index] ?? '#'} title={title}>{title}</Link> : <strong title={title}>{title}</strong>}
                          {subtitle && <small>{subtitle}</small>}
                        </div>
                      </div>
                      <em>{wins[index]} 胜</em>
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody>
              {groups.map((group) => (
                <Fragment key={group.label}>
                  <tr key={`${group.label}-heading`} className="mobile-versus-matrix-group">
                    <th scope="colgroup" colSpan={entities.length + 1}>{group.label}</th>
                  </tr>
                  <MetricRows metrics={group.metrics} entityCount={entities.length} />
                </Fragment>
              ))}

              {(personalMetrics.length > 0 || personalLoading) && (
                <>
                  <tr className="mobile-versus-matrix-group">
                    <th scope="colgroup" colSpan={entities.length + 1}>个人播放</th>
                  </tr>
                  <MetricRows metrics={personalMetrics} entityCount={entities.length} />
                  {personalLoading && (
                    <tr>
                      <td colSpan={entities.length + 1} className="mobile-versus-matrix-loading">个人数据加载中...</td>
                    </tr>
                  )}
                </>
              )}

              <tr className="mobile-versus-matrix-group">
                <th scope="colgroup" colSpan={entities.length + 1}>总分</th>
              </tr>
              <MetricRows
                metrics={[{
                  label: '胜出次数',
                  values: wins.map(String),
                  winners: totalWinners,
                }]}
                entityCount={entities.length}
              />
            </tbody>
          </table>
        </div>
      </section>

    </section>
  )
}
