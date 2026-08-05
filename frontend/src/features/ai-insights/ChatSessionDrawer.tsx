import { ChatSessionList } from './ChatSessionList'
import type { ChatSession } from '@/types/ai-insights'
import { MobileBottomSheet } from '@/components/mobile'

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
  const handleSelect = (id: number) => {
    onSelect(id)
    onClose()
  }

  const handleNew = () => {
    onNew()
    onClose()
  }

  return (
    <MobileBottomSheet
      open={open}
      onOpenChange={(next) => { if (!next) onClose() }}
      eyebrow="AI / Conversation"
      title="对话历史"
      description="切换历史对话，或开始一个新问题。"
      dataSheet="ai-history"
    >
      <ChatSessionList
        sessions={sessions}
        activeId={activeId}
        onSelect={handleSelect}
        onDelete={onDelete}
        onNew={handleNew}
        loading={loading}
      />
    </MobileBottomSheet>
  )
}
