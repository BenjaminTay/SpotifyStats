import { ArrowRight, Disc3, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'

import { displayName } from '@/lib/chinese'
import type { HomeChartChampion, HomeEntityMetric, HomeOverviewResponse } from '@/types/home'
import {
  HomeChange,
  HomeEntityArtwork,
  HomeEntityLink,
  HomeSectionHeading,
  HomeTrend,
} from './HomePrimitives'
import { formatHomeDate, formatHomeHours, formatHomeNumber, homeRecentAnalysisRoute } from './home-format'

function ArchivePassport({ data }: { data: HomeOverviewResponse }) {
  const archiveItems = [
    { label: '记录跨度', value: (data.coverage.first_source_date ?? data.coverage.first_play_date) ? `${(data.coverage.first_source_date ?? data.coverage.first_play_date)?.slice(0, 4)}—${(data.coverage.source_latest_date ?? data.coverage.latest_play_date)?.slice(0, 4)}` : '—' },
    { label: '有效播放', value: formatHomeNumber(data.archive.total_plays) },
    { label: '播放时长', value: `${formatHomeHours(data.archive.total_hours)}h` },
    { label: '不同歌曲', value: formatHomeNumber(data.archive.unique_tracks) },
  ]
  return (
    <dl className="home-archive-passport" aria-label="个人音乐档案">
      {archiveItems.map((item) => (
        <div key={item.label}>
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  )
}

function HeroCollage({ data }: { data: HomeOverviewResponse }) {
  const sideEntities = [data.recent?.leaders.album?.entity, data.recent?.leaders.artist?.entity]
    .filter((entity): entity is NonNullable<typeof entity> => Boolean(entity))
  return (
    <div className="home-hero-collage" aria-hidden="true">
      <div className="home-hero-orbit home-hero-orbit-one" />
      <div className="home-hero-orbit home-hero-orbit-two" />
      <HomeEntityArtwork entity={data.headline.entity} eager className="home-hero-cover-main" />
      {sideEntities[0] && <HomeEntityArtwork entity={sideEntities[0]} className="home-hero-cover-side home-hero-cover-side-one" />}
      {sideEntities[1] && <HomeEntityArtwork entity={sideEntities[1]} className="home-hero-cover-side home-hero-cover-side-two" />}
      <span className="home-hero-collage-caption">Your listening archive</span>
    </div>
  )
}

function RecentLeader({ kind, metric }: { kind: string; metric: HomeEntityMetric | null }) {
  if (!metric) return null
  const entity = metric.entity
  return (
    <HomeEntityLink entity={entity} className="home-recent-leader">
      <HomeEntityArtwork entity={entity} />
      <span className="home-recent-leader-copy">
        <small>{kind}</small>
        <strong>{displayName(entity.name)}</strong>
        <span>{displayName(entity.artist_name ?? '')}</span>
      </span>
      <span className="home-recent-leader-metric">{formatHomeNumber(metric.plays)}<small>次</small></span>
    </HomeEntityLink>
  )
}

function RecentChapter({ data }: { data: HomeOverviewResponse }) {
  const recent = data.recent
  if (!recent?.period) return null
  const analysisRoute = homeRecentAnalysisRoute(recent.period)
  return (
    <section className="home-section home-recent-section">
      <HomeSectionHeading
        number="01"
        eyebrow="The latest chapter"
        title="最近一章"
        aside={<span>截至 {formatHomeDate(recent.period.end_date)} 的最近 4 周</span>}
      />
      <div className="home-recent-layout">
        <div className="home-recent-story">
          <div className="home-recent-stats">
            <div>
              <span>有效播放</span>
              <strong>{formatHomeNumber(recent.summary.plays)}</strong>
              <HomeChange value={recent.comparison_available ? recent.summary.plays_delta_pct : null} />
            </div>
            <div>
              <span>播放时长</span>
              <strong>{formatHomeHours(recent.summary.hours)}<small> 小时</small></strong>
              <HomeChange value={recent.comparison_available ? recent.summary.hours_delta_pct : null} />
            </div>
          </div>
          <HomeTrend points={recent.trend} />
          <div className="home-rhythm-facts">
            <span>深夜聆听 <strong>{recent.summary.late_night_pct.toFixed(0)}%</strong></span>
            <span>周末聆听 <strong>{recent.summary.weekend_pct.toFixed(0)}%</strong></span>
            <span>活跃 <strong>{recent.summary.active_days} 天</strong></span>
          </div>
        </div>
        <div className="home-recent-leaders">
          <RecentLeader kind="近期歌曲" metric={recent.leaders.track} />
          <RecentLeader kind="近期专辑" metric={recent.leaders.album} />
          <RecentLeader kind="近期艺人" metric={recent.leaders.artist} />
          <Link to={analysisRoute} className="home-inline-link">打开完整播放分析 <ArrowRight aria-hidden="true" /></Link>
        </div>
      </div>
    </section>
  )
}

function movementLabel(champion: HomeChartChampion): string {
  if (champion.previous_rank === null) return '新入榜'
  if (!champion.rank_change) return '排名持平'
  return champion.rank_change > 0 ? `↑ ${champion.rank_change}` : `↓ ${Math.abs(champion.rank_change)}`
}

function ChartChampion({ label, champion }: { label: string; champion: HomeChartChampion | null }) {
  if (!champion) return <div className="home-chart-champion is-empty"><span>{label}</span><p>暂无可用榜单</p></div>
  return (
    <HomeEntityLink entity={champion.entity} className="home-chart-champion">
      <div className="home-chart-rank"><small>{label}</small><strong>01</strong></div>
      <HomeEntityArtwork entity={champion.entity} />
      <div className="home-chart-copy">
        <strong>{displayName(champion.entity.name)}</strong>
        <span>{displayName(champion.entity.artist_name ?? '')}</span>
        <small>{movementLabel(champion)} · {formatHomeNumber(champion.plays)} 次播放</small>
      </div>
      <ArrowRight className="home-chart-arrow" aria-hidden="true" />
    </HomeEntityLink>
  )
}

function BillboardSpotlight({ data }: { data: HomeOverviewResponse }) {
  return (
    <section className="home-section">
      <HomeSectionHeading
        number="02"
        eyebrow="Personal Billboard"
        title="最新个人 Billboard"
        aside={data.billboard.week ? <span>榜单周 {formatHomeDate(data.billboard.week)}</span> : undefined}
      />
      {data.billboard.state === 'ready' ? (
        <div className="home-chart-grid">
          <ChartChampion label="单曲冠军" champion={data.billboard.track} />
          <ChartChampion label="专辑冠军" champion={data.billboard.album} />
          <ChartChampion label="艺人冠军" champion={data.billboard.artist} />
        </div>
      ) : (
        <div className="home-module-unavailable">当前统计口径下还没有可用榜单。</div>
      )}
      <Link to="/billboard" className="home-inline-link home-section-link">进入完整榜单 <ArrowRight aria-hidden="true" /></Link>
    </section>
  )
}

function LongMemory({ data }: { data: HomeOverviewResponse }) {
  const yearly = data.yearly_review
  const rediscovery = data.rediscovery
  return (
    <section className="home-section">
      <HomeSectionHeading number="03" eyebrow="Long memory" title="长期记忆" />
      <div className="home-memory-grid">
        <Link to="/yearly-review" className="home-yearly-preview">
          <div className="home-yearly-copy">
            <span>{yearly.year ?? '年度'}</span>
            <p>年度音乐年鉴</p>
            <h3>{displayName(yearly.headline ?? (yearly.state === 'ready' ? '这一年的声音与轨迹' : '打开属于你的年度档案'))}</h3>
            <small>{displayName(yearly.statement ?? '完整八章，重读这一年的音乐生活。')}</small>
            <strong>翻开年鉴 <ArrowRight aria-hidden="true" /></strong>
          </div>
          <HomeEntityArtwork entity={yearly.entity} />
        </Link>
        {rediscovery ? (
          <HomeEntityLink entity={rediscovery.entity} className="home-rediscovery">
            <div className="home-rediscovery-label"><Sparkles aria-hidden="true" /> 从记忆中重逢</div>
            <HomeEntityArtwork entity={rediscovery.entity} />
            <div>
              <h3>{displayName(rediscovery.entity.name)}</h3>
              <p>{displayName(rediscovery.entity.artist_name ?? '')}</p>
              <small>上次播放于 {formatHomeDate(rediscovery.last_played)} · 历史播放 {formatHomeNumber(rediscovery.total_plays)} 次</small>
            </div>
            <ArrowRight aria-hidden="true" />
          </HomeEntityLink>
        ) : (
          <div className="home-rediscovery is-empty"><Disc3 aria-hidden="true" /><p>继续聆听，未来会在这里遇见一首久违的歌。</p></div>
        )}
      </div>
    </section>
  )
}

export function HomeDesktopExperience({ data }: { data: HomeOverviewResponse }) {
  const recentAnalysisRoute = homeRecentAnalysisRoute(data.recent?.period)
  return (
    <div className="home-experience home-desktop-experience" data-home-presentation="desktop">
      <section className="home-hero">
        <div className="home-hero-copy">
          <span className="home-hero-kicker">Your listening headline</span>
          <h1>{displayName(data.headline.title)}</h1>
          <p>{displayName(data.headline.statement)}</p>
          <div className="home-hero-actions">
            <Link to={recentAnalysisRoute}>查看最近播放 <ArrowRight aria-hidden="true" /></Link>
            {data.headline.entity?.deep_link && <Link to={data.headline.entity.deep_link} className="is-secondary">打开音乐详情</Link>}
          </div>
        </div>
        <HeroCollage data={data} />
      </section>

      <ArchivePassport data={data} />
      {data.state === 'limited' && (
        <div className="home-limited-note">目前记录范围较短，首页先呈现可确认的绝对数据；积累更多记录后将补充同期变化。</div>
      )}
      <RecentChapter data={data} />
      <BillboardSpotlight data={data} />
      <LongMemory data={data} />
    </div>
  )
}
