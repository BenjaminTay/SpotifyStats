import { ArrowUpRight, Clock3, Search, Trophy } from 'lucide-react'
import { Link } from 'react-router-dom'

import { MonthlyTrendChart } from '@/components/charts/MonthlyTrendChart'
import { PlatformDistChart } from '@/components/charts/PlatformDistChart'
import { MobileChartCard, MobilePageHeader } from '@/components/mobile'
import type { DashboardFullResponse } from '@/types/dashboard'

function formatNumber(value: number): string {
  return new Intl.NumberFormat('zh-CN').format(value)
}

function formatHours(value: number): string {
  return `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 0 }).format(value)}h`
}

interface MobileDashboardProps {
  data: DashboardFullResponse
  monthlyInsight: string
  peakHour: number
  peakHourText: string
}

const QUICK_LINKS = [
  { to: '/analysis/charts', label: '播放排行', detail: '看看最近最常听的音乐', icon: Trophy },
  { to: '/yearly-review', label: '年度总结', detail: '回到你的年度音乐故事', icon: Clock3 },
  { to: '/music/search', label: '音乐查找', detail: '搜索歌曲、专辑或艺人', icon: Search },
]

export function MobileDashboard({
  data,
  monthlyInsight,
  peakHour,
  peakHourText,
}: MobileDashboardProps) {
  const kpis = [
    { label: '播放次数', value: formatNumber(data.summary.total_plays), note: '有效播放' },
    { label: '播放时长', value: formatHours(data.summary.total_hours), note: '累计聆听' },
    { label: '独特歌曲', value: formatNumber(data.summary.total_tracks), note: '曲目覆盖' },
    { label: '覆盖艺人', value: formatNumber(data.summary.total_artists), note: '艺人范围' },
  ]

  return (
    <div className="mobile-m3-page" data-mobile-page="dashboard">
      <MobilePageHeader
        eyebrow="Listening / Overview"
        title="你的聆听概览"
        meta={<><span>完整播放历史</span><span>{formatNumber(data.summary.total_days)} 个数据日</span></>}
      />

      <section className="mobile-kpi-grid" aria-label="核心聆听数据">
        {kpis.map((kpi, index) => (
          <article key={kpi.label} className="mobile-kpi-tile">
            <span>{String(index + 1).padStart(2, '0')}</span>
            <p>{kpi.label}</p>
            <strong>{kpi.value}</strong>
            <small>{kpi.note}</small>
          </article>
        ))}
      </section>

      <MobileChartCard
        eyebrow="Monthly / Rhythm"
        title="月度播放趋势"
        description="按月查看播放次数与高低变化"
        chart={<MonthlyTrendChart data={data.monthly_trend} />}
        conclusion={monthlyInsight || undefined}
        interactionHint="点击数据点查看月份与播放次数"
      />

      <section className="mobile-dashboard-insights" aria-label="聆听习惯摘要">
        <article className="mobile-insight-card mobile-insight-card-peak">
          <p>一天中的聆听高峰</p>
          <strong>{String(peakHour).padStart(2, '0')}:00</strong>
          <span>{peakHourText}</span>
        </article>
        <article className="mobile-insight-card">
          <p>常用播放平台</p>
          <PlatformDistChart data={data.platform_dist} />
        </article>
      </section>

      <section className="mobile-quick-links" aria-labelledby="mobile-dashboard-next">
        <header>
          <p>Continue / Explore</p>
          <h2 id="mobile-dashboard-next">接下来想看什么</h2>
        </header>
        {QUICK_LINKS.map(({ to, label, detail, icon: Icon }) => (
          <Link key={to} to={to} className="mobile-quick-link">
            <span><Icon aria-hidden="true" /></span>
            <span className="min-w-0 flex-1"><strong>{label}</strong><small>{detail}</small></span>
            <ArrowUpRight aria-hidden="true" />
          </Link>
        ))}
      </section>
    </div>
  )
}
