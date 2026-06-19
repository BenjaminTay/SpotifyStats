import { GlassCard } from '@/components/shared/GlassCard'
import { Slider } from '@/components/ui/slider'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'
import { RefreshCw } from 'lucide-react'
import type { SettingsUpdatePayload } from '@/types/settings'
import { SectionHeader, FieldLabel } from '@/features/settings/components/SettingsHelpers'

const DOW_OPTIONS = [
  { value: 0, label: '周一 (Monday)' },
  { value: 1, label: '周二 (Tuesday)' },
  { value: 2, label: '周三 (Wednesday)' },
  { value: 3, label: '周四 (Thursday)' },
  { value: 4, label: '周五 (Friday / 默认)' },
  { value: 5, label: '周六 (Saturday)' },
  { value: 6, label: '周日 (Sunday)' },
]

export function BillboardParamsSection({
  settings,
  onUpdate,
  onRebuild,
  rebuildLoading,
}: {
  settings: { bb_top_n: number; bb_album_top_n: number; bb_artist_top_n: number; bb_week_start_dow: number; bb_week_start_hour: number }
  onUpdate: (p: SettingsUpdatePayload) => void
  onRebuild: () => void
  rebuildLoading: boolean
}) {
  return (
    <GlassCard className="p-6">
      <SectionHeader num={2} title="Billboard Parameters" desc="调整 Billboard 周榜的计算参数，修改后需重建聚合表才能生效。" />

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {/* Left: Top N sliders */}
        <div className="space-y-5">
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <FieldLabel label="单曲榜 Top N" badge={`bb_top_n = ${settings.bb_top_n}`} />
            </div>
            <p className="text-[12px] text-muted-foreground">每周单曲榜的最大上榜数量</p>
            <Slider
              aria-label="单曲榜 Top N"
              value={[settings.bb_top_n]}
              onValueChange={(v) => onUpdate({ bb_top_n: (v as number[])[0] })}
              min={10}
              max={100}
              step={5}
            />
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <FieldLabel label="专辑榜 Top N" badge={`bb_album_top_n = ${settings.bb_album_top_n}`} />
            </div>
            <p className="text-[12px] text-muted-foreground">每周专辑榜的最大上榜数量</p>
            <Slider
              aria-label="专辑榜 Top N"
              value={[settings.bb_album_top_n]}
              onValueChange={(v) => onUpdate({ bb_album_top_n: (v as number[])[0] })}
              min={5}
              max={100}
              step={5}
            />
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <FieldLabel label="艺人榜 Top N" badge={`bb_artist_top_n = ${settings.bb_artist_top_n}`} />
            </div>
            <p className="text-[12px] text-muted-foreground">每周艺人榜的最大上榜数量</p>
            <Slider
              aria-label="艺人榜 Top N"
              value={[settings.bb_artist_top_n]}
              onValueChange={(v) => onUpdate({ bb_artist_top_n: (v as number[])[0] })}
              min={5}
              max={100}
              step={5}
            />
          </div>
        </div>

        {/* Right: week boundary + rebuild */}
        <div className="space-y-5">
          <div className="space-y-1.5">
            <FieldLabel label="周起始日" badge="bb_week_start_dow" />
            <p className="text-[12px] text-muted-foreground">Billboard 周榜从周几开始计算</p>
            <Select
              value={String(settings.bb_week_start_dow)}
              onValueChange={(v) => onUpdate({ bb_week_start_dow: Number(v) })}
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
            <FieldLabel label="周起始时" badge="bb_week_start_hour" />
            <p className="text-[12px] text-muted-foreground">一周从几点开始计算</p>
            <Select
              value={String(settings.bb_week_start_hour)}
              onValueChange={(v) => onUpdate({ bb_week_start_hour: Number(v) })}
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

          <Separator />

          <div className="space-y-2">
            <p className="text-[12px] text-muted-foreground">
              修改 Billboard 参数后，需要重建预聚合表才能使新设置生效。
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={onRebuild}
              disabled={rebuildLoading}
              className="gap-1.5"
            >
              <RefreshCw className={cn('size-3.5', rebuildLoading && 'animate-spin')} />
              {rebuildLoading ? '重建中...' : '重建聚合表 (Rebuild Aggregations)'}
            </Button>
          </div>
        </div>
      </div>
    </GlassCard>
  )
}
