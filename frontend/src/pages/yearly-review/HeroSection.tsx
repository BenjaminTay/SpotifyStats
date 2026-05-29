import type { WrappedFullHero, LastYearComparison } from '@/types/yearly-review'
import type { PersonalityTheme } from '@/lib/personality-themes'

interface HeroSectionProps {
  hero: WrappedFullHero
  theme: PersonalityTheme
  lastYear: LastYearComparison | null
}

function formatNumber(n: number): string {
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return n.toLocaleString()
}

function formatHours(minutes: number): string {
  return Math.round(minutes / 60).toLocaleString()
}

function ChangeBadge({ value }: { value: number | null }) {
  if (value === null) return null
  const isUp = value > 0
  const isDown = value < 0
  return (
    <span className={`inline-block ml-1.5 text-[11px] font-sans font-semibold ${isUp ? 'text-green-300' : isDown ? 'text-red-300' : 'text-white/40'}`}>
      {isUp ? '↑' : isDown ? '↓' : '─'} {Math.abs(value).toFixed(1)}%
    </span>
  )
}

export function HeroSection({ hero, theme, lastYear }: HeroSectionProps) {
  // 检测是否有真实的去年对比数据
  const hasLastYear = lastYear && Object.values(lastYear).some(v => v !== null)
  const ch = (field: keyof LastYearComparison) => hasLastYear ? lastYear![field] : 100

  return (
    <section
      className="relative overflow-hidden rounded-2xl px-10 py-14 mb-12"
      style={{
        background: `linear-gradient(135deg, ${theme.bgStart}, ${theme.bgEnd})`,
      }}
    >
      {/* 年分数大字 */}
      <div className="mb-8">
        <p className="font-sans text-[13px] uppercase tracking-[2px] text-white/60 mb-2">
          年度总时长
          <ChangeBadge value={ch('total_hours_change')} />
        </p>
        <p className="font-serif text-[96px] font-bold leading-[0.95] tracking-[-2px] text-white">
          {formatHours(hero.total_minutes)}
          <span className="font-sans text-[24px] font-normal tracking-normal text-white/70 ml-2">小时</span>
        </p>
      </div>

      {/* 4 个 KPI */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
        <KpiItem label="总播放量" value={formatNumber(hero.total_plays)} change={ch('plays_change')} />
        <KpiItem label="独特曲目" value={formatNumber(hero.unique_tracks)} change={ch('tracks_change')} />
        <KpiItem label="独特艺人" value={formatNumber(hero.unique_artists)} change={ch('artists_change')} />
        <KpiItem label="听歌天数" value={String(hero.active_days)} change={ch('active_days_change')} />
      </div>
    </section>
  )
}

function KpiItem({ label, value, change }: { label: string; value: string; change?: number | null }) {
  return (
    <div>
      <p className="font-sans text-[11px] uppercase tracking-[1.2px] text-white/50 mb-1">{label}</p>
      <p className="font-serif text-[20px] font-semibold text-white/90">
        {value}
        {change != null && <ChangeBadge value={change} />}
      </p>
    </div>
  )
}
