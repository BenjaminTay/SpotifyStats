import { useNavigate, useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'

const pages = [
  { path: '/', label: '总览仪表盘' },
  { path: '/billboard', label: 'Billboard 周榜' },
]

export function PageSwitcher() {
  const navigate = useNavigate()
  const { pathname } = useLocation()

  return (
    <div className="mb-9 flex w-fit overflow-hidden rounded-[12px] border border-border transition-colors duration-400">
      {pages.map((page, i) => (
        <button
          key={page.path}
          onClick={() => navigate(page.path)}
          className={cn(
            'cursor-pointer border-none px-6 py-2.5 font-sans text-[13px] font-medium transition-[background,color] duration-200',
            pathname === page.path
              ? 'bg-card font-semibold text-foreground'
              : 'bg-transparent text-muted-foreground hover:text-foreground',
            i === 0 && 'border-r border-border',
          )}
        >
          {page.label}
        </button>
      ))}
    </div>
  )
}
