import { Sun, Moon } from 'lucide-react'
import { useTheme } from '@/hooks/useTheme'
import { cn } from '@/lib/utils'

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()

  return (
    <div className="flex items-center gap-1 rounded-full border border-border bg-card p-1 transition-[background,border] duration-400">
      <button
        onClick={() => setTheme('light')}
        className={cn(
          'flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-[11px] font-semibold transition-[color,background,box-shadow] duration-250',
          theme === 'light'
            ? 'bg-card text-foreground shadow-sm'
            : 'text-muted-foreground hover:text-foreground',
        )}
      >
        <Sun className="h-3.5 w-3.5" />
        白日
      </button>
      <button
        onClick={() => setTheme('dark')}
        className={cn(
          'flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-[11px] font-semibold transition-[color,background,box-shadow] duration-250',
          theme === 'dark'
            ? 'bg-card text-foreground shadow-sm'
            : 'text-muted-foreground hover:text-foreground',
        )}
      >
        <Moon className="h-3.5 w-3.5" />
        夜晚
      </button>
    </div>
  )
}
