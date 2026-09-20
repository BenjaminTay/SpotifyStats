import type { GovernanceSnapshot } from '@/types/governance-snapshot'

export function GovernanceSnapshotNotice({ snapshot }: { snapshot?: GovernanceSnapshot | null }) {
  if (!snapshot || snapshot.freshness === 'current') return null
  return <p role="status" className="rounded-lg border border-border p-3 text-sm text-muted-foreground">
    {snapshot.build_status === 'failed' ? '本次检查构建失败，显示上次检查结果。' : '显示上次检查结果，当前数据尚待重新检查。'}
    {' '}检查时间：{new Date(snapshot.checked_at).toLocaleString('zh-CN')}。
    {' '}请在本机完成治理检查重建后重新读取。
  </p>
}
