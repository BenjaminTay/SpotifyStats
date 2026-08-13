import { AlertCircle, ArrowRight, BarChart3, CalendarRange, Trophy } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useRuntimeCapabilities } from '@/hooks/useRuntimeCapabilities'

export function HomeLoading({ phone = false }: { phone?: boolean }) {
  return (
    <div className={phone ? 'home-phone-loading' : 'home-desktop-loading'} role="status" aria-label="正在加载个人音乐首页">
      <div className="home-loading-hero">
        <div><span /><strong /><span /></div>
        <i />
      </div>
      <div className="home-loading-passport">{Array.from({ length: 4 }).map((_, index) => <span key={index} />)}</div>
      <div className="home-loading-section" />
    </div>
  )
}

export function HomeError({ phone = false, onRetry }: { phone?: boolean; onRetry: () => void }) {
  return (
    <section className={phone ? 'home-state home-state-phone' : 'home-state'}>
      <AlertCircle aria-hidden="true" />
      <p>Personal music archive</p>
      <h1>音乐头版暂时无法打开</h1>
      <span>个人播放数据没有丢失，可以稍后再试或直接进入其他页面。</span>
      <div><button type="button" onClick={onRetry}>重新加载</button><Link to="/analysis/stats">进入播放分析</Link></div>
    </section>
  )
}

const FEATURES = [
  { icon: BarChart3, label: '播放分析', note: '看见时间、节奏与偏好如何变化' },
  { icon: Trophy, label: '个人 Billboard', note: '用自己的播放记录生成周榜与总榜' },
  { icon: CalendarRange, label: '年度音乐年鉴', note: '把一整年的声音整理成八章故事' },
]

export function HomeEmpty({ phone = false }: { phone?: boolean }) {
  const { capabilities } = useRuntimeCapabilities()
  return (
    <section className={phone ? 'home-empty home-empty-phone' : 'home-empty'}>
      <header>
        <p>Your personal music archive</p>
        <h1>把 Spotify 历史<br />变成你的音乐档案</h1>
        <span>导入官方 Extended Streaming History，SpotifyStats 会从真实播放记录中重建你的音乐生活。</span>
        {capabilities.imports && (
          <Link to="/settings#data-import">导入 Spotify 数据 <ArrowRight aria-hidden="true" /></Link>
        )}
      </header>
      <div className="home-empty-features">
        {FEATURES.map(({ icon: Icon, label, note }, index) => (
          <article key={label}>
            <span>0{index + 1}</span>
            <Icon aria-hidden="true" />
            <h2>{label}</h2>
            <p>{note}</p>
          </article>
        ))}
      </div>
      <small>你的播放记录只保存在自己的数据库中；首页不会用虚构示例代替真实数据。</small>
    </section>
  )
}
