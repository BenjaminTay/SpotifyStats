import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { GlassCard } from '@/components/shared/GlassCard'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'
import { CheckCircle2, Plus, RefreshCw, Trash2 } from 'lucide-react'
import anthropicLogoUrl from '@/assets/provider-logos/anthropic.svg?url'
import deepseekLogoUrl from '@/assets/provider-logos/deepseek.svg?url'
import openaiLogoUrl from '@/assets/provider-logos/openai.svg?url'
import type { SettingsUpdatePayload, LLMProfile, LLMProfileCreatePayload } from '@/types/settings'
import { CollapsibleSection, Toggle, FieldLabel, InlineNotice } from '@/features/settings/components/SettingsHelpers'

const LLM_PROVIDERS = [
  {
    value: 'deepseek',
    label: 'DeepSeek',
    defaultModel: 'deepseek-chat',
    avatar: 'DS',
    avatarClass: 'bg-emerald-500/10 text-emerald-700 ring-emerald-500/20 dark:text-emerald-200',
    logoUrl: deepseekLogoUrl,
  },
  {
    value: 'openai',
    label: 'OpenAI',
    defaultModel: 'gpt-4o-mini',
    avatar: 'AI',
    avatarClass: 'bg-zinc-500/10 text-zinc-700 ring-zinc-500/20 dark:text-zinc-200',
    logoUrl: openaiLogoUrl,
  },
  {
    value: 'anthropic',
    label: 'Anthropic',
    defaultModel: 'claude-haiku-4-5-20251001',
    avatar: 'A',
    avatarClass: 'bg-amber-500/10 text-amber-700 ring-amber-500/20 dark:text-amber-200',
    logoUrl: anthropicLogoUrl,
  },
  {
    value: 'custom',
    label: '自定义',
    defaultModel: '',
    avatar: 'API',
    avatarClass: 'bg-sky-500/10 text-sky-700 ring-sky-500/20 dark:text-sky-200',
  },
]

const inputClass = 'block w-full rounded-lg border border-border bg-muted/40 px-3 py-2 font-sans text-[13px] text-foreground placeholder:text-muted-foreground/60 focus:border-accent-foreground focus:outline-none'
const monoInputClass = 'block w-full rounded-lg border border-border bg-muted/40 px-3 py-2 font-mono text-[13px] text-foreground placeholder:text-muted-foreground/60 focus:border-accent-foreground focus:outline-none'

function getProviderLabel(provider: string) {
  return LLM_PROVIDERS.find((p) => p.value === provider)?.label || provider || '未配置'
}

function getProviderDefaultModel(provider: string) {
  return LLM_PROVIDERS.find((p) => p.value === provider)?.defaultModel || ''
}

function getProviderAvatar(provider: string) {
  const preset = LLM_PROVIDERS.find((p) => p.value === provider)
  if (preset) return { className: preset.avatarClass, logoUrl: preset.logoUrl, text: preset.avatar }
  return {
    className: 'bg-muted text-muted-foreground ring-border',
    logoUrl: undefined,
    text: (provider || 'AI').slice(0, 3).toUpperCase(),
  }
}

function ProviderLogoAvatar({ label, provider }: { label: string; provider: string }) {
  const [imageFailed, setImageFailed] = useState(false)
  const avatar = getProviderAvatar(provider)
  const ariaLabel = `${label} 模型头像`

  if (avatar.logoUrl && !imageFailed) {
    return (
      <div className="flex size-12 shrink-0 items-center justify-center rounded-full bg-white shadow-sm ring-1 ring-border">
        <img
          src={avatar.logoUrl}
          alt={ariaLabel}
          className="size-7 object-contain"
          draggable={false}
          onError={() => setImageFailed(true)}
        />
      </div>
    )
  }

  return (
    <div
      role="img"
      aria-label={ariaLabel}
      className={cn(
        'flex size-12 shrink-0 items-center justify-center rounded-full font-sans text-[14px] font-bold tracking-[0.2px] ring-1',
        avatar.className,
      )}
    >
      {avatar.text}
    </div>
  )
}

export function LLMTranslationSection({
  settings,
  onUpdate,
  onClearCache,
  hasLlmKey,
  onFetchProfiles,
  onApplyProfile,
  onCreateProfile,
  onDeleteProfile,
  onRefetch,
}: {
  settings: { llm_enabled: boolean; llm_provider: string; llm_model: string }
  onUpdate: (p: SettingsUpdatePayload) => void
  onClearCache: () => Promise<{ deleted_count: number }>
  hasLlmKey: boolean
  onFetchProfiles: () => Promise<LLMProfile[]>
  onApplyProfile: (profileId: number) => Promise<{ status: string; profile_id: number }>
  onCreateProfile: (payload: LLMProfileCreatePayload) => Promise<{ id: number; status: string }>
  onDeleteProfile: (profileId: number) => Promise<{ status: string }>
  onRefetch: () => void
}) {
  const [notice, setNotice] = useState(false)
  const [clearMsg, setClearMsg] = useState('')
  const [clearLoading, setClearLoading] = useState(false)
  const [localProfiles, setLocalProfiles] = useState<LLMProfile[]>([])
  const [selectedProfileId, setSelectedProfileId] = useState<number | null>(null)

  // ── Add/Edit Profile Modal ──
  const [showProfileModal, setShowProfileModal] = useState(false)
  const [profileSaving, setProfileSaving] = useState(false)
  const [profileError, setProfileError] = useState('')

  // Form fields for the modal
  const [formProfileName, setFormProfileName] = useState('')
  const [formProvider, setFormProvider] = useState('deepseek')
  const [formModel, setFormModel] = useState('')
  const [formApiKey, setFormApiKey] = useState('')
  const [formBaseUrl, setFormBaseUrl] = useState('')

  const currentProvider = LLM_PROVIDERS.find((p) => p.value === settings.llm_provider)
  const activeModel = settings.llm_model || currentProvider?.defaultModel || '未配置'
  const activeProviderLabel = currentProvider?.label || settings.llm_provider || '未配置'
  const formIsCustom = formProvider === 'custom'

  useEffect(() => {
    let active = true
    onFetchProfiles()
      .then((items) => {
        if (active) setLocalProfiles(items)
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [onFetchProfiles])

  const update = (p: SettingsUpdatePayload) => {
    onUpdate(p)
    setNotice(true)
    setTimeout(() => setNotice(false), 3000)
  }

  // ── Profile selection ──

  const handleSelectProfile = (profileId: number) => {
    setSelectedProfileId(profileId)
    onApplyProfile(profileId).then(() => {
      onRefetch()
      setNotice(true)
      setTimeout(() => setNotice(false), 3000)
    })
  }

  const handleDeleteProfile = (profileId: number) => {
    onDeleteProfile(profileId).then(() => {
      if (selectedProfileId === profileId) {
        setSelectedProfileId(null)
      }
      onFetchProfiles().then(setLocalProfiles)
    })
  }

  // ── Add Profile Modal ──

  const openAddProfileModal = () => {
    setFormProfileName('')
    setFormProvider('deepseek')
    setFormModel(LLM_PROVIDERS.find(p => p.value === 'deepseek')?.defaultModel || '')
    setFormApiKey('')
    setFormBaseUrl('')
    setProfileError('')
    setShowProfileModal(true)
  }

  const handleFormProviderChange = (provider: string | null) => {
    if (!provider) return
    setFormProvider(provider)
    const preset = LLM_PROVIDERS.find((p) => p.value === provider)
    setFormModel(preset?.defaultModel || '')
  }

  const handleSaveProfile = () => {
    if (!formProfileName.trim()) return
    setProfileSaving(true)
    setProfileError('')
    onCreateProfile({
      profile_name: formProfileName.trim(),
      llm_provider: formProvider,
      llm_model: formModel.trim(),
      llm_api_key: formApiKey.trim(),
      llm_base_url: formIsCustom ? formBaseUrl.trim() : '',
    }).then((res) => {
      setProfileSaving(false)
      setShowProfileModal(false)
      // Auto-select the newly created profile
      onFetchProfiles().then((updated) => {
        setLocalProfiles(updated)
        setSelectedProfileId(res.id)
        onApplyProfile(res.id).then(() => {
          onRefetch()
          setNotice(true)
          setTimeout(() => setNotice(false), 3000)
        })
      })
    }).catch((e: Error) => {
      setProfileSaving(false)
      setProfileError(e.message || '保存失败')
    })
  }

  // ── Cache ──

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
      <CollapsibleSection num={6} title="LLM 配置" desc="配置大模型供应商与模型，用于 Wikipedia 翻译、歌曲/专辑/艺人详情页智能摘要、AI 洞察报告与对话等场景。">

      <InlineNotice show={notice}>LLM 配置已保存。</InlineNotice>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.35fr)_minmax(260px,0.65fr)]">
        <div className="rounded-xl border border-border bg-muted/25 p-5">
          <div className="font-sans text-[11px] font-semibold uppercase tracking-[1.4px] text-muted-foreground">
            当前模型
          </div>
          <div className="mt-3 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div className="flex min-w-0 items-center gap-3">
              <ProviderLogoAvatar label={activeProviderLabel} provider={settings.llm_provider} />
              <div className="min-w-0">
                <div className="font-sans text-[20px] font-semibold leading-tight text-foreground">
                  {activeProviderLabel}
                </div>
                <div className="mt-1 truncate font-mono text-[13px] text-muted-foreground">
                  {activeModel}
                </div>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <span
                className={cn(
                  'inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[12px] font-medium',
                  hasLlmKey
                    ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
                    : 'bg-destructive/10 text-destructive',
                )}
              >
                {hasLlmKey && <CheckCircle2 className="size-3" />}
                {hasLlmKey ? 'Key 已配置' : '缺少 API Key'}
              </span>
            </div>
          </div>
          <p className="mt-4 max-w-[620px] text-[12.5px] leading-relaxed text-muted-foreground">
            {hasLlmKey
              ? '当前配置可用于 AI 洞察、智能摘要和详情页增强；Wikipedia 翻译由下方开关单独控制。'
              : '添加带 API Key 的配置档案后，AI 洞察、智能摘要和 LLM 翻译才能调用模型。'}
          </p>
        </div>

        <div className="rounded-xl border border-border bg-card/70 p-5">
          <div className="font-sans text-[11px] font-semibold uppercase tracking-[1.4px] text-muted-foreground">
            快速操作
          </div>
          <div className="mt-4 space-y-3">
            <Button variant="default" size="sm" onClick={openAddProfileModal} className="w-full gap-1.5">
              <Plus className="size-3.5" />
              添加配置
            </Button>
            <p className="rounded-lg border border-border bg-muted/25 p-3 text-[12px] leading-relaxed text-muted-foreground">
              新增 DeepSeek、OpenAI、Anthropic 或自定义兼容接口配置；选择档案后会立即切换当前模型。
            </p>
          </div>
        </div>
      </div>

      <Separator className="my-5" />

      <div className="space-y-3">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <FieldLabel label="配置档案" badge="profile" />
            <p className="mt-1 text-[12px] text-muted-foreground">
              选择后立即应用，API Key 只在后端保存与切换，不会回传到前端。
            </p>
          </div>
          <span className="font-sans text-[11px] uppercase tracking-[1.4px] text-muted-foreground">
            选择后立即应用
          </span>
        </div>

        {localProfiles.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border bg-muted/20 p-5 text-[13px] text-muted-foreground">
            暂无已保存的配置档案。添加后可在 DeepSeek、OpenAI、Anthropic 或自定义兼容接口之间快速切换。
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-2">
            {localProfiles.map((profile) => {
              const selected = selectedProfileId === profile.id
              const model = profile.llm_model || getProviderDefaultModel(profile.llm_provider) || '未指定模型'
              return (
                <div
                  key={profile.id}
                  className={cn(
                    'flex items-stretch gap-2 rounded-xl border bg-muted/20 p-2 transition-colors',
                    selected ? 'border-accent-foreground bg-accent-foreground/5' : 'border-border',
                  )}
                >
                  <button
                    type="button"
                    onClick={() => handleSelectProfile(profile.id)}
                    className="min-w-0 flex-1 rounded-lg px-3 py-2 text-left transition-colors hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-sans text-[13.5px] font-medium text-foreground">
                        {profile.profile_name}
                      </span>
                      {selected && (
                        <span className="rounded-full bg-accent-foreground/10 px-2 py-0.5 text-[11px] font-medium text-accent-foreground">
                          当前
                        </span>
                      )}
                    </div>
                    <div className="mt-1 truncate font-mono text-[12px] text-muted-foreground">
                      {getProviderLabel(profile.llm_provider)} · {model}
                    </div>
                  </button>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`删除 ${profile.profile_name}`}
                    onClick={() => handleDeleteProfile(profile.id)}
                    className="self-center text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </div>
              )
            })}
          </div>
        )}
      </div>

      <Separator className="my-5" />

      <div className="space-y-3">
        <div className="font-sans text-[11px] font-semibold uppercase tracking-[1.4px] text-muted-foreground">
          翻译与缓存
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="rounded-xl border border-border bg-muted/20 p-4">
            <FieldLabel label="Wikipedia 翻译" badge="llm_enabled" />
            <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
              关闭时翻译回退为普通机翻；模型配置本身仍供 AI 洞察和智能摘要使用。
            </p>
            <div className="mt-3">
              <Toggle
                checked={settings.llm_enabled}
                onChange={(v) => update({ llm_enabled: v })}
                label="启用 Wikipedia LLM 翻译"
              />
            </div>
          </div>

          <div className="rounded-xl border border-border bg-muted/20 p-4">
            <FieldLabel label="翻译缓存" badge="cache" />
            <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
              修改模型后清除缓存，已访问过的 Wikipedia 内容会按新配置重新翻译。
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-3">
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
        </div>
      </div>

      {/* ── Add Profile Modal ── */}
      {showProfileModal && typeof document !== 'undefined' && createPortal((
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 px-4 py-6 backdrop-blur-sm" onClick={() => setShowProfileModal(false)}>
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="llm-profile-modal-title"
            aria-describedby="llm-profile-modal-description"
            className="max-h-[min(720px,calc(100vh-48px))] w-[calc(100vw-32px)] max-w-md overflow-y-auto rounded-2xl border border-border bg-background p-6 shadow-2xl ring-1 ring-border/60"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="llm-profile-modal-title" className="font-sans text-[16px] font-semibold text-foreground">
              添加 LLM 配置档案
            </h3>
            <p id="llm-profile-modal-description" className="mt-1 text-[13px] text-muted-foreground">
              配置名称、供应商、模型与 API Key，保存后即可在选择器中切换
            </p>

            <div className="mt-5 space-y-4">
              {/* Profile Name */}
              <div className="space-y-1.5">
                <FieldLabel label="配置名称" />
                <input
                  type="text"
                  value={formProfileName}
                  onChange={(e) => setFormProfileName(e.target.value)}
                  placeholder="例如：DeepSeek、OpenAI GPT-4o"
                  className={inputClass}
                  autoFocus
                  onKeyDown={(e) => { if (e.key === 'Enter') handleSaveProfile() }}
                />
              </div>

              {/* Provider */}
              <div className="space-y-1.5">
                <FieldLabel label="供应商" />
                <Select value={formProvider} onValueChange={handleFormProviderChange}>
                  <SelectTrigger className="w-full">
                    <SelectValue>
                      {LLM_PROVIDERS.find((p) => p.value === formProvider)?.label || formProvider}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {LLM_PROVIDERS.map((p) => (
                      <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Model */}
              <div className="space-y-1.5">
                <FieldLabel label="模型" />
                <p className="text-[12px] text-muted-foreground">
                  {LLM_PROVIDERS.find(p => p.value === formProvider)?.defaultModel
                    ? `留空则使用默认：${LLM_PROVIDERS.find(p => p.value === formProvider)!.defaultModel}`
                    : '输入模型名称'}
                </p>
                <input
                  type="text"
                  value={formModel}
                  onChange={(e) => setFormModel(e.target.value)}
                  placeholder={LLM_PROVIDERS.find(p => p.value === formProvider)?.defaultModel || '模型名'}
                  className={inputClass}
                />
              </div>

              {/* API Key */}
              <div className="space-y-1.5">
                <FieldLabel label="API Key" />
                <p className="text-[12px] text-muted-foreground">留空则不设置密钥</p>
                <input
                  type="password"
                  value={formApiKey}
                  onChange={(e) => setFormApiKey(e.target.value)}
                  placeholder="sk-..."
                  className={monoInputClass}
                />
              </div>

              {/* Custom Base URL */}
              {formIsCustom && (
                <div className="space-y-1.5">
                  <FieldLabel label="自定义 URL" />
                  <p className="text-[12px] text-muted-foreground">OpenAI 兼容的 API 地址</p>
                  <input
                    type="text"
                    value={formBaseUrl}
                    onChange={(e) => setFormBaseUrl(e.target.value)}
                    placeholder="https://api.example.com/v1"
                    className={monoInputClass}
                  />
                </div>
              )}
            </div>

            {profileError && (
              <p className="mt-3 text-[12px] text-destructive">{profileError}</p>
            )}

            <div className="mt-5 flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={() => setShowProfileModal(false)}>
                取消
              </Button>
              <Button size="sm" onClick={handleSaveProfile} disabled={profileSaving || !formProfileName.trim()}>
                {profileSaving ? '保存中...' : '保存'}
              </Button>
            </div>
          </div>
        </div>
      ), document.body)}
      </CollapsibleSection>
    </GlassCard>
  )
}
