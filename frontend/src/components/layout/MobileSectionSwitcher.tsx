import type { RefObject } from 'react'
import { Check } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'

import { MobileBottomSheet } from '@/components/mobile/MobileBottomSheet'
import type { MobileSectionGroup } from './routeContext'
import { cn } from '@/lib/utils'

interface SectionItem {
  to: string
  label: string
  description: string
  preserve: 'none' | 'time' | 'all'
}

const ANALYSIS_ITEMS: SectionItem[] = [
  { to: '/analysis/stats', label: '播放统计', description: '趋势、时段与行为分布', preserve: 'time' },
  { to: '/analysis/charts', label: '播放排行', description: '歌曲、专辑与艺人排行', preserve: 'time' },
  { to: '/yearly-review', label: '年度总结', description: '年度回顾与音乐档案', preserve: 'none' },
  { to: '/analysis/records', label: '播放记录', description: '里程碑与极值记录', preserve: 'time' },
  { to: '/account', label: '账号中心', description: '收藏、播客与账号概览', preserve: 'none' },
]

const BILLBOARD_ITEMS: SectionItem[] = [
  { to: '/billboard', label: '周榜', description: '每周个人榜单走势', preserve: 'all' },
  { to: '/billboard/number-ones', label: '每周榜首', description: '冠军与连冠时间线', preserve: 'all' },
  { to: '/billboard/year-end', label: '年榜', description: '年度累计表现', preserve: 'all' },
  { to: '/billboard/all-time', label: '总榜', description: '完整历史总排名', preserve: 'all' },
  { to: '/billboard/records', label: '榜单记录', description: '纪录、突破与趣味成就', preserve: 'all' },
  { to: '/billboard/versus', label: '对决', description: '实体成绩并排比较', preserve: 'all' },
]

const TIME_RANGE_PARAMS = ['period', 'period_value', 'start', 'end']

function sectionSwitcherTarget(item: SectionItem, search: string): string {
  if (item.preserve === 'none') return item.to

  const current = new URLSearchParams(search)
  const preserved = new URLSearchParams()
  if (item.preserve === 'all') {
    current.forEach((value, key) => preserved.append(key, value))
  } else {
    TIME_RANGE_PARAMS.forEach((key) => {
      const value = current.get(key)
      if (value) preserved.set(key, value)
    })
  }

  const query = preserved.toString()
  return query ? `${item.to}?${query}` : item.to
}

interface MobileSectionSwitcherProps {
  group: MobileSectionGroup
  open: boolean
  onOpenChange: (open: boolean) => void
  triggerRef: RefObject<HTMLButtonElement | null>
}

export function MobileSectionSwitcher({
  group,
  open,
  onOpenChange,
  triggerRef,
}: MobileSectionSwitcherProps) {
  const location = useLocation()
  const items = group === 'analysis' ? ANALYSIS_ITEMS : BILLBOARD_ITEMS
  const groupLabel = group === 'analysis' ? '播放分析栏目' : 'Billboard 栏目'

  return (
    <MobileBottomSheet
      open={open}
      onOpenChange={onOpenChange}
      title={groupLabel}
      eyebrow="Navigate / Sections"
      triggerRef={triggerRef}
      dataSheet="section-switcher"
      contentClassName="mobile-section-nav"
    >
      <nav aria-label={groupLabel}>
        {items.map((item, index) => {
          const active = location.pathname === item.to
            || (item.to === '/analysis/stats' && location.pathname === '/analysis')
          return (
            <Link
              key={item.to}
              to={sectionSwitcherTarget(item, location.search)}
              aria-current={active ? 'page' : undefined}
              onClick={() => onOpenChange(false)}
              className={cn('mobile-section-link', active && 'mobile-section-link-active')}
            >
              <span className="mobile-section-index">{String(index + 1).padStart(2, '0')}</span>
              <span className="min-w-0 flex-1">
                <span className="block text-[15px] font-semibold text-foreground">{item.label}</span>
                <span className="mt-0.5 block truncate text-[11px] text-muted-foreground">{item.description}</span>
              </span>
              {active && <Check className="h-4.5 w-4.5 text-accent-foreground" aria-hidden="true" />}
            </Link>
          )
        })}
      </nav>
    </MobileBottomSheet>
  )
}
