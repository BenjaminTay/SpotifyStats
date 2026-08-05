import { useState, type ReactNode } from 'react'
import { ChevronDown } from 'lucide-react'

import { cn } from '@/lib/utils'

interface MobileHabitSectionProps {
  title: string
  summary: string
  defaultOpen?: boolean
  children: ReactNode
}

export function MobileHabitSection({
  title,
  summary,
  defaultOpen = false,
  children,
}: MobileHabitSectionProps) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <section className="mobile-account-disclosure">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <span><strong>{title}</strong><small>{summary}</small></span>
        <ChevronDown className={cn('h-4 w-4', open && 'rotate-180')} aria-hidden="true" />
      </button>
      {open && <div className="mobile-account-disclosure-content">{children}</div>}
    </section>
  )
}
