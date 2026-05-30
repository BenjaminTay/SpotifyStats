import { useState, useEffect } from 'react'
import { GlassCard } from '@/components/shared/GlassCard'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'
import { Plus, Trash2, RefreshCw, CheckCircle2 } from 'lucide-react'
import type { SettingsUpdatePayload, LLMProfile, LLMProfileDetail, LLMProfileCreatePayload } from '@/types/settings'
import { SectionHeader, Toggle, FieldLabel, InlineNotice } from '@/features/settings/components/SettingsHelpers'

const LLM_PROVIDERS = [
  { value: 'deepseek', label: 'DeepSeek', defaultModel: 'deepseek-chat' },
  { value: 'openai', label: 'OpenAI', defaultModel: 'gpt-4o-mini' },
  { value: 'anthropic', label: 'Anthropic', defaultModel: 'claude-haiku-4-5-20251001' },
  { value: 'custom', label: '自定义', defaultModel: '' },
]

export function LLMTranslationSection({
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
