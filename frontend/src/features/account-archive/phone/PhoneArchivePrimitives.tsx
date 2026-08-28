import { Disc3, LoaderCircle, RotateCcw } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useDisplayName } from '@/lib/chinese'

export function PhoneChapterHeading({
  number,
  title,
}: {
  number: string
  title: string
}) {
  return (
    <header className="phone-archive-heading">
      <span>{number}</span>
      <div>
        <h2>{title}</h2>
      </div>
    </header>
  )
}

export function PhoneArchiveLoading({ label = '正在整理这一章' }: { label?: string }) {
  return <div className="phone-archive-loading"><LoaderCircle className="animate-spin" />{label}</div>
}

export function PhoneArchiveError({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="phone-archive-loading phone-archive-error">
      <span>这一章暂时没有打开。</span>
      <button type="button" onClick={onRetry}><RotateCcw />重试</button>
    </div>
  )
}

export function PhoneArchiveUnavailable({ children }: { children: string }) {
  return <p className="phone-archive-unavailable">{children}</p>
}

export function PhoneEntityCard({
  name,
  artist,
  coverUrl,
  href,
  meta,
  ordinal,
}: {
  name: string
  artist: string
  coverUrl: string | null
  href: string | null
  meta?: string
  ordinal?: number
}) {
  const displayTrackName = useDisplayName(name)
  const displayArtistName = useDisplayName(artist)
  const content = (
    <>
      <span className="phone-archive-entity-art">
        {coverUrl ? <img src={coverUrl} alt="" loading="lazy" /> : <Disc3 aria-hidden="true" />}
      </span>
      <span className="phone-archive-entity-copy">
        {ordinal ? <small>{String(ordinal).padStart(2, '0')}</small> : null}
        <strong>{displayTrackName}</strong>
        <span className="phone-archive-entity-details">
          <span>{displayArtistName}</span>
          {meta ? <em>{meta}</em> : null}
        </span>
      </span>
    </>
  )
  return href ? <Link to={href} className="phone-archive-entity">{content}</Link> : <div className="phone-archive-entity">{content}</div>
}
