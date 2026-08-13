import { lazy, Suspense, useState } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { AlertCircle } from "lucide-react";
import { useSettings } from "@/hooks/useSettings";
import {
  getChineseStyle,
  setChineseStyle,
  type ChineseStyle,
} from "@/lib/chinese";
import { SettingsOverview } from "@/features/settings/components/SettingsOverview";
import { RebuildNotice } from "@/features/settings/components/RebuildNotice";
import { SpotifyConnectionSection } from "@/features/settings/components/SpotifyConnectionSection";
import { DataFilteringSection } from "@/features/settings/components/DataFilteringSection";
import { BillboardParamsSection } from "@/features/settings/components/BillboardParamsSection";
import { DataImportSection } from "@/features/settings/components/DataImportSection";
import { useViewportMode } from "@/hooks/useViewportMode";
import { MobileSettingsExperience } from "@/features/mobile/settings/MobileSettingsExperience";
import { CapabilityGate } from "@/components/capabilities/CapabilityGate";

const MusicMetadataSection = lazy(() =>
  import("@/features/settings/components/MusicMetadataSection").then((m) => ({
    default: m.MusicMetadataSection,
  })),
);
const LLMTranslationSection = lazy(() =>
  import("@/features/settings/components/LLMTranslationSection").then((m) => ({
    default: m.LLMTranslationSection,
  })),
);

export function SettingsPage() {
  const isPhone = useViewportMode() === "phone";
  const {
    settings,
    loading,
    error,
    refetch,
    updateSettings,
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
    applyProfile,
    createProfile,
    deleteProfile,
  } = useSettings();

  const [rebuildPendingOverride, setRebuildPending] = useState<boolean | null>(
    null,
  );
  const [rebuildLoading, setRebuildLoading] = useState(false);
  const [rebuildMsg, setRebuildMsg] = useState("");
  const [chineseStyle, setChineseStyleState] =
    useState<ChineseStyle>(getChineseStyle);

  const handleRequiresRebuild = () => setRebuildPending(true);

  const handleRebuild = () => {
    setRebuildLoading(true);
    setRebuildMsg("");
    rebuildAgg()
      .then((res) => {
        setRebuildMsg(res.status === "done" ? "聚合表重建完成" : "重建完成");
        setRebuildPending(false);
        setRebuildLoading(false);
      })
      .catch(() => {
        setRebuildMsg("重建失败，请重试");
        setRebuildLoading(false);
      });
  };

  if (loading) {
    if (isPhone) {
      return (
        <div className="mobile-settings-page" aria-label="正在加载设置">
          <div className="space-y-2 py-2">
            <Skeleton className="h-3 w-28" />
            <Skeleton className="h-9 w-24" />
          </div>
          <Skeleton className="h-11 w-full rounded-[14px]" />
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-[76px] w-full rounded-[16px]" />
          ))}
        </div>
      );
    }
    return (
      <div className="mx-auto max-w-[900px] space-y-6 px-6 py-12">
        <div className="space-y-3">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-10 w-72" />
          <Skeleton className="h-5 w-[420px]" />
        </div>
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="rounded-[16px] border border-border bg-card p-6"
          >
            <Skeleton className="mb-4 h-3 w-36" />
            <Skeleton className="mb-1 h-3 w-64" />
            <Skeleton className="h-24 w-full" />
          </div>
        ))}
      </div>
    );
  }

  if (error && !settings) {
    return (
      <div className="mx-auto flex max-w-[900px] flex-col items-center gap-4 px-6 py-24">
        <AlertCircle className="size-10 text-muted-foreground" />
        <p className="text-[15px] text-muted-foreground">
          无法加载设置: {error}
        </p>
        <Button variant="outline" size="sm" onClick={refetch}>
          重试
        </Button>
      </div>
    );
  }

  if (!settings) return null;

  const rebuildPending = rebuildPendingOverride ?? settings.rebuild_pending;

  if (isPhone) {
    return (
      <MobileSettingsExperience
        settings={settings}
        rebuildPending={rebuildPending}
        chineseStyle={chineseStyle}
        onChangeChineseStyle={(style) => {
          setChineseStyleState(style);
          setChineseStyle(style);
        }}
        onUpdate={updateSettings}
        onRequiresRebuild={handleRequiresRebuild}
        onSpotifyConnect={spotifyConnect}
        onSpotifyDisconnect={spotifyDisconnect}
        onSpotifySync={spotifySync}
        onFetchProfiles={fetchProfiles}
        onApplyProfile={applyProfile}
      />
    );
  }

  return (
    <div className="mx-auto max-w-[900px] space-y-6 px-6 py-12">
      {/* Hero */}
      <section className="mb-10">
        <div className="mb-3 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
          设置
        </div>
        <h1 className="font-serif text-[44px] font-bold tracking-[-1.2px] leading-[1.06]">
          参数与配置
        </h1>
      </section>

      <SettingsOverview
        dbRecordCount={settings.db_record_count}
        accountImported={settings.account_data_imported}
        spotifyConnected={settings.spotify_connected}
        hasLlmKey={settings.has_llm_key}
        llmProvider={settings.llm_provider}
        llmModel={settings.llm_model}
        rebuildPending={rebuildPending}
      />

      <CapabilityGate require="editing">
        <RebuildNotice
          pending={rebuildPending}
          loading={rebuildLoading}
          message={rebuildMsg}
          onRebuild={handleRebuild}
          onDismiss={() => setRebuildMsg("")}
        />
      </CapabilityGate>

      {/* Section 1: Spotify Connection */}
      <CapabilityGate require="spotify_oauth">
        <SpotifyConnectionSection
          connected={settings.spotify_connected}
          profile={settings.spotify_profile ?? null}
          onConnect={spotifyConnect}
          onDisconnect={spotifyDisconnect}
          onSync={spotifySync}
        />
      </CapabilityGate>

      {/* Section 2: Data Import */}
      <CapabilityGate require="imports">
        <DataImportSection
          dbRecordCount={settings.db_record_count}
          accountImported={settings.account_data_imported}
          streamingJob={streamingJob}
          accountJob={accountJob}
          onStreamingImport={startStreamingImport}
          onAccountImport={startAccountImport}
        />
      </CapabilityGate>

      {/* Section 3: Data & Display */}
      <CapabilityGate require="editing">
        <DataFilteringSection
          settings={{
            min_ms: settings.min_ms,
            music_only: settings.music_only,
            merge_enabled: settings.merge_enabled,
          }}
          onUpdate={updateSettings}
          onRequiresRebuild={handleRequiresRebuild}
          chineseStyle={chineseStyle}
          onChangeChineseStyle={(s: string | null) => {
            const style = (s as ChineseStyle) || "original";
            setChineseStyleState(style);
            setChineseStyle(style);
          }}
        />
      </CapabilityGate>

      {/* Section 4: Billboard Params */}
      <CapabilityGate require="editing">
        <BillboardParamsSection
          settings={{
            bb_top_n: settings.bb_top_n,
            bb_album_top_n: settings.bb_album_top_n,
            bb_artist_top_n: settings.bb_artist_top_n,
            bb_week_start_dow: settings.bb_week_start_dow,
            bb_week_start_hour: settings.bb_week_start_hour,
            include_compilations: settings.include_compilations,
          }}
          onUpdate={updateSettings}
          onRequiresRebuild={handleRequiresRebuild}
        />
      </CapabilityGate>

      {/* Section 5: Music Metadata Management */}
      <CapabilityGate require={["editing", "metadata_governance"]}>
        <Suspense
          fallback={
            <div className="rounded-[16px] border border-border bg-card p-6">
              <Skeleton className="mb-4 h-3 w-36" />
              <Skeleton className="mb-1 h-3 w-64" />
              <Skeleton className="h-24 w-full" />
            </div>
          }
        >
          <MusicMetadataSection />
        </Suspense>
      </CapabilityGate>

      {/* Section 6: LLM Translation */}
      <CapabilityGate require="ai">
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
            onClearCache={clearTranslationCache}
            hasLlmKey={settings.has_llm_key}
            activeProfileId={settings.llm_active_profile_id}
            activeProfileName={settings.llm_active_profile_name}
            onFetchProfiles={fetchProfiles}
            onApplyProfile={applyProfile}
            onCreateProfile={createProfile}
            onDeleteProfile={deleteProfile}
            onRefetch={refetch}
          />
        </Suspense>
      </CapabilityGate>
    </div>
  );
}
