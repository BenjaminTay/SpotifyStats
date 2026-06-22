import { AlertCircle, CheckCircle2, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function RebuildNotice({
  pending,
  loading,
  message,
  onRebuild,
}: {
  pending: boolean
  loading: boolean
  message: string
  onRebuild: () => void
}) {
  if (!pending && !message) return null

  return (
    <div
      className={cn(
        'sticky top-[73px] z-10 rounded-xl border px-4 py-3 backdrop-blur-sm',
        pending ? 'border-amber-500/30 bg-amber-500/5' : 'border-green-500/30 bg-green-500/5',
      )}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-2.5">
          {pending ? (
            <AlertCircle className="mt-0.5 size-4 shrink-0 text-amber-600 dark:text-amber-300" />
          ) : (
            <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-green-600 dark:text-green-400" />
          )}
          <div>
            <div className="text-[13px] font-semibold text-foreground">
              {pending ? '统计口径有改动待生效' : message}
            </div>
            {pending && (
              <p className="mt-0.5 text-[12px] leading-relaxed text-muted-foreground">
                播放过滤或榜单参数已改变。应用后，所有榜单和统计会按新规则重新计算。
              </p>
            )}
          </div>
        </div>
        {pending && (
          <Button size="sm" onClick={onRebuild} disabled={loading} className="gap-1.5 shrink-0">
            <RefreshCw className={cn('size-3.5', loading && 'animate-spin')} />
            {loading ? '重建中...' : '应用改动并重建统计'}
          </Button>
        )}
      </div>
    </div>
  )
}
