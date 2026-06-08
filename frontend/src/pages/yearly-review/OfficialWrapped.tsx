import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { queryKeys } from '@/api/query-keys'
import { GlassCard } from '@/components/shared/GlassCard'
import { api } from '@/lib/api'

interface OfficialWrappedData {
  available: boolean
  empty?: boolean
  top_artists?: { rank: number; name: string; ms_played: number; percentile: number | null; cover_url?: string }[]
  top_tracks?: { rank: number; track_id: number; name: string; play_count: number; ms_played: number; cover_url?: string }[]
  top_albums?: { rank: number; name: string; artist_name: string; play_count: number; ms_played: number; cover_url?: string }[]
  top_genres?: { rank: number; name: string }[]
  top_podcasts?: { rank: number; name: string }[]
  artist_race?: { artist_name: string; month: number; rank: number; trail_size: string }[]
  clubs?: { club_name: string; artist_name: string; percent_in_club: number; role: string }[]
  party_metrics?: { metric: string; value: number }[]
  listening_age?: { age: number; window_start_year: number; decade_phase: string } | null
  archive_reports?: { title: string; description: string; reason: string; minutes_listened: number; filed_under_tags: string }[]
}

function MiniCover({ url, name }: { url: string; name: string }) {
  return url ? (
    <img src={url} alt={name} className="w-10 h-10 object-cover rounded-md flex-shrink-0" loading="lazy" />
  ) : (
    <div className="w-10 h-10 bg-muted rounded-md flex items-center justify-center flex-shrink-0">
      <svg className="w-4 h-4 text-muted-foreground/40" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2z" /></svg>
    </div>
  )
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <div className="h-48 animate-pulse rounded-2xl bg-muted" />
      <div className="grid grid-cols-3 gap-6">
        <div className="h-64 animate-pulse rounded-xl bg-muted" />
        <div className="h-64 animate-pulse rounded-xl bg-muted" />
        <div className="h-64 animate-pulse rounded-xl bg-muted" />
      </div>
    </div>
  )
}

const CLUB_NAMES: Record<string, { name: string; desc: string; emoji: string }> = {
  "CLUB_SEROTONIN": { name: "血清素俱乐部", desc: "你听的音乐让人快乐、充满能量，像一剂天然的血清素", emoji: "🧪" },
  "CLUB_DOPAMINE": { name: "多巴胺俱乐部", desc: "节奏驱动型听众，每一次播放都是一次脑内奖励", emoji: "⚡" },
  "CLUB_OX_YTOCIN": { name: "催产素俱乐部", desc: "你的音乐品味温暖而富有情感连结", emoji: "💕" },
  "CLUB_CORTISOL": { name: "皮质醇俱乐部", desc: "你的音乐选择强烈而深刻，带着情绪的张力", emoji: "🔥" },
  "CLUB_ADRENALINE": { name: "肾上腺素俱乐部", desc: "充满爆发力的音乐品味，永远在高能量状态", emoji: "🚀" },
  "CLUB_MELATONIN": { name: "褪黑素俱乐部", desc: "舒缓宁静的音乐选择，营造放松的氛围", emoji: "🌙" },
}

export function OfficialWrapped() {
  const { data, isLoading: loading } = useQuery({
    queryKey: queryKeys.yearlyReview.hub(),
    queryFn: () => api.get<OfficialWrappedData>('/wrapped-hub'),
  })

  if (loading) return <LoadingSkeleton />

  if (!data || !data.available) {
    return (
      <div className="py-16 text-center">
        <p className="font-serif text-[28px] font-bold mb-4">官方 Wrapped 数据不可用</p>
        <p className="font-sans text-[14px] text-muted-foreground mb-4">
          尚未导入 Spotify 官方 Wrapped 数据。
        </p>
        <Link to="/settings" className="inline-block px-5 py-2 rounded-full bg-accent-foreground text-card font-sans text-[13px] font-semibold hover:opacity-90 transition-opacity">
          前往设置 → 数据导入
        </Link>
      </div>
    )
  }

  if (data.empty) {
    return (
      <div className="py-16 text-center">
        <p className="font-serif text-[28px] font-bold mb-3">暂无 Wrapped 数据</p>
        <p className="font-sans text-[14px] text-muted-foreground">数据已导入但内容为空</p>
      </div>
    )
  }

  // 从 party_metrics 提取关键指标
  const partyMap: Record<string, number> = {}
  data.party_metrics?.forEach(m => { partyMap[m.metric] = m.value })

  return (
    <div className="space-y-8">
      {/* Hero KPI */}
      {partyMap['totalNumListeningMinutes'] != null && (
        <section
          className="relative overflow-hidden rounded-2xl px-10 py-14 mb-8"
          style={{
            background: `linear-gradient(135deg, #0b3820, #051208)`,
          }}
        >
          <div className="mb-8">
            <p className="font-sans text-[13px] uppercase tracking-[2px] text-white/60 mb-2">
              Spotify Wrapped 2025
            </p>
            <p className="font-serif text-[96px] font-bold leading-[0.95] tracking-[-2px] text-white">
              {Math.round(partyMap['totalNumListeningMinutes'] / 60).toLocaleString()}
              <span className="font-sans text-[24px] font-normal tracking-normal text-white/70 ml-2">小时</span>
            </p>
          </div>
          <div className="grid grid-cols-3 gap-6">
            {partyMap['numUniqueArtists'] != null && (
              <KpiItem label="独特艺人" value={partyMap['numUniqueArtists'].toLocaleString()} />
            )}
            {partyMap['numUniqueTracks'] != null && (
              <KpiItem label="独特曲目" value={partyMap['numUniqueTracks'].toLocaleString()} />
            )}
            {partyMap['streakNumListeningDays'] != null && (
              <KpiItem label="连续听歌" value={partyMap['streakNumListeningDays'].toLocaleString()} unit="天" />
            )}
          </div>
        </section>
      )}

      {/* 俱乐部信息 */}
      {data.clubs && data.clubs.length > 0 && (() => {
        const club = data.clubs[0]
        const clubMeta = CLUB_NAMES[club.club_name] || { name: club.club_name, desc: "", emoji: "🎵" }
        return (
          <GlassCard className="p-6">
            <div className="flex items-center gap-4 mb-4">
              <span className="text-3xl">{clubMeta.emoji}</span>
              <div>
                <h3 className="font-serif text-[24px] font-bold">{clubMeta.name}</h3>
                <p className="font-sans text-[13px] text-muted-foreground">{clubMeta.desc}</p>
              </div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {data.clubs.map((c, i) => (
                <span key={i} className="font-sans text-[14px] px-3 py-2 bg-muted/50 rounded-lg">
                  {c.artist_name}
                  <span className="text-[11px] text-muted-foreground ml-1">{c.role}</span>
                </span>
              ))}
            </div>
          </GlassCard>
        )
      })()}

      {/* 排行榜三列 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Top 曲目 */}
        {data.top_tracks && data.top_tracks.length > 0 && (
          <GlassCard className="p-5">
            <h3 className="font-sans text-[12px] font-semibold uppercase tracking-[1.5px] text-muted-foreground mb-4">Top 曲目</h3>
            <div className="space-y-2">
              {data.top_tracks.slice(0, 5).map((t) => (
                <Link key={t.rank} to={`/music/tracks/${t.track_id}`} className="flex items-center gap-3 group">
                  <span className="font-sans text-[12px] font-bold text-muted-foreground w-5 text-right">{t.rank}</span>
                  <MiniCover url={t.cover_url || ''} name={t.name} />
                  <div className="min-w-0 flex-1">
                    <p className="font-sans text-[13px] font-semibold truncate group-hover:text-accent-foreground transition-colors">{t.name}</p>
                    <p className="font-sans text-[11px] text-muted-foreground tabular-nums">{t.play_count} 次</p>
                  </div>
                </Link>
              ))}
            </div>
          </GlassCard>
        )}

        {/* Top 艺人 */}
        {data.top_artists && data.top_artists.length > 0 && (
          <GlassCard className="p-5">
            <h3 className="font-sans text-[12px] font-semibold uppercase tracking-[1.5px] text-muted-foreground mb-4">Top 艺人</h3>
            <div className="space-y-2">
              {data.top_artists.slice(0, 5).map((a) => (
                <Link key={a.rank} to={`/music/artists/${encodeURIComponent(a.name)}`} className="flex items-center gap-3 group">
                  <span className="font-sans text-[12px] font-bold text-muted-foreground w-5 text-right">{a.rank}</span>
                  <MiniCover url={a.cover_url || ''} name={a.name} />
                  <p className="font-sans text-[13px] font-semibold truncate group-hover:text-accent-foreground transition-colors min-w-0 flex-1">{a.name}</p>
                </Link>
              ))}
            </div>
          </GlassCard>
        )}

        {/* Top 专辑 */}
        {data.top_albums && data.top_albums.length > 0 && (
          <GlassCard className="p-5">
            <h3 className="font-sans text-[12px] font-semibold uppercase tracking-[1.5px] text-muted-foreground mb-4">Top 专辑</h3>
            <div className="space-y-2">
              {data.top_albums.slice(0, 5).map((a) => (
                <Link key={a.rank} to={`/music/albums/${encodeURIComponent(a.name)}?artist=${encodeURIComponent(a.artist_name)}`} className="flex items-center gap-3 group">
                  <span className="font-sans text-[12px] font-bold text-muted-foreground w-5 text-right">{a.rank}</span>
                  <MiniCover url={a.cover_url || ''} name={a.name} />
                  <p className="font-sans text-[13px] font-semibold truncate group-hover:text-accent-foreground transition-colors min-w-0 flex-1">{a.name}</p>
                </Link>
              ))}
            </div>
          </GlassCard>
        )}
      </div>

      {/* 收听年龄 */}
      {data.listening_age && data.listening_age.age > 0 && (
        <GlassCard className="p-5 flex flex-col items-center text-center">
          <h3 className="font-sans text-[12px] font-semibold uppercase tracking-[1.5px] text-muted-foreground mb-3">收听年龄</h3>
          <p className="font-serif text-[48px] font-bold">{data.listening_age.age}<span className="font-sans text-[20px] font-normal text-muted-foreground ml-1">岁</span></p>
          <p className="font-sans text-[13px] text-muted-foreground mt-1">
            年代阶段: {data.listening_age.decade_phase || '未知'}
          </p>
        </GlassCard>
      )}

      {/* 存档报告 */}
      {data.archive_reports && data.archive_reports.length > 0 && (
        <GlassCard className="p-5">
          <h3 className="font-sans text-[12px] font-semibold uppercase tracking-[1.5px] text-muted-foreground mb-4">特殊日子</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {data.archive_reports.map((r, i) => (
              <div key={i} className="p-3 rounded-lg bg-muted/50">
                <p className="font-sans text-[14px] font-semibold">{r.title}</p>
                <p className="font-sans text-[12px] text-muted-foreground mt-1">{r.description}</p>
                {r.minutes_listened > 0 && (
                  <p className="font-sans text-[11px] text-muted-foreground mt-1 tabular-nums">
                    {Math.round(r.minutes_listened)} 分钟
                    {r.filed_under_tags && ` · ${r.filed_under_tags}`}
                  </p>
                )}
              </div>
            ))}
          </div>
        </GlassCard>
      )}
    </div>
  )
}

function KpiItem({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div>
      <p className="font-sans text-[11px] uppercase tracking-[1.2px] text-white/50 mb-1">{label}</p>
      <p className="font-serif text-[20px] font-semibold text-white/90">
        {value}
        {unit && <span className="font-sans text-[14px] font-normal text-white/50 ml-1">{unit}</span>}
      </p>
    </div>
  )
}
