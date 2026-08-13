import { useCallback, useEffect, useRef, useState } from 'react'

import { ARCHIVE_SECTIONS } from '@/features/account-archive/model/archiveModel'
import type { ArchiveSectionKey } from '@/types/accountArchive'

export function PhoneArchiveNav({
  activeSection,
  onSelect,
}: {
  activeSection: ArchiveSectionKey
  onSelect: (section: ArchiveSectionKey) => void
}) {
  const listRef = useRef<HTMLOListElement>(null)
  const buttonRefs = useRef<Partial<Record<ArchiveSectionKey, HTMLButtonElement | null>>>({})
  const [scrollEdges, setScrollEdges] = useState({ left: false, right: false })

  const updateScrollEdges = useCallback(() => {
    const list = listRef.current
    if (!list) return
    setScrollEdges({
      left: list.scrollLeft > 2,
      right: list.scrollLeft + list.clientWidth < list.scrollWidth - 2,
    })
  }, [])

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const list = listRef.current
      const button = buttonRefs.current[activeSection]
      if (!list || !button) return
      const targetLeft = Math.max(
        0,
        button.offsetLeft - (list.clientWidth - button.offsetWidth) / 2,
      )
      const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ?? false
      if (typeof list.scrollTo === 'function') {
        list.scrollTo({ left: targetLeft, behavior: reducedMotion ? 'auto' : 'smooth' })
      } else {
        list.scrollLeft = targetLeft
      }
      updateScrollEdges()
    })
    return () => window.cancelAnimationFrame(frame)
  }, [activeSection, updateScrollEdges])

  useEffect(() => {
    window.addEventListener('resize', updateScrollEdges)
    return () => window.removeEventListener('resize', updateScrollEdges)
  }, [updateScrollEdges])

  return (
    <nav
      className={`phone-archive-nav${scrollEdges.left ? ' can-scroll-left' : ''}${scrollEdges.right ? ' can-scroll-right' : ''}`}
      aria-label="音乐档案章节"
    >
      <ol ref={listRef} onScroll={updateScrollEdges}>
        {ARCHIVE_SECTIONS.map((section, index) => (
          <li key={section.key}>
            <button
              ref={(node) => { buttonRefs.current[section.key] = node }}
              type="button"
              className={activeSection === section.key ? 'active' : undefined}
              aria-current={activeSection === section.key ? 'true' : undefined}
              onClick={() => onSelect(section.key)}
            >
              <span>{String(index).padStart(2, '0')}</span>{section.shortLabel}
            </button>
          </li>
        ))}
      </ol>
    </nav>
  )
}
