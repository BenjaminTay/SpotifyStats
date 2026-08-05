import type { MobileEntityRowProps } from './MobileEntityRow'
import { MobileEntityRow } from './MobileEntityRow'
import { MobilePagination } from './MobilePagination'
import { MobileStatePanel } from './MobileStatePanel'

interface MobileRankListProps {
  title?: string
  eyebrow?: string
  rows: MobileEntityRowProps[]
  loading?: boolean
  error?: boolean
  emptyTitle?: string
  onRetry?: () => void
  page?: number
  pageCount?: number
  onPageChange?: (page: number) => void
  hasMore?: boolean
  loadingMore?: boolean
  onLoadMore?: () => void
}

export function MobileRankList({
  title,
  eyebrow,
  rows,
  loading = false,
  error = false,
  emptyTitle,
  onRetry,
  page,
  pageCount,
  onPageChange,
  hasMore,
  loadingMore,
  onLoadMore,
}: MobileRankListProps) {
  const paginationMode = onLoadMore ? 'load-more' : 'pages'

  return (
    <section className="mobile-rank-list">
      {(title || eyebrow) && (
        <header className="mobile-rank-header">
          <div>
            {eyebrow && <p>{eyebrow}</p>}
            {title && <h2>{title}</h2>}
          </div>
          {!loading && !error && <span>{rows.length} 项</span>}
        </header>
      )}
      {loading ? (
        <div className="mobile-rank-state-stack">
          {Array.from({ length: 5 }, (_, index) => <MobileStatePanel key={index} variant="loading" compact />)}
        </div>
      ) : error ? (
        <MobileStatePanel variant="error" actionLabel={onRetry ? '重新加载' : undefined} onAction={onRetry} />
      ) : rows.length === 0 ? (
        <MobileStatePanel variant="empty" title={emptyTitle} />
      ) : (
        <div className="mobile-rank-rows">
          {rows.map((row) => (
            <MobileEntityRow key={`${row.entityType}:${row.rank ?? ''}:${row.title}`} {...row} />
          ))}
        </div>
      )}
      {!loading && !error && rows.length > 0 && (onPageChange || onLoadMore) && (
        <MobilePagination
          mode={paginationMode}
          page={page}
          pageCount={pageCount}
          onPageChange={onPageChange}
          hasMore={hasMore}
          loading={loadingMore}
          onLoadMore={onLoadMore}
        />
      )}
    </section>
  )
}
