import { useQuery } from '@tanstack/react-query'
import { AlertCircle } from 'lucide-react'
import { Link, Navigate, useLocation, useParams } from 'react-router-dom'

import { api } from '@/lib/api'
import { displayName } from '@/lib/chinese'

type TrackIdentity = {
  l1_id: number
  spotify_track_id: string | null
  track_name: string
  artist_name: string | null
  album_name: string | null
  cover_url: string | null
  source_record_count: number
}

type LegacyResolution = {
  source_track_id: number
  resolution: 'not_found' | 'unique' | 'ambiguous'
  items: TrackIdentity[]
}

export function LegacyTrackDetailRedirect() {
  const { legacyTrackId } = useParams<{ legacyTrackId: string }>()
  const location = useLocation()
  const { data, isPending, error } = useQuery({
    queryKey: ['music', 'legacy-track-identity', legacyTrackId],
    queryFn: () => api.get<LegacyResolution>(`/music/tracks/legacy/${legacyTrackId}/identity`),
    enabled: Boolean(legacyTrackId),
  })

  if (isPending) return <p className="py-16 text-center text-sm text-muted-foreground">正在解析旧歌曲链接…</p>
  if (error || !data || data.resolution === 'not_found') {
    return (
      <div className="flex flex-col items-center gap-3 py-20 text-center">
        <AlertCircle className="size-8 text-accent-foreground" />
        <p className="font-semibold">无法解析这个旧歌曲链接</p>
        <p className="text-sm text-muted-foreground">对应的历史曲目记录不存在，或尚未建立基础身份。</p>
      </div>
    )
  }
  if (data.resolution === 'unique') {
    return <Navigate replace to={`/music/tracks/${data.items[0].l1_id}${location.search}`} />
  }
  return (
    <section className="mx-auto max-w-2xl space-y-5 py-10">
      <div>
        <h1 className="text-2xl font-semibold">请选择具体的 Spotify 曲目</h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          这个旧本地记录曾承载多个 Spotify Track ID，系统不能替你猜测要打开哪一个。
        </p>
      </div>
      <div className="space-y-2">
        {data.items.map((item) => (
          <Link
            key={item.l1_id}
            to={`/music/tracks/${item.l1_id}${location.search}`}
            className="flex min-h-16 items-center gap-3 rounded-2xl border border-border p-3 transition-colors hover:bg-muted/40"
          >
            {item.cover_url ? (
              <img src={item.cover_url} alt="" className="size-11 rounded-xl object-cover" />
            ) : <span className="size-11 rounded-xl bg-muted" />}
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-semibold">{displayName(item.track_name)}</span>
              <span className="block truncate text-xs text-muted-foreground">
                {displayName(item.artist_name ?? '艺人待确认')} · Spotify {item.spotify_track_id ?? 'ID 待补充'}
              </span>
            </span>
          </Link>
        ))}
      </div>
    </section>
  )
}
