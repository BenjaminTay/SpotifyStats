interface SuggestedQuestionsProps {
  questions: string[]
  onSelect: (q: string) => void
  disabled: boolean
}

export function SuggestedQuestions({ questions, onSelect, disabled }: SuggestedQuestionsProps) {
  if (!questions.length) return null

  return (
    <div className="flex flex-wrap gap-2">
      {questions.map((q) => (
        <button
          key={q}
          disabled={disabled}
          onClick={() => onSelect(q)}
          className="rounded-full border border-border bg-card/40 px-3 py-1.5 text-[12px] font-medium text-muted-foreground backdrop-blur-[8px] transition-colors hover:border-accent-foreground/20 hover:text-foreground disabled:opacity-50"
        >
          {q}
        </button>
      ))}
    </div>
  )
}
