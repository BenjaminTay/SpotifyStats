import { X } from 'lucide-react'

export function ReportSkeleton({ onCancel }: { onCancel?: () => void }) {
  return (
    <div className="animate-pulse space-y-3 rounded-[16px] border border-border bg-card/40 p-6 backdrop-blur-[12px]">
      <div className="flex items-center justify-between">
        <div className="h-5 w-36 rounded bg-muted" />
        {onCancel && (
          <button
            onClick={onCancel}
            className="flex animate-none items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.6px] text-muted-foreground/50 transition-colors hover:text-destructive"
          >
            <X className="h-3 w-3" />
            取消
          </button>
        )}
      </div>
      <div className="h-4 w-full rounded bg-muted" />
      <div className="h-4 w-5/6 rounded bg-muted" />
      <div className="h-4 w-full rounded bg-muted" />
      <div className="h-4 w-3/4 rounded bg-muted" />
      <div className="h-4 w-full rounded bg-muted" />
      <div className="h-4 w-4/5 rounded bg-muted" />
    </div>
  )
}
