import type { ReactNode } from 'react'

interface Props {
  filters: ReactNode
  fieldsSearch: ReactNode
  pagination: ReactNode
}

export function AllTimeToolbar({ filters, fieldsSearch, pagination }: Props) {
  return (
    <div
      data-testid="all-time-toolbar"
      className="mb-3 flex flex-col gap-3 xl:flex-row xl:items-center xl:flex-nowrap"
    >
      <div data-toolbar-part="filters" className="flex min-w-0 shrink-0 flex-wrap items-center gap-3">
        {filters}
      </div>
      <div data-toolbar-part="fields-search" className="min-w-0 w-full xl:flex-1">
        {fieldsSearch}
      </div>
      <div data-toolbar-part="pagination" className="flex shrink-0 justify-end xl:ml-auto">
        {pagination}
      </div>
    </div>
  )
}
