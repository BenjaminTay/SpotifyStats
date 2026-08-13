import { useState, useEffect } from 'react'
import { GlassCard } from '@/components/shared/GlassCard'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { AlertCircle, CheckCircle2, RefreshCw, Link, Unlink } from 'lucide-react'
import type { SpotifyProfile } from '@/types/settings'
import { CollapsibleSection } from '@/features/settings/components/SettingsHelpers'

export interface SpotifyConnectResult {
  total_in_spotify?: number
  total_in_db?: number
  matched?: number
  new_dates?: number
  error?: string
}

function readSpotifyOAuthCallback() {
  if (typeof window === 'undefined') {
    return { notice: '', error: '', shouldCleanUrl: false }
  }
  const params = new URLSearchParams(window.location.search)
  const errorCode = params.get('spotify_error')
  const error = errorCode === 'invalid_state'
    ? '安全校验失败，请重试'
    : errorCode === 'token_exchange_failed'
      ? '令牌交换失败，请重试'
      : errorCode
        ? `授权失败: ${errorCode}`
        : ''
  return {
    notice: params.get('spotify_connected') === 'true' ? 'Spotify 账号连接成功' : '',
    error,
    shouldCleanUrl: params.has('spotify_connected') || params.has('spotify_error'),
  }
}

export function SpotifyConnectionSection({
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
  const [oauthCallback] = useState(readSpotifyOAuthCallback)
  const [connecting, setConnecting] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState<SpotifyConnectResult | null>(null)
  const [syncError, setSyncError] = useState(oauthCallback.error)
  const [notice, setNotice] = useState(oauthCallback.notice)

  // Check URL params for OAuth callback
  useEffect(() => {
    if (oauthCallback.shouldCleanUrl) {
      const url = new URL(window.location.href)
      url.searchParams.delete('spotify_connected')
      url.searchParams.delete('spotify_error')
      window.history.replaceState({}, '', url.toString())
    }
  }, [oauthCallback])

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
      <CollapsibleSection
        num={1}
        title="Spotify 连接"
        desc="连接你的 Spotify 账号以获取收藏时间、播放列表等个人数据。仅请求 user-library-read 权限。"
        defaultOpen={!connected}
        summary={connected ? '已连接，可同步收藏时间' : undefined}
      >

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
        <p className="mt-4 font-sans text-[12px] text-muted-foreground leading-relaxed">
          连接后可同步 Spotify Library 中每首歌的收藏日期（added_at），让音乐档案中的收藏旅程与回访分析建立在真实日期上。如需导入 Extended Streaming History JSON 数据，请前往「02 · 数据导入」。
        </p>
      )}
      </CollapsibleSection>
    </GlassCard>
  )
}
