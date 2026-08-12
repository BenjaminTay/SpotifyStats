import { useEffect, useState } from 'react'
import { AlertTriangle, RotateCcw } from 'lucide-react'

export function YearlyReviewV2Loading({ year }: { year: number }) {
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    const startedAt = Date.now()
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - startedAt) / 1000)), 1000)
    return () => window.clearInterval(timer)
  }, [year])
  const message = elapsed < 8 ? '正在整理你的年度音乐故事' : elapsed < 30 ? '正在回顾这一年的冠军与高光' : '正在装订最后几页'

  return (
    <div className="yearly-v2-loading" role="status" aria-live="polite">
      <div className="yearly-v2-loading-disc" aria-hidden="true"><i /><b /></div>
      <p>ASSEMBLING ISSUE {String(year).slice(-2)}</p>
      <h2>{message}</h2>
      <span>第一次打开会多等一会儿，之后再回来就会快很多。</span>
      <small>已等待 {elapsed} 秒</small>
    </div>
  )
}

export function YearlyReviewV2Error({ message: _message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="yearly-v2-state-card is-error">
      <AlertTriangle aria-hidden="true" />
      <p>年度年鉴没有成功装订</p>
      <h2>报告加载失败</h2>
      <span>暂时没有加载成功，请稍后再试。</span>
      <button type="button" onClick={onRetry}><RotateCcw aria-hidden="true" />重新加载</button>
    </div>
  )
}

export function YearlyReviewV2Empty({ year }: { year: number }) {
  return (
    <div className="yearly-v2-state-card">
      <span aria-hidden="true" className="yearly-v2-empty-year">{year}</span>
      <p>YOUR NEXT MUSIC STORY</p>
      <h2>这一年还没有听歌记录</h2>
      <span>请选择另一个年份，或先导入该年度的 Spotify Extended Streaming History。</span>
    </div>
  )
}
