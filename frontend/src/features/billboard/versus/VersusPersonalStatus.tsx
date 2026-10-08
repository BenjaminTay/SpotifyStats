import type { VersusPersonalState } from './useVersusPersonal'

export function VersusPersonalStatus({ personal }: { personal: VersusPersonalState }) {
  return <div className="flex flex-wrap gap-3 text-[12px] text-muted-foreground" aria-live="polite">
    {(['stats', 'ranks'] as const).map((group) => {
      const query = personal[group]
      const label = group === 'stats' ? '个人播放' : '个人排名'
      const mismatch = group === 'ranks' && personal.mismatched
      const error = query.isError || (mismatch && !query.isFetching && !personal.stats.isFetching)
      return <span key={group}>
        {error ? `${label}暂不可用` : query.isFetching ? `${label}${query.data ? '更新中…' : '加载中…'}` : ''}
        {error && <button type="button" className="ml-2 min-h-11 min-w-11 rounded-full px-3 text-accent-foreground hover:bg-accent/10" onClick={() => void query.refetch()} aria-label={`重试${label}`}>重试</button>}
      </span>
    })}
  </div>
}
