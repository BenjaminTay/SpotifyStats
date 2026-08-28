import { useState, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import type { EntityListItem, VersusEntityData } from '@/types/billboard'
import { ENTITY_COLORS, MAX_QUEUE_SIZE } from './versusData'
import { displayName, useDisplayName, useChineseTextVersion } from '@/lib/chinese'

// ── Skeleton ──

export function VersusSkeleton() {
  return (
    <div className="space-y-6">
      <div className="h-6 w-32 animate-pulse rounded bg-muted/40" />
      <div className="flex flex-wrap gap-4">
        <div className="h-14 flex-1 min-w-[200px] animate-pulse rounded-lg bg-muted/40" />
        <div className="h-14 flex-1 min-w-[200px] animate-pulse rounded-lg bg-muted/40" />
      </div>
      <div className="h-[360px] animate-pulse rounded-lg bg-muted/40" />
    </div>
  )
}

// ── Entity Card (index-based color) ──

export function VersusEntityCard({
  entity,
  detailLink,
  index,
}: {
  entity: VersusEntityData | null
  detailLink?: string
  index: number
}) {
  const renderedName = useDisplayName(entity?.name ?? '')
  if (!entity) return null
  const color = ENTITY_COLORS[index % ENTITY_COLORS.length]
  const bg = `${color}0F`
  const border = `${color}40`

  return (
    <div
      className="flex items-center gap-3 rounded-xl border p-3"
      style={{ backgroundColor: bg, borderColor: border }}
    >
      {entity.cover_url && (
        <img
          src={entity.cover_url}
          alt=""
          className="h-12 w-12 flex-shrink-0 rounded-lg object-cover"
        />
      )}
      <div className="min-w-0 flex-1">
        <p className="truncate font-serif text-base font-semibold">{renderedName}</p>
        {detailLink && (
          <Link
            to={detailLink}
            className="inline-block mt-0.5 text-[11px] text-muted-foreground transition-colors hover:text-accent-foreground"
          >
            查看详情 →
          </Link>
        )}
      </div>
    </div>
  )
}

// ── Searchable Add Combobox ──

export function SearchableAddSelect({
  items,
  alreadySelected,
  onAdd,
  placeholder,
  disabled,
}: {
  items: EntityListItem[]
  alreadySelected: EntityListItem[]
  onAdd: (item: EntityListItem) => void
  placeholder: string
  disabled: boolean
}) {
  useChineseTextVersion()
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const selectedSet = new Set(
    alreadySelected.map((s) => {
      if (s.track_id != null) return `t:${s.track_id}`
      return `a:${s.artist_name}|${s.album_name ?? ''}`
    })
  )

  function isAlreadyAdded(item: EntityListItem): boolean {
    if (item.track_id != null) return selectedSet.has(`t:${item.track_id}`)
    return selectedSet.has(`a:${item.artist_name}|${item.album_name ?? ''}`)
  }

  const filtered = search
    ? items.filter(
        (item) =>
          item.display.toLowerCase().includes(search.toLowerCase()) &&
          !isAlreadyAdded(item),
      ).slice(0, 50)
    : items.filter((item) => !isAlreadyAdded(item)).slice(0, 50)

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => !disabled && setOpen(!open)}
        disabled={disabled}
        className="flex w-full items-center justify-between rounded-lg border border-border bg-card px-3 py-2.5 text-left text-[13px] transition-colors hover:border-accent-foreground/20 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        <span className="text-muted-foreground">
          {disabled ? `已达上限 (${MAX_QUEUE_SIZE} 个)` : placeholder}
        </span>
        <span className="ml-2 text-[10px] text-muted-foreground">▼</span>
      </button>
      {open && !disabled && (
        <div className="absolute z-50 mt-1 w-full rounded-lg border border-border bg-card shadow-lg">
          <input
            type="text"
            autoFocus
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="输入关键词搜索..."
            className="w-full border-b border-border bg-transparent px-3 py-2 text-[13px] outline-none placeholder:text-muted-foreground"
          />
          <div className="max-h-52 overflow-auto">
            {filtered.length === 0 ? (
              <p className="px-3 py-4 text-center text-[12px] text-muted-foreground">无匹配结果</p>
            ) : (
              filtered.map((item) => (
                <button
                  key={item.display}
                  type="button"
                  onClick={() => {
                    onAdd(item)
                    // Keep the current query and result list open so adjacent
                    // matches can be added without repeating the search.
                    if (alreadySelected.length + 1 >= MAX_QUEUE_SIZE) setOpen(false)
                  }}
                  className="w-full flex items-center justify-between px-3 py-2 text-left text-[13px] transition-colors hover:bg-muted"
                >
                  <span className="truncate">{displayName(item.display)}</span>
                  <span className="ml-2 text-[10px] text-muted-foreground flex-shrink-0">+ 添加</span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Entity Queue (ordered list with reorder / delete) ──

export function EntityQueue({
  items,
  onRemove,
  onMoveUp,
  onMoveDown,
}: {
  items: EntityListItem[]
  onRemove: (index: number) => void
  onMoveUp: (index: number) => void
  onMoveDown: (index: number) => void
}) {
  useChineseTextVersion()
  if (items.length === 0) return null

  return (
    <div className="space-y-2">
      <p className="text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
        对比队列 ({items.length}/{MAX_QUEUE_SIZE})
      </p>
      {items.map((item, i) => {
        const color = ENTITY_COLORS[i % ENTITY_COLORS.length]
        return (
          <div
            key={`${item.display}-${i}`}
            className="flex items-center gap-3 rounded-lg border border-border/60 bg-card px-3 py-2"
          >
            <span
              className="flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white"
              style={{ backgroundColor: color }}
            >
              {i + 1}
            </span>
            <span className="flex-1 truncate text-[13px] font-medium">{displayName(item.display)}</span>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => onMoveUp(i)}
                disabled={i === 0}
                title="上移"
                className="px-1.5 py-0.5 text-[10px] rounded transition-colors hover:bg-muted disabled:opacity-25 disabled:cursor-not-allowed"
              >
                ↑
              </button>
              <button
                type="button"
                onClick={() => onMoveDown(i)}
                disabled={i === items.length - 1}
                title="下移"
                className="px-1.5 py-0.5 text-[10px] rounded transition-colors hover:bg-muted disabled:opacity-25 disabled:cursor-not-allowed"
              >
                ↓
              </button>
              <button
                type="button"
                onClick={() => onRemove(i)}
                title="移除"
                className="ml-1 px-1.5 py-0.5 text-[10px] rounded text-red-400 transition-colors hover:bg-red-50 dark:hover:bg-red-950"
              >
                ✕
              </button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
