export type FeedTab = 'highlights' | 'all'

interface FeedToggleProps {
  active: FeedTab
  onChange: (tab: FeedTab) => void
  highlightsCount?: number
  allCount?: number
}

export function FeedToggle({ active, onChange, highlightsCount, allCount }: FeedToggleProps) {
  return (
    <div className="border-b border-white/10 bg-background">
      <div className="flex items-center h-[53px] gap-2">
        <button
          type="button"
          onClick={() => onChange('highlights')}
          className={`flex items-center gap-1.5 px-4 py-1.5 rounded-full text-[14px] font-medium transition-all ${
            active === 'highlights'
              ? 'bg-accent-foreground text-primary-foreground shadow-lg shadow-accent-foreground/20'
              : 'text-muted-foreground hover:text-foreground hover:bg-white/[0.06]'
          }`}
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
          </svg>
          精选
          {highlightsCount != null && (
            <span className="text-[11px] opacity-70 tabular-nums">{highlightsCount}</span>
          )}
        </button>
        <button
          type="button"
          onClick={() => onChange('all')}
          className={`flex items-center gap-1.5 px-4 py-1.5 rounded-full text-[14px] font-medium transition-all ${
            active === 'all'
              ? 'bg-accent-foreground text-primary-foreground shadow-lg shadow-accent-foreground/20'
              : 'text-muted-foreground hover:text-foreground hover:bg-white/[0.06]'
          }`}
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="8" y1="6" x2="21" y2="6" />
            <line x1="8" y1="12" x2="21" y2="12" />
            <line x1="8" y1="18" x2="21" y2="18" />
            <line x1="3" y1="6" x2="3.01" y2="6" />
            <line x1="3" y1="12" x2="3.01" y2="12" />
            <line x1="3" y1="18" x2="3.01" y2="18" />
          </svg>
          全部
          {allCount != null && (
            <span className="text-[11px] opacity-70 tabular-nums">{allCount}</span>
          )}
        </button>
      </div>
    </div>
  )
}
