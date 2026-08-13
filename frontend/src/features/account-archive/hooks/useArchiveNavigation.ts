import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useIsFetching } from '@tanstack/react-query'

import { isArchiveSection } from '@/features/account-archive/model/archiveModel'
import type { ArchiveSectionKey } from '@/types/accountArchive'

function scrollToSection(section: ArchiveSectionKey, behavior?: ScrollBehavior) {
  const node = document.getElementById(`archive-${section}`)
  if (typeof node?.scrollIntoView !== 'function') return
  node.scrollIntoView({ behavior, block: 'start' })
}

export function useArchiveNavigation(dataReady: boolean) {
  const [searchParams, setSearchParams] = useSearchParams()
  const archiveFetchingCount = useIsFetching({ queryKey: ['account', 'archive'] })
  const requestedSection = isArchiveSection(searchParams.get('section'))
    ? searchParams.get('section') as ArchiveSectionKey
    : 'cover'
  const [activeSection, setActiveSection] = useState<ArchiveSectionKey>(requestedSection)
  const initialScrollDone = useRef(false)
  const scrollTarget = useRef<ArchiveSectionKey | null>(null)
  const settleScrollTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const settleScrollDeadline = useRef<ReturnType<typeof setTimeout> | null>(null)
  const settleScrollObserver = useRef<ResizeObserver | null>(null)

  const finishSectionScroll = useCallback(() => {
    const section = scrollTarget.current
    settleScrollObserver.current?.disconnect()
    if (settleScrollDeadline.current) window.clearTimeout(settleScrollDeadline.current)
    if (section) scrollToSection(section)
    scrollTarget.current = null
  }, [])

  const settleSectionScroll = useCallback((section: ArchiveSectionKey) => {
    if (settleScrollTimer.current) window.clearTimeout(settleScrollTimer.current)
    if (settleScrollDeadline.current) window.clearTimeout(settleScrollDeadline.current)
    settleScrollObserver.current?.disconnect()

    const anchor = () => scrollToSection(section)
    const pages = document.querySelector('.archive-pages')
    if (pages && typeof ResizeObserver !== 'undefined') {
      settleScrollObserver.current = new ResizeObserver(anchor)
      settleScrollObserver.current.observe(pages)
      anchor()
      settleScrollDeadline.current = window.setTimeout(finishSectionScroll, 8_000)
      return
    }
    anchor()
    settleScrollDeadline.current = window.setTimeout(finishSectionScroll, 2_400)
  }, [finishSectionScroll])

  useEffect(() => {
    if (!scrollTarget.current) return
    if (settleScrollTimer.current) window.clearTimeout(settleScrollTimer.current)
    if (archiveFetchingCount > 0) return
    settleScrollTimer.current = window.setTimeout(finishSectionScroll, 650)
  }, [archiveFetchingCount, finishSectionScroll])

  useEffect(() => () => {
    if (settleScrollTimer.current) window.clearTimeout(settleScrollTimer.current)
    if (settleScrollDeadline.current) window.clearTimeout(settleScrollDeadline.current)
    settleScrollObserver.current?.disconnect()
  }, [])

  useEffect(() => {
    if (!dataReady || initialScrollDone.current || requestedSection === 'cover') return
    initialScrollDone.current = true
    scrollTarget.current = requestedSection
    window.requestAnimationFrame(() => scrollToSection(requestedSection))
    settleSectionScroll(requestedSection)
  }, [dataReady, requestedSection, settleSectionScroll])

  useEffect(() => {
    if (!dataReady) return
    const nodes = Array.from(document.querySelectorAll<HTMLElement>('[data-archive-section]'))
    let frame = 0
    const update = () => {
      frame = 0
      if (scrollTarget.current) return
      let next: ArchiveSectionKey = 'cover'
      for (const node of nodes) {
        const candidate = node.getAttribute('data-archive-section')
        if (node.getBoundingClientRect().top > 190) break
        if (isArchiveSection(candidate)) next = candidate
      }
      if (next === activeSection) return
      setActiveSection(next)
      setSearchParams((current) => {
        const params = new URLSearchParams(current)
        if (next === 'cover') params.delete('section')
        else params.set('section', next)
        return params
      }, { replace: true, preventScrollReset: true })
    }
    const onScroll = () => {
      if (!frame) frame = window.requestAnimationFrame(update)
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    update()
    return () => {
      window.removeEventListener('scroll', onScroll)
      if (frame) window.cancelAnimationFrame(frame)
    }
  }, [activeSection, dataReady, setSearchParams])

  const selectSection = useCallback((section: ArchiveSectionKey) => {
    scrollTarget.current = section
    setActiveSection(section)
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      if (section === 'cover') next.delete('section')
      else next.set('section', section)
      return next
    }, { replace: true, preventScrollReset: true })
    scrollToSection(section, 'smooth')
    settleSectionScroll(section)
  }, [setSearchParams, settleSectionScroll])

  return { activeSection, selectSection }
}
