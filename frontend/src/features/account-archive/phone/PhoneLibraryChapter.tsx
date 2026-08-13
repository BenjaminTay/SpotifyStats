import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ChevronLeft, ChevronRight, Disc3, Search, SlidersHorizontal, X } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'

import { useArchiveLibrary } from '@/features/account-archive/hooks/useAccountArchive'
import { useArchiveSection } from '@/features/account-archive/hooks/useArchiveSection'
import {
  DEFAULT_LIBRARY_SORT,
  LIBRARY_LABELS,
  LIBRARY_SORTS,
  formatArchiveDate,
  formatArchiveNumber,
  isLibraryEntity,
  librarySortFor,
} from '@/features/account-archive/model/archiveModel'
import type { ArchiveLibraryEntityType, ArchiveLibraryItem } from '@/types/accountArchive'
import { PhoneArchiveError, PhoneArchiveLoading, PhoneChapterHeading } from './PhoneArchivePrimitives'

function itemContent(item: ArchiveLibraryItem) {
  if (item.entity_type === 'track') return { name: item.track_name, secondary: item.artist_name, meta: formatArchiveDate(item.added_date), cover: item.cover_url, href: item.deep_link }
  if (item.entity_type === 'album') return { name: item.album_name, secondary: item.artist_name, meta: '专辑', cover: item.cover_url, href: item.deep_link }
  if (item.entity_type === 'artist') return { name: item.artist_name, secondary: '收藏艺人', meta: '艺人', cover: item.cover_url, href: item.deep_link }
  return { name: item.playlist_name, secondary: item.preview_tracks[0]?.track_name ?? '暂无曲目预览', meta: `${formatArchiveNumber(item.track_count)} 首`, cover: null, href: null }
}

function PhoneLibraryRow({ item, index }: { item: ArchiveLibraryItem; index: number }) {
  const detail = itemContent(item)
  const content = (
    <>
      <span className="phone-library-number">{String(index).padStart(3, '0')}</span>
      <span className="phone-library-art">{detail.cover ? <img src={detail.cover} alt="" loading="lazy" /> : <Disc3 />}</span>
      <span className="phone-library-copy"><strong>{detail.name}</strong><small>{detail.secondary}</small></span>
      <em>{detail.meta}</em>
    </>
  )
  return detail.href ? <Link className="phone-library-row" to={detail.href}>{content}</Link> : <div className="phone-library-row">{content}</div>
}

function PhoneLibrarySearch({ initialValue, label, onSearch }: { initialValue: string; label: string; onSearch: (value: string) => void }) {
  const [value, setValue] = useState(initialValue)
  return (
    <form className="phone-library-search" role="search" onSubmit={(event) => { event.preventDefault(); onSearch(value.trim()) }}>
      <Search />
      <label className="sr-only" htmlFor="phone-library-search">搜索当前收藏库</label>
      <input id="phone-library-search" value={value} maxLength={120} placeholder={`搜索${label}`} onChange={event => setValue(event.target.value)} />
      <button type="submit">搜索</button>
    </form>
  )
}

export function PhoneLibraryChapter() {
  const { ref, enabled } = useArchiveSection()
  const [searchParams, setSearchParams] = useSearchParams()
  const [pageJumpOpen, setPageJumpOpen] = useState(false)
  const [pageJumpValue, setPageJumpValue] = useState('1')
  const openerRef = useRef<HTMLButtonElement>(null)
  const closeRef = useRef<HTMLButtonElement>(null)
  const pageJumpOpenRef = useRef(false)
  const entityType = isLibraryEntity(searchParams.get('library')) ? searchParams.get('library') as ArchiveLibraryEntityType : 'tracks'
  const page = Math.max(Number(searchParams.get('page')) || 1, 1)
  const search = searchParams.get('search') ?? ''
  const sort = librarySortFor(entityType, searchParams.get('sort'))
  const open = searchParams.get('library_view') === 'full'
  const query = useArchiveLibrary({ entityType, page, limit: 10, search, sort }, enabled || open)

  const patchUrl = useCallback((patch: Record<string, string | null>, replace = true) => {
    setSearchParams(current => {
      const next = new URLSearchParams(current)
      next.set('section', 'library')
      Object.entries(patch).forEach(([key, value]) => value ? next.set(key, value) : next.delete(key))
      return next
    }, { replace, preventScrollReset: true })
  }, [setSearchParams])
  const patchUrlRef = useRef(patchUrl)
  useEffect(() => {
    patchUrlRef.current = patchUrl
  }, [patchUrl])
  useEffect(() => {
    pageJumpOpenRef.current = pageJumpOpen
  }, [pageJumpOpen])
  const goToPage = useCallback((nextPage: number) => {
    patchUrl({ page: nextPage > 1 ? String(nextPage) : null })
    setPageJumpOpen(false)
    window.requestAnimationFrame(() => {
      const list = document.querySelector<HTMLElement>('.phone-library-dialog > main')
      if (typeof list?.scrollTo === 'function') list.scrollTo({ top: 0 })
    })
  }, [patchUrl])

  useEffect(() => {
    if (!open) return undefined
    const opener = openerRef.current
    const appRoot = document.getElementById('root')
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    appRoot?.setAttribute('inert', '')
    closeRef.current?.focus()
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      if (pageJumpOpenRef.current) setPageJumpOpen(false)
      else patchUrlRef.current({ library_view: null })
    }
    window.addEventListener('keydown', onKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      appRoot?.removeAttribute('inert')
      window.removeEventListener('keydown', onKeyDown)
      opener?.focus()
    }
  }, [open])

  return (
    <section ref={ref} id="archive-library" className="phone-archive-chapter" data-archive-section="library">
      <PhoneChapterHeading number="06" title="收藏库" />
      {!enabled || query.isLoading ? <PhoneArchiveLoading label="正在打开收藏目录" /> : null}
      {query.isError ? <PhoneArchiveError onRetry={() => void query.refetch()} /> : null}
      {query.data ? (
        <div className="phone-library-preview">
          <div className="phone-library-preview-head"><span>收藏内容</span><strong>{formatArchiveNumber(query.data.total)} 条</strong></div>
          {query.data.items.slice(0, 5).map((item, index) => <PhoneLibraryRow key={item.item_key} item={item} index={index + 1} />)}
          <button ref={openerRef} type="button" className="phone-library-open" onClick={() => patchUrl({ library_view: 'full' }, false)}><SlidersHorizontal />打开完整收藏库</button>
        </div>
      ) : null}

      {open && query.data ? createPortal((
        <div className="phone-library-dialog" role="dialog" aria-modal="true" aria-labelledby="phone-library-title">
          <header>
            <div><h2 id="phone-library-title">收藏库</h2></div>
            <button ref={closeRef} type="button" aria-label="关闭完整收藏库" onClick={() => { setPageJumpOpen(false); patchUrl({ library_view: null }) }}><X /></button>
          </header>
          <div className="phone-library-tabs" role="tablist" aria-label="收藏库类型">
            {(Object.keys(LIBRARY_LABELS) as ArchiveLibraryEntityType[]).map(type => (
              <button key={type} type="button" role="tab" aria-selected={entityType === type} onClick={() => patchUrl({ library: type, page: null, search: null, sort: DEFAULT_LIBRARY_SORT[type] })}>{LIBRARY_LABELS[type]}</button>
            ))}
          </div>
          <div className="phone-library-tools">
            <PhoneLibrarySearch key={`${entityType}:${search}`} initialValue={search} label={LIBRARY_LABELS[entityType]} onSearch={value => patchUrl({ search: value || null, page: null })} />
            <label><span>排序方式</span><select aria-label="排序方式" value={sort} onChange={event => patchUrl({ sort: event.target.value, page: null })}>{LIBRARY_SORTS[entityType].map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
          </div>
          <div className="phone-library-dialog-summary"><span>{search ? `“${search}”` : `全部${LIBRARY_LABELS[entityType]}`}</span><strong>{formatArchiveNumber(query.data.total)} 条</strong></div>
          <main>
            {query.isFetching ? <div className="phone-library-updating">正在更新目录…</div> : null}
            {query.data.items.length ? query.data.items.map((item, index) => <PhoneLibraryRow key={item.item_key} item={item} index={(page - 1) * 10 + index + 1} />) : <p className="phone-library-empty">没有找到匹配的收藏</p>}
          </main>
          <footer aria-label="收藏库分页">
            {pageJumpOpen ? (
              <form
                id="phone-library-page-jump"
                className="phone-library-page-jump"
                onSubmit={(event) => {
                  event.preventDefault()
                  const totalPages = Math.max(query.data.total_pages, 1)
                  const requestedPage = Math.min(Math.max(Number(pageJumpValue) || 1, 1), totalPages)
                  setPageJumpValue(String(requestedPage))
                  goToPage(requestedPage)
                }}
              >
                <label htmlFor="phone-library-page-input">跳转到</label>
                <input
                  id="phone-library-page-input"
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={Math.max(query.data.total_pages, 1)}
                  value={pageJumpValue}
                  onChange={event => setPageJumpValue(event.target.value)}
                />
                <span>/ {Math.max(query.data.total_pages, 1)} 页</span>
                <button type="submit">跳转</button>
              </form>
            ) : null}
            <button type="button" aria-label="上一页" disabled={page <= 1} onClick={() => goToPage(page - 1)}><ChevronLeft /></button>
            <button
              type="button"
              className="phone-library-page-toggle"
              aria-expanded={pageJumpOpen}
              aria-controls={pageJumpOpen ? 'phone-library-page-jump' : undefined}
              onClick={() => {
                if (!pageJumpOpen) setPageJumpValue(String(page))
                setPageJumpOpen(current => !current)
              }}
            >第 {page} / {Math.max(query.data.total_pages, 1)} 页</button>
            <button type="button" aria-label="下一页" disabled={page >= query.data.total_pages} onClick={() => goToPage(page + 1)}><ChevronRight /></button>
          </footer>
        </div>
      ), document.body) : null}
    </section>
  )
}
