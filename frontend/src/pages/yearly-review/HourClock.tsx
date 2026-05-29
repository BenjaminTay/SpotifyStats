import { useState, useRef, useCallback } from 'react'
import type { HourlyDistItem } from '@/types/yearly-review'

interface HourClockProps {
  hourlyDist: HourlyDistItem[]
}

function formatHour(h: number): string {
  return `${h}:00`
}

function arcPath(
  cx: number,
  cy: number,
  innerR: number,
  outerR: number,
  startAngle: number,
  endAngle: number,
): string {
  const x1o = cx + outerR * Math.cos(startAngle)
  const y1o = cy + outerR * Math.sin(startAngle)
  const x2o = cx + outerR * Math.cos(endAngle)
  const y2o = cy + outerR * Math.sin(endAngle)
  const x2i = cx + innerR * Math.cos(endAngle)
  const y2i = cy + innerR * Math.sin(endAngle)
  const x1i = cx + innerR * Math.cos(startAngle)
  const y1i = cy + innerR * Math.sin(startAngle)

  return [
    `M ${x1o.toFixed(2)} ${y1o.toFixed(2)}`,
    `A ${outerR} ${outerR} 0 0 1 ${x2o.toFixed(2)} ${y2o.toFixed(2)}`,
    `L ${x2i.toFixed(2)} ${y2i.toFixed(2)}`,
    `A ${innerR} ${innerR} 0 0 0 ${x1i.toFixed(2)} ${y1i.toFixed(2)}`,
    'Z',
  ].join(' ')
}

function segmentColor(intensity: number): string {
  // Ice blue → deep indigo
  const L = 0.92 - intensity * 0.42
  const C = 0.02 + intensity * 0.16
  const H = 255 - intensity * 30
  const alpha = 0.5 + intensity * 0.45
  return `oklch(${L.toFixed(3)} ${C.toFixed(3)} ${H.toFixed(0)} / ${alpha.toFixed(2)})`
}

export function HourClock({ hourlyDist }: HourClockProps) {
  const cx = 100, cy = 100, innerR = 18

  const maxPlays = Math.max(...hourlyDist.map(h => h.plays), 1)
  const [hoveredHour, setHoveredHour] = useState<number | null>(null)
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 })
  const svgRef = useRef<SVGSVGElement>(null)

  const handleMouseMove = useCallback((e: React.MouseEvent, hour: number) => {
    setHoveredHour(hour)
    const svg = svgRef.current
    if (svg) {
      const rect = svg.getBoundingClientRect()
      setTooltipPos({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      })
    }
  }, [])

  const hoveredItem = hoveredHour !== null
    ? hourlyDist.find(h => h.hour === hoveredHour) ?? null
    : null

  return (
    <div className="relative flex justify-center">
      <svg
        ref={svgRef}
        viewBox="0 0 200 200"
        className="w-full max-w-[260px]"
      >
        {/* 24 hour segments */}
        {hourlyDist.map((h) => {
          const intensity = Math.max(h.plays / maxPlays, 0.06)
          const isHovered = hoveredHour === h.hour

          // Narrower range: 50 (min) to 75 (max)
          const baseOuterR = 50 + intensity * 25
          const outerR = isHovered ? baseOuterR + 8 : baseOuterR

          const startDeg = h.hour * 15 - 90
          const endDeg = (h.hour + 1) * 15 - 90
          const startAngle = (startDeg * Math.PI) / 180
          const endAngle = (endDeg * Math.PI) / 180

          return (
            <path
              key={h.hour}
              d={arcPath(cx, cy, innerR, outerR, startAngle, endAngle)}
              fill={segmentColor(intensity)}
              className="cursor-pointer transition-all duration-150"
              onMouseEnter={(e) => handleMouseMove(e, h.hour)}
              onMouseMove={(e) => handleMouseMove(e, h.hour)}
              onMouseLeave={() => setHoveredHour(null)}
            />
          )
        })}

        {/* Hour tick marks + 12/3/6/9 labels */}
        {Array.from({ length: 24 }, (_, h) => {
          const deg = h * 15 - 90
          const rad = (deg * Math.PI) / 180
          const tickInner = 77
          const tickOuter = 81
          const x1 = cx + tickInner * Math.cos(rad)
          const y1 = cy + tickInner * Math.sin(rad)
          const x2 = cx + tickOuter * Math.cos(rad)
          const y2 = cy + tickOuter * Math.sin(rad)
          const isCardinal = h % 3 === 0
          return (
            <line
              key={h}
              x1={x1} y1={y1} x2={x2} y2={y2}
              stroke="currentColor"
              className="text-muted-foreground/40"
              strokeWidth={isCardinal ? 1.4 : 0.7}
              strokeLinecap="round"
            />
          )
        })}

        {/* Clock numerals */}
        {[0, 3, 6, 9, 12, 15, 18, 21].map((h) => {
          const deg = h * 15 - 90
          const rad = (deg * Math.PI) / 180
          const labelR = 92
          return (
            <text
              key={h}
              x={cx + labelR * Math.cos(rad)}
              y={cy + labelR * Math.sin(rad)}
              textAnchor="middle"
              dominantBaseline="central"
              className="fill-muted-foreground/70 select-none pointer-events-none"
              style={{ fontSize: '14px', fontFamily: 'var(--font-serif)', fontStyle: 'italic' }}
            >
              {h}
            </text>
          )
        })}

        {/* Center circle */}
        <circle cx={cx} cy={cy} r={innerR - 1} fill="var(--card, #fff)" opacity={0.6} />
      </svg>

      {/* Tooltip */}
      {hoveredItem && (
        <div
          className="absolute pointer-events-none z-10 px-2.5 py-1 rounded-md bg-foreground text-background font-sans text-[12px] font-semibold whitespace-nowrap shadow-lg"
          style={{
            left: tooltipPos.x + 12,
            top: tooltipPos.y - 28,
          }}
        >
          {formatHour(hoveredItem.hour)} · {hoveredItem.plays.toLocaleString()} 次
        </div>
      )}
    </div>
  )
}
