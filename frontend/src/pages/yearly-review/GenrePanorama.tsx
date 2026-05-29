import { useMemo } from 'react'
import { GlassCard } from '@/components/shared/GlassCard'
import { inferLanguageDist } from '@/lib/genre-regions'
import type { GenrePanorama as GenrePanoramaType } from '@/types/yearly-review'

interface GenrePanoramaProps {
  genrePanorama: GenrePanoramaType | null
}

const LANG_LABELS: Record<string, string> = { chinese: '中文', english: '英文', korean: '韩文', japanese: '日文', instrumental: '纯器乐', other: '其他' }
const LANG_COLORS: Record<string, string> = {
  chinese: '#ef4444', english: '#3b82f6', korean: '#8b5cf6', japanese: '#ec4899', instrumental: '#6b7280', other: '#14b8a6',
}

export function GenrePanorama({ genrePanorama }: GenrePanoramaProps) {
  const languageDist = useMemo(() => {
    if (!genrePanorama?.top_genres?.length) return null
    return inferLanguageDist(genrePanorama.top_genres)
  }, [genrePanorama])

  if (!genrePanorama || !genrePanorama.top_genres.length) {
    return (
      <section className="mb-12">
        <h2 className="font-serif text-[28px] font-bold tracking-[-0.5px] mb-6">曲风全景</h2>
        <GlassCard className="p-8 text-center">
          <p className="font-sans text-[14px] text-muted-foreground">曲风流派数据不足，多听听歌获取更多洞察</p>
        </GlassCard>
      </section>
    )
  }

  const topGenres = genrePanorama.top_genres.slice(0, 10)
  const maxShare = Math.max(...topGenres.map(g => g.play_share), 1)

  return (
    <section className="mb-12">
      <h2 className="font-serif text-[28px] font-bold tracking-[-0.5px] mb-6">曲风全景</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Top 流派横向柱状图 */}
        <GlassCard className="p-5">
          <h3 className="font-sans text-[12px] font-semibold uppercase tracking-[1.5px] text-muted-foreground mb-4">Top 流派</h3>
          <div className="space-y-2.5">
            {topGenres.map((g) => (
              <div key={g.name} className="flex items-center gap-3">
                <span className="font-sans text-[13px] text-muted-foreground w-20 truncate text-right flex-shrink-0">{g.name}</span>
                <div className="flex-1 h-5 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full bg-accent-foreground/70 transition-all duration-700"
                    style={{ width: `${(g.play_share / maxShare) * 100}%` }}
                  />
                </div>
                <span className="font-sans text-[13px] font-semibold tabular-nums w-12 text-right">{g.play_share}%</span>
              </div>
            ))}
          </div>
        </GlassCard>

        {/* 语言分布环形图（纯 CSS） */}
        {languageDist && (
          <GlassCard className="p-5">
            <h3 className="font-sans text-[12px] font-semibold uppercase tracking-[1.5px] text-muted-foreground mb-4">语言分布</h3>
            <div className="space-y-3">
              {Object.entries(languageDist).map(([lang, share]) => {
                if (share <= 0) return null
                return (
                  <div key={lang} className="flex items-center gap-3">
                    <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: LANG_COLORS[lang] || '#6b7280' }} />
                    <span className="font-sans text-[13px] w-14">{LANG_LABELS[lang] || lang}</span>
                    <div className="flex-1 h-4 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-700"
                        style={{ width: `${share}%`, backgroundColor: LANG_COLORS[lang] || '#6b7280' }}
                      />
                    </div>
                    <span className="font-sans text-[13px] font-semibold tabular-nums w-10 text-right">{share}%</span>
                  </div>
                )
              })}
            </div>
          </GlassCard>
        )}
      </div>
    </section>
  )
}
