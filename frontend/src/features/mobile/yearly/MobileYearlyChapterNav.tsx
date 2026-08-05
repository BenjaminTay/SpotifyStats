import { useEffect, useState } from 'react'

import { cn } from '@/lib/utils'

const YEARLY_CHAPTERS = [
  { id: 'yearly-hero', label: '总览' },
  { id: 'yearly-favorites', label: '年度最爱' },
  { id: 'yearly-time', label: '时间故事' },
  { id: 'yearly-taste', label: '曲风语言' },
  { id: 'yearly-discovery', label: '发现回归' },
  { id: 'yearly-depth', label: '收听深度' },
  { id: 'yearly-personality', label: '听歌人格' },
  { id: 'yearly-comparison', label: '年度对比' },
] as const

export function MobileYearlyChapterNav() {
  const [activeId, setActiveId] = useState<(typeof YEARLY_CHAPTERS)[number]['id']>(YEARLY_CHAPTERS[0].id)

  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return
    const nodes = YEARLY_CHAPTERS
      .map((chapter) => document.getElementById(chapter.id))
      .filter((node): node is HTMLElement => Boolean(node))
    if (nodes.length === 0) return

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
        if (visible[0]?.target.id) setActiveId(visible[0].target.id as typeof activeId)
      },
      { rootMargin: '-132px 0px -58% 0px', threshold: [0, 0.08, 0.35] },
    )
    nodes.forEach((node) => observer.observe(node))
    return () => observer.disconnect()
  }, [])

  return (
    <nav className="mobile-yearly-chapters" aria-label="年度总结章节">
      {YEARLY_CHAPTERS.map((chapter, index) => (
        <button
          key={chapter.id}
          type="button"
          className={cn(activeId === chapter.id && 'active')}
          aria-current={activeId === chapter.id ? 'location' : undefined}
          onClick={() => {
            setActiveId(chapter.id)
            document.getElementById(chapter.id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
          }}
        >
          <span>{String(index + 1).padStart(2, '0')}</span>
          {chapter.label}
        </button>
      ))}
    </nav>
  )
}
