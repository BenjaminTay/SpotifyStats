import { useCallback, useRef, useEffect, type KeyboardEvent } from 'react'
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
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const autoResize = useCallback(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }, [])

  useEffect(() => {
    autoResize()
  }, [value, autoResize])

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      onSend()
    }
  }

  return (
    <div data-mobile-input-mode="true" className="border-t border-border/40 px-4 py-3">
      <div className="mb-2 flex items-center justify-end gap-2">
        <span
          className="text-[10px] text-muted-foreground/40"
          title="开启后 AI 将展示推理过程，回答更深入但耗时更长"
        >
          Shift+Enter 换行
        </span>
        <button
          type="button"
          role="switch"
          aria-label="思考模式"
          aria-checked={thinkingMode}
          disabled={disabled}
          onClick={() => onThinkingModeChange(!thinkingMode)}
          title="开启后 AI 将展示推理过程，回答更深入但耗时更长"
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
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入问题，如「我今年听最多的艺人是谁？」"
          disabled={disabled}
          maxLength={500}
          rows={1}
          className="flex-1 resize-none rounded-2xl border border-border/60 bg-card/30 px-4 py-2.5 text-[13px] leading-relaxed text-foreground placeholder:text-muted-foreground/40 backdrop-blur-[8px] outline-none transition-colors focus:border-accent-foreground/20 disabled:opacity-40"
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
