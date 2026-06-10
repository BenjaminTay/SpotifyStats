export interface TimePeriod {
  label: string
  date_from: string | null
  date_to: string | null
}

function yearPeriod(year: number): TimePeriod {
  return {
    label: String(year),
    date_from: `${year}-01-01`,
    date_to: `${year}-12-31`,
  }
}

function recentYearPeriod(): TimePeriod {
  const end = new Date()
  const start = new Date(end)
  start.setFullYear(start.getFullYear() - 1)
  return {
    label: '近一年',
    date_from: start.toISOString().slice(0, 10),
    date_to: end.toISOString().slice(0, 10),
  }
}

const ALL_PERIOD: TimePeriod = { label: '全部', date_from: null, date_to: null }

function buildPeriods(): TimePeriod[] {
  const currentYear = new Date().getFullYear()
  const periods: TimePeriod[] = [ALL_PERIOD, recentYearPeriod()]
  for (let y = currentYear; y >= 2021; y--) {
    periods.push(yearPeriod(y))
  }
  return periods
}

const PERIODS = buildPeriods()

interface TimeFilterProps {
  selected: TimePeriod
  onChange: (period: TimePeriod) => void
}

export function TimeFilter({ selected, onChange }: TimeFilterProps) {
  return (
    <div className="flex items-center gap-1.5 py-2 border-b border-white/10 overflow-x-auto scrollbar-none">
      {PERIODS.map(p => (
        <button
          key={p.label}
          type="button"
          onClick={() => onChange(p)}
          className={`px-3 py-1.5 rounded-full text-[12px] font-medium shrink-0 transition-all border ${
            selected.label === p.label
              ? 'bg-accent-foreground text-primary-foreground border-accent-foreground shadow-sm'
              : 'text-muted-foreground border-white/10 hover:border-white/25 hover:text-foreground'
          }`}
        >
          {p.label}
        </button>
      ))}
    </div>
  )
}

export { ALL_PERIOD, PERIODS }
