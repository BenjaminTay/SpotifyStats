import { EntityTabs, MetricToggle, useAnalysisQueryState } from '@/components/shared/AnalysisControls'
import { GlassCard } from '@/components/shared/GlassCard'
import { PersonalRankTable } from '@/components/shared/StatsTables'
import { Skeleton } from '@/components/ui/skeleton'
import { analysisApi, useAnalysisFilters, useApiData } from '@/hooks/useAnalysis'

const ENTITY_TITLE = {
  track: '歌曲榜',
  album: '专辑榜',
  artist: '艺人榜',
}

export function AnalysisChartsPage() {
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

  return (
    <div className="space-y-7">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-2 font-sans text-[11px] font-bold uppercase tracking-[1.5px] text-accent-foreground">Personal Charts</p>
          <h2 className="font-serif text-[34px] font-bold leading-tight">个人排行榜</h2>
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
          <div className="flex flex-wrap items-center gap-3">
            <EntityTabs entity={entity} onChange={(next) => setQuery({ entity: next })} />
          </div>
        </div>
        {loading || !data ? (
          <Skeleton className="h-[520px] rounded-[12px]" />
        ) : (
          <PersonalRankTable rows={data.rows} entity={entity} metric={metric} />
        )}
      </GlassCard>
    </div>
  )
}
