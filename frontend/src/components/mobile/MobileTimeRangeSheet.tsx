import { useMemo, useState, type RefObject } from 'react'
import { CalendarDays, Check } from 'lucide-react'

import type { AnalysisPeriod } from '@/types/analysis'
import { cn } from '@/lib/utils'
import { MobileBottomSheet } from './MobileBottomSheet'

export interface MobileTimeRangeValue {
  period: AnalysisPeriod
  periodValue?: string
  start?: string
  end?: string
}

interface MobileTimeRangeSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  value: MobileTimeRangeValue
  onApply: (value: MobileTimeRangeValue) => void
  triggerRef?: RefObject<HTMLElement | null>
}

const PERIOD_OPTIONS: Array<{ value: AnalysisPeriod; label: string; hint: string }> = [
  { value: 'lifetime', label: '全部时间', hint: '完整播放历史' },
  { value: 'last_6_months', label: '近 6 个月', hint: '滚动半年窗口' },
  { value: 'last_4_weeks', label: '近 4 周', hint: '最近 28 天' },
  { value: 'year', label: '按年', hint: '选择自然年' },
  { value: 'month', label: '按月', hint: '选择自然月' },
  { value: 'week', label: '按周', hint: '选择自然周' },
  { value: 'day', label: '按日', hint: '选择具体日期' },
  { value: 'custom', label: '自定义', hint: '指定开始与结束日期' },
]

function periodInputType(period: AnalysisPeriod): 'number' | 'month' | 'week' | 'date' | null {
  if (period === 'year') return 'number'
  if (period === 'month') return 'month'
  if (period === 'week') return 'date'
  if (period === 'day') return 'date'
  return null
}

type MobileTimeRangeSessionProps = Omit<MobileTimeRangeSheetProps, 'open'>

function MobileTimeRangeSession({ onOpenChange, value, onApply, triggerRef }: MobileTimeRangeSessionProps) {
  const [draft, setDraft] = useState<MobileTimeRangeValue>(() => ({ ...value }))
  const inputType = periodInputType(draft.period)
  const validationMessage = useMemo(() => {
    if (inputType && !draft.periodValue) return '请选择具体时间。'
    if (draft.period === 'custom' && (!draft.start || !draft.end)) return '请选择开始和结束日期。'
    if (draft.period === 'custom' && draft.start && draft.end && draft.start > draft.end) {
      return '开始日期不能晚于结束日期。'
    }
    return ''
  }, [draft.end, draft.period, draft.periodValue, draft.start, inputType])

  return (
    <MobileBottomSheet
      open
      onOpenChange={onOpenChange}
      title="时间范围"
      eyebrow="Time / Range"
      description="统一控制当前页面的数据窗口；应用后写回页面查询参数。"
      triggerRef={triggerRef}
      dataSheet="time-range"
      footer={(
        <div className="mobile-sheet-actions mobile-sheet-actions-end">
          <button
            type="button"
            className="mobile-primary-button"
            disabled={Boolean(validationMessage)}
            onClick={() => {
              onApply({ ...draft })
              onOpenChange(false)
            }}
          >
            应用时间范围
          </button>
        </div>
      )}
    >
      <div className="mobile-time-grid" role="radiogroup" aria-label="时间范围类型">
        {PERIOD_OPTIONS.map((option) => {
          const selected = option.value === draft.period
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={selected}
              className={cn('mobile-time-option', selected && 'mobile-time-option-selected')}
              onClick={() => setDraft({ period: option.value })}
            >
              <span>
                <strong>{option.label}</strong>
                <small>{option.hint}</small>
              </span>
              {selected && <Check className="h-4 w-4" aria-hidden="true" />}
            </button>
          )
        })}
      </div>

      {inputType && (
        <label className="mobile-date-field">
          <span><CalendarDays className="h-4 w-4" aria-hidden="true" />具体时间</span>
          <input
            type={inputType}
            min={inputType === 'number' ? 1900 : undefined}
            max={inputType === 'number' ? 2200 : undefined}
            value={draft.periodValue ?? ''}
            onChange={(event) => setDraft((current) => ({ ...current, periodValue: event.target.value }))}
          />
        </label>
      )}

      {draft.period === 'custom' && (
        <div className="mobile-custom-range">
          <label className="mobile-date-field">
            <span>开始日期</span>
            <input
              type="date"
              value={draft.start ?? ''}
              onChange={(event) => setDraft((current) => ({ ...current, start: event.target.value }))}
            />
          </label>
          <label className="mobile-date-field">
            <span>结束日期</span>
            <input
              type="date"
              value={draft.end ?? ''}
              onChange={(event) => setDraft((current) => ({ ...current, end: event.target.value }))}
            />
          </label>
        </div>
      )}
      {validationMessage && <p className="mobile-field-message" role="status">{validationMessage}</p>}
    </MobileBottomSheet>
  )
}

export function MobileTimeRangeSheet(props: MobileTimeRangeSheetProps) {
  if (!props.open) return null
  return <MobileTimeRangeSession {...props} />
}
