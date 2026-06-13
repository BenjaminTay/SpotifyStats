import { useState, useEffect } from 'react'
import { GlassCard } from '@/components/shared/GlassCard'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { type ChineseStyle } from '@/lib/chinese'
import type { SettingsUpdatePayload } from '@/types/settings'
import { setDynamicThreshold } from '@/hooks/useAnalysis'
import { SectionHeader, Toggle, FieldLabel, InlineNotice } from '@/features/settings/components/SettingsHelpers'

const MIN_MS_OPTIONS = [
  { value: 0, label: '0s (不过滤)' },
  { value: 10000, label: '10s' },
  { value: 30000, label: '30s (默认)' },
  { value: 60000, label: '60s' },
  { value: 120000, label: '120s' },
]

export function DataFilteringSection({
  settings,
  onUpdate,
  chineseStyle,
  onChangeChineseStyle,
}: {
  settings: { min_ms: number; music_only: boolean; merge_enabled: boolean }
  onUpdate: (p: SettingsUpdatePayload) => void
  chineseStyle: ChineseStyle
  onChangeChineseStyle: (s: string | null) => void
}) {
  const [notice, setNotice] = useState(false)
  const [dynamicThreshold, setDynamicThresholdLocal] = useState(() => {
    try { return localStorage.getItem('spotify_stats_dynamic_threshold') !== 'false' } catch { return true }
  })

  useEffect(() => {
    setDynamicThreshold(dynamicThreshold)
  }, [dynamicThreshold])

  const update = (p: SettingsUpdatePayload) => {
    onUpdate(p)
    setNotice(true)
    setTimeout(() => setNotice(false), 3000)
  }

  return (
    <GlassCard className="p-6">
      <SectionHeader num={1} title="Data & Display" desc="控制播放记录的过滤策略和名称显示偏好，影响所有页面的结果。" />

      <InlineNotice show={notice}>过滤参数已更新，数据统计将基于新的过滤条件。</InlineNotice>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
        <div className="space-y-1.5">
          <FieldLabel label="最短播放时长" badge="min_ms" />
          <p className="text-[12px] text-muted-foreground">低于此时长的播放记录将被忽略</p>
          <Select
            value={String(settings.min_ms)}
            onValueChange={(v) => update({ min_ms: Number(v) })}
          >
            <SelectTrigger className="mt-1 w-[160px]">
              <SelectValue>
                {MIN_MS_OPTIONS.find((o) => o.value === settings.min_ms)?.label ?? String(settings.min_ms)}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              {MIN_MS_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={String(opt.value)}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1.5">
          <FieldLabel label="仅音乐" badge="music_only" />
          <p className="text-[12px] text-muted-foreground">排除播客、有声书等非音乐内容</p>
          <div className="mt-2">
            <Toggle
              checked={settings.music_only}
              onChange={(v) => update({ music_only: v })}
              label="仅音乐"
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <FieldLabel label="合并连续播放" badge="merge_enabled" />
          <p className="text-[12px] text-muted-foreground">将同一曲目的连续播放合并为一次</p>
          <div className="mt-2">
            <Toggle
              checked={settings.merge_enabled}
              onChange={(v) => update({ merge_enabled: v })}
              label="合并连续播放"
            />
          </div>
        </div>
      </div>

      <Separator className="my-5" />

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        <div className="space-y-1.5">
          <FieldLabel label="动态有效播放阈值" badge="dynamic_threshold" />
          <p className="text-[12px] text-muted-foreground">
            根据曲目时长动态计算有效播放阈值（R2），关闭则使用固定 min_ms 阈值
          </p>
          <div className="mt-2">
            <Toggle
              checked={dynamicThreshold}
              onChange={(v) => setDynamicThresholdLocal(v)}
              label="动态阈值"
            />
          </div>
        </div>
      </div>

      <Separator className="my-5" />

      <div className="flex items-center gap-6">
        <div className="space-y-1.5">
          <FieldLabel label="中文名称显示" badge="简/繁" />
          <p className="text-[12px] text-muted-foreground">仅影响前端显示，不修改数据库内容</p>
        </div>
        <Select value={chineseStyle} onValueChange={onChangeChineseStyle}>
          <SelectTrigger className="w-[150px]">
            <SelectValue>
              {CHINESE_STYLE_OPTIONS.find((o) => o.value === chineseStyle)?.label ?? chineseStyle}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            {CHINESE_STYLE_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </GlassCard>
  )
}

const CHINESE_STYLE_OPTIONS = [
  { value: 'original', label: '原样显示' },
  { value: 'simplified', label: '简体中文' },
  { value: 'traditional', label: '繁体中文' },
]
