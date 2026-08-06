import { useState } from 'react'
import { Plus, Sparkles } from 'lucide-react'
import { BillboardSubNav } from '@/components/shared/BillboardSubNav'
import { GlassCard } from '@/components/shared/GlassCard'
import { useEntityLists, useVersus } from '@/hooks/useBillboard'
import { useAnalysisFilters } from '@/hooks/useAnalysis'
import type { EntityListItem, VersusResponse } from '@/types/billboard'
import type { VersusKind } from './versusData'
import { MAX_QUEUE_SIZE } from './versusData'
import { VersusSkeleton } from './versusPrimitives'
import { VersusSelectorSection } from './VersusSelectorSection'
import { VersusScoreboardSection } from './VersusScoreboardSection'
import { VersusChartSection } from './VersusChartSection'
import { VersusReleaseCycleSection } from './VersusReleaseCycleSection'
import { buildBillboardContextParams, buildPersonalStatsParams } from '../billboardContext'
import { MobilePageHeader } from '@/components/mobile'
import { useViewportMode } from '@/hooks/useViewportMode'
import { cn } from '@/lib/utils'

const KIND_LABELS: Record<VersusKind, string> = { track: '歌曲', album: '专辑', artist: '艺人' }

let cachedKind: VersusKind = 'track'
const cachedQueues: Record<VersusKind, EntityListItem[]> = { track: [], album: [], artist: [] }

function buildDetailLink(kind: VersusKind, item: EntityListItem): string | null {
  switch (kind) {
    case 'track':
      return `/music/tracks/${item.track_id}`
    case 'album':
      return `/music/albums/${encodeURIComponent(item.album_name ?? '')}?artist=${encodeURIComponent(item.artist_name ?? '')}`
    case 'artist':
      return `/music/artists/${encodeURIComponent(item.artist_name ?? '')}`
  }
}

function buildVersusBody(kind: VersusKind, queue: EntityListItem[]): Record<string, unknown> {
  switch (kind) {
    case 'track':
      return { track_ids: queue.map((q) => q.track_id).filter(Boolean) }
    case 'album':
      return { albums: queue.map((q) => ({ album_name: q.album_name, artist_name: q.artist_name })) }
    case 'artist':
      return { artist_names: queue.map((q) => q.artist_name).filter(Boolean) }
  }
}

function cacheQueue(k: VersusKind, q: EntityListItem[]) {
  cachedQueues[k] = q
}

function entityKey(item: EntityListItem): string {
  if (item.track_id != null) return `track:${item.track_id}`
  return `${item.artist_name ?? ''}:${item.album_name ?? ''}`
}

export function VersusExperience() {
  const isPhone = useViewportMode() === 'phone'
  const [kind, setKindState] = useState<VersusKind>(cachedKind)
  const [queue, setQueue] = useState<EntityListItem[]>(cachedQueues[cachedKind])
  const { filters, loading: filtersLoading } = useAnalysisFilters()
  const billboardParams = buildBillboardContextParams(filters)
  const personalStatsParams = buildPersonalStatsParams(filters)

  const { data: lists } = useEntityLists(billboardParams, undefined, !filtersLoading)

  // Build POST body and fetch
  const body = queue.length >= 2 ? buildVersusBody(kind, queue) : null
  const versus = useVersus(kind, filtersLoading ? null : body, billboardParams)

  const versusData: VersusResponse | null = versus.data
  const versusLoading = versus.loading
  const versusError = versus.error

  function setKind(k: VersusKind) {
    // Save current queue, restore target kind's queue
    cacheQueue(cachedKind, queue)
    cachedKind = k
    setKindState(k)
    setQueue(cachedQueues[k])
  }

  function handleAdd(item: EntityListItem) {
    if (queue.length >= MAX_QUEUE_SIZE) return
    const next = [...queue, item]
    cacheQueue(cachedKind, next)
    setQueue(next)
  }

  function handleRemove(index: number) {
    const next = [...queue]
    next.splice(index, 1)
    cacheQueue(cachedKind, next)
    setQueue(next)
  }

  function handleMoveUp(index: number) {
    if (index === 0) return
    const next = [...queue]
    ;[next[index - 1], next[index]] = [next[index], next[index - 1]]
    cacheQueue(cachedKind, next)
    setQueue(next)
  }

  function handleMoveDown(index: number) {
    if (index >= queue.length - 1) return
    const next = [...queue]
    ;[next[index], next[index + 1]] = [next[index + 1], next[index]]
    cacheQueue(cachedKind, next)
    setQueue(next)
  }

  const entityNames = queue.map((q) => q.display)
  const readyToCompare = queue.length >= 2
  const itemsForKind = kind === 'track' ? lists?.tracks : kind === 'album' ? lists?.albums : lists?.artists
  const selectedKeys = new Set(queue.map(entityKey))
  const quickAddItems = (itemsForKind ?? []).filter((item) => !selectedKeys.has(entityKey(item))).slice(0, 2)

  return (
    <div className={cn(isPhone && 'mobile-m4-page')} data-mobile-page={isPhone ? 'billboard-versus' : undefined}>
      {!isPhone && <BillboardSubNav active="versus" />}

      {isPhone ? (
        <MobilePageHeader
          eyebrow="Chart / Versus"
          title="对决"
          description={`分三步选择 2–${MAX_QUEUE_SIZE} 个实体，再用纵向成绩卡比较榜单、播放与发行周期。`}
        />
      ) : <section className="mt-6 mb-6">
        <p className="mb-4 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
          Chart / Versus
        </p>
        <h1 className="font-serif text-[44px] font-bold leading-[1.06] tracking-[-1.2px]">
          对决
        </h1>
        <p className="mt-2 text-[13px] text-muted-foreground">
          选取 2-{MAX_QUEUE_SIZE} 个单曲、专辑或艺人，对比榜单表现、个人播放与发行周期
        </p>
      </section>}

      {/* Selector */}
      <GlassCard className={cn('relative z-10 mb-8 p-6', isPhone && 'mobile-versus-builder-card')}>
          <VersusSelectorSection
          key={kind}
          kind={kind}
          onKindChange={setKind}
          items={lists ?? { tracks: [], albums: [], artists: [] }}
          queue={queue}
          onAdd={handleAdd}
          onRemove={handleRemove}
          onMoveUp={handleMoveUp}
          onMoveDown={handleMoveDown}
        />
      </GlassCard>

      {/* Idle */}
      {!readyToCompare && (
        isPhone ? (
          <section className="mobile-versus-idle" aria-label="对决准备">
            <span className="mobile-versus-idle-icon" aria-hidden="true"><Sparkles /></span>
            <div>
              <strong>{queue.length === 0 ? `先添加 2 个${KIND_LABELS[kind]}` : `再添加 1 个${KIND_LABELS[kind]}`}</strong>
              <p>{queue.length === 0 ? '可从上方搜索，也可以直接用下面的建议开始。' : '加入后会自动生成纵向成绩卡。'}</p>
            </div>
            {quickAddItems.length > 0 && (
              <div className="mobile-versus-quick-add">
                {quickAddItems.map((item) => (
                  <button key={entityKey(item)} type="button" onClick={() => handleAdd(item)}>
                    <Plus aria-hidden="true" />
                    <span>{item.display}</span>
                  </button>
                ))}
              </div>
            )}
          </section>
        ) : (
          <div className="py-12 text-center">
            <p className="text-[13px] text-muted-foreground">
              {queue.length === 0 ? `请搜索并添加${KIND_LABELS[kind]}开始对决` : `还需添加 ${2 - queue.length} 个${KIND_LABELS[kind]}开始对决`}
            </p>
          </div>
        )
      )}

      {/* Loading / Error */}
      {readyToCompare && versusLoading && <VersusSkeleton />}

      {readyToCompare && versusError && (
        <GlassCard className="p-8 text-center">
          <p className="text-[13px] text-red-500">{versusError}</p>
        </GlassCard>
      )}

      {readyToCompare && versusData && !versusData.found && (
        <GlassCard className="p-8 text-center">
          <p className="text-[13px] text-muted-foreground">
            {versusData.reason ?? '无法完成对比'}
          </p>
        </GlassCard>
      )}

      {/* Results */}
      {readyToCompare && versusData && versusData.found && versusData.entities && (
        <div className="space-y-8">
          <VersusScoreboardSection
            entities={versusData.entities}
            kind={kind}
            queue={queue}
            buildDetailLink={(item) => buildDetailLink(kind, item)}
            personalStatsParams={personalStatsParams}
          />

          <VersusChartSection
            rankHistories={versusData.entities.map((e) => e.rank_history)}
            names={entityNames}
          />

          {kind === 'album' && queue.length >= 2 && (
            <VersusReleaseCycleSection
              albums={queue.map((q) => ({
                albumName: q.album_name ?? '',
                artistName: q.artist_name ?? '',
                name: q.display,
              }))}
              billboardParams={billboardParams}
            />
          )}
        </div>
      )}
      {isPhone && readyToCompare && <button type="button" className="mobile-versus-adjust" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>调整对决对象</button>}
    </div>
  )
}
