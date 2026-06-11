import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'
import { ChatSessionList } from './ChatSessionList'
import type { ChatSession } from '@/types/ai-insights'

interface Props {
  open: boolean
  onClose: () => void
  sessions: ChatSession[]
  activeId: number | null
  onSelect: (id: number) => void
  onDelete: (id: number) => void
  onNew: () => void
  loading: boolean
}

export function ChatSessionDrawer({
  open,
  onClose,
  sessions,
  activeId,
  onSelect,
  onDelete,
  onNew,
  loading,
}: Props) {
  const drawerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', handler)
      document.body.style.overflow = ''
    }
  }, [open, onClose])

  const handleSelect = (id: number) => {
    onSelect(id)
    onClose()
  }

  const handleNew = () => {
    onNew()
    onClose()
  }

  const handleBackdrop = (e: React.MouseEvent) => {
    if (drawerRef.current && !drawerRef.current.contains(e.target as Node)) {
      onClose()
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-40 lg:hidden" onClick={handleBackdrop}>
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
      <div
        ref={drawerRef}
        className="fixed inset-x-0 bottom-0 z-50 max-h-[85vh] rounded-t-2xl border-t border-border bg-background shadow-2xl animate-slide-up"
      >
        <div className="flex items-center justify-center pt-3 pb-1">
          <div className="h-1 w-10 rounded-full bg-muted-foreground/20" />
        </div>
        <div className="flex items-center justify-between px-4 pb-2">
          <h3 className="font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-muted-foreground">
            对话历史
          </h3>
          <button
            onClick={onClose}
            className="rounded-full p-1 text-muted-foreground/50 hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="overflow-y-auto max-h-[calc(85vh-4rem)]">
          <ChatSessionList
            sessions={sessions}
            activeId={activeId}
            onSelect={handleSelect}
            onDelete={onDelete}
            onNew={handleNew}
            loading={loading}
          />
        </div>
      </div>
    </div>
  )
}
