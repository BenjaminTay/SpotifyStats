import { useRef, useState } from 'react'
import { BookOpen, ChevronDown } from 'lucide-react'

import { MobileBottomSheet } from '@/components/mobile'

export interface MobileYearlyChapterItem {
  id: string
  label: string
}

interface MobileYearlyChapterNavV2Props {
  chapters: MobileYearlyChapterItem[]
  activeId: string
  onSelect: (id: string) => void
}

export function MobileYearlyChapterNavV2({
  chapters,
  activeId,
  onSelect,
}: MobileYearlyChapterNavV2Props) {
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const activeIndex = Math.max(0, chapters.findIndex(chapter => chapter.id === activeId))
  const activeChapter = chapters[activeIndex] ?? chapters[0]

  return (
    <>
      <nav className="mobile-yearly-v2-chapter-nav" aria-label="年度总结章节">
        <button
          ref={triggerRef}
          type="button"
          onClick={() => setOpen(true)}
          aria-haspopup="dialog"
          aria-expanded={open}
        >
          <span className="mobile-yearly-v2-chapter-count">
            {String(activeIndex + 1).padStart(2, '0')} / {String(chapters.length).padStart(2, '0')}
          </span>
          <strong>{activeChapter?.label ?? '年度章节'}</strong>
          <ChevronDown aria-hidden="true" />
        </button>
        <div aria-hidden="true">
          <i style={{ width: `${((activeIndex + 1) / Math.max(chapters.length, 1)) * 100}%` }} />
        </div>
      </nav>

      <MobileBottomSheet
        open={open}
        onOpenChange={setOpen}
        title="翻阅年度章节"
        eyebrow="Contents"
        triggerRef={triggerRef}
        dataSheet="yearly-v2-chapters"
        contentClassName="mobile-yearly-v2-chapter-sheet"
      >
        <ol>
          {chapters.map((chapter, index) => (
            <li key={chapter.id}>
              <button
                type="button"
                aria-current={chapter.id === activeId ? 'page' : undefined}
                onClick={() => {
                  setOpen(false)
                  window.requestAnimationFrame(() => onSelect(chapter.id))
                }}
              >
                <span>{String(index + 1).padStart(2, '0')}</span>
                <strong>{chapter.label}</strong>
                {chapter.id === activeId && <BookOpen aria-hidden="true" />}
              </button>
            </li>
          ))}
        </ol>
      </MobileBottomSheet>
    </>
  )
}
