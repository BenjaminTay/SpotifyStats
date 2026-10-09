import type { ReactNode } from 'react'
import { AlertCircle } from 'lucide-react'
import { SnapshotUnavailableError } from '@/api/errors'
import { Skeleton } from '@/components/ui/skeleton'

export function DetailViewState({ hasData, error, fetching, retry, label = '榜单成绩', children }: {
  hasData: boolean
  error: Error | null
  fetching: boolean
  retry: () => unknown
  label?: string
  children: ReactNode
}) {
  const unavailable = error instanceof SnapshotUnavailableError
  return <>
    {error && <div role="alert" className="mb-6 rounded-2xl border border-border bg-card p-5">
      <div className="flex items-center gap-2 font-semibold"><AlertCircle className="size-4 text-accent-foreground" />
        {unavailable ? `${label}暂时不可用` : `${label}加载失败`}
      </div>
      <p className="mt-2 text-sm text-muted-foreground">{unavailable ? error.message : '请检查网络后重试。'}</p>
      {hasData && <p className="mt-2 text-xs text-muted-foreground">仍显示上次成功加载的结果。</p>}
      <button type="button" onClick={retry} disabled={fetching} className="mt-3 min-h-11 rounded-full border border-border px-5 text-sm font-semibold disabled:opacity-50">
        {fetching ? '重新加载中…' : '重新加载'}
      </button>
    </div>}
    {hasData ? <>
      {fetching && <p role="status" className="mb-4 text-sm text-muted-foreground">正在更新{label}…</p>}
      {children}
    </> : !error && <Skeleton aria-label={`正在加载${label}`} className="h-[420px] w-full rounded-[16px]" />}
  </>
}
