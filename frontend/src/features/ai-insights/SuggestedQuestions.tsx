interface SuggestedQuestionsProps {
  questions: string[]
  onSelect: (q: string) => void
  disabled: boolean
  isLoading?: boolean
}

function SkeletonPill() {
  return (
    <span className="inline-block h-8 w-24 animate-pulse rounded-full border border-border bg-card/40 backdrop-blur-[8px]" />
  )
}

export function SuggestedQuestions({ questions, onSelect, disabled, isLoading }: SuggestedQuestionsProps) {
  if (isLoading) {
    return (
      <div className="mobile-ai-suggestion-block">
        <p>可以这样问</p>
        <div className="mobile-ai-suggestions flex flex-wrap gap-2">
          <SkeletonPill />
          <SkeletonPill />
          <SkeletonPill />
          <span className="inline-block h-8 w-20 animate-pulse rounded-full border border-border bg-card/40 backdrop-blur-[8px]" />
        </div>
      </div>
    )
  }

  if (!questions.length) return null

  return (
    <div className="mobile-ai-suggestion-block">
      <p>可以这样问</p>
      <div className="mobile-ai-suggestions flex flex-wrap gap-2">
        {questions.map((q) => (
          <button
            key={q}
            disabled={disabled}
            onClick={() => onSelect(q)}
            title={disabled ? 'AI 回答中，请等待' : undefined}
            className="rounded-full border border-border bg-card/40 px-3 py-1.5 text-[12px] font-medium text-muted-foreground backdrop-blur-[8px] transition-colors hover:border-accent-foreground/20 hover:text-foreground disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  )
}
