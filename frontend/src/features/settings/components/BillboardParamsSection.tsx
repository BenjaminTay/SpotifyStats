import { useEffect, useState } from 'react'
import { GlassCard } from '@/components/shared/GlassCard'
import { Slider } from '@/components/ui/slider'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { getBillboardName } from '@/lib/billboard-name'
import type { SettingsUpdatePayload } from '@/types/settings'
import { CollapsibleSection, FieldLabel, Toggle } from '@/features/settings/components/SettingsHelpers'

const DOW_OPTIONS = [
  { value: 0, label: '周一 (Monday)' },
  { value: 1, label: '周二 (Tuesday)' },
  { value: 2, label: '周三 (Wednesday)' },
  { value: 3, label: '周四 (Thursday)' },
  { value: 4, label: '周五 (Friday / 默认)' },
  { value: 5, label: '周六 (Saturday)' },
  { value: 6, label: '周日 (Sunday)' },
]

type TopNValue = number | readonly number[]

const TOP_N_VISUAL_MIN = 0
const TOP_N_VISUAL_MAX = 100
const TRACK_TOP_N_MIN = 10
const ALBUM_ARTIST_TOP_N_MIN = 5

function normalizeTopN(value: TopNValue, fallback: number, min: number) {
  const raw = Array.isArray(value) ? value[0] : value
  if (typeof raw !== 'number' || !Number.isFinite(raw)) return fallback
  const stepped = Math.round(raw / 5) * 5
  return Math.min(TOP_N_VISUAL_MAX, Math.max(min, stepped))
}

export function BillboardParamsSection({
  settings,
  onUpdate,
  onRequiresRebuild,
}: {
  settings: {
    bb_top_n: number
    bb_album_top_n: number
    bb_artist_top_n: number
    bb_week_start_dow: number
    bb_week_start_hour: number
    include_compilations: boolean
  }
  onUpdate: (p: SettingsUpdatePayload) => void
  onRequiresRebuild: () => void
}) {
  const bbName = getBillboardName()

  // Slider drag updates local state; commit writes settings once the interaction ends.
  const [localBbTopN, setLocalBbTopN] = useState(settings.bb_top_n)
  const [localBbAlbumTopN, setLocalBbAlbumTopN] = useState(settings.bb_album_top_n)
  const [localBbArtistTopN, setLocalBbArtistTopN] = useState(settings.bb_artist_top_n)

  useEffect(() => { setLocalBbTopN(settings.bb_top_n) }, [settings.bb_top_n])
  useEffect(() => { setLocalBbAlbumTopN(settings.bb_album_top_n) }, [settings.bb_album_top_n])
  useEffect(() => { setLocalBbArtistTopN(settings.bb_artist_top_n) }, [settings.bb_artist_top_n])

  const commitAndRequireRebuild = (p: SettingsUpdatePayload) => {
    onUpdate(p)
    onRequiresRebuild()
  }

  const commitBbTopN = (value: TopNValue) => {
    const newVal = normalizeTopN(value, localBbTopN, TRACK_TOP_N_MIN)
    setLocalBbTopN(newVal)
    commitAndRequireRebuild({ bb_top_n: newVal })
  }

  const commitBbAlbumTopN = (value: TopNValue) => {
    const newVal = normalizeTopN(value, localBbAlbumTopN, ALBUM_ARTIST_TOP_N_MIN)
    setLocalBbAlbumTopN(newVal)
    commitAndRequireRebuild({ bb_album_top_n: newVal })
  }

  const commitBbArtistTopN = (value: TopNValue) => {
    const newVal = normalizeTopN(value, localBbArtistTopN, ALBUM_ARTIST_TOP_N_MIN)
    setLocalBbArtistTopN(newVal)
    commitAndRequireRebuild({ bb_artist_top_n: newVal })
  }

  return (
    <GlassCard className="p-6">
      <CollapsibleSection
        num={4}
        title="榜单参数"
        desc={`调整 ${bbName} 周榜的计算边界和榜单容量，修改后需重建聚合表才能生效。`}
        defaultOpen={false}
        tone="advanced"
        summary={`单曲 ${localBbTopN} · 专辑 ${localBbAlbumTopN} · 艺人 ${localBbArtistTopN} · 精选集${settings.include_compilations ? '包含' : '排除'}`}
      >

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {/* Left: Top N sliders */}
        <div className="space-y-5">
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <FieldLabel label="单曲榜 Top N" badge={localBbTopN} />
            </div>
            <p className="text-[12px] text-muted-foreground">每周单曲榜的最大上榜数量</p>
            <Slider
              aria-label="单曲榜 Top N"
              value={[localBbTopN]}
              onValueChange={(v) => setLocalBbTopN(normalizeTopN(v, localBbTopN, TRACK_TOP_N_MIN))}
              onValueCommitted={commitBbTopN}
              min={TOP_N_VISUAL_MIN}
              max={TOP_N_VISUAL_MAX}
              step={5}
            />
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <FieldLabel label="专辑榜 Top N" badge={localBbAlbumTopN} />
            </div>
            <p className="text-[12px] text-muted-foreground">每周专辑榜的最大上榜数量</p>
            <Slider
              aria-label="专辑榜 Top N"
              value={[localBbAlbumTopN]}
              onValueChange={(v) => setLocalBbAlbumTopN(normalizeTopN(v, localBbAlbumTopN, ALBUM_ARTIST_TOP_N_MIN))}
              onValueCommitted={commitBbAlbumTopN}
              min={TOP_N_VISUAL_MIN}
              max={TOP_N_VISUAL_MAX}
              step={5}
            />
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <FieldLabel label="艺人榜 Top N" badge={localBbArtistTopN} />
            </div>
            <p className="text-[12px] text-muted-foreground">每周艺人榜的最大上榜数量</p>
            <Slider
              aria-label="艺人榜 Top N"
              value={[localBbArtistTopN]}
              onValueChange={(v) => setLocalBbArtistTopN(normalizeTopN(v, localBbArtistTopN, ALBUM_ARTIST_TOP_N_MIN))}
              onValueCommitted={commitBbArtistTopN}
              min={TOP_N_VISUAL_MIN}
              max={TOP_N_VISUAL_MAX}
              step={5}
            />
          </div>
        </div>

        {/* Right: week boundary + rebuild */}
        <div className="space-y-5">
          <div className="space-y-1.5">
            <FieldLabel label="周起始日" />
            <p className="text-[12px] text-muted-foreground">{bbName} 周榜从周几开始计算</p>
            <Select
              value={String(settings.bb_week_start_dow)}
              onValueChange={(v) => commitAndRequireRebuild({ bb_week_start_dow: Number(v) })}
            >
              <SelectTrigger className="mt-1 w-[200px]">
                <SelectValue>
                  {DOW_OPTIONS.find((o) => o.value === settings.bb_week_start_dow)?.label ?? String(settings.bb_week_start_dow)}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {DOW_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={String(opt.value)}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <FieldLabel label="周起始时" />
            <p className="text-[12px] text-muted-foreground">一周从几点开始计算</p>
            <Select
              value={String(settings.bb_week_start_hour)}
              onValueChange={(v) => commitAndRequireRebuild({ bb_week_start_hour: Number(v) })}
            >
              <SelectTrigger className="mt-1 w-[160px]">
                <SelectValue>
                  {`${String(settings.bb_week_start_hour).padStart(2, '0')}:00`}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {Array.from({ length: 24 }, (_, i) => (
                  <SelectItem key={i} value={String(i)}>
                    {String(i).padStart(2, '0')}:00
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center justify-between gap-4 rounded-[10px] border border-border bg-muted/20 px-4 py-3">
            <div className="min-w-0">
              <FieldLabel label="专辑榜包含精选集" />
              <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
                适用于 {bbName} 周榜专辑榜和播放分析播放排行专辑榜。
              </p>
            </div>
            <Toggle
              checked={settings.include_compilations}
              onChange={(value) => onUpdate({ include_compilations: value })}
              label="专辑榜包含精选集"
            />
          </div>

        </div>
      </div>
      </CollapsibleSection>
    </GlassCard>
  )
}
