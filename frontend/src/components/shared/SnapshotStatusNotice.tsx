import { useCallback, useSyncExternalStore } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type { components } from '@/api/generated/api-types'

type SnapshotPayload = {
  snapshot?: (components['schemas']['SnapshotReadState'] & { build_status?: string }) | null
  pages?: SnapshotPayload[]
}

/** Show publication freshness for currently observed Home/Billboard queries. */
export function SnapshotStatusNotice() {
  const cache = useQueryClient().getQueryCache()
  const subscribe = useCallback((notify: () => void) => cache.subscribe(notify), [cache])
  const getSnapshot = useCallback(() => {
    let state = ''
    for (const query of cache.getAll()) {
      if (query.getObserversCount() === 0) continue
      const data = query.state.data as SnapshotPayload | undefined
      for (const item of [data, ...(data?.pages ?? [])]) {
        if (item?.snapshot?.freshness === 'last_known_good') {
          if (item.snapshot.build_status === 'failed') return 'failed'
          state = 'warming'
        }
      }
    }
    return state
  }, [cache])
  const stale = useSyncExternalStore(subscribe, getSnapshot, () => '')
  if (!stale) return null
  return (
    <p role="status" className="mb-4 rounded-lg border border-border px-4 py-3 text-sm text-muted-foreground">
      {stale === 'failed' ? '最新数据构建失败，正在显示上次发布的数据。' : '正在显示上次发布的数据，最新数据发布后可刷新查看。'}
    </p>
  )
}
