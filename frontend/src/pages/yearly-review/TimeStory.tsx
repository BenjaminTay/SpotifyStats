import { useState, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { GlassCard } from '@/components/shared/GlassCard'
import type { TimeStory as TimeStoryType } from '@/types/yearly-review'
import { HourClock } from './HourClock'

interface TimeStoryProps {
  timeStory: TimeStoryType
}

const MONTH_NAMES = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']

function MiniCover({ url, name }: { url: string; name: string }) {
  return url ? (
    <img src={url} alt={name} className="w-10 h-10 object-cover rounded-md flex-shrink-0" loading="lazy" />
  ) : (
    <div className="w-10 h-10 bg-muted rounded-md flex items-center justify-center flex-shrink-0">
      <svg className="w-4 h-4 text-muted-foreground/40" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2z" /></svg>
    </div>
  )
}

function ListeningWaveform({ dailyGrid }: { dailyGrid: number[][] }) {
  const values: number[] = dailyGrid.flat()
  const maxValue = Math.max(...values, 1)

  // 7-day moving average
  const ma: number[] = []
  for (let i = 0; i < values.length; i++) {
    const start = Math.max(0, i - 3)
    const end = Math.min(values.length, i + 4)
    let sum = 0
    for (let j = start; j < end; j++) sum += values[j]
    ma.push(sum / (end - start))
  }

  const N = values.length
  const H = 130, CX = 0, CY = H / 2, MAX_AMP = 52

  // Build symmetrical waveform path
  const topPts: string[] = []
  const botPts: string[] = []
  for (let i = 0; i < N; i++) {
    const x = i
    const amp = (values[i] / maxValue) * MAX_AMP
    topPts.push(`${x},${(CY - amp).toFixed(1)}`)
    botPts.push(`${x},${(CY + amp).toFixed(1)}`)
  }

  const areaD = [
    `M ${CX},${CY}`,
    ...topPts.map(p => `L ${p}`),
    `L ${N - 1},${CY}`,
    ...botPts.reverse().map(p => `L ${p}`),
    'Z',
  ].join(' ')

  // Moving average envelope (top half only)
  const maPts = ma.map((v, i) => {
    const amp = (v / maxValue) * MAX_AMP
    return `${i},${(CY - amp).toFixed(1)}`
  })
  const maD = maPts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p}`).join(' ')

  // Month dividers and labels
  const months: { x: number; label: string; midX: number }[] = []
  let offset = 0
  for (let m = 0; m < 12; m++) {
    const days = dailyGrid[m].length
    months.push({ x: offset, label: MONTH_NAMES[m], midX: offset + days / 2 })
    offset += days
  }

  // Tooltip
  const [tooltip, setTooltip] = useState<{ x: number; y: number; month: number; day: number; count: number } | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    const svg = svgRef.current
    if (!svg) return
    const rect = svg.getBoundingClientRect()
    const scaleX = N / rect.width
    const dayIdx = Math.floor((e.clientX - rect.left) * scaleX)
    if (dayIdx < 0 || dayIdx >= N) { setTooltip(null); return }

    // Find which month/day this index belongs to
    let remaining = dayIdx
    let month = 0
    for (let m = 0; m < 12; m++) {
      if (remaining < dailyGrid[m].length) { month = m; break }
      remaining -= dailyGrid[m].length
    }
    setTooltip({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
      month,
      day: remaining + 1,
      count: values[dayIdx],
    })
  }, [N, dailyGrid, values])

  return (
    <div className="relative">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${N} ${H}`}
        className="w-full"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setTooltip(null)}
      >
        <defs>
          <linearGradient id="wf-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="oklch(0.48 0.19 260)" stopOpacity="0.9" />
            <stop offset="12%" stopColor="oklch(0.55 0.16 255)" stopOpacity="0.6" />
            <stop offset="35%" stopColor="oklch(0.68 0.08 245)" stopOpacity="0.18" />
            <stop offset="50%" stopColor="oklch(0.85 0.03 240)" stopOpacity="0.04" />
            <stop offset="65%" stopColor="oklch(0.68 0.08 245)" stopOpacity="0.18" />
            <stop offset="88%" stopColor="oklch(0.55 0.16 255)" stopOpacity="0.6" />
            <stop offset="100%" stopColor="oklch(0.48 0.19 260)" stopOpacity="0.9" />
          </linearGradient>
        </defs>

        {/* Waveform area */}
        <path d={areaD} fill="url(#wf-fill)" />

        {/* Waveform edge lines */}
        <path d={topPts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p}`).join(' ')}
          fill="none" stroke="oklch(0.48 0.19 260 / 0.45)" strokeWidth="0.4" />
        <path d={botPts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p}`).join(' ')}
          fill="none" stroke="oklch(0.48 0.19 260 / 0.45)" strokeWidth="0.4" />

        {/* Moving average line */}
        <path d={maD} fill="none" stroke="oklch(0.42 0.2 270 / 0.3)" strokeWidth="0.6" strokeLinecap="round" />

        {/* Center line */}
        <line x1={CX} y1={CY} x2={N - 1} y2={CY} stroke="currentColor" strokeWidth="0.3" className="text-muted-foreground/15" />

        {/* Month dividers */}
        {months.map((m) => (
          <line key={m.x} x1={m.x} y1={CY - MAX_AMP - 4} x2={m.x} y2={CY + MAX_AMP + 4}
            stroke="currentColor" strokeWidth="0.4" className="text-muted-foreground/20" />
        ))}

        {/* Month labels */}
        {months.map((m, i) => {
          // Only show label if month has enough space (skip if too close to edge)
          const span = i < 11 ? months[i + 1].x - m.x : N - m.x
          if (span < 14) return null
          return (
            <text key={m.label}
              x={m.midX} y={14}
              textAnchor="middle"
              className="fill-muted-foreground/50 select-none pointer-events-none"
              style={{ fontSize: '8px', fontFamily: 'Inter, sans-serif' }}
            >
              {m.label}
            </text>
          )
        })}
      </svg>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="absolute pointer-events-none z-10 px-2 py-0.5 rounded bg-foreground text-background font-sans text-[11px] font-semibold whitespace-nowrap -translate-x-1/2"
          style={{ left: tooltip.x, top: tooltip.y - 24 }}
        >
          {tooltip.month + 1}月{tooltip.day}日 · {tooltip.count.toLocaleString()} 首
        </div>
      )}
    </div>
  )
}

export function TimeStory({ timeStory }: TimeStoryProps) {
  const maxMonthHours = Math.max(...timeStory.monthly_pulse.map(m => m.hours), 1)
  const minMonthHours = Math.min(...timeStory.monthly_pulse.map(m => m.hours))

  return (
    <section className="mb-12">
      <h2 className="font-serif text-[28px] font-bold tracking-[-0.5px] mb-6">时间故事</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* 听歌日历 */}
        <GlassCard className="p-5 relative flex flex-col justify-center">
          <h3 className="font-sans text-[12px] font-semibold uppercase tracking-[1.5px] text-muted-foreground mb-4">听歌日历</h3>
          <ListeningWaveform dailyGrid={timeStory.daily_grid} />
        </GlassCard>

        {/* 月度脉搏 */}
        <GlassCard className="p-5">
          <h3 className="font-sans text-[12px] font-semibold uppercase tracking-[1.5px] text-muted-foreground mb-4">月度脉搏</h3>
          <div className="space-y-1.5">
            {timeStory.monthly_pulse.map((m) => {
              const isMax = m.hours === maxMonthHours
              const isMin = m.hours === minMonthHours
              return (
                <div key={m.month} className="flex items-center gap-2">
                  <span className="font-sans text-[11px] text-muted-foreground w-7 text-right tabular-nums flex-shrink-0">{m.month}月</span>
                  <div className="flex-1 h-4 bg-muted rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${isMax ? 'bg-amber-500' : isMin ? 'bg-zinc-400 dark:bg-zinc-600' : 'bg-accent-foreground/50'}`}
                      style={{ width: `${(m.hours / maxMonthHours) * 100}%` }}
                    />
                  </div>
                  <span className="font-sans text-[12px] font-semibold tabular-nums w-10 text-right">{m.hours.toFixed(0)}h</span>
                </div>
              )
            })}
          </div>
        </GlassCard>

        {/* 听歌高峰时段 */}
        <GlassCard className="p-5">
          <h3 className="font-sans text-[12px] font-semibold uppercase tracking-[1.5px] text-muted-foreground mb-4">听歌高峰时段</h3>
          <HourClock hourlyDist={timeStory.hourly_dist} />
        </GlassCard>

        {/* 深夜听歌画像 */}
        {timeStory.late_night && (
          <GlassCard className="p-5">
            <h3 className="font-sans text-[12px] font-semibold uppercase tracking-[1.5px] text-muted-foreground mb-4">深夜听歌</h3>
            <p className="font-serif text-[36px] font-bold tabular-nums mb-1">{timeStory.late_night.ratio}%</p>
            <p className="font-sans text-[13px] text-muted-foreground mb-4">的歌曲在凌晨 0-5 点播放</p>
            {timeStory.late_night.top_tracks.length > 0 && (
              <div className="space-y-2">
                <p className="font-sans text-[11px] uppercase tracking-[1px] text-muted-foreground">深夜最爱</p>
                {timeStory.late_night.top_tracks.map((t) => (
                  <Link key={t.name + t.artist_name} to={`/music/tracks/${t.track_id}`} className="flex items-center gap-2 group">
                    <MiniCover url={t.cover_url} name={t.name} />
                    <div className="min-w-0 flex-1">
                      <p className="font-sans text-[13px] font-semibold truncate group-hover:text-accent-foreground transition-colors">{t.name}</p>
                      <p className="font-sans text-[11px] text-muted-foreground truncate">{t.artist_name} · {t.plays} 次</p>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </GlassCard>
        )}
      </div>
    </section>
  )
}
