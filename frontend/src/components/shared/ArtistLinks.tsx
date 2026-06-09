import { Link } from 'react-router-dom'
import { displayName } from '@/lib/chinese'
import { billboardDetailLink } from '@/lib/navigation'
import { cn } from '@/lib/utils'

/** 多艺人独立可点击链接，单艺人时退化为普通链接 */
export function ArtistLinks({
  artistName,
  artistNames,
  className,
}: {
  artistName: string
  artistNames?: string[]
  className?: string
}) {
  const names =
    artistNames && artistNames.length > 1 ? artistNames : [artistName]

  return (
    <span className={cn('inline-flex flex-wrap items-center gap-x-[2px]', className)}>
      {names.map((name, idx) => (
        <span key={name}>
          <Link
            to={billboardDetailLink(
              `/music/artists/${encodeURIComponent(name)}`,
            )}
            className="transition-colors hover:text-accent-foreground"
          >
            {displayName(name)}
          </Link>
          {idx < names.length - 1 && (
            <span className="select-none text-muted-foreground/40">{' · '}</span>
          )}
        </span>
      ))}
    </span>
  )
}
