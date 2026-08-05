import { Search, SlidersHorizontal, X } from 'lucide-react'

import { MobileBottomSheet } from '@/components/mobile'
import { cn } from '@/lib/utils'
import { PERIODS, type TimePeriod } from '@/features/community/TimeFilter'

interface MobileCommunityFiltersProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  search: string
  onSearchChange: (value: string) => void
  period: TimePeriod
  onPeriodChange: (period: TimePeriod) => void
}

export function MobileCommunityFilterBar({
  search,
  period,
  onOpen,
}: Pick<MobileCommunityFiltersProps, 'search' | 'period'> & { onOpen: () => void }) {
  const activeCount = Number(Boolean(search)) + Number(period.label !== '全部')

  return (
    <button
      type="button"
      className="mobile-community-filter-bar"
      onClick={onOpen}
      aria-label="打开社区搜索与时间筛选"
    >
      <span className="mobile-community-filter-icon" aria-hidden="true">
        <Search className="h-4 w-4" />
      </span>
      <span className="min-w-0 flex-1 truncate text-left">
        {search || (period.label === '全部' ? '搜索帖子、账号或艺人' : `时间 · ${period.label}`)}
      </span>
      {activeCount > 0 && <span className="mobile-community-filter-count">{activeCount}</span>}
      <SlidersHorizontal className="h-4 w-4 shrink-0" aria-hidden="true" />
    </button>
  )
}

export function MobileCommunityFilters({
  open,
  onOpenChange,
  search,
  onSearchChange,
  period,
  onPeriodChange,
}: MobileCommunityFiltersProps) {
  return (
    <MobileBottomSheet
      open={open}
      onOpenChange={onOpenChange}
      eyebrow="Community / Refine"
      title="查找与筛选"
      description="搜索社区内容，或限定帖子发布时间。"
      dataSheet="community-filters"
    >
      <div className="space-y-6">
        <label className="mobile-settings-field">
          <span>搜索社区</span>
          <div className="mobile-community-search-field">
            <Search className="h-4 w-4" aria-hidden="true" />
            <input
              value={search}
              onChange={(event) => onSearchChange(event.target.value)}
              placeholder="帖子、账号、艺人…"
              autoFocus
            />
            {search && (
              <button type="button" onClick={() => onSearchChange('')} aria-label="清空搜索">
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            )}
          </div>
        </label>

        <fieldset className="mobile-filter-group">
          <legend>发布时间</legend>
          <div className="grid grid-cols-2 gap-2">
            {PERIODS.map((option) => (
              <button
                key={option.label}
                type="button"
                role="radio"
                aria-checked={period.label === option.label}
                className={cn(
                  'mobile-filter-option min-h-12',
                  period.label === option.label && 'mobile-filter-option-selected',
                )}
                onClick={() => onPeriodChange(option)}
              >
                <span className="mobile-filter-option-label">{option.label}</span>
              </button>
            ))}
          </div>
        </fieldset>
      </div>
    </MobileBottomSheet>
  )
}
