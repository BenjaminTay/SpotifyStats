import { Clock3, X } from 'lucide-react'
import { Link } from 'react-router-dom'

import { MUSIC_SEARCH_KIND_LABELS } from './musicSearchUtils'
import type { RecentMusicEntity } from './recentMusicEntities'

export function RecentMusicEntityList({
  items,
  onClear,
  onOpen,
  compact = false,
}: {
  items: RecentMusicEntity[]
  onClear: () => void
  onOpen?: () => void
  compact?: boolean
}) {
  if (items.length === 0) return null
  return (
    <section className="overflow-hidden rounded-lg border border-border bg-card/80" aria-label="最近查看的音乐">
      <header className="flex min-h-11 items-center gap-2 border-b border-border px-3 text-xs font-semibold text-muted-foreground">
        <Clock3 className="size-3.5" aria-hidden="true" />
        <span>最近查看</span>
        <button type="button" onClick={onClear} className="ml-auto inline-flex min-h-9 items-center gap-1 rounded px-2 hover:bg-muted" aria-label="清除最近查看">
          <X className="size-3" aria-hidden="true" />
          清除
        </button>
      </header>
      <ul className="divide-y divide-border/70">
        {items.map((item) => (
          <li key={item.entity_key}>
            <Link
              to={item.href}
              onClick={onOpen}
              className={`flex min-h-11 items-center gap-3 px-3 transition-colors hover:bg-muted/40 ${compact ? 'py-2' : 'py-2.5'}`}
            >
              <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-semibold text-muted-foreground">
                {MUSIC_SEARCH_KIND_LABELS[item.kind]}
              </span>
              <span className="min-w-0 truncate text-sm font-medium text-foreground">{item.label}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
