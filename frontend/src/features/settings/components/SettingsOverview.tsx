import { CheckCircle2, Database, Link, RefreshCw, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'

function StatusCell({
  icon,
  label,
  value,
  tone = 'neutral',
}: {
  icon: React.ReactNode
  label: string
  value: string
  tone?: 'good' | 'warn' | 'neutral'
}) {
  return (
    <div className="rounded-xl border border-border bg-card/70 p-4">
      <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[1.2px] text-muted-foreground">
        {icon}
        {label}
      </div>
      <div
        className={cn(
          'mt-2 font-sans text-[14px] font-semibold leading-snug',
          tone === 'good' && 'text-green-700 dark:text-green-400',
          tone === 'warn' && 'text-amber-700 dark:text-amber-300',
          tone === 'neutral' && 'text-foreground',
        )}
      >
        {value}
      </div>
    </div>
  )
}

function providerLabel(provider: string): string {
  if (provider === 'deepseek') return 'DeepSeek'
  if (provider === 'openai') return 'OpenAI'
  if (provider === 'anthropic') return 'Anthropic'
  return provider || '未配置'
}

export function SettingsOverview({
  dbRecordCount,
  accountImported,
  spotifyConnected,
  hasLlmKey,
  llmProvider,
  llmModel,
  rebuildPending,
}: {
  dbRecordCount: number
  accountImported: boolean
  spotifyConnected: boolean
  hasLlmKey: boolean
  llmProvider: string
  llmModel: string
  rebuildPending: boolean
}) {
  const dataReady = dbRecordCount > 0 && accountImported

  return (
    <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <StatusCell
        icon={dataReady ? <CheckCircle2 className="size-3.5" /> : <Database className="size-3.5" />}
        label="数据状态"
        value={dataReady ? '数据就绪' : '需要导入'}
        tone={dataReady ? 'good' : 'warn'}
      />
      <StatusCell
        icon={<Link className="size-3.5" />}
        label="Spotify"
        value={spotifyConnected ? '已连接' : '未连接'}
        tone={spotifyConnected ? 'good' : 'neutral'}
      />
      <StatusCell
        icon={<RefreshCw className="size-3.5" />}
        label="统计口径"
        value={rebuildPending ? '有改动待生效' : '统计已生效'}
        tone={rebuildPending ? 'warn' : 'good'}
      />
      <StatusCell
        icon={<Sparkles className="size-3.5" />}
        label="当前模型"
        value={hasLlmKey ? `${providerLabel(llmProvider)} · ${llmModel || '默认模型'}` : '缺少 API Key'}
        tone={hasLlmKey ? 'good' : 'warn'}
      />
    </section>
  )
}
