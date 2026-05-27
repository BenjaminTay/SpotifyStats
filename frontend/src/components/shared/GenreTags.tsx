import { cn } from '@/lib/utils'

const GENRE_COLORS: Record<string, string> = {
  'pop': 'bg-rose-500/10 text-rose-700 dark:text-rose-300 border-rose-500/20',
  'rock': 'bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/20',
  'country': 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/20',
  'folk': 'bg-green-500/10 text-green-700 dark:text-green-300 border-green-500/20',
  'indie': 'bg-sky-500/10 text-sky-700 dark:text-sky-300 border-sky-500/20',
  'synth': 'bg-violet-500/10 text-violet-700 dark:text-violet-300 border-violet-500/20',
  'trap': 'bg-slate-500/10 text-slate-700 dark:text-slate-300 border-slate-500/20',
  'electronic': 'bg-cyan-500/10 text-cyan-700 dark:text-cyan-300 border-cyan-500/20',
  'r&b': 'bg-fuchsia-500/10 text-fuchsia-700 dark:text-fuchsia-300 border-fuchsia-500/20',
  'hip': 'bg-orange-500/10 text-orange-700 dark:text-orange-300 border-orange-500/20',
  'soul': 'bg-pink-500/10 text-pink-700 dark:text-pink-300 border-pink-500/20',
  'jazz': 'bg-blue-500/10 text-blue-700 dark:text-blue-300 border-blue-500/20',
  'alternative': 'bg-teal-500/10 text-teal-700 dark:text-teal-300 border-teal-500/20',
  'dance': 'bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-500/20',
  'soft': 'bg-stone-500/10 text-stone-700 dark:text-stone-300 border-stone-500/20',
}

function genreColor(genre: string): string {
  const lower = genre.toLowerCase()
  for (const [key, cls] of Object.entries(GENRE_COLORS)) {
    if (lower.includes(key)) return cls
  }
  return 'bg-muted text-muted-foreground border-border'
}

interface GenreTagsProps {
  genres: string[]
  className?: string
}

export function GenreTags({ genres, className }: GenreTagsProps) {
  if (!genres.length) return null
  return (
    <div className={cn('flex flex-wrap gap-2', className)}>
      {genres.map((g) => (
        <span
          key={g}
          className={cn(
            'inline-flex items-center rounded-full border px-3 py-1 font-sans text-[12px] font-medium transition-colors',
            genreColor(g),
          )}
        >
          {g}
        </span>
      ))}
    </div>
  )
}
