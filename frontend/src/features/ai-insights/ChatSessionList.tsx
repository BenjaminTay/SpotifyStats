import { useState } from 'react'
import { MessageSquare, Plus, Trash2, X } from 'lucide-react'
import type { ChatSession } from '@/types/ai-insights'

interface Props {
  sessions: ChatSession[]
  activeId: number | null
  onSelect: (id: number) => void
  onDelete: (id: number) => void
  onNew: () => void
  loading: boolean
}

function relativeTime(isoString: string): string {
  const then = new Date(isoString).getTime()
  const now = Date.now()
  const minutes = Math.floor((now - then) / 60000)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days} 天前`
  const weeks = Math.floor(days / 7)
  if (weeks < 5) return `${weeks} 周前`
  const months = Math.floor(days / 30)
  return `${months} 个月前`
}

export function ChatSessionList({ sessions, activeId, onSelect, onDelete, onNew, loading }: Props) {
  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <h3 className="font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-muted-foreground">
          对话历史
        </h3>
        <button
          onClick={onNew}
          className="flex items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.6px] text-muted-foreground/60 transition-colors hover:text-foreground"
        >
          <Plus className="h-3 w-3" />
          新对话
        </button>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto px-2 pb-4">
        {loading && sessions.length === 0 && (
          <div className="space-y-2 px-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-14 animate-pulse rounded-lg bg-muted/30" />
            ))}
          </div>
        )}

        {!loading && sessions.length === 0 && (
          <div className="flex flex-col items-center gap-2 py-12 text-center">
            <MessageSquare className="h-5 w-5 text-muted-foreground/20" />
            <p className="text-[12px] text-muted-foreground/50">暂无对话记录</p>
          </div>
        )}

        {sessions.map((session) => (
          <SessionItem
            key={session.id}
            session={session}
            isActive={session.id === activeId}
            onSelect={() => onSelect(session.id)}
            onDelete={() => onDelete(session.id)}
          />
        ))}
      </div>
    </div>
  )
}

function SessionItem({
  session,
  isActive,
  onSelect,
  onDelete,
}: {
  session: ChatSession
  isActive: boolean
  onSelect: () => void
  onDelete: () => void
}) {
  const [confirming, setConfirming] = useState(false)

  return (
    <button
      onClick={onSelect}
      className={`group w-full text-left px-2.5 py-2 rounded-lg transition-colors ${
        isActive
          ? 'bg-accent-foreground/8 border border-accent-foreground/15'
          : 'border border-transparent hover:bg-muted/40'
      }`}
    >
      <div className="flex items-start justify-between gap-1">
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-medium text-foreground/85">
            {session.title}
          </p>
          <div className="mt-0.5 flex items-center gap-2 text-[10px] text-muted-foreground/40">
            <span>{session.message_count} 条消息</span>
            <span>·</span>
            <span>{relativeTime(session.updated_at)}</span>
          </div>
        </div>

        {confirming ? (
          <div className="flex items-center gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
            <button
              onClick={() => { onDelete(); setConfirming(false) }}
              className="rounded px-1.5 py-0.5 text-[10px] font-semibold text-destructive hover:bg-destructive/10"
            >
              删除
            </button>
            <button
              onClick={() => setConfirming(false)}
              className="rounded p-0.5 text-muted-foreground/40 hover:text-foreground"
            >
              <X className="h-3 w-3" />
            </button>
          </div>
        ) : (
          <button
            onClick={(e) => { e.stopPropagation(); setConfirming(true) }}
            className="opacity-0 group-hover:opacity-100 rounded p-0.5 text-muted-foreground/30 hover:text-destructive transition-opacity shrink-0"
          >
            <Trash2 className="h-3 w-3" />
          </button>
        )}
      </div>
    </button>
  )
}
