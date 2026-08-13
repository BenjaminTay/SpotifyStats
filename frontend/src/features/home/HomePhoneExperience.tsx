import { ArrowRight, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'

import { displayName } from '@/lib/chinese'
import type { HomeChartChampion, HomeEntityMetric, HomeOverviewResponse } from '@/types/home'
import {
  HomeChange,
  HomeEntityArtwork,
  HomeEntityLink,
  HomeTrend,
} from './HomePrimitives'
import { formatHomeDate, formatHomeHours, formatHomeNumber, homeRecentAnalysisRoute } from './home-format'

function PhoneEntityLeader({ label, metric }: { label: string; metric: HomeEntityMetric | null }) {
  if (!metric) return null
  return (
    <HomeEntityLink entity={metric.entity} className="home-phone-entity-row">
      <HomeEntityArtwork entity={metric.entity} />
      <span><small>{label}</small><strong>{displayName(metric.entity.name)}</strong><em>{displayName(metric.entity.artist_name ?? '')}</em></span>
      <b>{formatHomeNumber(metric.plays)}<small>次</small></b>
    </HomeEntityLink>
  )
}

function phoneMovement(champion: HomeChartChampion): string {
  if (champion.previous_rank === null) return 'NEW'
  if (!champion.rank_change) return '—'
  return champion.rank_change > 0 ? `↑${champion.rank_change}` : `↓${Math.abs(champion.rank_change)}`
}

function PhoneChartChampion({ label, champion }: { label: string; champion: HomeChartChampion | null }) {
  if (!champion) return null
  return (
    <HomeEntityLink entity={champion.entity} className="home-phone-chart-row">
      <span className="home-phone-chart-no">01</span>
      <HomeEntityArtwork entity={champion.entity} />
      <span><small>{label}</small><strong>{displayName(champion.entity.name)}</strong><em>{displayName(champion.entity.artist_name ?? '')}</em></span>
      <b>{phoneMovement(champion)}</b>
    </HomeEntityLink>
  )
}

function PhoneSection({ index, eyebrow, title, children }: { index: string; eyebrow: string; title: string; children: React.ReactNode }) {
  return (
    <section className="home-phone-section">
      <header><span>{index}</span><div><p>{eyebrow}</p><h2>{title}</h2></div></header>
      {children}
    </section>
  )
}

export function HomePhoneExperience({ data }: { data: HomeOverviewResponse }) {
  const recent = data.recent
  const recentAnalysisRoute = homeRecentAnalysisRoute(recent?.period)
  return (
    <div className="home-experience home-phone-experience" data-home-presentation="phone">
      <section className="home-phone-hero">
        <div className="home-phone-hero-art">
          <div className="home-phone-record" aria-hidden="true" />
          <HomeEntityArtwork entity={data.headline.entity} eager />
        </div>
        <span>Your listening headline</span>
        <h1>{displayName(data.headline.title)}</h1>
        <p>{displayName(data.headline.statement)}</p>
        <div className="home-phone-hero-actions">
          <Link to={recentAnalysisRoute}>查看最近播放 <ArrowRight aria-hidden="true" /></Link>
          {data.headline.entity?.deep_link && (
            <Link to={data.headline.entity.deep_link} className="is-secondary">音乐详情</Link>
          )}
        </div>
      </section>

      <dl className="home-phone-passport">
        <div><dt>有效播放</dt><dd>{formatHomeNumber(data.archive.total_plays)}</dd></div>
        <div><dt>播放时长</dt><dd>{formatHomeHours(data.archive.total_hours)}h</dd></div>
        <div><dt>不同歌曲</dt><dd>{formatHomeNumber(data.archive.unique_tracks)}</dd></div>
        <div><dt>记录跨度</dt><dd>{(data.coverage.first_source_date ?? data.coverage.first_play_date)?.slice(0, 4) ?? '—'}—{(data.coverage.source_latest_date ?? data.coverage.latest_play_date)?.slice(0, 4) ?? '—'}</dd></div>
      </dl>

      {data.state === 'limited' && <div className="home-phone-limited">记录仍在积累，暂不展示无法确认的同期变化。</div>}

      {recent?.period && (
        <PhoneSection index="01" eyebrow="The latest chapter" title="最近一章">
          <div className="home-phone-recent-summary">
            <div><span>最近 4 周</span><strong>{formatHomeNumber(recent.summary.plays)} 次</strong><HomeChange value={recent.comparison_available ? recent.summary.plays_delta_pct : null} /></div>
            <div><span>播放时长</span><strong>{formatHomeHours(recent.summary.hours)} 小时</strong><HomeChange value={recent.comparison_available ? recent.summary.hours_delta_pct : null} /></div>
          </div>
          <HomeTrend points={recent.trend} />
          <div className="home-phone-rhythm"><span>深夜 {recent.summary.late_night_pct.toFixed(0)}%</span><span>周末 {recent.summary.weekend_pct.toFixed(0)}%</span><span>活跃 {recent.summary.active_days} 天</span></div>
          <div className="home-phone-entity-list">
            <PhoneEntityLeader label="近期歌曲" metric={recent.leaders.track} />
            <PhoneEntityLeader label="近期专辑" metric={recent.leaders.album} />
            <PhoneEntityLeader label="近期艺人" metric={recent.leaders.artist} />
          </div>
          <Link to={recentAnalysisRoute} className="home-phone-more">完整播放分析 <ArrowRight aria-hidden="true" /></Link>
        </PhoneSection>
      )}

      <PhoneSection index="02" eyebrow="Personal Billboard" title="最新个人 Billboard">
        {data.billboard.week && <p className="home-phone-week">榜单周 {formatHomeDate(data.billboard.week)}</p>}
        {data.billboard.state === 'ready' ? (
          <div className="home-phone-chart-list">
            <PhoneChartChampion label="单曲冠军" champion={data.billboard.track} />
            <PhoneChartChampion label="专辑冠军" champion={data.billboard.album} />
            <PhoneChartChampion label="艺人冠军" champion={data.billboard.artist} />
          </div>
        ) : <p className="home-module-unavailable">当前还没有可用榜单。</p>}
        <Link to="/billboard" className="home-phone-more">进入完整榜单 <ArrowRight aria-hidden="true" /></Link>
      </PhoneSection>

      <PhoneSection index="03" eyebrow="Long memory" title="长期记忆">
        <Link to="/yearly-review" className="home-phone-yearly">
          <span>{data.yearly_review.year ?? 'YEAR'}</span>
          <div><small>年度音乐年鉴</small><h3>{displayName(data.yearly_review.headline ?? '打开属于你的年度档案')}</h3><p>{displayName(data.yearly_review.statement ?? '完整八章，重读这一年的音乐生活。')}</p></div>
          <HomeEntityArtwork entity={data.yearly_review.entity} />
          <ArrowRight aria-hidden="true" />
        </Link>
        {data.rediscovery && (
          <HomeEntityLink entity={data.rediscovery.entity} className="home-phone-rediscovery">
            <div><Sparkles aria-hidden="true" /><span>从记忆中重逢</span></div>
            <HomeEntityArtwork entity={data.rediscovery.entity} />
            <span><strong>{displayName(data.rediscovery.entity.name)}</strong><small>{displayName(data.rediscovery.entity.artist_name ?? '')}</small><em>{data.rediscovery.days_since_last_play} 天未播放</em></span>
            <ArrowRight aria-hidden="true" />
          </HomeEntityLink>
        )}
      </PhoneSection>

    </div>
  )
}
