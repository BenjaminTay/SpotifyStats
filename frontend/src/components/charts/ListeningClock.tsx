import { useState, useRef, useCallback } from 'react'
import { useTheme } from '@/hooks/useTheme'
import { getChartColors } from '@/lib/theme'

interface HourDatum {
  hour: number
  plays: number
  hours: number
}

function arcPath(cx: number, cy: number, innerR: number, outerR: number, startAngle: number, endAngle: number): string {
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

export function ListeningClock({
  data,
  metricLabel,
  maxWidth = 280,
}: {
  data: HourDatum[]
  metricLabel: string
  maxWidth?: number
}) {
  const { isDark } = useTheme()
  const colors = getChartColors(isDark)
  const cx = 100, cy = 100, innerR = 14

  const maxVal = Math.max(...data.map((d) => d.plays), 1)

  const [hoveredHour, setHoveredHour] = useState<number | null>(null)
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 })
  const svgRef = useRef<SVGSVGElement>(null)

  const handleMouseMove = useCallback((e: React.MouseEvent, hour: number) => {
    setHoveredHour(hour)
    const svg = svgRef.current
    if (svg) {
      const rect = svg.getBoundingClientRect()
      setTooltipPos({ x: e.clientX - rect.left, y: e.clientY - rect.top })
    }
  }, [])

  const selectHour = useCallback((hour: number) => {
    setHoveredHour(hour)
    setTooltipPos({ x: 100, y: 100 })
  }, [])

  const hoveredItem = hoveredHour !== null ? data.find((d) => d.hour === hoveredHour) ?? null : null

  return (
    <div className="relative flex justify-center">
      <svg ref={svgRef} viewBox="0 0 200 200" className="w-full" style={{ maxWidth }}>
        {data.map((h) => {
          const intensity = h.plays > 0 ? h.plays / maxVal : 0
          const isHovered = hoveredHour === h.hour
          const baseOuterR = innerR + intensity * (80 - innerR)
          const outerR = isHovered ? baseOuterR + 8 : baseOuterR
          const startDeg = h.hour * 15 - 90
          const endDeg = (h.hour + 1) * 15 - 90
          const startAngle = (startDeg * Math.PI) / 180
          const endAngle = (endDeg * Math.PI) / 180

          return (
            <path
              key={h.hour}
              d={arcPath(cx, cy, innerR, outerR, startAngle, endAngle)}
              fill={colors[0]}
              opacity={isHovered ? 0.95 : 0.12 + intensity * 0.78}
              className="cursor-pointer transition-all duration-150"
              role="button"
              tabIndex={0}
              aria-label={`${h.hour}:00 · ${h.plays.toLocaleString()} ${metricLabel}`}
              onMouseEnter={(e) => handleMouseMove(e, h.hour)}
              onMouseMove={(e) => handleMouseMove(e, h.hour)}
              onMouseLeave={() => setHoveredHour(null)}
              onClick={() => selectHour(h.hour)}
              onTouchStart={() => selectHour(h.hour)}
              onFocus={() => selectHour(h.hour)}
              onBlur={() => setHoveredHour(null)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  selectHour(h.hour)
                }
              }}
            />
          )
        })}

        {/* Hour tick marks */}
        {Array.from({ length: 24 }, (_, h) => {
          const deg = h * 15 - 90
          const rad = (deg * Math.PI) / 180
          const tickInner = 80
          const tickOuter = 83
          const isCardinal = h % 3 === 0
          return (
            <line
              key={h}
              x1={cx + tickInner * Math.cos(rad)}
              y1={cy + tickInner * Math.sin(rad)}
              x2={cx + tickOuter * Math.cos(rad)}
              y2={cy + tickOuter * Math.sin(rad)}
              stroke="currentColor"
              className="text-muted-foreground/35"
              strokeWidth={isCardinal ? 1.2 : 0.6}
              strokeLinecap="round"
            />
          )
        })}

        {/* Clock numerals */}
        {[0, 3, 6, 9, 12, 15, 18, 21].map((h) => {
          const deg = h * 15 - 90
          const rad = (deg * Math.PI) / 180
          const labelR = 93
          return (
            <text
              key={h}
              x={cx + labelR * Math.cos(rad)}
              y={cy + labelR * Math.sin(rad)}
              textAnchor="middle"
              dominantBaseline="central"
              className="fill-muted-foreground/60 select-none pointer-events-none"
              style={{ fontSize: '13px', fontFamily: 'var(--font-serif)', fontStyle: 'italic' }}
            >
              {h}
            </text>
          )
        })}

        {/* Center dot */}
        <circle cx={cx} cy={cy} r={innerR - 1} fill="var(--card, #fff)" opacity={0.7} />
      </svg>

      {hoveredItem && (
        <div
          className="absolute pointer-events-none z-10 px-2.5 py-1 rounded-md bg-foreground text-background font-sans text-[12px] font-semibold whitespace-nowrap shadow-lg"
          style={{ left: tooltipPos.x + 12, top: tooltipPos.y - 28 }}
        >
          {hoveredItem.hour}:00 · {hoveredItem.plays.toLocaleString()} {metricLabel}
        </div>
      )}
    </div>
  )
}
