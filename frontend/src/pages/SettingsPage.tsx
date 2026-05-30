import { useState, useEffect, useCallback } from 'react'
import { GlassCard } from '@/components/shared/GlassCard'
import { Slider } from '@/components/ui/slider'
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import {
  AlertCircle,
  CheckCircle2,
  Upload,
  RefreshCw,
  Star,
  Trash2,
  Plus,
  X,
  Search,
  ChevronDown,
  Link,
  Unlink,
  Music,
} from 'lucide-react'
import { useSettings, useVersionMerge } from '@/hooks/useSettings'
import { getChineseStyle, setChineseStyle, type ChineseStyle } from '@/lib/chinese'
import type {
  SettingsUpdatePayload,
  ImportJob,
  DetectionResult,
  DetectionMember,
  ReleaseGroup,
  GroupMember,
  UngroupedAlbum,
  TrackComparison,
  LLMProfile,
  LLMProfileDetail,
  LLMProfileCreatePayload,
  SpotifyProfile,
} from '@/types/settings'

// ═══════════════════════════════════════════════════════════════
// Internal sub-components
// ═══════════════════════════════════════════════════════════════

// ── Toggle ──────────────────────────────────────────────────

function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors duration-200',
        checked ? 'bg-accent-foreground' : 'bg-muted',
      )}
    >
      <span
        className={cn(
          'pointer-events-none block h-4 w-4 rounded-full bg-white shadow-sm transition-transform duration-200',
          checked ? 'translate-x-5' : 'translate-x-0.5',
        )}
      />
      <span className="sr-only">{label}</span>
    </button>
  )
}

// ── Section Header ──────────────────────────────────────────

function SectionHeader({ num, title, desc }: { num: number; title: string; desc: string }) {
  return (
    <div className="mb-6">
      <div className="mb-1 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
        {String(num).padStart(2, '0')} · {title}
      </div>
      <p className="font-sans text-[14px] leading-relaxed text-muted-foreground">{desc}</p>
    </div>
  )
}

// ── FieldLabel ──────────────────────────────────────────────

function FieldLabel({ label, badge }: { label: string; badge?: string | number }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="font-sans text-[13.5px] font-medium text-foreground">{label}</span>
      {badge !== undefined && (
        <span className="font-mono text-[12px] text-accent-foreground">{badge}</span>
      )}
    </div>
  )
}

// ── Inline Notice ───────────────────────────────────────────

function InlineNotice({ show, children }: { show: boolean; children: React.ReactNode }) {
  return (
    <div
      className={cn(
        'overflow-hidden transition-all duration-300',
        show ? 'mb-4 max-h-10 opacity-100' : 'mb-0 max-h-0 opacity-0',
      )}
    >
      <div className="flex items-center gap-2 rounded-lg bg-accent-foreground/10 px-3 py-2 text-[13px] text-accent-foreground">
        <CheckCircle2 className="size-3.5 shrink-0" />
        {children}
      </div>
    </div>
  )
}

// ── ImportProgressCard ──────────────────────────────────────

function ImportProgressCard({
  title,
  label,
  job,
  onStart,
  statusBadge,
}: {
  title: string
  label: string
  job: ImportJob | null
  onStart: () => void
  statusBadge?: React.ReactNode
}) {
  const isRunning = job?.status === 'running'
  const isDone = job?.status === 'done'
  const isError = job?.status === 'error'

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="font-sans text-[13.5px] font-medium text-foreground">{title}</span>
        {statusBadge}
      </div>
      <p className="font-sans text-[13px] text-muted-foreground">{label}</p>

      {isRunning && (
        <div className="space-y-1.5">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-accent-foreground transition-all duration-300"
              style={{ width: `${Math.round((job.progress_pct ?? 0) * 100)}%` }}
            />
          </div>
          <p className="text-[12px] text-muted-foreground">{job.message}</p>
        </div>
      )}
      {isDone && (
        <div className="flex items-center gap-1.5 text-[13px] text-green-600 dark:text-green-400">
          <CheckCircle2 className="size-3.5" />
          导入完成
        </div>
      )}
      {isError && (
        <div className="flex items-center gap-1.5 text-[13px] text-accent-foreground">
          <AlertCircle className="size-3.5" />
          {job.message || '导入失败'}
        </div>
      )}

      <Button
        variant="outline"
        size="sm"
        onClick={onStart}
        disabled={isRunning}
        className="w-fit gap-1.5"
      >
        {isRunning ? (
          <RefreshCw className="size-3.5 animate-spin" />
        ) : (
          <Upload className="size-3.5" />
        )}
        {isRunning ? '导入中...' : isDone ? '重新导入' : '开始导入'}
      </Button>
    </div>
  )
}

// ── TrackComparePanel ───────────────────────────────────────

function TrackComparePanel({ data }: { data: TrackComparison | null }) {
  if (!data) return <Skeleton className="h-20 w-full" />

  const allEmpty = data.shared.length === 0 && data.only_in_a.length === 0 && data.only_in_b.length === 0
  if (allEmpty) {
    return <p className="py-4 text-center text-[13px] text-muted-foreground">无曲目数据</p>
  }

  const renderTrack = (row: TrackComparison['shared'][number], idx: number) => (
    <div key={idx} className="flex items-center justify-between py-1 text-[12.5px]">
      <span className="truncate pr-2">
        {row[0]}
        <span className="ml-1 text-muted-foreground">{row[1]}</span>
      </span>
      <span className="shrink-0 text-muted-foreground">
        {row[2] !== null ? `Track ${row[2]}` : ''}
        {row[3] !== null ? ` · Disc ${row[3]}` : ''}
      </span>
    </div>
  )

  return (
    <div className="space-y-3">
      {data.shared.length > 0 && (
        <div>
          <div className="mb-1 flex items-center gap-1.5 text-[12px] font-semibold text-green-600 dark:text-green-400">
            <span className="size-1.5 rounded-full bg-current" />
            共享曲目 ({data.shared.length})
          </div>
          <div className="divide-y divide-border/50">{data.shared.map(renderTrack)}</div>
        </div>
      )}
      {data.only_in_a.length > 0 && (
        <div>
          <div className="mb-1 flex items-center gap-1.5 text-[12px] font-semibold text-blue-600 dark:text-blue-400">
            <span className="size-1.5 rounded-full bg-current" />
            仅主版本 ({data.only_in_a.length})
          </div>
          <div className="divide-y divide-border/50">{data.only_in_a.map(renderTrack)}</div>
        </div>
      )}
      {data.only_in_b.length > 0 && (
        <div>
          <div className="mb-1 flex items-center gap-1.5 text-[12px] font-semibold text-amber-600 dark:text-amber-400">
            <span className="size-1.5 rounded-full bg-current" />
            仅对比版本 ({data.only_in_b.length})
          </div>
          <div className="divide-y divide-border/50">{data.only_in_b.map(renderTrack)}</div>
        </div>
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════
// Section components
// ═══════════════════════════════════════════════════════════════

// ── Data Filtering Section ──────────────────────────────────

const MIN_MS_OPTIONS = [
  { value: 0, label: '0s (不过滤)' },
  { value: 10000, label: '10s' },
  { value: 30000, label: '30s (默认)' },
  { value: 60000, label: '60s' },
  { value: 120000, label: '120s' },
]

// ── Spotify Connection Section ────────────────────────────

interface SpotifyConnectResult {
  total_in_spotify?: number
  total_in_db?: number
  matched?: number
  new_dates?: number
  error?: string
}

function SpotifyConnectionSection({
  connected,
  profile,
  onConnect,
  onDisconnect,
  onSync,
}: {
  connected: boolean
  profile: SpotifyProfile | null
  onConnect: () => Promise<{ auth_url: string; state: string }>
  onDisconnect: () => Promise<void>
  onSync: () => Promise<SpotifyConnectResult>
}) {
  const [connecting, setConnecting] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState<SpotifyConnectResult | null>(null)
  const [syncError, setSyncError] = useState('')
  const [notice, setNotice] = useState('')

  // Check URL params for OAuth callback
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('spotify_connected') === 'true') {
      setNotice('Spotify 账号连接成功')
      // Clean URL
      const url = new URL(window.location.href)
      url.searchParams.delete('spotify_connected')
      url.searchParams.delete('spotify_error')
      window.history.replaceState({}, '', url.toString())
    }
    const err = params.get('spotify_error')
    if (err) {
      setSyncError(err === 'invalid_state' ? '安全校验失败，请重试' :
        err === 'token_exchange_failed' ? '令牌交换失败，请重试' : `授权失败: ${err}`)
      const url = new URL(window.location.href)
      url.searchParams.delete('spotify_connected')
      url.searchParams.delete('spotify_error')
      window.history.replaceState({}, '', url.toString())
    }
  }, [])

  const handleConnect = async () => {
    setConnecting(true)
    try {
      const { auth_url } = await onConnect()
      window.location.href = auth_url
    } catch {
      setConnecting(false)
    }
  }

  const handleSync = async () => {
    setSyncing(true)
    setSyncError('')
    setSyncResult(null)
    try {
      const result = await onSync()
      setSyncResult(result)
    } catch (e: unknown) {
      setSyncError(e instanceof Error ? e.message : '同步失败')
    } finally {
      setSyncing(false)
    }
  }

  const handleDisconnect = async () => {
    await onDisconnect()
    setSyncResult(null)
    setSyncError('')
    setNotice('')
  }

  return (
    <GlassCard className="p-6">
      <SectionHeader
        num={0}
        title="Spotify 连接"
        desc="连接你的 Spotify 账号以获取收藏时间、播放列表等个人数据。仅请求 user-library-read 权限。"
      />

      {notice && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-green-50 px-4 py-2.5 text-[13px] text-green-700 dark:bg-green-950/30 dark:text-green-400">
          <CheckCircle2 className="size-3.5" />
          {notice}
        </div>
      )}

      {/* Connection status badge */}
      <div className="mb-4 flex items-center gap-3">
        <span className="font-sans text-[13px] text-muted-foreground">状态</span>
        <Badge
          className={cn(
            'font-sans text-[11px] font-semibold',
            connected
              ? 'bg-green-100 text-green-700 dark:bg-green-950/40 dark:text-green-400'
              : 'bg-muted text-muted-foreground',
          )}
        >
          {connected ? '已连接' : '未连接'}
        </Badge>
      </div>

      {/* Profile card when connected */}
      {connected && profile && (
        <div className="mb-5 flex items-center gap-4 rounded-xl border border-border bg-muted/30 p-4">
          {profile.images.length > 0 && (
            <img
              src={profile.images[0].url}
              alt={profile.display_name}
              className="size-14 rounded-full border-2 border-border"
            />
          )}
          <div className="space-y-0.5">
            <p className="font-sans text-[15px] font-semibold text-foreground">
              {profile.display_name || 'Spotify User'}
            </p>
            <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-[12px] text-muted-foreground">
              {profile.email && <span>{profile.email}</span>}
              <span>{profile.country?.toUpperCase()}</span>
              <span className="capitalize">{profile.product}</span>
              <span>{profile.followers.toLocaleString()} 粉丝</span>
            </div>
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex flex-wrap gap-3">
        {!connected ? (
          <Button
            variant="default"
            size="sm"
            onClick={handleConnect}
            disabled={connecting}
            className="gap-1.5 bg-[#1DB954] text-white hover:bg-[#1ed760]"
          >
            <Link className="size-3.5" />
            {connecting ? '跳转中...' : '连接 Spotify'}
          </Button>
        ) : (
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={handleSync}
              disabled={syncing}
              className="gap-1.5"
            >
              <RefreshCw className={cn('size-3.5', syncing && 'animate-spin')} />
              {syncing ? '同步中...' : '同步收藏时间'}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleDisconnect}
              className="gap-1.5 text-destructive hover:bg-destructive/10"
            >
              <Unlink className="size-3.5" />
              断开连接
            </Button>
          </>
        )}
      </div>

      {/* Sync result */}
      {syncResult && (
        <div className="mt-4 rounded-lg border border-border bg-muted/30 px-4 py-3">
          <p className="font-sans text-[13px] font-semibold">同步结果</p>
          <p className="mt-1 font-sans text-[13px] text-muted-foreground">
            Spotify 收藏 {syncResult.total_in_spotify} 首，本地 {syncResult.total_in_db} 首，
            回填日期 {syncResult.new_dates ?? syncResult.matched} 首
          </p>
        </div>
      )}

      {/* Error message */}
      {syncError && (
        <div className="mt-3 flex items-center gap-2 text-[13px] text-red-600 dark:text-red-400">
          <AlertCircle className="size-3.5" />
          {syncError}
        </div>
      )}

      {/* Note about what this enables */}
      {connected && (
        <p className="mt-4 font-sans text-[12px] text-muted-foreground">
          连接后可同步收藏时间，CollectionTab 的生命周期分析、化学反应等模块将从全零数据变为真实分析。
        </p>
      )}
    </GlassCard>
  )
}

// ── Data Filtering ────────────────────────────────────────

function DataFilteringSection({
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

// ── Billboard Params Section ────────────────────────────────

const DOW_OPTIONS = [
  { value: 0, label: '周一 (Monday)' },
  { value: 1, label: '周二 (Tuesday)' },
  { value: 2, label: '周三 (Wednesday)' },
  { value: 3, label: '周四 (Thursday)' },
  { value: 4, label: '周五 (Friday / 默认)' },
  { value: 5, label: '周六 (Saturday)' },
  { value: 6, label: '周日 (Sunday)' },
]

function BillboardParamsSection({
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

// ── Version Merge Section ───────────────────────────────────

type MergeTabKey = 'detect' | 'saved' | 'create'
const MERGE_TABS: { key: MergeTabKey; label: string }[] = [
  { key: 'detect', label: '自动检测' },
  { key: 'saved', label: '已保存分组' },
  { key: 'create', label: '手动创建' },
]

// ── LLM Translation Providers ────────────────────────────────

const LLM_PROVIDERS = [
  { value: 'deepseek', label: 'DeepSeek', defaultModel: 'deepseek-chat' },
  { value: 'openai', label: 'OpenAI', defaultModel: 'gpt-4o-mini' },
  { value: 'anthropic', label: 'Anthropic', defaultModel: 'claude-haiku-4-5-20251001' },
  { value: 'custom', label: '自定义', defaultModel: '' },
]

function LLMTranslationSection({
  settings,
  onUpdate,
  onUpdateApiKey,
  onClearCache,
  hasLlmKey,
  profiles,
  onFetchProfiles,
  onGetProfileDetail,
  onApplyProfile,
  onCreateProfile,
  onDeleteProfile,
  onRefetch,
}: {
  settings: { llm_enabled: boolean; llm_provider: string; llm_model: string }
  onUpdate: (p: SettingsUpdatePayload) => void
  onUpdateApiKey: (apiKey: string, baseUrl?: string) => Promise<void>
  onClearCache: () => Promise<{ deleted_count: number }>
  hasLlmKey: boolean
  profiles: LLMProfile[]
  onFetchProfiles: () => Promise<LLMProfile[]>
  onGetProfileDetail: (profileId: number) => Promise<LLMProfileDetail>
  onApplyProfile: (profileId: number) => Promise<{ status: string; profile_id: number }>
  onCreateProfile: (payload: LLMProfileCreatePayload) => Promise<{ id: number; status: string }>
  onDeleteProfile: (profileId: number) => Promise<{ status: string }>
  onRefetch: () => void
}) {
  const [notice, setNotice] = useState(false)
  const [apiKeyInput, setApiKeyInput] = useState('')
  const [baseUrlInput, setBaseUrlInput] = useState('')
  const [clearMsg, setClearMsg] = useState('')
  const [clearLoading, setClearLoading] = useState(false)
  const [localProfiles, setLocalProfiles] = useState<LLMProfile[]>(profiles)
  const [selectedProfileId, setSelectedProfileId] = useState<number | null>(null)
  const [showSaveDialog, setShowSaveDialog] = useState(false)
  const [profileSaving, setProfileSaving] = useState(false)
  const [profileError, setProfileError] = useState('')
  const [saveProfileName, setSaveProfileName] = useState('')

  const isCustom = settings.llm_provider === 'custom'
  const currentProvider = LLM_PROVIDERS.find((p) => p.value === settings.llm_provider)

  useEffect(() => {
    onFetchProfiles().then(setLocalProfiles)
  }, [onFetchProfiles])

  const update = (p: SettingsUpdatePayload) => {
    onUpdate(p)
    setNotice(true)
    setTimeout(() => setNotice(false), 3000)
  }

  const handleProviderChange = (provider: string | null) => {
    if (!provider) return
    const preset = LLM_PROVIDERS.find((p) => p.value === provider)
    update({
      llm_provider: provider,
      llm_model: preset?.defaultModel || '',
    })
  }

  const handleSaveApiKey = () => {
    if (!apiKeyInput.trim()) return
    onUpdateApiKey(apiKeyInput.trim(), isCustom ? baseUrlInput.trim() || undefined : undefined).then(() => {
      setApiKeyInput('')
      setNotice(true)
      setTimeout(() => setNotice(false), 3000)
    })
  }

  const handleSelectProfile = (profileId: number) => {
    setSelectedProfileId(profileId)
    onGetProfileDetail(profileId).then((detail) => {
      update({
        llm_provider: detail.llm_provider,
        llm_model: detail.llm_model,
      })
      // Apply profile config server-side — key never transits through frontend
      onApplyProfile(profileId).then(() => onRefetch())
      setApiKeyInput('')
      setBaseUrlInput(detail.llm_base_url || '')
    })
  }

  const handleSaveProfile = () => {
    if (!saveProfileName.trim()) return
    setProfileSaving(true)
    setProfileError('')
    onCreateProfile({
      profile_name: saveProfileName.trim(),
      llm_provider: settings.llm_provider,
      llm_model: settings.llm_model,
      llm_api_key: apiKeyInput.trim(),
      llm_base_url: baseUrlInput.trim(),
    }).then(() => {
      setProfileSaving(false)
      setShowSaveDialog(false)
      setSaveProfileName('')
      onFetchProfiles().then(setLocalProfiles)
    }).catch((e: Error) => {
      setProfileSaving(false)
      setProfileError(e.message || '保存失败')
    })
  }

  const handleDeleteProfile = () => {
    if (selectedProfileId === null) return
    onDeleteProfile(selectedProfileId).then(() => {
      setSelectedProfileId(null)
      onFetchProfiles().then(setLocalProfiles)
    })
  }

  const handleClearCache = () => {
    setClearLoading(true)
    setClearMsg('')
    onClearCache().then((res) => {
      setClearMsg(`已清除 ${res.deleted_count} 条翻译缓存，下次访问时将重新翻译。`)
      setClearLoading(false)
    }).catch(() => {
      setClearMsg('清除失败，请重试。')
      setClearLoading(false)
    })
  }

  return (
    <GlassCard className="p-6">
      <SectionHeader num={5} title="LLM 翻译" desc="使用大模型替代 Google 机翻，产出自然中文并保留段落结构、粗体/斜体排版。" />

      <InlineNotice show={notice}>LLM 翻译配置已保存。</InlineNotice>

      {/* ── Profile Selector ── */}
      <div className="mb-5 space-y-2">
        <FieldLabel label="LLM 配置档案" badge="profile" />
        <p className="text-[12px] text-muted-foreground">
          保存当前 LLM 配置为档案，方便快速切换
        </p>
        <div className="flex items-center gap-2">
          <Select
            value={selectedProfileId !== null ? String(selectedProfileId) : ''}
            onValueChange={(v) => {
              if (!v) {
                setSelectedProfileId(null)
                return
              }
              handleSelectProfile(Number(v))
            }}
          >
            <SelectTrigger className="w-[220px]">
              <SelectValue placeholder="选择已保存的档案..." />
            </SelectTrigger>
            <SelectContent>
              {localProfiles.map((p) => (
                <SelectItem key={p.id} value={String(p.id)}>
                  {p.profile_name} <span className="ml-2 text-[11px] text-muted-foreground">({p.llm_provider})</span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Button variant="outline" size="sm" onClick={() => {
            setSaveProfileName('')
            setProfileError('')
            setShowSaveDialog(true)
          }} className="gap-1">
            <Plus className="size-3.5" />
            保存当前配置
          </Button>

          {selectedProfileId !== null && (
            <Button variant="ghost" size="sm" onClick={handleDeleteProfile} className="text-destructive">
              <Trash2 className="size-3.5" />
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        {/* Enable Toggle */}
        <div className="space-y-1.5">
          <FieldLabel label="启用 LLM 翻译" badge="llm_enabled" />
          <p className="text-[12px] text-muted-foreground">关闭时使用 Google 机翻作为回退</p>
          <div className="mt-2">
            <Toggle
              checked={settings.llm_enabled}
              onChange={(v) => update({ llm_enabled: v })}
              label="启用"
            />
          </div>
        </div>

        {/* Provider Select */}
        <div className="space-y-1.5">
          <FieldLabel label="供应商" badge="llm_provider" />
          <p className="text-[12px] text-muted-foreground">选择 LLM API 供应商</p>
          <Select value={settings.llm_provider} onValueChange={handleProviderChange}>
            <SelectTrigger className="mt-1 w-[180px]">
              <SelectValue>{currentProvider?.label || settings.llm_provider}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              {LLM_PROVIDERS.map((p) => (
                <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Model Input */}
        <div className="space-y-1.5">
          <FieldLabel label="模型" badge="llm_model" />
          <p className="text-[12px] text-muted-foreground">
            {currentProvider?.defaultModel
              ? `留空则使用默认: ${currentProvider.defaultModel}`
              : '输入模型名称'}
          </p>
          <input
            type="text"
            value={settings.llm_model}
            onChange={(e) => update({ llm_model: e.target.value })}
            placeholder={currentProvider?.defaultModel || '模型名'}
            className="mt-1 block w-full max-w-[280px] rounded-lg border border-border bg-muted/40 px-3 py-2 font-sans text-[13px] text-foreground placeholder:text-muted-foreground/60 focus:border-accent-foreground focus:outline-none"
          />
        </div>

        {/* API Key */}
        <div className="space-y-1.5">
          <FieldLabel label="API Key" badge="secret" />
          <p className="text-[12px] text-muted-foreground">
            密钥已持久化存储
            {hasLlmKey && (
              <span className="ml-2 inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 className="size-3" /> 已配置
              </span>
            )}
          </p>
          <div className="mt-1 flex gap-2">
            <input
              type="password"
              value={apiKeyInput}
              onChange={(e) => setApiKeyInput(e.target.value)}
              placeholder={hasLlmKey ? '已配置，留空不覆盖' : 'sk-...'}
              className="block w-full max-w-[280px] rounded-lg border border-border bg-muted/40 px-3 py-2 font-mono text-[13px] text-foreground placeholder:text-muted-foreground/60 focus:border-accent-foreground focus:outline-none"
            />
            <Button variant="outline" size="sm" onClick={handleSaveApiKey} disabled={!apiKeyInput.trim()}>
              保存
            </Button>
          </div>
        </div>

        {/* Custom Base URL (only when custom provider) */}
        {isCustom && (
          <div className="space-y-1.5">
            <FieldLabel label="自定义 URL" badge="llm_base_url" />
            <p className="text-[12px] text-muted-foreground">OpenAI 兼容的 API 地址</p>
            <input
              type="text"
              value={baseUrlInput}
              onChange={(e) => setBaseUrlInput(e.target.value)}
              placeholder="https://api.example.com/v1"
              className="mt-1 block w-full max-w-[400px] rounded-lg border border-border bg-muted/40 px-3 py-2 font-mono text-[13px] text-foreground placeholder:text-muted-foreground/60 focus:border-accent-foreground focus:outline-none"
            />
          </div>
        )}
      </div>

      <Separator className="my-5" />

      <div className="space-y-3">
        <FieldLabel label="翻译缓存" badge="cache" />
        <p className="text-[12px] text-muted-foreground">
          Wikipedia 翻译结果会被缓存以避免重复翻译。修改 LLM 配置后，需清除缓存才会用新配置重新翻译已访问过的页面。
        </p>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={handleClearCache}
            disabled={clearLoading}
          >
            <RefreshCw className={cn('mr-1.5 h-3.5 w-3.5', clearLoading && 'animate-spin')} />
            {clearLoading ? '清除中...' : '清除翻译缓存'}
          </Button>
          {clearMsg && (
            <span className="text-[12px] text-muted-foreground">{clearMsg}</span>
          )}
        </div>
      </div>

      {/* ── Save Profile Dialog ── */}
      {showSaveDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowSaveDialog(false)}>
          <div className="w-full max-w-sm rounded-2xl border border-border bg-card p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-sans text-[16px] font-semibold text-foreground">
              保存 LLM 配置档案
            </h3>
            <p className="mt-1 text-[13px] text-muted-foreground">
              为当前配置命名以便日后快速切换
            </p>
            <input
              type="text"
              value={saveProfileName}
              onChange={(e) => setSaveProfileName(e.target.value)}
              placeholder="例如：DeepSeek、OpenAI GPT-4o"
              className="mt-4 block w-full rounded-lg border border-border bg-muted/40 px-3 py-2 font-sans text-[13px] text-foreground placeholder:text-muted-foreground/60 focus:border-accent-foreground focus:outline-none"
              autoFocus
              onKeyDown={(e) => { if (e.key === 'Enter') handleSaveProfile() }}
            />
            {profileError && (
              <p className="mt-2 text-[12px] text-destructive">{profileError}</p>
            )}
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={() => setShowSaveDialog(false)}>
                取消
              </Button>
              <Button size="sm" onClick={handleSaveProfile} disabled={profileSaving || !saveProfileName.trim()}>
                {profileSaving ? '保存中...' : '保存'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </GlassCard>
  )
}

// ── Version Merge Section ────────────────────────────────────

function VersionMergeSection() {
  const [activeTab, setActiveTab] = useState<MergeTabKey>('detect')
  const vm = useVersionMerge()

  useEffect(() => {
    if (activeTab === 'saved') vm.fetchGroups()
  }, [activeTab, vm.fetchGroups])

  return (
    <GlassCard className="p-6">
      <SectionHeader num={3} title="Version Merge" desc="管理专辑版本合并规则，将同一专辑的不同版本（豪华版、Acoustic版等）合并为统一条目。" />

      {/* Sub-tabs */}
      <div className="mb-5 flex gap-7 border-b border-border">
        {MERGE_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              '-mb-px cursor-pointer border-none bg-transparent px-0 pb-2.5 font-sans text-[13px] font-medium transition-[color,border] duration-200',
              'border-b-2',
              activeTab === tab.key
                ? 'border-accent-foreground font-semibold text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'detect' && <AutoDetectionTab vm={vm} />}
      {activeTab === 'saved' && <SavedGroupsTab vm={vm} />}
      {activeTab === 'create' && <ManualCreateTab vm={vm} />}
    </GlassCard>
  )
}

// ── Tab A: Auto Detection ──────────────────────────────────

function AutoDetectionTab({ vm }: { vm: ReturnType<typeof useVersionMerge> }) {
  const [threshold, setThreshold] = useState(0.4)
  const [results, setResults] = useState<DetectionResult[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [applying, setApplying] = useState(false)
  const [applyMsg, setApplyMsg] = useState('')

  const handleDetect = () => {
    setLoading(true)
    setResults(null)
    setSelected(new Set())
    vm.detectGroups(threshold)
      .then(setResults)
      .finally(() => setLoading(false))
  }

  const toggleGroup = (key: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(key)) { next.delete(key) } else { next.add(key) }
      return next
    })
  }

  const selectAll = () => {
    if (!results) return
    const all = new Set(results.map((r, i) => `${r.artist_id}-${r.canonical_name}-${i}`))
    setSelected(all)
  }

  const deselectAll = () => setSelected(new Set())

  const handleApply = () => {
    if (!results) return
    const confirmed = results.filter((r, i) => selected.has(`${r.artist_id}-${r.canonical_name}-${i}`))
    if (confirmed.length === 0) return
    setApplying(true)
    vm.applyDetected(confirmed).then((res) => {
      setApplyMsg(`成功创建 ${res.created_count} 个分组，跳过 ${res.skipped_count} 个`)
      setApplying(false)
    })
  }

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-end gap-4">
        <div className="space-y-1.5">
          <FieldLabel label="重叠率阈值" badge={threshold} />
          <p className="text-[12px] text-muted-foreground">曲目重叠率高于此值时视为同一专辑的不同版本</p>
          <div className="w-[200px]">
            <Slider
              value={[threshold]}
              onValueChange={(v) => setThreshold((v as number[])[0])}
              min={0.1}
              max={1.0}
              step={0.05}
            />
          </div>
        </div>
        <Button size="sm" onClick={handleDetect} disabled={loading} className="gap-1.5">
          {loading ? <RefreshCw className="size-3.5 animate-spin" /> : <Search className="size-3.5" />}
          {loading ? '检测中...' : '开始检测'}
        </Button>
      </div>

      {/* Results */}
      {results !== null && results.length === 0 && !loading && (
        <div className="py-8 text-center text-[14px] text-muted-foreground">
          未检测到可合并的分组，建议降低重叠率阈值后重试。
        </div>
      )}

      {results && results.length > 0 && (
        <>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={selectAll} className="h-7 text-[12px]">全选</Button>
            <Button variant="ghost" size="sm" onClick={deselectAll} className="h-7 text-[12px]">取消全选</Button>
            <span className="ml-auto text-[12px] text-muted-foreground">
              已选 {selected.size} / {results.length}
            </span>
          </div>

          <div className="max-h-[500px] space-y-3 overflow-y-auto pr-1">
            {results.map((r, i) => {
              const key = `${r.artist_id}-${r.canonical_name}-${i}`
              const isSelected = selected.has(key)
              return (
                <DetectionCard
                  key={key}
                  result={r}
                  isSelected={isSelected}
                  onToggle={() => toggleGroup(key)}
                  compareAlbums={vm.compareAlbums}
                />
              )
            })}
          </div>

          {applyMsg && (
            <div className="flex items-center gap-2 text-[13px] text-green-600 dark:text-green-400">
              <CheckCircle2 className="size-3.5" />
              {applyMsg}
            </div>
          )}

          <Button size="sm" onClick={handleApply} disabled={applying || selected.size === 0} className="gap-1.5">
            {applying ? <RefreshCw className="size-3.5 animate-spin" /> : <Plus className="size-3.5" />}
            {applying ? '应用中...' : `应用选中分组 (${selected.size})`}
          </Button>
        </>
      )}
    </div>
  )
}

function DetectionCard({
  result: r,
  isSelected,
  onToggle,
  compareAlbums,
}: {
  result: DetectionResult
  isSelected: boolean
  onToggle: () => void
  compareAlbums: (aId: number, bId: number) => Promise<TrackComparison>
}) {
  const [compareData, setCompareData] = useState<TrackComparison | null>(null)
  const [compareOpen, setCompareOpen] = useState(false)
  const [compareLoading, setCompareLoading] = useState(false)

  const handleToggleCompare = () => {
    if (!compareOpen && !compareData) {
      setCompareLoading(true)
      compareAlbums(r.primary_album_id, r.members[0]?.album_id ?? r.primary_album_id)
        .then(setCompareData)
        .finally(() => setCompareLoading(false))
    }
    setCompareOpen(!compareOpen)
  }

  return (
    <div
      className={cn(
        'rounded-xl border p-4 transition-colors duration-200',
        isSelected ? 'border-accent-foreground/50 bg-accent-foreground/5' : 'border-border',
      )}
    >
      <div className="flex items-start gap-3">
        <button
          onClick={onToggle}
          className={cn(
            'mt-0.5 flex size-5 shrink-0 items-center justify-center rounded border-2 transition-colors',
            isSelected ? 'border-accent-foreground bg-accent-foreground text-white' : 'border-muted-foreground/30',
          )}
        >
          {isSelected && <CheckCircle2 className="size-3.5" />}
        </button>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate font-sans text-[14px] font-semibold text-foreground">
              {r.canonical_name}
            </span>
            <Badge variant={r.confidence === 'high' ? 'default' : 'secondary'} className="text-[11px]">
              {r.confidence === 'high' ? '高置信' : '低置信'}
            </Badge>
          </div>
          <p className="text-[12.5px] text-muted-foreground">
            {r.artist_name} · {r.member_count} 个版本 · {r.reason}
          </p>

          {/* Members */}
          <div className="mt-2 flex flex-wrap gap-1.5">
            {r.members.map((m: DetectionMember) => (
              <span
                key={m.album_id}
                className={cn(
                  'inline-flex items-center rounded-md border border-border px-2 py-0.5 text-[12px] text-muted-foreground',
                  m.album_id === r.primary_album_id && 'border-accent-foreground/30 text-foreground',
                )}
              >
                {m.album_id === r.primary_album_id && <Star className="mr-1 size-3 text-accent-foreground" />}
                {m.album_name}
              </span>
            ))}
          </div>

          {/* Compare toggle */}
          <button
            onClick={handleToggleCompare}
            className="mt-2 flex items-center gap-1 text-[12px] text-muted-foreground hover:text-foreground transition-colors"
          >
            <ChevronDown className={cn('size-3.5 transition-transform', compareOpen && 'rotate-180')} />
            对比曲目
          </button>
          {compareOpen && (
            <div className="mt-2 rounded-lg border border-border bg-muted/30 p-3">
              {compareLoading ? <Skeleton className="h-16 w-full" /> : <TrackComparePanel data={compareData} />}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Tab B: Saved Groups ─────────────────────────────────────

function SavedGroupsTab({ vm }: { vm: ReturnType<typeof useVersionMerge> }) {
  const { groups, groupsLoading, fetchGroups } = vm

  useEffect(() => {
    fetchGroups()
  }, [fetchGroups])

  if (groupsLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full rounded-xl" />
        ))}
      </div>
    )
  }

  if (groups.length === 0) {
    return (
      <div className="py-8 text-center text-[14px] text-muted-foreground">
        暂无已保存的分组，请使用「自动检测」或「手动创建」功能。
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {groups.map((g) => (
        <SavedGroupCard key={g.group_id} group={g} vm={vm} />
      ))}
    </div>
  )
}

function SavedGroupCard({ group: g, vm }: { group: ReleaseGroup; vm: ReturnType<typeof useVersionMerge> }) {
  const [members, setMembers] = useState<GroupMember[]>([])
  const [membersOpen, setMembersOpen] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const loadMembers = () => {
    if (!membersOpen) {
      vm.getGroupMembers(g.group_id).then(setMembers)
    }
    setMembersOpen(!membersOpen)
  }

  const handleRemoveMember = (albumId: number) => {
    vm.updateMembers(g.group_id, undefined, [albumId]).then(() => {
      setMembers((prev) => prev.filter((m) => m.album_id !== albumId))
      vm.fetchGroups()
    })
  }

  const handleDelete = () => {
    vm.deleteGroup(g.group_id).then(() => vm.fetchGroups())
    setConfirmDelete(false)
  }

  return (
    <div className="rounded-xl border border-border p-4">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-sans text-[14px] font-semibold text-foreground">{g.canonical_name}</span>
            {g.is_manual ? (
              <Badge variant="outline" className="text-[10px]">手动</Badge>
            ) : (
              <Badge variant="outline" className="text-[10px]">自动</Badge>
            )}
          </div>
          <p className="text-[12.5px] text-muted-foreground">{g.artist_name}</p>
          {g.primary_album_name && (
            <p className="mt-1 flex items-center gap-1 text-[12.5px] text-muted-foreground">
              <Star className="size-3 text-accent-foreground" />
              主版本：{g.primary_album_name}
            </p>
          )}
        </div>

        <div className="flex gap-1">
          <Button variant="ghost" size="sm" onClick={loadMembers} className="h-7 text-[12px]">
            {membersOpen ? '收起成员' : '查看成员'}
          </Button>
          {!confirmDelete ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setConfirmDelete(true)}
              className="h-7 text-[12px] text-destructive hover:text-destructive"
            >
              <Trash2 className="size-3" />
            </Button>
          ) : (
            <div className="flex gap-1">
              <Button variant="destructive" size="sm" onClick={handleDelete} className="h-7 text-[12px]">
                确认删除
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(false)} className="h-7 text-[12px]">
                取消
              </Button>
            </div>
          )}
        </div>
      </div>

      {membersOpen && (
        <div className="mt-3 space-y-1 border-t border-border pt-3">
          {members.map((m) => (
            <div key={m.album_id} className="flex items-center justify-between text-[13px]">
              <span className={cn(m.is_primary ? 'font-medium text-foreground' : 'text-muted-foreground')}>
                {m.is_primary ? <Star className="mr-1 inline size-3 text-accent-foreground" /> : null}
                {m.album_name}
              </span>
              <div className="flex gap-1">
                {!m.is_primary && (
                  <>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 text-[11px]"
                      onClick={() => vm.setPrimary(g.group_id, m.album_id).then(() => loadMembers())}
                    >
                      设为主版本
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 text-[11px] text-destructive"
                      onClick={() => handleRemoveMember(m.album_id)}
                    >
                      <X className="size-3" />
                    </Button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Tab C: Manual Create ────────────────────────────────────

function ManualCreateTab({ vm }: { vm: ReturnType<typeof useVersionMerge> }) {
  const [albums, setAlbums] = useState<UngroupedAlbum[]>([])
  const [artistFilter, setArtistFilter] = useState('')
  const [canonicalName, setCanonicalName] = useState('')
  const [selectedAlbums, setSelectedAlbums] = useState<Set<number>>(new Set())
  const [primaryId, setPrimaryId] = useState<number | null>(null)
  const [creating, setCreating] = useState(false)
  const [msg, setMsg] = useState('')

  const loadAlbums = () => {
    vm.getUngroupedAlbums(artistFilter || undefined).then(setAlbums)
  }

  const toggleAlbum = (id: number) => {
    setSelectedAlbums((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
        if (primaryId === id) setPrimaryId(null)
      } else {
        next.add(id)
        if (primaryId === null) setPrimaryId(id)
      }
      return next
    })
  }

  const handleCreate = () => {
    if (!primaryId) return
    const firstAlbum = albums.find((a) => a.album_id === primaryId)
    if (!firstAlbum) return

    // Find artist_id from the first selected album
    setCreating(true)
    // Extract artist_id from album data; the backend expects artist_id as int
    // We don't have artist_id directly from ungrouped albums, so we use a workaround
    vm.createGroup(
      canonicalName || firstAlbum.album_name,
      0, // artist_id will be resolved from members by the backend
      primaryId,
      Array.from(selectedAlbums),
    ).then((res) => {
      if (res.group_id) {
        setMsg(`分组创建成功 (ID: ${res.group_id})`)
        setSelectedAlbums(new Set())
        setPrimaryId(null)
        setCanonicalName('')
      } else {
        setMsg('创建失败')
      }
      setCreating(false)
    })
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-3">
        <div className="flex-1 space-y-1.5">
          <FieldLabel label="艺人筛选" />
          <div className="flex gap-2">
            <input
              type="text"
              value={artistFilter}
              onChange={(e) => setArtistFilter(e.target.value)}
              placeholder="输入艺人名称筛选..."
              className="flex h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-[13px] outline-none focus-visible:border-ring"
            />
            <Button size="sm" variant="outline" onClick={loadAlbums} className="shrink-0">
              查询专辑
            </Button>
          </div>
        </div>
      </div>

      {albums.length > 0 && (
        <>
          <div className="space-y-1.5">
            <FieldLabel label="未分组专辑" badge={`${selectedAlbums.size} 已选`} />
            <div className="max-h-[250px] space-y-0.5 overflow-y-auto rounded-lg border border-border p-2">
              {albums.map((a) => (
                <label
                  key={a.album_id}
                  className={cn(
                    'flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-[13px] transition-colors hover:bg-muted/50',
                    selectedAlbums.has(a.album_id) && 'bg-accent-foreground/5',
                  )}
                >
                  <input
                    type="checkbox"
                    checked={selectedAlbums.has(a.album_id)}
                    onChange={() => toggleAlbum(a.album_id)}
                    className="size-3.5 accent-accent-foreground"
                  />
                  <span className="flex-1 truncate">{a.album_name}</span>
                  <span className="text-[12px] text-muted-foreground">{a.artist_name}</span>
                </label>
              ))}
            </div>
          </div>

          {selectedAlbums.size > 0 && (
            <>
              <div className="space-y-1.5">
                <FieldLabel label="统一名称 (canonical_name)" />
                <input
                  type="text"
                  value={canonicalName}
                  onChange={(e) => setCanonicalName(e.target.value)}
                  placeholder="留空则使用主版本名称"
                  className="flex h-8 w-full max-w-[360px] rounded-lg border border-input bg-transparent px-2.5 text-[13px] outline-none focus-visible:border-ring"
                />
              </div>

              <div className="space-y-1.5">
                <FieldLabel label="主版本" />
                <Select
                  value={primaryId ? String(primaryId) : ''}
                  onValueChange={(v) => setPrimaryId(Number(v))}
                >
                  <SelectTrigger className="w-[280px]">
                    <SelectValue placeholder="选择主版本专辑" />
                  </SelectTrigger>
                  <SelectContent>
                    {albums
                      .filter((a) => selectedAlbums.has(a.album_id))
                      .map((a) => (
                        <SelectItem key={a.album_id} value={String(a.album_id)}>
                          {a.album_name}
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>

              {msg && (
                <div className="flex items-center gap-2 text-[13px] text-green-600 dark:text-green-400">
                  <CheckCircle2 className="size-3.5" />
                  {msg}
                </div>
              )}

              <Button size="sm" onClick={handleCreate} disabled={creating || !primaryId} className="gap-1.5">
                {creating ? <RefreshCw className="size-3.5 animate-spin" /> : <Plus className="size-3.5" />}
                {creating ? '创建中...' : '创建分组'}
              </Button>
            </>
          )}
        </>
      )}

      {albums.length === 0 && (
        <div className="py-8 text-center text-[14px] text-muted-foreground">
          请选择艺人后查询可用的未分组专辑。
        </div>
      )}
    </div>
  )
}

// ── Data Import Section ─────────────────────────────────────

function DataImportSection({
  dbRecordCount,
  accountImported,
  streamingJob,
  accountJob,
  onStreamingImport,
  onAccountImport,
}: {
  dbRecordCount: number
  accountImported: boolean
  streamingJob: ImportJob | null
  accountJob: ImportJob | null
  onStreamingImport: () => void
  onAccountImport: () => void
}) {
  return (
    <GlassCard className="p-6">
      <SectionHeader num={4} title="Data Import" desc="管理流媒体数据和账号数据的导入。导入过程在后台进行，可以离开页面等待。" />

      <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
        <ImportProgressCard
          title="串流数据"
          label={`当前数据库记录数：${new Intl.NumberFormat('zh-CN').format(dbRecordCount)}`}
          job={streamingJob}
          onStart={onStreamingImport}
        />
        <ImportProgressCard
          title="账号数据"
          label="导入 Spotify 账号数据包中的搜索历史、收藏、播客等信息"
          job={accountJob}
          onStart={onAccountImport}
          statusBadge={
            accountImported ? (
              <Badge variant="default" className="text-[11px]">已导入</Badge>
            ) : (
              <Badge variant="secondary" className="text-[11px]">未导入</Badge>
            )
          }
        />
      </div>
    </GlassCard>
  )
}

// ═══════════════════════════════════════════════════════════════
// Main Settings Page
// ═══════════════════════════════════════════════════════════════

export function SettingsPage() {
  const {
    settings,
    loading,
    error,
    refetch,
    updateSettings,
    updateApiKey,
    clearTranslationCache,
    rebuildAgg,
    startStreamingImport,
    startAccountImport,
    streamingJob,
    accountJob,
    spotifyConnect,
    spotifyDisconnect,
    spotifySync,
    fetchProfiles,
    getProfileDetail,
    applyProfile,
    createProfile,
    deleteProfile,
  } = useSettings()

  const [rebuildLoading, setRebuildLoading] = useState(false)
  const [rebuildMsg, setRebuildMsg] = useState('')
  const [chineseStyle, setChineseStyleState] = useState<ChineseStyle>(getChineseStyle)
  const [profiles] = useState<LLMProfile[]>([])

  const handleRebuild = () => {
    setRebuildLoading(true)
    setRebuildMsg('')
    rebuildAgg().then((res) => {
      setRebuildMsg(res.status === 'done' ? '聚合表重建完成' : '重建完成')
      setRebuildLoading(false)
    })
  }

  // ── Loading state ─────────────────────────────────────
  if (loading) {
    return (
      <div className="mx-auto max-w-[900px] space-y-6 px-6 py-12">
        {/* Hero skeleton */}
        <div className="space-y-3">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-10 w-72" />
          <Skeleton className="h-5 w-[420px]" />
        </div>
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-[16px] border border-border bg-card p-6">
            <Skeleton className="mb-4 h-3 w-36" />
            <Skeleton className="mb-1 h-3 w-64" />
            <Skeleton className="h-24 w-full" />
          </div>
        ))}
      </div>
    )
  }

  // ── Error state ───────────────────────────────────────
  if (error && !settings) {
    return (
      <div className="mx-auto flex max-w-[900px] flex-col items-center gap-4 px-6 py-24">
        <AlertCircle className="size-10 text-muted-foreground" />
        <p className="text-[15px] text-muted-foreground">无法加载设置: {error}</p>
        <Button variant="outline" size="sm" onClick={refetch}>
          重试
        </Button>
      </div>
    )
  }

  if (!settings) return null

  return (
    <div className="mx-auto max-w-[900px] space-y-6 px-6 py-12">
      {/* ── Hero ─────────────────────────────────────── */}
      <section className="mb-10">
        <div className="mb-3 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
          Settings / Configuration
        </div>
        <h1 className="font-serif text-[44px] font-bold tracking-[-1.2px] leading-[1.06]">
          参数与配置
        </h1>
        <p className="mt-3 max-w-[520px] font-sans text-[17px] leading-relaxed text-muted-foreground">
          调整数据过滤、Billboard 参数、版本合并规则，以及管理数据导入。
        </p>
      </section>

      {/* ── Section 0: Spotify Connection ─────────────── */}
      <SpotifyConnectionSection
        connected={settings.spotify_connected}
        profile={settings.spotify_profile ?? null}
        onConnect={spotifyConnect}
        onDisconnect={spotifyDisconnect}
        onSync={spotifySync}
      />

      {/* ── Section 1: Data Filtering ────────────────── */}
      <DataFilteringSection
        settings={{
          min_ms: settings.min_ms,
          music_only: settings.music_only,
          merge_enabled: settings.merge_enabled,
        }}
        onUpdate={updateSettings}
        chineseStyle={chineseStyle}
        onChangeChineseStyle={(s: string | null) => {
          const style = (s as ChineseStyle) || 'original'
          setChineseStyleState(style)
          setChineseStyle(style)
        }}
      />

      {/* ── Section 2: Billboard Params ──────────────── */}
      <BillboardParamsSection
        settings={{
          bb_top_n: settings.bb_top_n,
          bb_album_top_n: settings.bb_album_top_n,
          bb_artist_top_n: settings.bb_artist_top_n,
          bb_week_start_dow: settings.bb_week_start_dow,
          bb_week_start_hour: settings.bb_week_start_hour,
        }}
        onUpdate={updateSettings}
        onRebuild={handleRebuild}
        rebuildLoading={rebuildLoading}
      />
      {rebuildMsg && (
        <div className="-mt-3 flex items-center gap-2 pl-6 text-[13px] text-green-600 dark:text-green-400">
          <CheckCircle2 className="size-3.5" />
          {rebuildMsg}
        </div>
      )}

      {/* ── Section 3: Version Merge ─────────────────── */}
      <VersionMergeSection />

      {/* ── Section 4: Data Import ───────────────────── */}
      <DataImportSection
        dbRecordCount={settings.db_record_count}
        accountImported={settings.account_data_imported}
        streamingJob={streamingJob}
        accountJob={accountJob}
        onStreamingImport={startStreamingImport}
        onAccountImport={startAccountImport}
      />

      {/* ── Section 5: LLM Translation ─────────────────── */}
      <LLMTranslationSection
        settings={{
          llm_enabled: settings.llm_enabled,
          llm_provider: settings.llm_provider,
          llm_model: settings.llm_model,
        }}
        onUpdate={updateSettings}
        onUpdateApiKey={updateApiKey}
        onClearCache={clearTranslationCache}
        hasLlmKey={settings.has_llm_key}
        profiles={profiles}
        onFetchProfiles={fetchProfiles}
        onGetProfileDetail={getProfileDetail}
        onApplyProfile={applyProfile}
        onCreateProfile={createProfile}
        onDeleteProfile={deleteProfile}
        onRefetch={refetch}
      />
    </div>
  )
}
