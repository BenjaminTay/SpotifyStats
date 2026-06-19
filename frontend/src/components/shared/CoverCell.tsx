import { useState, useEffect } from 'react'

const COVER_COLORS = [
  'oklch(0.563 0.18 28.2)',
  'oklch(0.583 0.108 51.4)',
  'oklch(0.623 0.14 79.9)',
  'oklch(0.443 0.065 151.5)',
  'oklch(0.425 0.095 267.8)',
  'oklch(0.47 0.06 330)',
]

export function CoverCell({
  index,
  isNewOrRe = false,
  coverUrl,
  className = 'h-10 w-10',
  label,
}: {
  index: number
  isNewOrRe?: boolean
  coverUrl?: string | null
  className?: string
  label?: string
}) {
  const [imgError, setImgError] = useState(false)
  useEffect(() => { setImgError(false) }, [coverUrl])
  const coverAlt = label ? `${label} 封面` : ''

  if (isNewOrRe) {
    if (coverUrl && !imgError) {
      return (
        <img
          src={coverUrl}
          alt={coverAlt}
          className={`${className} rounded-[8px] object-cover`}
          onError={() => setImgError(true)}
          loading="lazy"
        />
      )
    }
    return (
      <div className={`flex ${className} items-center justify-center rounded-[8px] bg-muted text-base`}>
        <span aria-hidden="true">{'🆕'}</span>
        {coverAlt && <span className="sr-only">{coverAlt}</span>}
      </div>
    )
  }
  if (coverUrl && !imgError) {
    return (
      <img
        src={coverUrl}
        alt={coverAlt}
        className={`${className} rounded-[8px] object-cover`}
        onError={() => setImgError(true)}
        loading="lazy"
      />
    )
  }
  const c = COVER_COLORS[index % COVER_COLORS.length]
  const c2 = COVER_COLORS[(index + 1) % COVER_COLORS.length]
  return (
    <div
      className={`flex ${className} items-center justify-center rounded-[8px] text-base opacity-85`}
      style={{ background: `linear-gradient(135deg, ${c}, ${c2})` }}
    >
      <span aria-hidden="true">🎵</span>
      {coverAlt && <span className="sr-only">{coverAlt}</span>}
    </div>
  )
}
