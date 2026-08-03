import { useState } from 'react'

import { FieldLabel } from '@/features/settings/components/SettingsHelpers'
import { getBillboardName } from '@/lib/billboard-name'
import { getDefaultMergeLevel, setDefaultMergeLevel } from '@/lib/merge-level'
import { cn } from '@/lib/utils'

const MERGE_LEVELS = [
  {
    value: 1,
    shortLabel: 'L1 不归并',
    desc: '歌曲与专辑版本各自独立统计，不应用人工录音组或专辑项目归并。',
  },
  {
    value: 2,
    shortLabel: 'L2 同一录音',
    desc: '合并同一录音的不同发行记录；专辑统计同时使用已管理的发行项目与版本关系。',
  },
  {
    value: 3,
    shortLabel: 'L3 同一作品',
    desc: '包含 L2，并进一步合并 Acoustic、Live、Remix 等属于同一作品的不同录音。',
  },
] as const

export function MergeLevelControl() {
  const [mergeLevel, setMergeLevel] = useState(getDefaultMergeLevel)
  const current = MERGE_LEVELS.find((level) => level.value === mergeLevel)!

  const selectLevel = (level: number) => {
    setMergeLevel(level)
    setDefaultMergeLevel(level)
  }

  return (
    <div className="rounded-xl border border-border bg-muted/25 p-4">
      <FieldLabel label="默认归并级别" badge={current.shortLabel} />
      <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
        这是歌曲归并与专辑发行版本共用的唯一全局默认值，影响相关播放统计与个人 {getBillboardName()}；页面 URL 中的 merge_level 仍可临时覆盖。
      </p>
      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3" role="radiogroup" aria-label="默认归并级别">
        {MERGE_LEVELS.map((level) => (
          <button
            key={level.value}
            type="button"
            role="radio"
            aria-checked={mergeLevel === level.value}
            onClick={() => selectLevel(level.value)}
            className={cn(
              'rounded-lg border px-3 py-2 text-left transition-colors',
              mergeLevel === level.value
                ? 'border-accent-foreground bg-accent-foreground text-primary-foreground shadow-sm'
                : 'border-border bg-background hover:border-accent-foreground/35',
            )}
          >
            <span className="block text-[13px] font-semibold">{level.shortLabel}</span>
          </button>
        ))}
      </div>
      <p className="mt-3 rounded-lg bg-background/70 px-3 py-2 text-[12.5px] leading-relaxed text-foreground/80">
        {current.desc}
      </p>
    </div>
  )
}
