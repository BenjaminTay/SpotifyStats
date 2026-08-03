import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import type { AlbumDetailResponse, ArtistDetailResponse } from '@/types/billboard'
import { displayName } from '@/lib/chinese'
import { cn } from '@/lib/utils'
import { formatAlbumKind, formatArtistFollowers } from './MusicDetailFormatters'

function formatAlbumReleaseDate(iso: string): string {
  const [y, m, d] = iso.split('-')
  const months = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
  ]
  const mi = parseInt(m) - 1
  if (mi < 0 || mi >= 12) return iso
  return `${parseInt(d)} ${months[mi]} ${y}`
}

export type MusicDetailTabOption<T extends string> = {
  key: T
  label: string
}

export function ArtistDetailHero({
  data,
  onBack,
}: {
  data: ArtistDetailResponse
  onBack: () => void
}) {
  return (
    <section className="mb-6">
      <button
        onClick={onBack}
        className="mb-4 inline-flex items-center gap-1.5 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-muted-foreground transition-colors hover:text-accent-foreground"
      >
        <ArrowLeft className="h-3 w-3" />
        Music / 艺人详情
      </button>
      <div className="flex min-w-0 flex-col gap-4 sm:flex-row sm:items-start sm:gap-6">
        {data.cover_url && (
          <img
            src={data.cover_url}
            alt={data.artist_name}
            style={{ width: 120, height: 120 }}
            className="h-[120px] w-[120px] flex-shrink-0 rounded-full object-cover shadow-lg"
          />
        )}
        <div className="min-w-0 max-w-full">
          <h1 className="break-words font-serif text-[44px] font-bold leading-[1.06] tracking-normal">
            {displayName(data.artist_name)}
          </h1>
          {data.meta && (
            <div className="mt-2 font-sans text-[14px] text-muted-foreground">
              {data.meta.genres && data.meta.genres.length > 0 && (
                <p>
                  {data.meta.genres
                    .slice(0, 4)
                    .map((genre) => genre.charAt(0).toUpperCase() + genre.slice(1))
                    .join(' · ')}
                </p>
              )}
              {[
                data.meta.followers != null &&
                  `${formatArtistFollowers(data.meta.followers)} followers`,
              ].filter(Boolean).length > 0 && (
                <p>
                  {[
                    data.meta.followers != null &&
                      `${formatArtistFollowers(data.meta.followers)} followers`,
                  ]
                    .filter(Boolean)
                    .join(' · ')}
                </p>
              )}
              {data.meta.popularity != null && (
                <div className="mt-1.5 flex min-w-0 flex-wrap items-center gap-2">
                  <span className="font-sans text-[12px] text-muted-foreground">Popularity</span>
                  <span className="inline-block h-[5px] w-[120px] rounded-[3px] bg-muted align-middle">
                    <span
                      className="block h-full rounded-[3px] bg-accent-foreground"
                      style={{ width: `${data.meta.popularity}%` }}
                    />
                  </span>
                  <span className="font-sans text-[12px] font-semibold tabular-nums">
                    {data.meta.popularity}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

export function AlbumDetailHero({
  data,
  onBack,
  projectTrackCount,
}: {
  data: AlbumDetailResponse
  onBack: () => void
  projectTrackCount?: number
}) {
  const showDualTrackCount =
    projectTrackCount != null &&
    data.meta?.total_tracks != null &&
    projectTrackCount !== data.meta.total_tracks

  return (
    <section className="mb-6">
      <button
        onClick={onBack}
        className="mb-4 inline-flex items-center gap-1.5 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-muted-foreground transition-colors hover:text-accent-foreground"
      >
        <ArrowLeft className="h-3 w-3" />
        Music / 专辑详情
      </button>
      <div className="flex min-w-0 flex-col gap-4 sm:flex-row sm:items-start sm:gap-6">
        {data.cover_url && (
          <img
            src={data.cover_url}
            alt={data.album_name}
            style={{ width: 120, height: 120 }}
            className="h-[120px] w-[120px] flex-shrink-0 rounded-[12px] object-cover shadow-lg"
          />
        )}
        <div className="min-w-0 max-w-full">
          <h1 className="break-words font-serif text-[44px] font-bold leading-[1.06] tracking-normal">
            {displayName(data.album_name)}
          </h1>
          <p className="mt-2 font-sans text-[17px] text-muted-foreground">
            <Link
              to={`/music/artists/${encodeURIComponent(data.artist_name)}`}
              className="transition-colors hover:text-accent-foreground"
            >
              {displayName(data.artist_name)}
            </Link>
          </p>
          {data.meta && (
            <p className="mt-1 break-words font-sans text-[14px] text-muted-foreground">
              {[
                data.meta.album_type && formatAlbumKind(data.meta.album_type),
                data.meta.release_date && formatAlbumReleaseDate(data.meta.release_date),
                showDualTrackCount
                  ? `${data.meta.total_tracks} tracks (${projectTrackCount} total)`
                  : data.meta.total_tracks && `${data.meta.total_tracks} tracks`,
                data.meta.label,
              ]
                .filter(Boolean)
                .join(' · ')}
            </p>
          )}
        </div>
      </div>
    </section>
  )
}

export function DetailTabs<T extends string>({
  tabs,
  activeTab,
  onChange,
}: {
  tabs: MusicDetailTabOption<T>[]
  activeTab: T
  onChange: (tab: T) => void
}) {
  return (
    <div className="mb-6 flex gap-7 border-b border-border">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          onClick={() => onChange(tab.key)}
          className={cn(
            '-mb-px cursor-pointer border-none bg-transparent px-0 pb-2.5 font-sans text-[13px] font-medium transition-[color,border] duration-200',
            'border-b-2',
            activeTab === tab.key
              ? 'border-accent-foreground font-semibold text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground',
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}
