import { useEffect, useMemo, useState, type ComponentType, type ReactNode, type SelectHTMLAttributes } from 'react'
import {
  ArrowLeft,
  BarChart3,
  Bot,
  CheckCircle2,
  ChevronRight,
  Database,
  ExternalLink,
  Laptop,
  Link2,
  Moon,
  Palette,
  ShieldCheck,
  SlidersHorizontal,
  Sun,
} from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'

import { useTheme } from '@/hooks/useTheme'
import { setDynamicThreshold, setMaxMergeGapMinutes } from '@/hooks/useAnalysis'
import { getDefaultMergeLevel, setDefaultMergeLevel } from '@/lib/merge-level'
import { getBillboardName, setBillboardName } from '@/lib/billboard-name'
import type { ChineseStyle } from '@/lib/chinese'
import type { LLMProfile, SettingsData, SettingsUpdatePayload } from '@/types/settings'
import { cn } from '@/lib/utils'
import { PwaInstallCard } from './PwaInstallCard'

type Panel = 'appearance' | 'playback' | 'billboard' | 'spotify' | 'data' | 'ai' | 'advanced'

interface MobileSettingsExperienceProps {
  settings: SettingsData
  rebuildPending: boolean
  chineseStyle: ChineseStyle
  onChangeChineseStyle: (style: ChineseStyle) => void
  onUpdate: (payload: SettingsUpdatePayload) => Promise<void>
  onRequiresRebuild: () => void
  onSpotifyConnect: () => Promise<{ auth_url: string; state: string }>
  onSpotifyDisconnect: () => Promise<void>
  onSpotifySync: () => Promise<{ success: boolean; new_dates?: number; matched?: number; error?: string }>
  onFetchProfiles: () => Promise<LLMProfile[]>
  onApplyProfile: (profileId: number) => Promise<{ status: string; profile_id: number }>
}

interface Category {
  id: Panel
  title: string
  description: string
  status: string
  icon: ComponentType<{ className?: string }>
  advanced?: boolean
}

function storedBool(key: string, fallback: boolean): boolean {
  try {
    const value = localStorage.getItem(key)
    return value == null ? fallback : value !== 'false'
  } catch {
    return fallback
  }
}

function storedGap(): string {
  try { return localStorage.getItem('spotify_stats_max_merge_gap_minutes') ?? '' } catch { return '' }
}

function SettingRow({
  label,
  description,
  children,
}: {
  label: string
  description?: string
  children: ReactNode
}) {
  return (
    <div className="mobile-settings-row">
      <div className="min-w-0 flex-1">
        <p>{label}</p>
        {description && <span>{description}</span>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  )
}

function Switch({ checked, onChange, label }: { checked: boolean; onChange: (next: boolean) => void; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      className={cn('mobile-settings-switch', checked && 'mobile-settings-switch-on')}
      onClick={() => onChange(!checked)}
    >
      <span />
    </button>
  )
}

function SelectField(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={cn('mobile-settings-select', props.className)} />
}

function PanelHeader({ title, onBack }: { title: string; onBack: () => void }) {
  return (
    <header className="mobile-settings-panel-header">
      <button type="button" onClick={onBack} aria-label="返回设置首页">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
      </button>
      <div>
        <p>Settings / Mobile</p>
        <h1>{title}</h1>
      </div>
    </header>
  )
}

export function MobileSettingsExperience({
  settings,
  rebuildPending,
  chineseStyle,
  onChangeChineseStyle,
  onUpdate,
  onRequiresRebuild,
  onSpotifyConnect,
  onSpotifyDisconnect,
  onSpotifySync,
  onFetchProfiles,
  onApplyProfile,
}: MobileSettingsExperienceProps) {
  const [searchParams, setSearchParams] = useSearchParams()
  const metadataTarget = searchParams.get('metadata')
  const routePanel = searchParams.get('panel') as Panel | null
  const panel = metadataTarget ? 'advanced' : routePanel
  const { theme, setTheme } = useTheme()
  const [dynamicThreshold, setDynamicThresholdState] = useState(() => storedBool('spotify_stats_dynamic_threshold', true))
  const [mergeLevel, setMergeLevel] = useState(getDefaultMergeLevel)
  const [mergeGap, setMergeGap] = useState(storedGap)
  const [billboardDisplayName, setBillboardDisplayName] = useState(() => getBillboardName())
  const [spotifyBusy, setSpotifyBusy] = useState<'connect' | 'sync' | 'disconnect' | null>(null)
  const [spotifyMessage, setSpotifyMessage] = useState('')
  const [llmProfiles, setLlmProfiles] = useState<LLMProfile[]>([])
  const [profilesLoading, setProfilesLoading] = useState(panel === 'ai')
  const [profileBusy, setProfileBusy] = useState(false)
  const [profileMessage, setProfileMessage] = useState('')

  useEffect(() => {
    if (panel !== 'ai') return
    let active = true
    void onFetchProfiles()
      .then((profiles) => {
        if (active) setLlmProfiles(profiles)
      })
      .catch((error) => {
        if (active) setProfileMessage(error instanceof Error ? error.message : '无法加载配置档案')
      })
      .finally(() => {
        if (active) setProfilesLoading(false)
      })
    return () => { active = false }
  }, [onFetchProfiles, panel])

  const metadataSummary = useMemo(() => {
    if (metadataTarget === 'track-credits') {
      const trackId = searchParams.get('track_id')
      return trackId ? `曲目署名 · Track ${trackId}` : '曲目署名'
    }
    if (metadataTarget === 'album-projects') {
      const album = searchParams.get('album_name')
      const artist = searchParams.get('artist')
      return [album || '专辑版本与发行项目', artist].filter(Boolean).join(' · ')
    }
    if (metadataTarget === 'artist-identities') {
      const artist = searchParams.get('artist')
      return artist ? `艺人身份归并 · ${artist}` : '艺人身份归并'
    }
    return metadataTarget
  }, [metadataTarget, searchParams])

  const setPanel = (next: Panel | null) => {
    if (next === 'ai') {
      setProfilesLoading(true)
      setProfileMessage('')
    }
    setSearchParams((current) => {
      const params = new URLSearchParams(current)
      params.delete('metadata')
      params.delete('track_id')
      params.delete('album_name')
      params.delete('artist')
      if (next) params.set('panel', next)
      else params.delete('panel')
      return params
    }, { replace: true })
  }

  const categories = useMemo<Category[]>(() => [
    { id: 'appearance', title: '外观与名称', description: '主题、中文显示和榜单名称', status: theme === 'dark' ? '深色' : '浅色', icon: Palette },
    { id: 'playback', title: '播放统计', description: '有效播放、合并与内容过滤', status: dynamicThreshold ? '动态阈值' : `${settings.min_ms / 1000}s`, icon: SlidersHorizontal },
    { id: 'billboard', title: '榜单参数', description: 'Top N、周边界与精选集', status: `单曲 Top ${settings.bb_top_n}`, icon: BarChart3 },
    { id: 'spotify', title: 'Spotify 连接', description: '授权状态与收藏时间同步', status: settings.spotify_connected ? '已连接' : '未连接', icon: Link2 },
    { id: 'data', title: '数据状态', description: '播放记录、账号数据与待重建状态', status: `${settings.db_record_count.toLocaleString('zh-CN')} 条`, icon: Database },
    { id: 'ai', title: 'AI 洞察', description: '启用状态与当前配置档案', status: settings.llm_enabled ? '已启用' : '未启用', icon: Bot },
    { id: 'advanced', title: '高级数据管理', description: '导入、归并、署名、元数据与系统维护', status: rebuildPending ? '有待处理项' : '电脑端管理', icon: ShieldCheck, advanced: true },
  ], [dynamicThreshold, rebuildPending, settings, theme])

  const updateAndRebuild = (payload: SettingsUpdatePayload) => {
    void onUpdate(payload)
    onRequiresRebuild()
  }

  const renderPanel = () => {
    if (panel === 'appearance') {
      return (
        <div className="mobile-settings-panel-card">
          <SettingRow label="界面主题" description="立即应用到全部页面">
            <div className="mobile-settings-segment">
              <button type="button" aria-pressed={theme === 'light'} onClick={() => setTheme('light')}><Sun className="h-4 w-4" />浅色</button>
              <button type="button" aria-pressed={theme === 'dark'} onClick={() => setTheme('dark')}><Moon className="h-4 w-4" />深色</button>
            </div>
          </SettingRow>
          <SettingRow label="中文名称显示" description="只改变界面文案，不修改数据库">
            <SelectField value={chineseStyle} onChange={(event) => onChangeChineseStyle(event.target.value as ChineseStyle)} aria-label="中文名称显示">
              <option value="original">原样</option><option value="simplified">简体</option><option value="traditional">繁体</option>
            </SelectField>
          </SettingRow>
          <label className="mobile-settings-field mobile-settings-field-block">
            <span>榜单显示名称</span>
            <input
              value={billboardDisplayName}
              onChange={(event) => {
                const value = event.target.value
                setBillboardDisplayName(value)
                setBillboardName(value || 'Billboard')
              }}
              placeholder="Billboard"
            />
          </label>
        </div>
      )
    }

    if (panel === 'playback') {
      return (
        <div className="mobile-settings-panel-card">
          <SettingRow label="动态有效播放阈值" description="按歌曲时长计算有效播放">
            <Switch checked={dynamicThreshold} label="动态有效播放阈值" onChange={(next) => { setDynamicThresholdState(next); setDynamicThreshold(next); onRequiresRebuild() }} />
          </SettingRow>
          <SettingRow label="固定最短时长" description="关闭动态阈值时作为兜底">
            <SelectField value={settings.min_ms} onChange={(event) => updateAndRebuild({ min_ms: Number(event.target.value) })} aria-label="固定最短播放时长">
              <option value={0}>不过滤</option><option value={10_000}>10 秒</option><option value={30_000}>30 秒</option><option value={60_000}>60 秒</option><option value={120_000}>120 秒</option>
            </SelectField>
          </SettingRow>
          <SettingRow label="仅统计音乐" description="排除播客和有声书">
            <Switch checked={settings.music_only} label="仅统计音乐" onChange={(next) => updateAndRebuild({ music_only: next })} />
          </SettingRow>
          <SettingRow label="合并连续播放" description="连续播放同一曲目合并为一次">
            <Switch checked={settings.merge_enabled} label="合并连续播放" onChange={(next) => updateAndRebuild({ merge_enabled: next })} />
          </SettingRow>
          <SettingRow label="统计合并级别" description="L1 原始版本，L3 合并到作品">
            <SelectField value={mergeLevel} onChange={(event) => { const next = Number(event.target.value); setMergeLevel(next); setDefaultMergeLevel(next); onRequiresRebuild() }} aria-label="统计合并级别">
              <option value={1}>L1 原始</option><option value={2}>L2 发行项目</option><option value={3}>L3 作品</option>
            </SelectField>
          </SettingRow>
          {settings.merge_enabled && (
            <label className="mobile-settings-field mobile-settings-field-block">
              <span>连续播放最大间隔（分钟）</span>
              <input
                type="number" min={1} max={240} value={mergeGap} placeholder="无限制"
                onChange={(event) => {
                  const value = event.target.value
                  setMergeGap(value)
                  const parsed = Number(value)
                  setMaxMergeGapMinutes(parsed >= 1 && parsed <= 240 ? parsed : undefined)
                  onRequiresRebuild()
                }}
              />
            </label>
          )}
        </div>
      )
    }

    if (panel === 'billboard') {
      return (
        <div className="mobile-settings-panel-card">
          {([
            ['单曲榜容量', 'bb_top_n', settings.bb_top_n, 10],
            ['专辑榜容量', 'bb_album_top_n', settings.bb_album_top_n, 5],
            ['艺人榜容量', 'bb_artist_top_n', settings.bb_artist_top_n, 5],
          ] as const).map(([label, key, value, min]) => (
            <label key={key} className="mobile-settings-field mobile-settings-field-block">
              <span>{label} · Top {value}</span>
              <input type="range" min={min} max={100} step={5} value={value} onChange={(event) => updateAndRebuild({ [key]: Number(event.target.value) } as SettingsUpdatePayload)} />
            </label>
          ))}
          <SettingRow label="榜单周起始日" description="默认周五开始">
            <SelectField value={settings.bb_week_start_dow} onChange={(event) => updateAndRebuild({ bb_week_start_dow: Number(event.target.value) })} aria-label="榜单周起始日">
              {['周一', '周二', '周三', '周四', '周五', '周六', '周日'].map((label, index) => <option key={label} value={index}>{label}</option>)}
            </SelectField>
          </SettingRow>
          <SettingRow label="包含精选集" description="把 compilation 纳入专辑统计">
            <Switch checked={settings.include_compilations} label="包含精选集" onChange={(next) => updateAndRebuild({ include_compilations: next })} />
          </SettingRow>
        </div>
      )
    }

    if (panel === 'spotify') {
      const runSpotify = async (action: 'connect' | 'sync' | 'disconnect') => {
        setSpotifyBusy(action)
        setSpotifyMessage('')
        try {
          if (action === 'connect') {
            const result = await onSpotifyConnect()
            window.location.assign(result.auth_url)
            return
          }
          if (action === 'disconnect') {
            await onSpotifyDisconnect()
            setSpotifyMessage('已断开 Spotify 连接')
          } else {
            const result = await onSpotifySync()
            setSpotifyMessage(result.error || `同步完成，更新 ${result.new_dates ?? result.matched ?? 0} 首歌曲`)
          }
        } catch (error) {
          setSpotifyMessage(error instanceof Error ? error.message : '操作失败，请重试')
        } finally {
          setSpotifyBusy(null)
        }
      }
      return (
        <div className="mobile-settings-panel-card space-y-4">
          <div className="mobile-settings-status-hero">
            <CheckCircle2 className={cn('h-6 w-6', settings.spotify_connected ? 'text-emerald-500' : 'text-muted-foreground')} />
            <div><strong>{settings.spotify_connected ? 'Spotify 已连接' : '尚未连接 Spotify'}</strong><span>{settings.spotify_profile?.display_name || '连接后可同步收藏日期与账号资料'}</span></div>
          </div>
          <div className="grid gap-2">
            {!settings.spotify_connected ? (
              <button type="button" className="mobile-primary-button" disabled={spotifyBusy !== null} onClick={() => void runSpotify('connect')}>{spotifyBusy === 'connect' ? '正在跳转…' : '连接 Spotify'}</button>
            ) : (
              <><button type="button" className="mobile-primary-button" disabled={spotifyBusy !== null} onClick={() => void runSpotify('sync')}>{spotifyBusy === 'sync' ? '同步中…' : '同步收藏时间'}</button><button type="button" className="mobile-secondary-button" disabled={spotifyBusy !== null} onClick={() => void runSpotify('disconnect')}>断开连接</button></>
            )}
          </div>
          {spotifyMessage && <p className="mobile-settings-notice">{spotifyMessage}</p>}
        </div>
      )
    }

    if (panel === 'data') {
      return (
        <div className="mobile-settings-panel-card">
          <SettingRow label="播放记录" description="本地 SQLite 中的已导入记录"><strong>{settings.db_record_count.toLocaleString('zh-CN')} 条</strong></SettingRow>
          <SettingRow label="账号资料" description="收藏、搜索、播客与视频数据"><strong>{settings.account_data_imported ? '已导入' : '未导入'}</strong></SettingRow>
          <SettingRow label="统计聚合" description="参数变更后的计算状态"><strong className={rebuildPending ? 'text-amber-500' : 'text-emerald-500'}>{rebuildPending ? '等待重建 · 统计可能不是最新' : '已同步'}</strong></SettingRow>
          <p className="mobile-settings-explanation">{rebuildPending ? '当前页面的聚合统计可能尚未反映最新参数。' : '当前统计已经同步。'}文件导入、聚合重建和故障排查请在电脑上完成。</p>
        </div>
      )
    }

    if (panel === 'ai') {
      const applySelectedProfile = async (profileId: number) => {
        setProfileBusy(true)
        setProfileMessage('')
        try {
          await onApplyProfile(profileId)
          setProfileMessage('当前配置档案已切换')
        } catch (error) {
          setProfileMessage(error instanceof Error ? error.message : '切换失败，请重试')
        } finally {
          setProfileBusy(false)
        }
      }
      return (
        <div className="mobile-settings-panel-card">
          <SettingRow label="启用 AI 洞察" description={settings.has_llm_key ? '用于报告和只读问答' : '需要先在电脑端配置 API 密钥'}>
            <Switch checked={settings.llm_enabled} label="启用 AI 洞察" onChange={(next) => void onUpdate({ llm_enabled: next })} />
          </SettingRow>
          <SettingRow label="当前配置档案" description={`${settings.llm_provider} · ${settings.llm_model}`}>
            <SelectField
              aria-label="当前 AI 配置档案"
              value={settings.llm_active_profile_id ?? ''}
              disabled={profilesLoading || profileBusy || llmProfiles.length === 0}
              onChange={(event) => void applySelectedProfile(Number(event.target.value))}
            >
              {settings.llm_active_profile_id == null && <option value="">默认档案</option>}
              {llmProfiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.profile_name}</option>)}
            </SelectField>
          </SettingRow>
          <SettingRow label="API 密钥" description="手机端不展示或编辑敏感凭据"><strong>{settings.has_llm_key ? '已配置' : '未配置'}</strong></SettingRow>
          {profilesLoading && <p className="mobile-settings-notice">正在加载配置档案…</p>}
          {profileMessage && <p className="mobile-settings-notice">{profileMessage}</p>}
          <p className="mobile-settings-explanation"><Laptop className="h-4 w-4" />新增档案、修改模型地址或 API 密钥，请在电脑端设置中完成。</p>
        </div>
      )
    }

    return (
      <div className="space-y-3">
        {metadataTarget && (
          <div className="mobile-settings-deep-link">
            <ShieldCheck className="h-5 w-5" />
            <div><strong>已定位高级治理任务</strong><span>{metadataSummary}</span></div>
          </div>
        )}
        {[
          ['数据导入', settings.account_data_imported ? '账号数据已导入' : '账号数据待导入'],
          ['音乐源数据管理', '归并、曲目署名、艺人身份、流派与语言'],
          ['LLM 完整配置', settings.has_llm_key ? '密钥已配置' : '密钥待配置'],
          ['系统维护', rebuildPending ? '聚合表等待重建，统计可能不是最新' : '当前无需重建'],
        ].map(([title, status]) => (
          <div key={title} className="mobile-settings-advanced-card">
            <div><strong>{title}</strong><span>{status}</span></div>
            <span><Laptop className="h-4 w-4" />在电脑上管理</span>
          </div>
        ))}
        {searchParams.get('return_to') && (
          <Link className="mobile-secondary-button w-full" to={searchParams.get('return_to') || '/'}>
            返回原页面 <ExternalLink className="h-4 w-4" />
          </Link>
        )}
      </div>
    )
  }

  if (panel) {
    const title = categories.find((item) => item.id === panel)?.title ?? '设置'
    return <div className="mobile-settings-page"><PanelHeader title={title} onBack={() => setPanel(null)} />{renderPanel()}</div>
  }

  return (
    <div className="mobile-settings-page" data-mobile-settings="landing">
      <header className="mobile-settings-landing-header">
        <p>Preferences / Mobile</p>
        <h1>设置</h1>
        <span>日常参数可直接调整，高级数据治理会引导到电脑端。</span>
      </header>
      <div className="mobile-settings-health-strip">
        <span><Database className="h-4 w-4" />{settings.db_record_count.toLocaleString('zh-CN')} 条播放</span>
        <span className={rebuildPending ? 'text-amber-500' : 'text-emerald-500'}>{rebuildPending ? '等待重建 · 统计可能不是最新' : '统计已同步'}</span>
      </div>
      <PwaInstallCard />
      <div className="mobile-settings-categories">
        {categories.map(({ id, title, description, status, icon: Icon, advanced }) => (
          <button key={id} type="button" onClick={() => setPanel(id)} className={cn('mobile-settings-category', advanced && 'mobile-settings-category-advanced')}>
            <span className="mobile-settings-category-icon"><Icon className="h-5 w-5" /></span>
            <span className="min-w-0 flex-1 text-left"><strong>{title}</strong><small>{description}</small><em>{status}</em></span>
            <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
          </button>
        ))}
      </div>
    </div>
  )
}
