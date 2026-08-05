import { ChevronLeft, ChevronRight } from 'lucide-react'

import { cn } from '@/lib/utils'

interface MobilePaginationProps {
  mode?: 'pages' | 'load-more'
  page?: number
  pageCount?: number
  totalLabel?: string
  onPageChange?: (page: number) => void
  hasMore?: boolean
  loading?: boolean
  onLoadMore?: () => void
  className?: string
}

export function MobilePagination({
  mode = 'pages',
  page = 1,
  pageCount = 1,
  totalLabel,
  onPageChange,
  hasMore = false,
  loading = false,
  onLoadMore,
  className,
}: MobilePaginationProps) {
  if (mode === 'load-more') {
    return (
      <div className={cn('mobile-pagination mobile-pagination-load-more', className)}>
        {hasMore ? (
          <button
            type="button"
            className="mobile-secondary-button mobile-pagination-more"
            disabled={loading}
            onClick={onLoadMore}
          >
            {loading ? '正在加载…' : '加载更多'}
          </button>
        ) : (
          <p className="mobile-pagination-end">— 已经到底了 —</p>
        )}
      </div>
    )
  }

  return (
    <nav className={cn('mobile-pagination', className)} aria-label="列表分页">
      <button
        type="button"
        className="mobile-pagination-button"
        disabled={page <= 1 || loading}
        onClick={() => onPageChange?.(page - 1)}
      >
        <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        上一页
      </button>
      <p className="mobile-pagination-status" aria-live="polite">
        <strong>{page}</strong> / {Math.max(pageCount, 1)}
        {totalLabel && <span>{totalLabel}</span>}
      </p>
      <button
        type="button"
        className="mobile-pagination-button"
        disabled={page >= pageCount || loading}
        onClick={() => onPageChange?.(page + 1)}
      >
        下一页
        <ChevronRight className="h-4 w-4" aria-hidden="true" />
      </button>
    </nav>
  )
}
