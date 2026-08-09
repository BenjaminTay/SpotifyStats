import { GlassCard } from '@/components/shared/GlassCard'
import { cn } from '@/lib/utils'

export function formatNumber(n: number): string {
  return new Intl.NumberFormat('zh-CN').format(n)
}

export function dateOnly(iso: string): string {
  if (!iso) return ''
  return iso.split('T')[0].split(' ')[0]
}

export function formatWeekStart(iso: string): string {
  if (!iso) return ''
  const dateStr = dateOnly(iso)
  const date = new Date(`${dateStr}T00:00:00`)
  if (isNaN(date.getTime())) return iso
  return `${date.getFullYear()}/${date.getMonth() + 1}/${date.getDate()}`
}

export function formatDateShort(iso: string): string {
  if (!iso) return '—'
  const dateStr = dateOnly(iso)
  const date = new Date(`${dateStr}T00:00:00`)
  if (isNaN(date.getTime())) return dateStr || iso
  return `${date.getFullYear()}/${date.getMonth() + 1}/${date.getDate()}`
}

export function formatTimeSpan(start: string, end: string): string {
  if (!start || !end) return '—'
  const startDate = new Date(`${dateOnly(start)}T00:00:00`)
  const endDate = new Date(`${dateOnly(end)}T00:00:00`)
  if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) return '—'
  const diffMs = endDate.getTime() - startDate.getTime()
  const diffWeeks = Math.round(diffMs / (7 * 24 * 60 * 60 * 1000))
  const totalMonths =
    (endDate.getFullYear() - startDate.getFullYear()) * 12 +
    (endDate.getMonth() - startDate.getMonth())
  if (totalMonths < 1) return `${diffWeeks} 周`
  const years = Math.floor(totalMonths / 12)
  const months = totalMonths % 12
  if (years > 0 && months > 0) return `${years} 年 ${months} 个月`
  if (years > 0) return `${years} 年`
  return `${months} 个月`
}

export function formatOptionalRank(rank: number | null | undefined): string {
  return rank ? `#${rank}` : '—'
}

export function KpiCard({
  label,
  value,
  sub,
  accent,
  accentColor,
}: {
  label: string
  value: string
  sub?: string
  accent?: boolean
  accentColor?: string
}) {
  return (
    <GlassCard className="p-5">
      <p className="font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
        {label}
      </p>
      <p
        className="mt-1 font-serif text-[32px] font-bold leading-none"
        style={accentColor ? { color: accentColor } : accent ? { color: 'var(--accent-foreground)' } : undefined}
      >
        {value}
      </p>
      {sub && (
        <p className="mt-1 font-sans text-[12px] text-muted-foreground">{sub}</p>
      )}
    </GlassCard>
  )
}

export function KpiStrip({
  items,
  compactFive = false,
}: {
  items: { label: string; value: string; accent?: boolean }[]
  compactFive?: boolean
}) {
  return (
    <div className={cn('mb-5 flex flex-wrap gap-x-6 gap-y-2 border-b border-border pb-5', compactFive && 'mobile-achievement-kpis')}>
      {items.map((item) => (
        <div key={item.label} className="flex items-baseline gap-1.5">
          <span className="font-sans text-[11px] font-bold uppercase tracking-[1px] text-muted-foreground">
            {item.label}
          </span>
          <span
            className="font-serif text-[22px] font-bold leading-none"
            style={item.accent ? { color: 'var(--accent-foreground)' } : undefined}
          >
            {item.value}
          </span>
        </div>
      ))}
    </div>
  )
}

export function PlaysCell({ plays, maxPlays }: { plays: number; maxPlays: number }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span className="font-sans text-[13px] tabular-nums">{formatNumber(plays)}</span>
      <span className="inline-block h-[3px] w-[60px] rounded-[2px] bg-muted align-middle">
        <span
          className="block h-full rounded-[2px] bg-accent-foreground"
          style={{ width: `${Math.round((plays / maxPlays) * 100)}%` }}
        />
      </span>
    </span>
  )
}
