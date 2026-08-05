import { useState, type RefObject } from 'react'
import { Check, RotateCcw } from 'lucide-react'

import { cn } from '@/lib/utils'
import { MobileBottomSheet } from './MobileBottomSheet'

export interface MobileFilterOption {
  value: string
  label: string
  description?: string
}

export interface MobileFilterGroup {
  id: string
  label: string
  type: 'single' | 'multiple'
  options: MobileFilterOption[]
}

export type MobileFilterValues = Record<string, string | string[]>

interface MobileFilterSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  groups: MobileFilterGroup[]
  appliedValues: MobileFilterValues
  defaultValues?: MobileFilterValues
  onApply: (values: MobileFilterValues) => void
  title?: string
  description?: string
  applying?: boolean
  triggerRef?: RefObject<HTMLElement | null>
}

function cloneValues(values: MobileFilterValues): MobileFilterValues {
  return Object.fromEntries(
    Object.entries(values).map(([key, value]) => [key, Array.isArray(value) ? [...value] : value]),
  )
}

type MobileFilterSheetSessionProps = Omit<MobileFilterSheetProps, 'open'>

function MobileFilterSheetSession({
  onOpenChange,
  groups,
  appliedValues,
  defaultValues = {},
  onApply,
  title = '筛选条件',
  description = '调整只影响草稿，点击应用后才会更新页面。',
  applying = false,
  triggerRef,
}: MobileFilterSheetSessionProps) {
  const [draft, setDraft] = useState<MobileFilterValues>(() => cloneValues(appliedValues))

  const toggleOption = (group: MobileFilterGroup, option: MobileFilterOption) => {
    setDraft((current) => {
      if (group.type === 'single') return { ...current, [group.id]: option.value }
      const selected = Array.isArray(current[group.id]) ? current[group.id] as string[] : []
      const next = selected.includes(option.value)
        ? selected.filter((value) => value !== option.value)
        : [...selected, option.value]
      return { ...current, [group.id]: next }
    })
  }

  return (
    <MobileBottomSheet
      open
      onOpenChange={onOpenChange}
      title={title}
      eyebrow="Refine / Filters"
      description={description}
      triggerRef={triggerRef}
      dataSheet="filters"
      footer={(
        <div className="mobile-sheet-actions">
          <button
            type="button"
            className="mobile-secondary-button"
            onClick={() => setDraft(cloneValues(defaultValues))}
          >
            <RotateCcw className="h-4 w-4" aria-hidden="true" />
            重置为默认
          </button>
          <button
            type="button"
            className="mobile-primary-button"
            disabled={applying}
            onClick={() => {
              onApply(cloneValues(draft))
              onOpenChange(false)
            }}
          >
            {applying ? '应用中…' : '应用筛选'}
          </button>
        </div>
      )}
    >
      <div className="mobile-filter-groups">
        {groups.map((group) => (
          <fieldset key={group.id} className="mobile-filter-group">
            <legend>{group.label}</legend>
            <div className="mobile-filter-options">
              {group.options.map((option) => {
                const current = draft[group.id]
                const selected = Array.isArray(current)
                  ? current.includes(option.value)
                  : current === option.value
                return (
                  <button
                    key={option.value}
                    type="button"
                    role={group.type === 'single' ? 'radio' : 'checkbox'}
                    aria-checked={selected}
                    className={cn('mobile-filter-option', selected && 'mobile-filter-option-selected')}
                    onClick={() => toggleOption(group, option)}
                  >
                    <span className="mobile-filter-check" aria-hidden="true">
                      {selected && <Check className="h-3.5 w-3.5" />}
                    </span>
                    <span className="min-w-0 flex-1 text-left">
                      <span className="mobile-filter-option-label">{option.label}</span>
                      {option.description && (
                        <span className="mobile-filter-option-description">{option.description}</span>
                      )}
                    </span>
                  </button>
                )
              })}
            </div>
          </fieldset>
        ))}
      </div>
    </MobileBottomSheet>
  )
}

export function MobileFilterSheet(props: MobileFilterSheetProps) {
  if (!props.open) return null
  return <MobileFilterSheetSession {...props} />
}
