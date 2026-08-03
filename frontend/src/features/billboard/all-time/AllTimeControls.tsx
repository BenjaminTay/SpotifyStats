import { Columns3, RotateCcw, Search, X } from 'lucide-react'

import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { cn } from '@/lib/utils'
import type { AllTimeRow, ColumnDef, ColumnGroup } from './allTimeData'

const GROUP_ORDER: ColumnGroup[] = ['榜单核心', '歌曲相关', '专辑相关', '个人数据']

interface Props {
  query: string
  onQueryChange: (value: string) => void
  columns: ColumnDef<AllTimeRow>[]
  visibleColumnIds: string[]
  onVisibleColumnIdsChange: (ids: string[]) => void
  onRestoreRecommended: () => void
}

export function AllTimeControls({
  query,
  onQueryChange,
  columns,
  visibleColumnIds,
  onVisibleColumnIdsChange,
  onRestoreRecommended,
}: Props) {
  const visible = new Set(visibleColumnIds)
  const configurable = columns.filter((column) => !column.fixed)

  function toggleColumn(key: string, checked: boolean) {
    const next = checked
      ? [...visibleColumnIds, key]
      : visibleColumnIds.filter((id) => id !== key)
    onVisibleColumnIdsChange([...new Set(next)])
  }

  return (
    <div className="flex min-w-0 w-full flex-wrap items-center gap-2 sm:w-auto xl:flex-1 xl:flex-nowrap">
      <Popover>
        <PopoverTrigger asChild>
          <button
            type="button"
            aria-label="选择总榜显示字段"
            className="inline-flex h-9 items-center gap-1.5 rounded-full border border-border bg-card/70 px-3 font-sans text-[12px] font-medium text-foreground transition-colors hover:bg-muted"
          >
            <Columns3 className="h-4 w-4" />
            字段
          </button>
        </PopoverTrigger>
        <PopoverContent
          align="end"
          collisionPadding={12}
          className="flex max-h-[40dvh] w-[min(340px,calc(100vw-24px))] flex-col overflow-hidden p-3 sm:max-h-[calc(100dvh-24px)]"
        >
          <div className="mb-3 flex shrink-0 items-center justify-between gap-3">
            <div>
              <p className="font-sans text-[13px] font-semibold">显示字段</p>
              <p className="font-sans text-[11px] text-muted-foreground">当前排名和名称固定显示，其余选择会自动记忆</p>
            </div>
            <button
              type="button"
              onClick={onRestoreRecommended}
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 font-sans text-[11px] text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              恢复推荐显示
            </button>
          </div>
          <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
            {GROUP_ORDER.map((group) => {
              const groupColumns = configurable.filter((column) => column.group === group)
              if (groupColumns.length === 0) return null
              return (
                <fieldset key={group}>
                  <legend className="mb-1.5 font-sans text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground">
                    {group}
                  </legend>
                  <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
                    {groupColumns.map((column) => (
                      <label
                        key={column.key}
                        className={cn(
                          'flex min-h-8 cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 font-sans text-[12px] transition-colors hover:bg-muted',
                          visible.has(column.key) ? 'text-foreground' : 'text-muted-foreground',
                        )}
                      >
                        <input
                          type="checkbox"
                          checked={visible.has(column.key)}
                          onChange={(event) => toggleColumn(column.key, event.target.checked)}
                          className="h-3.5 w-3.5 accent-[var(--accent-foreground)]"
                        />
                        <span>{column.label}</span>
                      </label>
                    ))}
                  </div>
                </fieldset>
              )
            })}
          </div>
        </PopoverContent>
      </Popover>

      <label className="relative min-w-[180px] flex-1 xl:max-w-[300px]">
        <span className="sr-only">在当前总榜中搜索</span>
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          type="search"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="在当前榜单中搜索"
          className="h-9 w-full rounded-full border border-border bg-card/70 pl-9 pr-9 font-sans text-[13px] outline-none transition-colors placeholder:text-muted-foreground focus:border-accent-foreground"
        />
        {query && (
          <button
            type="button"
            onClick={() => onQueryChange('')}
            aria-label="清除总榜搜索"
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </label>
    </div>
  )
}
