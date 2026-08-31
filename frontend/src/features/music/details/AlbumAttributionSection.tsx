import { ArrowRight, Disc3, Radio } from 'lucide-react'
import { Link } from 'react-router'

import { GlassCard } from '@/components/shared/GlassCard'
import { displayName, useChineseTextVersion } from '@/lib/chinese'
import type { AlbumProject } from '@/types/billboard'

export function AlbumAttributionSection({ project }: { project: AlbumProject }) {
  useChineseTextVersion()
  const residual = project.residual_tracks ?? []
  const transferred = project.transferred_tracks ?? []
  const sources = project.source_tracks ?? []
  if (residual.length === 0 && transferred.length === 0 && sources.length === 0) return null

  return (
    <GlassCard className="mt-8 overflow-hidden p-0">
      <div className="border-b border-border/40 px-4 py-4 sm:px-5">
        <div className="flex items-center gap-2">
          <Disc3 className="size-4 text-primary" />
          <h3 className="text-sm font-semibold">L3 原生专辑归属</h3>
        </div>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          本项目在 L3 保留 {project.play_count.toLocaleString()} 次播放；实际来源播放共 {(project.source_play_count ?? 0).toLocaleString()} 次。回流只改变统计归属，不删除来源记录。
        </p>
      </div>

      <AttributionList
        title="保留在本项目"
        empty="没有残余曲目；本来源发行不会进入默认 L3 专辑榜。"
        items={residual.map((item) => ({
          key: item.canonical_song_key,
          name: item.canonical_song_name,
          detail: `${item.play_count.toLocaleString()} 次来源播放`,
          targetProjectId: item.target_project_id,
          targetName: item.target_project_name,
        }))}
      />
      <AttributionList
        title="已回流到原生专辑"
        empty="没有曲目从本项目回流。"
        items={transferred.map((item) => ({
          key: item.canonical_song_key,
          name: item.canonical_song_name,
          detail: `${item.play_count.toLocaleString()} 次 · ${item.attribution_kind}`,
          targetProjectId: item.target_project_id,
          targetName: item.target_project_name,
        }))}
      />
      <details className="border-t border-border/30">
        <summary className="flex min-h-12 cursor-pointer items-center gap-2 px-4 text-xs font-semibold sm:px-5">
          <Radio className="size-3.5" />完整来源曲目（{sources.length}）
        </summary>
        <div className="space-y-1 border-t border-border/30 px-4 py-3 sm:px-5">
          {sources.map((item) => (
            <div key={`${item.track_id}-${item.canonical_song_key}`} className="flex min-w-0 items-center gap-3 py-1.5 text-xs">
              <span className="min-w-0 flex-1 truncate">{displayName(item.track_name)}</span>
              <span className="shrink-0 tabular-nums text-muted-foreground">{item.play_count.toLocaleString()} 次</span>
            </div>
          ))}
        </div>
      </details>
    </GlassCard>
  )
}

function AttributionList({
  title,
  empty,
  items,
}: {
  title: string
  empty: string
  items: Array<{
    key: string
    name: string
    detail: string
    targetProjectId: number
    targetName: string
  }>
}) {
  return (
    <div className="border-t border-border/30 px-4 py-3 sm:px-5">
      <h4 className="text-xs font-semibold">{title}（{items.length}）</h4>
      {items.length === 0 ? (
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{empty}</p>
      ) : (
        <div className="mt-2 space-y-1">
          {items.map((item) => (
            <div key={item.key} className="flex min-w-0 items-center gap-2 py-1.5 text-xs">
              <span className="min-w-0 flex-1 truncate">{displayName(item.name)}</span>
              <span className="hidden shrink-0 text-muted-foreground sm:inline">{item.detail}</span>
              <ArrowRight className="size-3 shrink-0 text-muted-foreground" />
              <Link to={`/music/album-projects/${item.targetProjectId}`} className="max-w-[42%] truncate text-primary hover:underline">
                {displayName(item.targetName)}
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
