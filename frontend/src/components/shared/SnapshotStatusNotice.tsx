import type { components } from '@/api/generated/api-types'

type SnapshotState = components['schemas']['SnapshotReadState'] & { build_status?: string }

/** Keep non-blocking snapshot refreshes accessible without changing page layout. */
export function SnapshotStatusNotice({ snapshot }: { snapshot?: SnapshotState | null }) {
  if (snapshot?.freshness !== 'last_known_good') return null
  return (
    <span role="status" aria-live="polite" className="sr-only">
      {snapshot.build_status === 'failed'
        ? '后台更新暂未完成，当前内容仍可正常使用。'
        : '内容正在后台更新。'}
    </span>
  )
}
