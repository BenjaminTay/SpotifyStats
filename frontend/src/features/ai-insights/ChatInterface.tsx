import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import rehypeSanitize from 'rehype-sanitize'
import { Send } from 'lucide-react'

import { useAskQuestion, useSuggestedQuestions } from '@/hooks/useAiInsights'
import { SuggestedQuestions } from './SuggestedQuestions'
import { AiDisclaimer } from './AiInsightsPrimitives'
import type { ChatMessage } from '@/types/ai-insights'

export function ChatInterface() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const { ask, asking } = useAskQuestion()
  const { questions } = useSuggestedQuestions()

  const handleSend = async () => {
    const q = input.trim()
    if (!q || asking) return
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: q }])

    const history = messages.slice(-5)
    try {
      const result = await ask({ question: q, conversation_history: history })
      setMessages((prev) => [...prev, { role: 'assistant', content: result.answer }])
    } catch {
      setMessages((prev) => [...prev, { role: 'assistant', content: '抱歉，回答生成失败，请稍后重试。' }])
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Chat messages */}
      <div className="min-h-[300px] max-h-[500px] overflow-y-auto space-y-4 rounded-[16px] border border-border bg-card/40 p-4 backdrop-blur-[12px]">
        {messages.length === 0 && (
          <div className="flex flex-col items-center gap-4 py-12 text-center">
            <p className="text-[14px] text-muted-foreground">
              向我提问，了解你的听歌数据
            </p>
            <SuggestedQuestions
              questions={questions}
              onSelect={(q) => {
                setInput(q)
              }}
              disabled={false}
            />
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-[13px] leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-accent-foreground text-card'
                  : 'bg-muted/50 text-muted-foreground'
              }`}
            >
              {msg.role === 'assistant' ? (
                <div className="prose prose-sm max-w-none text-[13px] [&_strong]:text-foreground">
                  <ReactMarkdown rehypePlugins={[rehypeSanitize]}>{msg.content}</ReactMarkdown>
                </div>
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}

        {asking && (
          <div className="flex justify-start">
            <div className="rounded-2xl bg-muted/50 px-4 py-2.5">
              <span className="inline-flex gap-1">
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/50 [animation-delay:0ms]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/50 [animation-delay:150ms]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground/50 [animation-delay:300ms]" />
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入问题，如「我今年听最多的艺人是谁？」"
          disabled={asking}
          maxLength={500}
          className="flex-1 rounded-full border border-border bg-card/40 px-4 py-2.5 text-[13px] text-foreground placeholder:text-muted-foreground/50 backdrop-blur-[8px] outline-none transition-colors focus:border-accent-foreground/30 disabled:opacity-50"
        />
        <button
          onClick={handleSend}
          disabled={asking || !input.trim()}
          className="flex h-10 w-10 items-center justify-center rounded-full bg-accent-foreground text-card transition-opacity hover:opacity-85 disabled:opacity-40"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>

      <AiDisclaimer />
    </div>
  )
}
