import { Link } from 'react-router-dom'
import { AlertCircle, Sparkles } from 'lucide-react'

export function LlmNotConfiguredState() {
  return (
    <div className="flex flex-col items-center gap-4 py-20 text-center">
      <Sparkles className="h-10 w-10 text-muted-foreground/60" />
      <div className="space-y-1">
        <p className="font-serif text-[20px] font-semibold">AI 功能尚未配置</p>
        <p className="text-[14px] text-muted-foreground">
          请在设置中配置 LLM API Key 后使用 AI 洞察功能
        </p>
      </div>
      <Link
        to="/settings"
        className="rounded-full bg-accent-foreground px-5 py-2 text-[13px] font-semibold text-card transition-opacity hover:opacity-85"
      >
        前往设置
      </Link>
    </div>
  )
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center gap-3 py-16 text-center">
      <AlertCircle className="h-8 w-8 text-muted-foreground/50" />
      <p className="text-[14px] text-muted-foreground">{message}</p>
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center gap-4 py-16 text-center">
      <AlertCircle className="h-8 w-8 text-accent-foreground" />
      <p className="text-[14px] text-muted-foreground">{message}</p>
      <button
        onClick={onRetry}
        className="rounded-full border border-border bg-card/40 px-4 py-1.5 text-[12px] font-semibold uppercase tracking-[1px] text-muted-foreground backdrop-blur-[8px] transition-colors hover:text-foreground"
      >
        重试
      </button>
    </div>
  )
}

export function AiDisclaimer() {
  return (
    <p className="text-center text-[11px] text-muted-foreground/60">
      由 AI 生成，仅供参考
    </p>
  )
}
