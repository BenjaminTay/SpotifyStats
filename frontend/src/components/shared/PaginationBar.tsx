import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react'

export function PaginationBar({
  page,
  totalPages,
  totalEntries,
  pageSize,
  onPageChange,
}: {
  page: number
  totalPages: number
  totalEntries: number
  pageSize: number
  onPageChange: (page: number) => void
}) {
  if (totalPages <= 1) return null
  const safePage = Math.min(page, totalPages)
  return (
    <div className="flex items-center justify-between border-t border-border px-7 py-3">
      <span className="font-sans text-[12px] text-muted-foreground tabular-nums">
        显示 {(safePage - 1) * pageSize + 1}–{Math.min(safePage * pageSize, totalEntries)} / 总数 {totalEntries} 条
      </span>
      <div className="flex items-center gap-1">
        <span className="mr-2 font-sans text-[12px] text-muted-foreground tabular-nums">
          {safePage} / {totalPages}
        </span>
        <button
          onClick={() => onPageChange(1)}
          disabled={page <= 1}
          aria-label="第一页"
          className="inline-flex items-center justify-center h-7 w-7 rounded-full text-muted-foreground hover:bg-muted disabled:opacity-30 disabled:cursor-default"
        >
          <ChevronsLeft className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={page <= 1}
          aria-label="上一页"
          className="inline-flex items-center justify-center h-7 w-7 rounded-full text-muted-foreground hover:bg-muted disabled:opacity-30 disabled:cursor-default"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={() => onPageChange(Math.min(totalPages, page + 1))}
          disabled={page >= totalPages}
          aria-label="下一页"
          className="inline-flex items-center justify-center h-7 w-7 rounded-full text-muted-foreground hover:bg-muted disabled:opacity-30 disabled:cursor-default"
        >
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={() => onPageChange(totalPages)}
          disabled={page >= totalPages}
          aria-label="最后一页"
          className="inline-flex items-center justify-center h-7 w-7 rounded-full text-muted-foreground hover:bg-muted disabled:opacity-30 disabled:cursor-default"
        >
          <ChevronsRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}
