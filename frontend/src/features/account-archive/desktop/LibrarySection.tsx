import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Disc3, FolderOpen, Search } from 'lucide-react'

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
import {
  ArchiveError,
  ArchiveLoading,
  ArchiveSectionHeading,
} from '@/features/account-archive/components/ArchivePrimitives'
import type { ArchiveLibraryEntityType } from '@/types/accountArchive'
import { cn } from '@/lib/utils'

function LibrarySearch({
  initialValue,
  label,
  onSearch,
}: {
  initialValue: string
  label: string
  onSearch: (value: string) => void
}) {
  const [value, setValue] = useState(initialValue)
  return (
    <form
      className="archive-library-search"
      role="search"
      onSubmit={(event) => {
        event.preventDefault()
        onSearch(value.trim())
      }}
    >
      <Search aria-hidden="true" />
      <label className="sr-only" htmlFor="archive-library-search">搜索当前收藏库</label>
      <input
        id="archive-library-search"
        value={value}
        maxLength={120}
        placeholder={`搜索${label}`}
        onChange={(event) => setValue(event.target.value)}
      />
      <button type="submit">搜索</button>
    </form>
  )
}

export function LibrarySection() {
  const { ref, enabled } = useArchiveSection()
  const [searchParams, setSearchParams] = useSearchParams()
  const entityType = isLibraryEntity(searchParams.get('library'))
    ? searchParams.get('library') as ArchiveLibraryEntityType
    : 'tracks'
  const page = Math.max(Number(searchParams.get('page')) || 1, 1)
  const search = searchParams.get('search') ?? ''
  const sort = librarySortFor(entityType, searchParams.get('sort'))
  const query = useArchiveLibrary({ entityType, page, limit: 20, search, sort }, enabled)

  const patchUrl = (patch: Record<string, string | null>) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      next.set('section', 'library')
      Object.entries(patch).forEach(([key, value]) => {
        if (!value) next.delete(key)
        else next.set(key, value)
      })
      return next
    }, { replace: true, preventScrollReset: true })
  }

  return (
    <section ref={ref} id="archive-library" className="archive-chapter" data-archive-section="library">
      <ArchiveSectionHeading
        number="06"
        title="收藏库"
      />
      <div className="archive-library-shell">
        <div className="archive-library-toolbar">
          <div className="archive-library-tabs" role="tablist" aria-label="收藏库类型">
            {(Object.keys(LIBRARY_LABELS) as ArchiveLibraryEntityType[]).map((type) => (
              <button
                type="button"
                role="tab"
                aria-selected={entityType === type}
                className={cn(entityType === type && 'active')}
                key={type}
                onClick={() => patchUrl({
                  library: type,
                  page: null,
                  sort: DEFAULT_LIBRARY_SORT[type],
                })}
              >
                {LIBRARY_LABELS[type]}
              </button>
            ))}
          </div>
          <LibrarySearch
            key={`${entityType}:${search}`}
            initialValue={search}
            label={LIBRARY_LABELS[entityType]}
            onSearch={(value) => patchUrl({ search: value || null, page: null })}
          />
          <label className="archive-library-sort">
            <span>排序</span>
            <select value={sort} onChange={(event) => patchUrl({ sort: event.target.value, page: null })}>
              {LIBRARY_SORTS[entityType].map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>
        </div>

        {!enabled || query.isLoading ? <ArchiveLoading label="正在打开收藏目录" /> : null}
        {query.isError && <ArchiveError onRetry={() => void query.refetch()} />}
        {query.data && (
          <>
            <div className="archive-library-summary">
              <span>{search ? `“${search}”` : `全部${LIBRARY_LABELS[entityType]}`}</span>
              <strong>{formatArchiveNumber(query.data.total)} 条</strong>
            </div>
            {query.data.items.length === 0 ? (
              <div className="archive-library-empty"><FolderOpen /><span>没有找到匹配的收藏</span></div>
            ) : (
              <div className="archive-library-list">
                {query.data.items.map((item, index) => {
                  const cover = 'cover_url' in item ? item.cover_url : null
                  const href = 'deep_link' in item ? item.deep_link : null
                  const name = item.entity_type === 'track'
                    ? item.track_name
                    : item.entity_type === 'album'
                      ? item.album_name
                      : item.entity_type === 'artist'
                        ? item.artist_name
                        : item.playlist_name
                  const secondary = item.entity_type === 'track' || item.entity_type === 'album'
                    ? item.artist_name
                    : item.entity_type === 'artist'
                      ? '收藏艺人'
                      : `${formatArchiveNumber(item.track_count)} 首曲目${item.preview_tracks[0] ? ` · ${item.preview_tracks[0].track_name}` : ''}`
                  const meta = item.entity_type === 'track'
                    ? formatArchiveDate(item.added_date)
                    : item.entity_type === 'playlist'
                      ? formatArchiveDate(item.last_modified_date)
                      : LIBRARY_LABELS[`${item.entity_type}s` as ArchiveLibraryEntityType]
                  const content = (
                    <>
                      <span className="archive-library-index">{String((page - 1) * 20 + index + 1).padStart(3, '0')}</span>
                      <span className="archive-library-cover">
                        {cover ? <img src={cover} alt="" loading="lazy" /> : <Disc3 aria-hidden="true" />}
                      </span>
                      <span className="archive-library-copy"><strong>{name}</strong><small>{secondary}</small></span>
                      <span className="archive-library-meta">{meta}</span>
                    </>
                  )
                  return href ? (
                    <Link to={href} className="archive-library-row" key={item.item_key}>{content}</Link>
                  ) : (
                    <div className="archive-library-row" key={item.item_key}>{content}</div>
                  )
                })}
              </div>
            )}
            <div className="archive-pagination" aria-label="收藏库分页">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => patchUrl({ page: String(page - 1) })}
                aria-label="上一页"
              ><ChevronLeft /></button>
              <span>第 {page} / {Math.max(query.data.total_pages, 1)} 页</span>
              <button
                type="button"
                disabled={page >= query.data.total_pages}
                onClick={() => patchUrl({ page: String(page + 1) })}
                aria-label="下一页"
              ><ChevronRight /></button>
            </div>
          </>
        )}
      </div>
    </section>
  )
}
