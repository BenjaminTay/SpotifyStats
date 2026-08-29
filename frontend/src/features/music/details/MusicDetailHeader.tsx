import { Link } from 'react-router-dom'
import { ArrowLeft, ChevronDown, Fingerprint, GitMerge, ListMusic, Settings2 } from 'lucide-react'
import type { AlbumDetailResponse, ArtistDetailResponse, TrackDetailResponse } from '@/types/billboard'
import { displayName, useChineseTextVersion } from '@/lib/chinese'
import { cn } from '@/lib/utils'
import { formatAlbumKind, formatArtistFollowers } from './MusicDetailFormatters'
import { CapabilityGate } from '@/components/capabilities/CapabilityGate'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'

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

function formatTrackDuration(ms: number): string {
  const totalSec = Math.floor(ms / 1000)
  return `${Math.floor(totalSec / 60)}:${String(totalSec % 60).padStart(2, '0')}`
}

export function TrackDetailHero({
  data,
  trackId,
  onBack,
}: {
  data: TrackDetailResponse
  trackId: string
  onBack: () => void
}) {
  useChineseTextVersion()
  const artists = data.artist_names?.length ? data.artist_names : [data.artist_name]
  const returnTo = `/music/tracks/${trackId}`
  const representativeTrackId = data.representative_track_id ?? data.track_id
  const artistName = data.primary_artist_name ?? artists[0] ?? data.artist_name
  const renderedTrackName = displayName(data.track_name)
  return (
    <section className="mb-6">
      <button
        onClick={onBack}
        className="mb-4 inline-flex items-center gap-1.5 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-muted-foreground transition-colors hover:text-accent-foreground"
      >
        <ArrowLeft className="h-3 w-3" />
        Music / 单曲详情
      </button>
      <div className="flex min-w-0 flex-col gap-4 sm:flex-row sm:items-start sm:gap-6">
        {data.cover_url && (
          <img src={data.cover_url} alt={renderedTrackName} className="h-[120px] w-[120px] flex-shrink-0 rounded-[12px] object-cover shadow-lg" />
        )}
        <div className="min-w-0 max-w-full flex-1">
          <div className="flex min-w-0 items-start justify-between gap-3">
            <h1 className="min-w-0 break-words font-serif text-[44px] font-bold leading-[1.06] tracking-normal">
              {renderedTrackName}
            </h1>
            <CapabilityGate require={['editing', 'metadata_governance']}>
              <Popover>
                <PopoverTrigger asChild>
                  <button
                    type="button"
                    aria-label={`编辑 ${renderedTrackName} 的曲目信息`}
                    title="选择要编辑的内容"
                    className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-full border border-border px-2.5 text-[11px] font-semibold text-muted-foreground transition hover:border-accent-foreground/40 hover:text-foreground"
                  >
                    <Settings2 className="size-3.5" />
                    <span className="hidden md:inline">编辑</span>
                    <ChevronDown className="size-3" />
                  </button>
                </PopoverTrigger>
                <PopoverContent align="end" sideOffset={8} className="w-[min(330px,calc(100vw-24px))] rounded-2xl p-2 shadow-xl">
                  <div className="px-2.5 pb-2 pt-1.5">
                    <p className="text-[12px] font-semibold">管理这首歌</p>
                    <p className="mt-0.5 text-[10px] leading-relaxed text-muted-foreground">选择本次要修改的元数据关系。</p>
                  </div>
                  <Link
                    to={`/settings?metadata=merge&merge_type=track&track_id=${encodeURIComponent(trackId)}&artist=${encodeURIComponent(artistName)}&return_to=${encodeURIComponent(returnTo)}#music-metadata-management`}
                    className="flex min-h-14 items-center gap-3 rounded-xl px-2.5 py-2 transition hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-foreground/30"
                  >
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-accent-foreground/10 text-accent-foreground"><GitMerge className="size-4" /></span>
                    <span className="min-w-0 flex-1"><span className="block text-[12px] font-semibold">归并歌曲版本</span><span className="block text-[10px] text-muted-foreground">选择另一首歌，并指定 L2 录音或 L3 作品层级</span></span>
                  </Link>
                  <Link
                    to={`/settings?metadata=track-credits&track_id=${encodeURIComponent(representativeTrackId)}&return_to=${encodeURIComponent(returnTo)}#music-metadata-management`}
                    className="flex min-h-14 items-center gap-3 rounded-xl px-2.5 py-2 transition hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-foreground/30"
                  >
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground"><ListMusic className="size-4" /></span>
                    <span className="min-w-0 flex-1"><span className="block text-[12px] font-semibold">调整曲目署名</span><span className="block text-[10px] text-muted-foreground">编辑当前代表来源的主艺人与合作艺人</span></span>
                  </Link>
                  <Link
                    to={`/settings?metadata=artist-identities&artist=${encodeURIComponent(artistName)}&return_to=${encodeURIComponent(returnTo)}#music-metadata-management`}
                    className="flex min-h-14 items-center gap-3 rounded-xl px-2.5 py-2 transition hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-foreground/30"
                  >
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground"><Fingerprint className="size-4" /></span>
                    <span className="min-w-0 flex-1"><span className="block text-[12px] font-semibold">管理艺人身份</span><span className="block text-[10px] text-muted-foreground">处理别名、canonical 身份和 provider 关联</span></span>
                  </Link>
                </PopoverContent>
              </Popover>
            </CapabilityGate>
          </div>
          <p className="mt-2 font-sans text-[17px] text-muted-foreground">
            {artists.map((name, index) => (
              <span key={name}>
                <Link to={`/music/artists/${encodeURIComponent(name)}`} className="transition-colors hover:text-accent-foreground">
                  {displayName(name)}
                </Link>
                {index < artists.length - 1 && <span className="text-muted-foreground/40"> · </span>}
              </span>
            ))}
          </p>
          {data.meta && (
            <p className="mt-1 break-words font-sans text-[14px] text-muted-foreground">
              {(data.album_attribution?.display_album_name ?? data.meta.spotify_album_name) && (
                <Link
                  to={`/music/albums/${encodeURIComponent(data.album_attribution?.display_album_name ?? data.meta.spotify_album_name ?? '')}?artist=${encodeURIComponent(data.primary_artist_name ?? artists[0] ?? data.artist_name)}`}
                  className="transition-colors hover:text-accent-foreground"
                >
                  {displayName(data.album_attribution?.display_album_name ?? data.meta.spotify_album_name ?? '')}
                </Link>
              )}
              {data.meta.track_number ? ` · Track ${data.meta.track_number}` : ''}
              {data.meta.duration_ms ? ` · ${formatTrackDuration(data.meta.duration_ms)}` : ''}
              {data.meta.explicit ? ' · 🅴 Explicit' : ''}
            </p>
          )}
        </div>
      </div>
    </section>
  )
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
  useChineseTextVersion()
  const renderedArtistName = displayName(data.artist_name)
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
            alt={renderedArtistName}
            style={{ width: 120, height: 120 }}
            className="h-[120px] w-[120px] flex-shrink-0 rounded-full object-cover shadow-lg"
          />
        )}
        <div className="min-w-0 max-w-full flex-1">
          <div className="flex min-w-0 items-start justify-between gap-3">
            <h1 className="min-w-0 break-words font-serif text-[44px] font-bold leading-[1.06] tracking-normal">
              {renderedArtistName}
            </h1>
            <CapabilityGate require={['editing', 'metadata_governance']}>
              <Link
                aria-label={`管理 ${renderedArtistName} 的艺人身份`}
                title="管理艺人身份"
                to={`/settings?metadata=artist-identities&artist=${encodeURIComponent(data.artist_name)}&return_to=${encodeURIComponent(`/music/artists/${data.artist_name}`)}#music-metadata-management`}
                className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-full border border-border px-2.5 text-[11px] font-semibold text-muted-foreground transition hover:border-accent-foreground/40 hover:text-foreground"
              >
                <Settings2 className="size-3.5" />
                <span className="hidden md:inline">管理</span>
              </Link>
            </CapabilityGate>
          </div>
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
  useChineseTextVersion()
  const showDualTrackCount =
    projectTrackCount != null &&
    data.meta?.total_tracks != null &&
    projectTrackCount !== data.meta.total_tracks
  const renderedAlbumName = displayName(data.album_name)
  const renderedArtistName = displayName(data.artist_name)

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
            alt={renderedAlbumName}
            style={{ width: 120, height: 120 }}
            className="h-[120px] w-[120px] flex-shrink-0 rounded-[12px] object-cover shadow-lg"
          />
        )}
        <div className="min-w-0 max-w-full flex-1">
          <div className="flex min-w-0 items-start justify-between gap-3">
            <h1 className="min-w-0 break-words font-serif text-[44px] font-bold leading-[1.06] tracking-normal">
              {renderedAlbumName}
            </h1>
            <CapabilityGate require={['editing', 'metadata_governance']}>
              <Link
                aria-label={`管理 ${renderedAlbumName} 的专辑版本`}
                title="管理专辑版本"
                to={`/settings?metadata=album-projects&album_name=${encodeURIComponent(data.album_name)}&artist=${encodeURIComponent(data.artist_name)}&return_to=${encodeURIComponent(`/music/albums/${data.album_name}?artist=${data.artist_name}`)}#music-metadata-management`}
                className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-full border border-border px-2.5 text-[11px] font-semibold text-muted-foreground transition hover:border-accent-foreground/40 hover:text-foreground"
              >
                <Settings2 className="size-3.5" />
                <span className="hidden md:inline">管理</span>
              </Link>
            </CapabilityGate>
          </div>
          <p className="mt-2 font-sans text-[17px] text-muted-foreground">
            <Link
              to={`/music/artists/${encodeURIComponent(data.artist_name)}`}
              className="transition-colors hover:text-accent-foreground"
            >
              {renderedArtistName}
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
