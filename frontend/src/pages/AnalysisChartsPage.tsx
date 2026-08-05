import { useState } from 'react'
import { Search, X } from 'lucide-react'
import { EntityTabs, MetricToggle, useAnalysisQueryState } from '@/components/shared/AnalysisControls'
import { GlassCard } from '@/components/shared/GlassCard'
import { PersonalRankTable } from '@/components/shared/StatsTables'
import { Skeleton } from '@/components/ui/skeleton'
import { analysisApi, useAnalysisFilters, useApiData } from '@/hooks/useAnalysis'
import { MobilePersonalRankList } from '@/features/mobile/analysis/MobilePersonalRankList'
import { useViewportMode } from '@/hooks/useViewportMode'

const ENTITY_TITLE = {
  track: '歌曲榜',
  album: '专辑榜',
  artist: '艺人榜',
}

export function AnalysisChartsPage() {
  const isPhone = useViewportMode() === 'phone'
  const [searchQuery, setSearchQuery] = useState('')
  const { filters, loading: filtersLoading } = useAnalysisFilters()
  const { metric, entity, setQuery, apiParams } = useAnalysisQueryState('track')
  const { data, loading } = useApiData(
    () => analysisApi.charts(filters, {
      ...apiParams,
      entity,
      metric,
      limit: 250,
      include_compilations: filters.include_compilations,
    }),
    [filters, apiParams, entity, metric],
    !filtersLoading,
  )

  if (isPhone) {
    return (
      <MobilePersonalRankList
        data={data}
        loading={loading}
        entity={entity}
        metric={metric}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onEntityChange={(next) => {
          setSearchQuery('')
          setQuery({ entity: next })
        }}
        onMetricChange={(next) => setQuery({ metric: next })}
      />
    )
  }

  return (
    <div className="space-y-7">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-2 font-sans text-[11px] font-bold uppercase tracking-[1.5px] text-accent-foreground">Playback Ranking</p>
          <h2 className="font-serif text-[34px] font-bold leading-tight">播放排行</h2>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <MetricToggle metric={metric} onChange={(next) => setQuery({ metric: next })} />
        </div>
      </div>

      <GlassCard className="p-5">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 className="font-serif text-2xl font-semibold">{ENTITY_TITLE[entity]}</h3>
            <p className="mt-1 text-[13px] text-muted-foreground">
              {data ? `${data.period.label} · 共 ${data.total.toLocaleString('zh-CN')} 条记录` : '正在加载'}
            </p>
          </div>
          <div className="flex w-full flex-wrap items-center justify-start gap-3 sm:w-auto sm:justify-end">
            <label className="relative w-full sm:w-[260px]">
              <span className="sr-only">在当前播放排行中搜索</span>
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                type="search"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="在当前榜单中搜索"
                className="h-9 w-full rounded-full border border-border bg-card/70 pl-9 pr-9 font-sans text-[13px] outline-none transition-colors placeholder:text-muted-foreground focus:border-accent-foreground"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  aria-label="清除播放排行搜索"
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </label>
            <EntityTabs entity={entity} onChange={(next) => {
              setSearchQuery('')
              setQuery({ entity: next })
            }} />
          </div>
        </div>
        {loading || !data ? (
          <Skeleton className="h-[520px] rounded-[12px]" />
        ) : (
          <PersonalRankTable rows={data.rows} entity={entity} metric={metric} searchQuery={searchQuery} />
        )}
      </GlassCard>
    </div>
  )
}
