import { CalendarDays, Headphones, UserRoundCheck } from 'lucide-react'

import { cn } from '@/lib/utils'

export interface MobileAccountHeroProps {
  displayName: string
  imageUrl?: string | null
  username?: string | null
  country?: string | null
  listeningYears: number | null
  startYear: number | null
  totalPlays: number
  followsCount: number
  personality?: { icon: string; type: string } | null
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat('zh-CN', { notation: value > 9_999 ? 'compact' : 'standard' }).format(value)
}

export function MobileAccountHero({
  displayName,
  imageUrl,
  username,
  country,
  listeningYears,
  startYear,
  totalPlays,
  followsCount,
  personality,
}: MobileAccountHeroProps) {
  const facts = [
    { label: '收听年数', value: listeningYears !== null ? String(listeningYears) : '—', icon: CalendarDays },
    { label: '播放', value: formatNumber(totalPlays), icon: Headphones },
    { label: '起点', value: startYear ? String(startYear) : '—', icon: CalendarDays },
    { label: '关注', value: formatNumber(followsCount), icon: UserRoundCheck },
  ]

  return (
    <section className="mobile-account-hero" data-mobile-account="hero">
      <div className="mobile-account-portrait">
        {imageUrl ? (
          <img src={imageUrl} alt={displayName} />
        ) : (
          <span>{displayName.charAt(0).toUpperCase()}</span>
        )}
      </div>

      <div className="min-w-0 flex-1">
        <p className="mobile-account-kicker">Your listening identity</p>
        <h1>{displayName}</h1>
        <p className="mobile-account-handle">
          {username ? `@${username}` : 'Spotify listener'}
          {country ? ` · ${country}` : ''}
        </p>
        <p className="mobile-account-story">
          {listeningYears !== null && startYear !== null
            ? `从 ${startYear} 年开始，${listeningYears} 年的收听轨迹在这里汇成一份个人档案。`
            : '你的收藏、搜索和收听习惯在这里汇成一份个人档案。'}
        </p>
        {personality && (
          <span className={cn('mobile-account-personality')}>
            <span aria-hidden="true">{personality.icon}</span>
            {personality.type}
          </span>
        )}
      </div>

      <div className="mobile-account-facts" aria-label="账号摘要">
        {facts.map(({ label, value, icon: Icon }) => (
          <div key={label}>
            <Icon className="h-3.5 w-3.5" aria-hidden="true" />
            <strong>{value}</strong>
            <span>{label}</span>
          </div>
        ))}
      </div>
    </section>
  )
}
