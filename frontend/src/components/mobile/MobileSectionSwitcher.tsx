import { useRef, useState } from 'react'
import { Check, ChevronDown } from 'lucide-react'

import { cn } from '@/lib/utils'
import { MobileBottomSheet } from './MobileBottomSheet'

export interface MobileSectionOption<T extends string> {
  value: T
  label: string
  description?: string
}

interface MobileSectionSwitcherProps<T extends string> {
  value: T
  options: MobileSectionOption<T>[]
  onChange: (value: T) => void
  label?: string
  title?: string
  className?: string
}

export function MobileSectionSwitcher<T extends string>({
  value,
  options,
  onChange,
  label = '当前栏目',
  title = '选择栏目',
  className,
}: MobileSectionSwitcherProps<T>) {
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const current = options.find((option) => option.value === value) ?? options[0]

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className={cn('mobile-section-switcher', className)}
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        aria-expanded={open}
      >
        <span>
          <small>{label}</small>
          <strong>{current?.label}</strong>
        </span>
        <ChevronDown aria-hidden="true" />
      </button>

      <MobileBottomSheet
        open={open}
        onOpenChange={setOpen}
        title={title}
        eyebrow="Section"
        description="切换只改变当前页面的内容章节。"
        triggerRef={triggerRef}
        dataSheet="section-switcher"
      >
        <div className="mobile-section-options" role="listbox" aria-label={title}>
          {options.map((option) => {
            const selected = option.value === value
            return (
              <button
                key={option.value}
                type="button"
                role="option"
                aria-selected={selected}
                className={cn(selected && 'active')}
                data-mobile-autofocus={selected ? 'true' : undefined}
                onClick={() => {
                  onChange(option.value)
                  setOpen(false)
                }}
              >
                <span>
                  <strong>{option.label}</strong>
                  {option.description && <small>{option.description}</small>}
                </span>
                {selected && <Check aria-hidden="true" />}
              </button>
            )
          })}
        </div>
      </MobileBottomSheet>
    </>
  )
}
