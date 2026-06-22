import { useState, useEffect } from 'react'
import { GlassCard } from '@/components/shared/GlassCard'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { type ChineseStyle } from '@/lib/chinese'
import { getBillboardName, setBillboardName } from '@/lib/billboard-name'
import type { SettingsUpdatePayload } from '@/types/settings'
import { setDynamicThreshold, setMaxMergeGapMinutes } from '@/hooks/useAnalysis'
import { CollapsibleSection, Toggle, FieldLabel, InlineNotice } from '@/features/settings/components/SettingsHelpers'

const MIN_MS_OPTIONS = [
  { value: 0, label: '0s (不过滤)' },
  { value: 10000, label: '10s' },
  { value: 30000, label: '30s (默认)' },
  { value: 60000, label: '60s' },
  { value: 120000, label: '120s' },
]

function getStoredMaxMergeGap(): string {
  try {
    const v = localStorage.getItem('spotify_stats_max_merge_gap_minutes')
    if (v != null) {
      const n = parseInt(v, 10)
      if (!isNaN(n) && n >= 1 && n <= 240) return String(n)
    }
  } catch { /* localStorage unavailable */ }
  return ''
}

export function DataFilteringSection({
  settings,
  onUpdate,
  onRequiresRebuild,
  chineseStyle,
  onChangeChineseStyle,
}: {
  settings: { min_ms: number; music_only: boolean; merge_enabled: boolean }
  onUpdate: (p: SettingsUpdatePayload) => void
  onRequiresRebuild: () => void
  chineseStyle: ChineseStyle
  onChangeChineseStyle: (s: string | null) => void
}) {
  const [notice, setNotice] = useState(false)
  const [dynamicThreshold, setDynamicThresholdLocal] = useState(() => {
    try { return localStorage.getItem('spotify_stats_dynamic_threshold') !== 'false' } catch { return true }
  })
  const [mergeGapMinutes, setMergeGapMinutes] = useState(getStoredMaxMergeGap)
  const [billboardName, setBillboardNameState] = useState(() => {
    try { return localStorage.getItem('spotify_stats_billboard_name') || '' } catch { return '' }
  })

  useEffect(() => {
    setDynamicThreshold(dynamicThreshold)
  }, [dynamicThreshold])

  const update = (p: SettingsUpdatePayload) => {
    onUpdate(p)
    setNotice(true)
    setTimeout(() => setNotice(false), 3000)
  }

  const updateAndRequireRebuild = (p: SettingsUpdatePayload) => {
    update(p)
    onRequiresRebuild()
  }

  const handleMergeGapChange = (value: string) => {
    setMergeGapMinutes(value)
    const n = parseInt(value, 10)
    if (!isNaN(n) && n >= 1 && n <= 240) {
      setMaxMergeGapMinutes(n)
    } else {
      setMaxMergeGapMinutes(undefined)
    }
    onRequiresRebuild()
  }

  const handleBillboardNameChange = (value: string) => {
    setBillboardNameState(value)
    setBillboardName(value || 'Billboard')
  }

  return (
    <GlassCard className="p-6">
      <CollapsibleSection num={3} title="数据与显示" desc="控制播放记录的过滤策略和名称显示偏好，影响所有页面的结果。">

      <InlineNotice show={notice}>过滤参数已更新，数据统计将基于新的过滤条件。</InlineNotice>

      {/* ── 播放过滤 ── */}
      <div className="mb-1 font-sans text-[11px] font-semibold uppercase tracking-[1.4px] text-muted-foreground">
        播放过滤
      </div>

      <div className="mt-3 grid grid-cols-1 gap-5 md:grid-cols-2">
        <div className="space-y-1.5">
          <FieldLabel label="最短播放时长" />
          <p className="text-[12px] text-muted-foreground">低于此时长的播放记录将被忽略</p>
          <Select
            value={String(settings.min_ms)}
            onValueChange={(v) => updateAndRequireRebuild({ min_ms: Number(v) })}
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
          <FieldLabel label="动态有效播放阈值" />
          <p className="text-[12px] text-muted-foreground">
            开启后基于 R2 算法根据曲目时长动态计算有效播放阈值；关闭时使用左侧固定 min_ms 阈值作为兜底
          </p>
          <div className="mt-2">
            <Toggle
              checked={dynamicThreshold}
              onChange={(v) => { setDynamicThresholdLocal(v); onRequiresRebuild() }}
              label="动态阈值"
            />
          </div>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-5 md:grid-cols-2">
        <div className="space-y-1.5">
          <FieldLabel label="仅音乐" />
          <p className="text-[12px] text-muted-foreground">排除播客、有声书等非音乐内容</p>
          <div className="mt-2">
            <Toggle
              checked={settings.music_only}
              onChange={(v) => updateAndRequireRebuild({ music_only: v })}
              label="仅音乐"
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <FieldLabel label="合并连续播放" />
          <p className="text-[12px] text-muted-foreground">将同一曲目的连续播放合并为一次</p>
          <div className="mt-2">
            <Toggle
              checked={settings.merge_enabled}
              onChange={(v) => updateAndRequireRebuild({ merge_enabled: v })}
              label="合并连续播放"
            />
          </div>
        </div>
      </div>

      {settings.merge_enabled && (
        <div className="mt-5">
          <div className="space-y-1.5">
            <FieldLabel label="合并最大间隔" />
            <p className="text-[12px] text-muted-foreground">
              两次播放之间允许的最大间隔分钟数（1–240），留空表示无限制
            </p>
            <input
              type="number"
              min={1}
              max={240}
              value={mergeGapMinutes}
              onChange={(e) => handleMergeGapChange(e.target.value)}
              placeholder="无限制"
              className="mt-1 block w-full max-w-[160px] rounded-lg border border-border bg-muted/40 px-3 py-2 font-mono text-[13px] text-foreground placeholder:text-muted-foreground/60 focus:border-accent-foreground focus:outline-none"
            />
          </div>
        </div>
      )}

      <Separator className="my-5" />

      {/* ── 显示偏好 ── */}
      <div className="mb-1 font-sans text-[11px] font-semibold uppercase tracking-[1.4px] text-muted-foreground">
        显示偏好
      </div>

      <div className="mt-3 grid grid-cols-1 gap-5 md:grid-cols-2">
        <div className="space-y-1.5">
          <FieldLabel label="中文名称显示" badge="简/繁" />
          <p className="text-[12px] text-muted-foreground">仅影响前端显示，不修改数据库内容</p>
          <Select value={chineseStyle} onValueChange={onChangeChineseStyle}>
            <SelectTrigger className="mt-1 w-[150px]">
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

        <div className="space-y-1.5">
          <FieldLabel label={`${getBillboardName()} 显示名称`} badge="自定义" />
          <p className="text-[12px] text-muted-foreground">
            自定义应用中 "{getBillboardName()}" 的显示名称，留空恢复默认 "Billboard"
          </p>
          <input
            type="text"
            value={billboardName}
            onChange={(e) => handleBillboardNameChange(e.target.value)}
            placeholder="Billboard"
            className="mt-1 block w-full max-w-[200px] rounded-lg border border-border bg-muted/40 px-3 py-2 font-sans text-[13px] text-foreground placeholder:text-muted-foreground/60 focus:border-accent-foreground focus:outline-none"
          />
        </div>
      </div>
      </CollapsibleSection>
    </GlassCard>
  )
}

const CHINESE_STYLE_OPTIONS = [
  { value: 'original', label: '原样显示' },
  { value: 'simplified', label: '简体中文' },
  { value: 'traditional', label: '繁体中文' },
]
