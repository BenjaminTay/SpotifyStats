import type { KeyboardEvent } from 'react'
import { Brain, Send } from 'lucide-react'

interface ChatComposerProps {
  value: string
  disabled: boolean
  thinkingMode: boolean
  onChange: (value: string) => void
  onThinkingModeChange: (value: boolean) => void
  onSend: () => void
}

export function ChatComposer({
  value,
  disabled,
  thinkingMode,
  onChange,
  onThinkingModeChange,
  onSend,
}: ChatComposerProps) {
  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      onSend()
    }
  }

  return (
    <div className="border-t border-border/40 px-4 py-3">
      <div className="mb-2 flex items-center justify-end">
        <button
          type="button"
          role="switch"
          aria-label="思考模式"
          aria-checked={thinkingMode}
          disabled={disabled}
          onClick={() => onThinkingModeChange(!thinkingMode)}
          className={[
            'inline-flex h-7 items-center gap-1.5 rounded-full border px-2.5 text-[11px] font-semibold transition-colors',
            thinkingMode
              ? 'border-accent-foreground/25 bg-accent-foreground text-card'
              : 'border-border/60 bg-card/30 text-muted-foreground hover:text-foreground',
            disabled ? 'opacity-40' : '',
          ].join(' ')}
        >
          <Brain className="h-3.5 w-3.5" />
          <span>思考模式</span>
        </button>
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入问题，如「我今年听最多的艺人是谁？」"
          disabled={disabled}
          maxLength={500}
          className="flex-1 rounded-full border border-border/60 bg-card/30 px-4 py-2.5 text-[13px] text-foreground placeholder:text-muted-foreground/40 backdrop-blur-[8px] outline-none transition-colors focus:border-accent-foreground/20 disabled:opacity-40"
        />
        <button
          onClick={onSend}
          disabled={disabled || !value.trim()}
          aria-label="发送问题"
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent-foreground text-card transition-opacity hover:opacity-85 disabled:opacity-30"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
