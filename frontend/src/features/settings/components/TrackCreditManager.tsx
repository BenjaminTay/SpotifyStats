import { useDeferredValue, useState, type ComponentProps } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  Loader2,
  Music2,
  Pencil,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldCheck,
  UserRound,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  useTrackCredits,
  type TrackCreditDraft,
} from "@/hooks/useTrackCredits";
import { cn } from "@/lib/utils";
import type {
  ArtistIdentityCandidate,
  EffectiveTrackCredit,
  TrackCreditAction,
  TrackCreditManualChange,
  TrackCreditRole,
  TrackCreditState,
} from "@/types/settings";

function Input({ className, ...props }: ComponentProps<"input">) {
  return (
    <input
      className={cn(
        "h-10 w-full rounded-lg border border-input bg-background px-3 text-sm outline-none transition focus:border-accent-foreground focus:ring-2 focus:ring-accent-foreground/15",
        className,
      )}
      {...props}
    />
  );
}

function Avatar({ name, coverUrl }: { name: string; coverUrl?: string | null }) {
  const [failed, setFailed] = useState(false);
  if (!coverUrl || failed) {
    return (
      <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-accent-foreground/10 font-serif text-sm font-bold text-accent-foreground">
        {name.trim().slice(0, 1).toUpperCase() || <UserRound className="size-4" />}
      </span>
    );
  }
  return (
    <img
      src={coverUrl}
      alt=""
      className="size-10 shrink-0 rounded-full object-cover"
      onError={() => setFailed(true)}
    />
  );
}

type SelectedArtist = Pick<
  ArtistIdentityCandidate,
  | "artist_id"
  | "artist_name"
  | "canonical_artist_id"
  | "canonical_display_name"
  | "cover_url"
  | "play_count"
>;

function selectedFromCredit(credit: EffectiveTrackCredit): SelectedArtist {
  return {
    artist_id: credit.raw_artist_ids[0] ?? credit.artist_id,
    artist_name: credit.artist_name,
    canonical_artist_id: credit.artist_id,
    canonical_display_name: credit.artist_name,
    cover_url: `/covers/artists/${credit.artist_id}.jpg`,
    play_count: 0,
  };
}

function candidateMaintenanceLabel(state: TrackCreditState | undefined): string {
  if (!state) return "搜索候选 · 检查中";
  const maintenance = state.candidate_maintenance_status;
  if (state.serving_revision != null) {
    if (maintenance === "pending" || maintenance === "building") {
      return "搜索候选 · 上一版本可用";
    }
    if (maintenance === "failed") return "搜索候选 · 上一版本可用";
    return "搜索候选 · 已同步";
  }
  if (maintenance === "missing" || maintenance === "failed") {
    return "搜索候选 · 暂不可用";
  }
  return state.rebuild_status === "ready"
    ? "搜索候选 · 已同步"
    : "搜索候选 · 状态待确认";
}

function statisticsMaintenanceLabel(state: TrackCreditState | undefined): string {
  if (!state) return "播放统计 · 检查中";
  const variants = state.statistics_variant_statuses ?? [];
  if (variants.some((variant) => variant.maintenance_status === "failed")) {
    return "播放统计 · 部分更新失败";
  }
  if (variants.some((variant) =>
    variant.maintenance_status === "pending" || variant.maintenance_status === "building"
  )) {
    return variants.some((variant) => variant.freshness === "last_known_good")
      ? "播放统计 · 上一版本可用"
      : "播放统计 · 更新中";
  }
  if (variants.length > 0 && variants.every((variant) => variant.maintenance_status === "ready")) {
    return "播放统计 · 已同步";
  }
  if (state.rebuild_status === "failed") return "播放统计 · 更新失败";
  if (state.rebuild_status === "running") return "播放统计 · 更新中";
  if (state.rebuild_status === "pending") return "播放统计 · 待同步";
  return "播放统计 · 已同步";
}

function maintenanceTone(
  state: TrackCreditState | undefined,
  layer: "candidate" | "statistics",
): string {
  if (!state) return "bg-muted text-muted-foreground";
  if (layer === "candidate") {
    if (state.serving_revision != null) {
      return state.candidate_maintenance_status === "ready" || state.candidate_maintenance_status == null
        ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
        : "bg-amber-500/10 text-amber-700 dark:text-amber-300";
    }
    if (state.candidate_maintenance_status === "failed" || state.candidate_maintenance_status === "missing") {
      return "bg-destructive/10 text-destructive";
    }
  }
  const variants = state.statistics_variant_statuses ?? [];
  if (state.rebuild_status === "failed" || variants.some((variant) => variant.maintenance_status === "failed")) {
    return "bg-destructive/10 text-destructive";
  }
  if (
    state.rebuild_status === "pending" || state.rebuild_status === "running" ||
    variants.some((variant) => variant.maintenance_status === "pending" || variant.maintenance_status === "building")
  ) {
    return "bg-amber-500/10 text-amber-700 dark:text-amber-300";
  }
  return "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
}

export function TrackCreditManager({
  initialTrackId,
  onComplete,
  onCancel,
}: {
  initialTrackId?: number | null;
  onComplete?: () => void;
  onCancel?: () => void;
}) {
  const [tab, setTab] = useState<"edit" | "manual">("edit");
  const [trackSearch, setTrackSearch] = useState("");
  const [selectedTrackId, setSelectedTrackId] = useState<number | null>(
    initialTrackId ?? null,
  );
  const [artistSearch, setArtistSearch] = useState("");
  const [selectedArtist, setSelectedArtist] = useState<SelectedArtist | null>(null);
  const [action, setAction] = useState<TrackCreditAction>("add");
  const [role, setRole] = useState<TrackCreditRole>("featured");
  const [confirmConflict, setConfirmConflict] = useState(false);
  const deferredTrackSearch = useDeferredValue(trackSearch);
  const deferredArtistSearch = useDeferredValue(artistSearch);
  const credits = useTrackCredits(
    deferredTrackSearch,
    deferredArtistSearch,
    selectedTrackId,
  );
  const detail = credits.detail.data;
  const state = credits.state;
  const retryAllowed = state?.retry_allowed ?? (
    state?.rebuild_status === "pending" || state?.rebuild_status === "failed"
  );

  const draft: TrackCreditDraft | null =
    selectedTrackId != null && selectedArtist
      ? {
          track_id: selectedTrackId,
          artist_id: selectedArtist.artist_id,
          action,
          role: action === "remove" ? null : role,
        }
      : null;

  const clearDraft = () => {
    setSelectedArtist(null);
    setArtistSearch("");
    setConfirmConflict(false);
    credits.preview.reset();
  };

  const save = async (allowConflict = false) => {
    if (!draft || !state) return;
    const preview = await credits.preview.mutateAsync(draft);
    if (preview.no_change) return;
    if (preview.duplicate_canonical_identity && !allowConflict) return;
    await credits.create.mutateAsync({
      ...draft,
      expected_revision: state.current_revision,
      confirm_duplicate_identity: allowConflict,
    });
    clearDraft();
    onComplete?.();
  };

  const selectCurrentCredit = (
    credit: EffectiveTrackCredit,
    nextAction: TrackCreditAction,
  ) => {
    setSelectedArtist(selectedFromCredit(credit));
    setAction(nextAction);
    setRole(credit.role === "primary" ? "featured" : "primary");
    credits.preview.reset();
  };

  const editManualChange = (change: TrackCreditManualChange) => {
    setTab("edit");
    setSelectedTrackId(change.track_id);
    setSelectedArtist({
      artist_id: change.artist_id,
      artist_name: change.artist_name,
      canonical_artist_id: change.canonical_artist_id,
      canonical_display_name: change.canonical_display_name,
      cover_url: `/covers/artists/${change.canonical_artist_id}.jpg`,
      play_count: 0,
    });
    setAction("set_role");
    setRole(change.role === "primary" ? "featured" : "primary");
    credits.preview.reset();
  };

  const undoManualChange = async (change: TrackCreditManualChange) => {
    if (!state || change.event_id == null) return;
    if (!window.confirm(`撤销“${change.track_name} · ${change.artist_name}”的人工修改？`)) {
      return;
    }
    await credits.undo.mutateAsync({
      eventId: change.event_id,
      revision: state.current_revision,
    });
  };

  return (
    <section className="space-y-5" aria-label="曲目署名工作区">
      <div className="flex flex-wrap items-center justify-end gap-2 text-[11px]">
          <span className="rounded-full border border-border bg-background px-2.5 py-1">
            人工修改 {credits.manualChanges.length} 项
          </span>
          <span
            className={cn("rounded-full px-2.5 py-1", maintenanceTone(state, "candidate"))}
          >
            {candidateMaintenanceLabel(state)}
          </span>
          <span className={cn("rounded-full px-2.5 py-1", maintenanceTone(state, "statistics"))}>
            {statisticsMaintenanceLabel(state)}
          </span>
          {state?.serving_revision != null && state.target_revision != null && (
            <span className="rounded-full border border-border bg-background px-2.5 py-1 tabular-nums text-muted-foreground">
              服务 revision {state.serving_revision} → 目标 {state.target_revision}
            </span>
          )}
          {retryAllowed && (
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={credits.rebuild.isPending}
              onClick={() => credits.rebuild.mutate()}
            >
              <RefreshCw className={cn("size-3.5", credits.rebuild.isPending && "animate-spin")} />
              {state?.rebuild_status === "failed" ? "重试维护" : "恢复维护"}
            </Button>
          )}
      </div>

      <div className="flex gap-6 border-b border-border" role="tablist" aria-label="曲目署名管理">
        {([
          ["edit", "编辑署名"],
          ["manual", `人工修改（${credits.manualChanges.length}）`],
        ] as const).map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={cn(
              "-mb-px border-b-2 pb-2.5 text-[13px] font-semibold",
              tab === key
                ? "border-accent-foreground text-foreground"
                : "border-transparent text-muted-foreground",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "edit" && (
        <div className="space-y-5">
          <div>
            <label htmlFor="track-credit-track-search" className="mb-2 block text-xs font-semibold">
              1. 选择曲目
            </label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="track-credit-track-search"
                value={trackSearch}
                onChange={(event) => setTrackSearch(event.target.value)}
                placeholder="搜索歌名、艺人、专辑或 Spotify track id"
                className="pl-9"
              />
            </div>
            {trackSearch.trim() && (
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                {credits.tracks.map((track) => (
                  <button
                    key={track.track_id}
                    type="button"
                    onClick={() => {
                      setSelectedTrackId(track.track_id);
                      setTrackSearch("");
                      clearDraft();
                    }}
                    className="flex min-w-0 items-center gap-3 rounded-xl border border-border bg-background p-3 text-left transition hover:border-accent-foreground/40"
                  >
                    <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted">
                      <Music2 className="size-4" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block break-words text-sm font-semibold">{track.track_name}</span>
                      <span className="block break-words text-[11px] text-muted-foreground">
                        {track.effective_artist_names.join("、") || track.artist_name} · #{track.track_id} · {track.play_count.toLocaleString()} 次
                      </span>
                    </span>
                    <ArrowRight className="size-4 shrink-0 text-muted-foreground" />
                  </button>
                ))}
              </div>
            )}
          </div>

          {detail && (
            <div className="space-y-4 rounded-2xl border border-border bg-muted/20 p-4 sm:p-5">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="font-serif text-xl font-bold">{detail.track.track_name}</p>
                  <p className="text-xs text-muted-foreground">
                    {detail.track.album_name ?? "未知专辑"} · local track #{detail.track.track_id}
                    {detail.track.spotify_track_id ? ` · Spotify ${detail.track.spotify_track_id}` : ""}
                  </p>
                </div>
                <Button type="button" size="sm" variant="ghost" onClick={() => setSelectedTrackId(null)}>
                  <X className="size-3.5" />更换曲目
                </Button>
              </div>
              <div className="grid gap-3 lg:grid-cols-3">
                <CreditColumn
                  title="自动署名"
                  description="导入事实，只读"
                  credits={detail.raw_credits.map((credit) => ({
                    ...credit,
                    artist_id: credit.canonical_artist_id,
                    artist_name: credit.canonical_display_name,
                    raw_artist_ids: [credit.artist_id],
                    override_id: null,
                  }))}
                />
                <CreditColumn
                  title="人工修改"
                  description="当前覆盖规则"
                  credits={detail.manual_overrides.map((override) => ({
                    ...override,
                    artist_name:
                      detail.effective_credits.find((credit) => credit.raw_artist_ids.includes(override.artist_id))?.artist_name ?? `artist #${override.artist_id}`,
                    raw_artist_ids: [override.artist_id],
                    source: "manual" as const,
                    override_id: override.override_id,
                    role: override.role ?? "featured",
                  }))}
                />
                <CreditColumn
                  title="最终有效署名"
                  description="全站实际使用"
                  credits={detail.effective_credits}
                  onSetRole={(credit) => selectCurrentCredit(credit, "set_role")}
                  onRemove={(credit) => selectCurrentCredit(credit, "remove")}
                />
              </div>
            </div>
          )}

          {detail && (
            <div className="space-y-4 rounded-2xl border border-border bg-background p-4 sm:p-5">
              <div>
                <p className="text-xs font-semibold">2. 选择艺人和角色</p>
                <p className="mt-1 text-[11px] text-muted-foreground">
                  名称只用于查找；写入始终绑定 local artist ID，并显示 canonical 与 Spotify 信息防止同名误选。
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_140px_140px]">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    aria-label="搜索署名艺人候选"
                    value={artistSearch}
                    onChange={(event) => setArtistSearch(event.target.value)}
                    placeholder="搜索本地艺人"
                    className="pl-9"
                  />
                </div>
                <select
                  aria-label="署名操作"
                  value={action}
                  onChange={(event) => {
                    setAction(event.target.value as TrackCreditAction);
                    credits.preview.reset();
                  }}
                  className="h-10 rounded-lg border border-input bg-background px-3 text-sm"
                >
                  <option value="add">添加署名</option>
                  <option value="remove">移除署名</option>
                  <option value="set_role">调整角色</option>
                </select>
                <select
                  aria-label="署名角色"
                  value={role}
                  disabled={action === "remove"}
                  onChange={(event) => setRole(event.target.value as TrackCreditRole)}
                  className="h-10 rounded-lg border border-input bg-background px-3 text-sm disabled:opacity-50"
                >
                  <option value="primary">主艺人</option>
                  <option value="featured">合作艺人</option>
                </select>
              </div>
              {artistSearch.trim() && (
                <div className="grid gap-2 sm:grid-cols-2">
                  {credits.artists.map((artist) => (
                    <button
                      key={artist.artist_id}
                      type="button"
                      onClick={() => {
                        setSelectedArtist(artist);
                        credits.preview.reset();
                      }}
                      className={cn(
                        "flex min-w-0 items-center gap-3 rounded-xl border p-3 text-left transition",
                        selectedArtist?.artist_id === artist.artist_id
                          ? "border-accent-foreground bg-accent-foreground/5"
                          : "border-border hover:border-accent-foreground/40",
                      )}
                    >
                      <Avatar name={artist.artist_name} coverUrl={artist.cover_url} />
                      <span className="min-w-0 flex-1">
                        <span className="block break-words text-sm font-semibold">{artist.artist_name}</span>
                        <span className="block break-words text-[11px] text-muted-foreground">
                          raw #{artist.artist_id} → canonical #{artist.canonical_artist_id} {artist.canonical_display_name} · {artist.play_count.toLocaleString()} 次
                        </span>
                        <span className="block break-words text-[10px] text-muted-foreground">
                          {artist.external_ids.map((item) => `${item.provider}:${item.external_id}${item.verified ? " ✓" : ""}`).join(" · ") || "暂无 provider id"}
                        </span>
                      </span>
                      {selectedArtist?.artist_id === artist.artist_id ? <Check className="size-4 text-accent-foreground" /> : <Plus className="size-4 text-muted-foreground" />}
                    </button>
                  ))}
                </div>
              )}
              {selectedArtist && (
                <div className="flex flex-col gap-3 rounded-xl border border-accent-foreground/25 bg-accent-foreground/5 p-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex min-w-0 items-center gap-3">
                    <Avatar name={selectedArtist.artist_name} coverUrl={selectedArtist.cover_url} />
                    <div className="min-w-0">
                      <p className="break-words text-sm font-semibold">{selectedArtist.artist_name}</p>
                      <p className="text-[11px] text-muted-foreground">
                        local #{selectedArtist.artist_id} · {action === "remove" ? "移除署名" : role === "primary" ? "主艺人" : "合作艺人"}
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {onCancel && <Button type="button" variant="ghost" size="sm" onClick={onCancel}>取消并返回</Button>}
                    <Button type="button" disabled={!draft || credits.preview.isPending || credits.create.isPending} onClick={() => void save()}>
                      {(credits.preview.isPending || credits.create.isPending) && <Loader2 className="size-4 animate-spin" />}
                      应用修改
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}

          {credits.preview.data?.duplicate_canonical_identity && (
            <div className="space-y-3 rounded-xl border border-amber-500/35 bg-amber-500/5 p-4">
              <div className="flex items-center gap-2 text-sm font-semibold">
                <AlertTriangle className="size-4 text-amber-600" />该艺人与现有署名指向同一 canonical 身份
              </div>
              <p className="text-xs text-muted-foreground">继续不会让同一播放事件重复计数，但通常无需重复添加。确认确有需要后可直接执行。</p>
              <label className="flex items-start gap-2 text-xs">
                <input type="checkbox" checked={confirmConflict} onChange={(event) => setConfirmConflict(event.target.checked)} className="mt-0.5" />
                <span>我已核对 local ID 与身份映射，仍要保留这条人工规则。</span>
              </label>
              <Button type="button" disabled={!confirmConflict || credits.create.isPending} onClick={() => void save(true)}>确认应用</Button>
            </div>
          )}
          {credits.preview.data?.no_change && (
            <p role="status" className="rounded-xl border border-border bg-muted/30 p-3 text-xs text-muted-foreground">当前选择不会改变有效署名，无需保存。</p>
          )}
          {(credits.preview.error || credits.create.error) && (
            <p role="alert" className="text-xs text-destructive">
              {(credits.preview.error || credits.create.error) instanceof Error
                ? (credits.preview.error || credits.create.error)?.message
                : "操作失败"}
            </p>
          )}
        </div>
      )}

      {tab === "manual" && (
        <div className="space-y-2" aria-label="当前人工修改">
          {credits.manualChanges.map((change) => (
            <div key={change.override_id} className="flex flex-col gap-3 rounded-xl border border-border bg-background p-3 sm:flex-row sm:items-center">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-accent-foreground/10 text-accent-foreground"><ShieldCheck className="size-4" /></span>
              <div className="min-w-0 flex-1">
                <p className="break-words text-sm font-semibold">{change.track_name} · {change.canonical_display_name}</p>
                <p className="break-words text-xs text-muted-foreground">
                  {change.action === "add" ? "添加" : change.action === "remove" ? "移除" : "调整"}署名 · {change.role === "primary" ? "主艺人" : "合作艺人"} · local artist #{change.artist_id}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {change.action !== "remove" && <Button type="button" size="sm" variant="outline" onClick={() => editManualChange(change)}><Pencil className="size-3.5" />编辑</Button>}
                <Button type="button" size="sm" variant="outline" disabled={change.event_id == null || credits.undo.isPending} onClick={() => void undoManualChange(change)}><RotateCcw className="size-3.5" />撤销</Button>
              </div>
            </div>
          ))}
          {credits.manualChanges.length === 0 && (
            <p className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">暂无生效中的人工署名修改。</p>
          )}
        </div>
      )}
    </section>
  );
}

function CreditColumn({
  title,
  description,
  credits,
  onSetRole,
  onRemove,
}: {
  title: string;
  description: string;
  credits: EffectiveTrackCredit[];
  onSetRole?: (credit: EffectiveTrackCredit) => void;
  onRemove?: (credit: EffectiveTrackCredit) => void;
}) {
  return (
    <div className="min-w-0 rounded-xl border border-border bg-background p-3">
      <div className="mb-3"><p className="text-xs font-bold uppercase tracking-[1px]">{title}</p><p className="text-[10px] text-muted-foreground">{description}</p></div>
      <div className="space-y-2">
        {credits.map((credit) => (
          <div key={`${credit.artist_id}-${credit.action ?? credit.source}`} className="rounded-lg bg-muted/40 p-2.5">
            <div className="flex min-w-0 items-center gap-2">
              <Avatar name={credit.artist_name} coverUrl={`/covers/artists/${credit.artist_id}.jpg`} />
              <span className="min-w-0 flex-1"><span className="block break-words text-sm font-semibold">{credit.artist_name}</span><span className="text-[10px] text-muted-foreground">canonical #{credit.artist_id} · {credit.role === "primary" ? "主艺人" : "合作艺人"}</span></span>
            </div>
            {(onSetRole || onRemove) && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {onSetRole && <button type="button" onClick={() => onSetRole(credit)} className="rounded-md border border-border px-2 py-1 text-[10px] hover:bg-muted">调整角色</button>}
                {onRemove && <button type="button" onClick={() => onRemove(credit)} className="rounded-md border border-border px-2 py-1 text-[10px] text-destructive hover:bg-destructive/5">移除</button>}
              </div>
            )}
          </div>
        ))}
        {credits.length === 0 && <p className="text-[11px] text-muted-foreground">暂无记录</p>}
      </div>
    </div>
  );
}
