import { lazy, Suspense, useState } from 'react'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { AlertCircle, CheckCircle2 } from 'lucide-react'
import { useSettings } from '@/hooks/useSettings'
import { getChineseStyle, setChineseStyle, type ChineseStyle } from '@/lib/chinese'
import type { LLMProfile } from '@/types/settings'
import { SpotifyConnectionSection } from '@/features/settings/components/SpotifyConnectionSection'
import { DataFilteringSection } from '@/features/settings/components/DataFilteringSection'
import { BillboardParamsSection } from '@/features/settings/components/BillboardParamsSection'
import { DataImportSection } from '@/features/settings/components/DataImportSection'

const VersionMergeSection = lazy(() =>
  import('@/features/settings/components/VersionMergeSection').then(
    (m) => ({ default: m.VersionMergeSection }),
  ),
)
const LLMTranslationSection = lazy(() =>
  import('@/features/settings/components/LLMTranslationSection').then(
    (m) => ({ default: m.LLMTranslationSection }),
  ),
)

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

  if (loading) {
    return (
      <div className="mx-auto max-w-[900px] space-y-6 px-6 py-12">
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
      {/* Hero */}
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

      {/* Section 0: Spotify Connection */}
      <SpotifyConnectionSection
        connected={settings.spotify_connected}
        profile={settings.spotify_profile ?? null}
        onConnect={spotifyConnect}
        onDisconnect={spotifyDisconnect}
        onSync={spotifySync}
      />

      {/* Section 1: Data Filtering */}
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

      {/* Section 2: Billboard Params */}
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

      {/* Section 3: Version Merge */}
      <Suspense
        fallback={
          <div className="rounded-[16px] border border-border bg-card p-6">
            <Skeleton className="mb-4 h-3 w-36" />
            <Skeleton className="mb-1 h-3 w-64" />
            <Skeleton className="h-24 w-full" />
          </div>
        }
      >
        <VersionMergeSection />
      </Suspense>

      {/* Section 4: Data Import */}
      <DataImportSection
        dbRecordCount={settings.db_record_count}
        accountImported={settings.account_data_imported}
        streamingJob={streamingJob}
        accountJob={accountJob}
        onStreamingImport={startStreamingImport}
        onAccountImport={startAccountImport}
      />

      {/* Section 5: LLM Translation */}
      <Suspense
        fallback={
          <div className="rounded-[16px] border border-border bg-card p-6">
            <Skeleton className="mb-4 h-3 w-36" />
            <Skeleton className="mb-1 h-3 w-64" />
            <Skeleton className="h-24 w-full" />
          </div>
        }
      >
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
      </Suspense>
    </div>
  )
}
