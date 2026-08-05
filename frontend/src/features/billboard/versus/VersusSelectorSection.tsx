import type { EntityListItem } from '@/types/billboard'
import type { VersusKind } from './versusData'
import { KIND_TABS, MAX_QUEUE_SIZE } from './versusData'
import { SearchableAddSelect, EntityQueue } from './versusPrimitives'

interface VersusSelectorSectionProps {
  kind: VersusKind
  onKindChange: (kind: VersusKind) => void
  items: { tracks: EntityListItem[]; albums: EntityListItem[]; artists: EntityListItem[] }
  queue: EntityListItem[]
  onAdd: (item: EntityListItem) => void
  onRemove: (index: number) => void
  onMoveUp: (index: number) => void
  onMoveDown: (index: number) => void
}

export function VersusSelectorSection({
  kind,
  onKindChange,
  items,
  queue,
  onAdd,
  onRemove,
  onMoveUp,
  onMoveDown,
}: VersusSelectorSectionProps) {
  const currentItems = kind === 'track' ? items.tracks : kind === 'album' ? items.albums : items.artists
  const placeholder = kind === 'track' ? '搜索单曲以添加...' : kind === 'album' ? '搜索专辑以添加...' : '搜索艺人以添加...'
  const atLimit = queue.length >= MAX_QUEUE_SIZE

  return (
    <div className="mobile-versus-selector">
      {/* Entity type tabs */}
      <div className="mb-5 flex items-center gap-1 mobile-versus-kind">
        {KIND_TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => onKindChange(tab.key)}
            className="rounded-full px-4 py-1.5 text-[12px] font-semibold transition-colors cursor-pointer"
            style={{
              backgroundColor: kind === tab.key ? 'var(--accent-foreground)' : 'transparent',
              color: kind === tab.key ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Search + Queue side-by-side to avoid dropdown overlap */}
      <div className="flex gap-6 items-start mobile-versus-builder">
        {/* Search */}
        <div className="w-[38%] flex-shrink-0 mobile-versus-search">
          <SearchableAddSelect
            items={currentItems}
            alreadySelected={queue}
            onAdd={onAdd}
            placeholder={placeholder}
            disabled={atLimit}
          />
        </div>

        {/* Queue */}
        <div className="flex-1 min-w-0 mobile-versus-queue">
          <EntityQueue
            items={queue}
            onRemove={onRemove}
            onMoveUp={onMoveUp}
            onMoveDown={onMoveDown}
          />
        </div>
      </div>
    </div>
  )
}
