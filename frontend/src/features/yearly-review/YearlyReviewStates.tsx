import { useEffect, useState } from 'react'
import { AlertTriangle, RotateCcw } from 'lucide-react'

export function YearlyReviewV2Loading({ year }: { year: number }) {
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    const startedAt = Date.now()
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - startedAt) / 1000)), 1000)
    return () => window.clearInterval(timer)
  }, [year])
  const message = elapsed < 8 ? '正在核对年度播放事实' : elapsed < 30 ? '正在计算个人 Billboard 赛季' : '正在整理纪录、品味迁移与完整索引'

  return (
    <div className="yearly-v2-loading" role="status" aria-live="polite">
      <div className="yearly-v2-loading-disc" aria-hidden="true"><i /><b /></div>
      <p>ASSEMBLING ISSUE {String(year).slice(-2)}</p>
      <h2>{message}</h2>
      <span>首次生成通常需要约 1 分钟；完成后同一统计口径会从缓存快速打开。</span>
      <small>已等待 {elapsed} 秒</small>
    </div>
  )
}

export function YearlyReviewV2Error({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="yearly-v2-state-card is-error">
      <AlertTriangle aria-hidden="true" />
      <p>年度年鉴没有成功装订</p>
      <h2>报告加载失败</h2>
      <span>{message}</span>
      <button type="button" onClick={onRetry}><RotateCcw aria-hidden="true" />重新生成</button>
    </div>
  )
}

export function YearlyReviewV2Empty({ year }: { year: number }) {
  return (
    <div className="yearly-v2-state-card">
      <span aria-hidden="true" className="yearly-v2-empty-year">{year}</span>
      <p>NO PLAYABLE ISSUE</p>
      <h2>这一年还没有足够的有效播放</h2>
      <span>请选择另一个年份，或先导入该年度的 Spotify Extended Streaming History。</span>
    </div>
  )
}
