/** 高光时刻中的播放里程碑卡片 */

import { displayName, useChineseTextVersion } from '@/lib/chinese'
import type { PlaybackBehaviorRecords } from '@/types/analysis'
import { RecordCard, TrackCell } from './PlaybackRecordsPrimitives'

interface Props { data: PlaybackBehaviorRecords }

export function PlaybackMilestonesCard({ data }: Props) {
  useChineseTextVersion()
  const milestones = data.playback_milestones ?? []
  const currentTotal = milestones[0]?.total_plays

  return (
    <RecordCard title="播放里程碑 · Playback Milestones" subtitle={`${currentTotal ? `当前共 ${currentTotal.toLocaleString('zh-CN')} 次有效播放 · ` : ''}仅展示已经完成的动态标准节点`}>
      {milestones.length > 0 ? (
          <ol className="divide-y divide-border/50">
            {milestones.map((row) => (
              <li key={row.value} className="grid min-w-0 grid-cols-[88px_minmax(0,1fr)] gap-3 py-3 sm:grid-cols-[120px_minmax(0,1fr)_140px] sm:items-center">
                <div>
                  <p className="font-serif text-[22px] font-semibold tabular-nums">{row.value.toLocaleString('zh-CN')}</p>
                </div>
                <div className="min-w-0">
                  <TrackCell trackId={row.entity_id} name={displayName(row.name || '—')} artistName={displayName(row.artist_name || '未知艺人')} coverUrl={row.cover_url} />
                </div>
                <div className="col-start-2 font-sans text-[11px] text-muted-foreground sm:col-start-auto sm:text-right">
                  <time dateTime={row.date ?? undefined}>{row.date ?? '—'}</time>
                  <p className="mt-0.5 tabular-nums">第 {row.value.toLocaleString('zh-CN')} 次播放</p>
                </div>
              </li>
            ))}
          </ol>
      ) : <p className="py-6 text-center font-sans text-[12px] text-muted-foreground">当前有效播放量尚未达到首个标准节点</p>}
    </RecordCard>
  )
}
