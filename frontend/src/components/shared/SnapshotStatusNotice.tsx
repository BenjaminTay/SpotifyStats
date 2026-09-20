import type { components } from '@/api/generated/api-types'

type SnapshotState = components['schemas']['SnapshotReadState'] & { build_status?: string }

/** Page-local freshness messaging without exposing backend publication terminology. */
export function SnapshotStatusNotice({ snapshot }: { snapshot?: SnapshotState | null }) {
  if (snapshot?.freshness !== 'last_known_good') return null
  return (
    <p role="status" className="mb-4 rounded-lg border border-border px-4 py-3 text-sm text-muted-foreground">
      {snapshot.build_status === 'failed'
        ? '数据更新暂未完成，当前显示上一次计算结果。'
        : '数据正在更新，当前显示上一次计算结果。'}
    </p>
  )
}
