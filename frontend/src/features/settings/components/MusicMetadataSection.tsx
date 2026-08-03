import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, Fingerprint, GitMerge, ListMusic, Tags } from "lucide-react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";

import { GlassCard } from "@/components/shared/GlassCard";
import { Skeleton } from "@/components/ui/skeleton";
import { MergeLevelControl } from "@/features/settings/components/MergeLevelControl";
import { CollapsibleSection } from "@/features/settings/components/SettingsHelpers";
import { cn } from "@/lib/utils";

const TrackCreditManager = lazy(() =>
  import("@/features/settings/components/TrackCreditManager").then(
    (module) => ({ default: module.TrackCreditManager }),
  ),
);
const VersionMergeSection = lazy(() =>
  import("@/features/settings/components/VersionMergeSection").then(
    (module) => ({ default: module.VersionMergeSection }),
  ),
);
const ArtistIdentitySection = lazy(() =>
  import("@/features/settings/components/ArtistIdentitySection").then(
    (module) => ({ default: module.ArtistIdentitySection }),
  ),
);
const GenreDataHealthSection = lazy(() =>
  import("@/features/settings/components/GenreDataHealthSection").then(
    (module) => ({ default: module.GenreDataHealthSection }),
  ),
);

type MetadataTab = "merge" | "track-credits" | "artist-identities" | "genre-language";

const TABS: Array<{
  key: MetadataTab;
  label: string;
  icon: typeof ListMusic;
  desc: string;
}> = [
  {
    key: "merge",
    label: "归并与版本",
    icon: GitMerge,
    desc: "歌曲与专辑版本统一管理",
  },
  {
    key: "track-credits",
    label: "曲目署名",
    icon: ListMusic,
    desc: "主艺人与合作艺人",
  },
  {
    key: "artist-identities",
    label: "艺人身份",
    icon: Fingerprint,
    desc: "别名与 canonical 身份",
  },
  {
    key: "genre-language",
    label: "流派与语言",
    icon: Tags,
    desc: "分类覆盖与人工审核",
  },
];

function LoadingPanel() {
  return (
    <div className="space-y-3 rounded-2xl border border-border p-5">
      <Skeleton className="h-5 w-36" />
      <Skeleton className="h-4 w-72 max-w-full" />
      <Skeleton className="h-36 w-full" />
    </div>
  );
}

export function MusicMetadataSection() {
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const sectionRef = useRef<HTMLElement>(null);
  const handledDeepLinkRef = useRef<string | null>(null);
  const requested = searchParams.get("metadata");
  const [initialRequested] = useState(requested);
  const legacyMerge = requested === "track-merge" || requested === "album-projects";
  const legacyGenreParam =
    requested === "genre-health" ||
    requested === "artist-languages";
  const legacyGenreHash =
    requested == null &&
    (location.hash === "#genre-data-health" || location.hash === "#artist-language-data");
  const legacyGenre = legacyGenreParam || legacyGenreHash;
  const active: MetadataTab = legacyMerge
    ? "merge"
    : TABS.some((tab) => tab.key === requested)
      ? (requested as MetadataTab)
      : legacyGenre
        ? "genre-language"
      : "merge";
  const mergeObjectType =
    requested === "album-projects" || searchParams.get("merge_type") === "album"
      ? "album"
      : "track";
  const trackIdValue = Number(searchParams.get("track_id"));
  const initialTrackId =
    Number.isInteger(trackIdValue) && trackIdValue > 0 ? trackIdValue : null;
  const initialArtist = searchParams.get("artist") ?? "";
  const initialAlbum = searchParams.get("album_name") ?? "";
  const requestedReturnTo = searchParams.get("return_to") ?? "";
  const returnTo = requestedReturnTo.startsWith("/music/") ? requestedReturnTo : "";
  const deepLinkSignature = useMemo(() => {
    const hasEntityContext = Boolean(
      searchParams.get("track_id") ||
      searchParams.get("artist") ||
      searchParams.get("album_name") ||
      returnTo,
    );
    const isLegacyTarget = legacyMerge || legacyGenre;
    const isInitialExplicitTarget =
      requested != null && initialRequested === requested;
    if (!hasEntityContext && !isLegacyTarget && !isInitialExplicitTarget) return null;
    return `${location.pathname}?${searchParams.toString()}${location.hash}`;
  }, [initialRequested, legacyGenre, legacyMerge, location.hash, location.pathname, requested, returnTo, searchParams]);

  useEffect(() => {
    if (!deepLinkSignature || handledDeepLinkRef.current === deepLinkSignature) return;
    const frame = requestAnimationFrame(() => {
      handledDeepLinkRef.current = deepLinkSignature;
      sectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      document.getElementById(`metadata-panel-${active}`)?.focus({ preventScroll: true });
    });
    return () => cancelAnimationFrame(frame);
  }, [active, deepLinkSignature]);

  const selectTab = (key: MetadataTab) => {
    const next = new URLSearchParams(searchParams);
    next.set("metadata", key);
    next.delete("track_id");
    next.delete("artist");
    next.delete("album_name");
    next.delete("return_to");
    next.delete("merge_view");
    next.delete("merge_type");
    setSearchParams(next, { preventScrollReset: true });
  };

  return (
    <section
      id="music-metadata-management"
      ref={sectionRef}
      className="scroll-mt-44 md:scroll-mt-24"
    >
    <GlassCard className="p-6">
      <CollapsibleSection
        num={5}
        title="音乐源数据管理"
        desc="个人项目可直接人工修订；底层仍安全保留 revision、撤销与重建，无需填写理由或证据。"
      >
      {returnTo && (
        <div className="mb-4 flex justify-end">
          <Link
            to={returnTo}
            className="inline-flex items-center gap-1.5 rounded-full border border-border bg-background px-3 py-1.5 text-[11px] font-semibold text-muted-foreground transition hover:border-accent-foreground/40 hover:text-foreground"
          >
            <ArrowLeft className="size-3.5" />返回详情
          </Link>
        </div>
      )}
        <div
          className="mb-6 grid gap-2 sm:grid-cols-2 lg:grid-cols-4"
          role="tablist"
          aria-label="音乐源数据管理类别"
        >
          {TABS.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.key}
                type="button"
                role="tab"
                aria-selected={active === tab.key}
                onClick={() => selectTab(tab.key)}
                className={cn(
                  "flex min-w-0 items-center gap-3 rounded-xl border p-3 text-left transition",
                  active === tab.key
                    ? "border-accent-foreground bg-accent-foreground/5 shadow-sm"
                    : "border-border bg-background hover:border-accent-foreground/35",
                )}
              >
                <span
                  className={cn(
                    "flex size-9 shrink-0 items-center justify-center rounded-lg",
                    active === tab.key
                      ? "bg-accent-foreground text-primary-foreground"
                      : "bg-muted text-muted-foreground",
                  )}
                >
                  <Icon className="size-4" />
                </span>
                <span className="min-w-0">
                  <span className="block text-sm font-semibold">{tab.label}</span>
                  <span className="block break-words text-[10px] text-muted-foreground">{tab.desc}</span>
                </span>
              </button>
            );
          })}
        </div>

        <div
          id={`metadata-panel-${active}`}
          tabIndex={-1}
          className="rounded-2xl border border-border bg-background/55 p-4 outline-none sm:p-5"
        >
        <Suspense fallback={<LoadingPanel />}>
          {active === "merge" && (
            <div className="space-y-5">
              <MergeLevelControl />
              <VersionMergeSection
                initialArtistFilter={initialArtist}
                initialCanonicalName={initialAlbum}
                initialObjectType={mergeObjectType}
              />
            </div>
          )}
          {active === "track-credits" && (
            <TrackCreditManager
              key={initialTrackId ?? "track-credit-manager"}
              initialTrackId={initialTrackId}
              onComplete={returnTo ? () => navigate(returnTo) : undefined}
              onCancel={returnTo ? () => navigate(returnTo) : undefined}
            />
          )}
          {active === "artist-identities" && (
            <ArtistIdentitySection initialSearch={initialArtist} />
          )}
          {active === "genre-language" && <GenreDataHealthSection embedded />}
        </Suspense>
        </div>
      </CollapsibleSection>
    </GlassCard>
    </section>
  );
}
