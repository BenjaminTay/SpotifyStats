import { useEffect, useState } from "react";
import {
  CheckCircle2,
  ChevronDown,
  Disc3,
  Music2,
  Plus,
  RefreshCw,
  Search,
  Star,
  Trash2,
  X,
} from "lucide-react";

import { CoverCell } from "@/components/shared/CoverCell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Slider } from "@/components/ui/slider";
import {
  FieldLabel,
  TrackComparePanel,
} from "@/features/settings/components/SettingsHelpers";
import { useVersionMerge } from "@/hooks/useSettings";
import { api } from "@/lib/api";
import { displayName } from "@/lib/chinese";
import { cn } from "@/lib/utils";
import type {
  DetectionResult,
  GroupMember,
  ReleaseGroup,
  TrackComparison,
  TrackCreditTrackCandidate,
  TrackGroup,
  TrackGroupCandidate,
  TrackGroupMember,
  TrackIdentitySource,
  UngroupedAlbum,
} from "@/types/settings";

type ObjectType = "track" | "album";
type MergeTabKey = "detect" | "saved" | "create";
type MergeScope = "recording" | "release" | "composition";

const MERGE_TABS: Array<{ key: MergeTabKey; label: string; helper: string }> = [
  { key: "detect", label: "自动检测", helper: "扫描候选并逐项确认" },
  { key: "saved", label: "已保存分组", helper: "查看和维护现有关系" },
  { key: "create", label: "手动创建", helper: "明确选择成员与层级" },
];

const OBJECT_COPY = {
  track: {
    label: "歌曲归并",
    helper: "管理具体曲目、同一录音与同一作品",
    icon: Music2,
  },
  album: {
    label: "专辑归并",
    helper: "管理具体发行、发行版本与作品版本",
    icon: Disc3,
  },
} satisfies Record<
  ObjectType,
  { label: string; helper: string; icon: typeof Music2 }
>;

export function VersionMergeSection({
  initialArtistFilter = "",
  initialCanonicalName = "",
  initialObjectType = "track",
  initialTrackId = null,
}: {
  initialArtistFilter?: string;
  initialCanonicalName?: string;
  initialObjectType?: ObjectType;
  initialTrackId?: number | null;
}) {
  const [objectType, setObjectType] = useState<ObjectType>(initialObjectType);
  const [activeTab, setActiveTab] = useState<MergeTabKey>(
    initialArtistFilter || initialCanonicalName || initialTrackId
      ? "create"
      : "detect",
  );
  const vm = useVersionMerge();

  return (
    <section className="space-y-5" aria-label="归并与版本工作区">
      <ObjectTypeSwitch value={objectType} onChange={setObjectType} />
      <div
        className="grid grid-cols-3 gap-1 rounded-2xl border border-border bg-muted/20 p-1"
        aria-label="归并工作方式"
      >
        {MERGE_TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            aria-label={tab.label}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              "min-h-12 rounded-xl px-2 py-2 text-center transition sm:min-h-14 sm:px-3",
              activeTab === tab.key
                ? "bg-background text-foreground shadow-sm ring-1 ring-border"
                : "text-muted-foreground hover:bg-background/60 hover:text-foreground",
            )}
          >
            <span className="block text-[12px] font-semibold sm:text-[13px]">
              {tab.label}
            </span>
            <span className="mt-0.5 hidden text-[10px] font-normal text-muted-foreground sm:block">
              {tab.helper}
            </span>
          </button>
        ))}
      </div>
      <div className="rounded-2xl border border-border bg-background p-4 sm:p-5">
        {activeTab === "detect" && (
          <AutoDetectionTab vm={vm} objectType={objectType} />
        )}
        {activeTab === "saved" && (
          <SavedGroupsTab vm={vm} objectType={objectType} />
        )}
        {activeTab === "create" && (
          <ManualCreateTab
            key={objectType}
            vm={vm}
            objectType={objectType}
            initialArtistFilter={initialArtistFilter}
            initialCanonicalName={initialCanonicalName}
            initialTrackId={initialTrackId}
          />
        )}
      </div>
    </section>
  );
}

function ObjectTypeSwitch({
  value,
  onChange,
}: {
  value: ObjectType;
  onChange: (value: ObjectType) => void;
}) {
  return (
    <div
      className="grid gap-2 sm:grid-cols-2"
      role="radiogroup"
      aria-label="归并对象类型"
    >
      {(Object.keys(OBJECT_COPY) as ObjectType[]).map((type) => {
        const item = OBJECT_COPY[type];
        const Icon = item.icon;
        const active = value === type;
        return (
          <button
            key={type}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(type)}
            className={cn(
              "flex min-h-16 items-center gap-3 rounded-2xl border px-4 py-3 text-left transition",
              active
                ? "border-accent-foreground bg-accent-foreground/5 shadow-sm"
                : "border-border bg-background hover:border-accent-foreground/35",
            )}
          >
            <span
              className={cn(
                "flex size-10 shrink-0 items-center justify-center rounded-xl",
                active
                  ? "bg-accent-foreground text-primary-foreground"
                  : "bg-muted text-muted-foreground",
              )}
            >
              <Icon className="size-4" />
            </span>
            <span className="min-w-0">
              <span className="block text-[13px] font-semibold">
                {item.label}
              </span>
              <span className="mt-0.5 block text-[10.5px] leading-relaxed text-muted-foreground">
                {item.helper}
              </span>
            </span>
            {active && (
              <CheckCircle2 className="ml-auto size-4 shrink-0 text-accent-foreground" />
            )}
          </button>
        );
      })}
    </div>
  );
}

function WorkflowBlock({
  number,
  title,
  helper,
  children,
}: {
  number: number;
  title: string;
  helper: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-border bg-muted/10 p-4 sm:p-5">
      <div className="mb-4 flex items-start gap-3">
        <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-foreground text-[11px] font-bold text-background">
          {number}
        </span>
        <div>
          <p className="text-[13px] font-semibold">{title}</p>
          <p className="mt-0.5 text-[11px] leading-relaxed text-muted-foreground">
            {helper}
          </p>
        </div>
      </div>
      {children}
    </div>
  );
}

function AutoDetectionTab({
  vm,
  objectType,
}: {
  vm: ReturnType<typeof useVersionMerge>;
  objectType: ObjectType;
}) {
  return objectType === "track" ? (
    <TrackAutoDetection vm={vm} />
  ) : (
    <AlbumAutoDetection vm={vm} />
  );
}

function TrackAutoDetection({
  vm,
}: {
  vm: ReturnType<typeof useVersionMerge>;
}) {
  const [scope, setScope] = useState<"recording" | "composition">(
    "recording",
  );
  const [candidates, setCandidates] = useState<TrackGroupCandidate[] | null>(
    null,
  );
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [ignored, setIgnored] = useState<Set<string>>(new Set());
  const [message, setMessage] = useState("");
  const keyFor = (item: TrackGroupCandidate) =>
    `${item.original_l1_id ?? item.original_track_id}-${item.candidate_l1_id ?? item.candidate_track_id}`;
  const visible =
    candidates?.filter((item) => !ignored.has(keyFor(item))) ?? [];
  const detect = () => {
    setLoading(true);
    setMessage("");
    setIgnored(new Set());
    vm.fetchCollaborationCandidates()
      .then(setCandidates)
      .finally(() => setLoading(false));
  };
  const confirm = (item: TrackGroupCandidate) => {
    const key = keyFor(item);
    setConfirming(key);
    setMessage("");
    vm.confirmTrackCandidate(
      item.original_l1_id ?? item.original_track_id,
      item.candidate_l1_id ?? item.candidate_track_id,
      scope,
    )
      .then((result) => {
        if (result.status !== "ok")
          throw new Error(result.message ?? "确认失败");
        setCandidates(
          (current) =>
            current?.filter((candidate) => keyFor(candidate) !== key) ?? null,
        );
        setMessage(
          `已保存为 ${scope === "recording" ? "L2 同一录音" : "L3 同一作品"}分组`,
        );
      })
      .catch((error: unknown) =>
        setMessage(error instanceof Error ? error.message : "确认失败"),
      )
      .finally(() => setConfirming(null));
  };
  return (
    <div className="space-y-4">
      <WorkflowBlock
        number={1}
        title="设置检测规则"
        helper="先确定候选通过后写入哪个统计层级，再开始扫描。"
      >
        <ScopeSelector
          objectType="track"
          value={scope}
          onChange={(value) => setScope(value as "recording" | "composition")}
        />
        <Button
          type="button"
          onClick={detect}
          disabled={loading}
          className="mt-4 min-h-11 gap-2"
        >
          {loading ? (
            <RefreshCw className="size-4 animate-spin" />
          ) : (
            <Search className="size-4" />
          )}
          {loading ? "正在检测…" : "检测歌曲候选"}
        </Button>
      </WorkflowBlock>
      <WorkflowBlock
        number={2}
        title="审核候选结果"
        helper="自动检测只提供候选；每一组仍需明确确认或忽略。"
      >
        {candidates === null ? (
          <EmptyState text="尚未开始检测。" />
        ) : visible.length === 0 ? (
          <EmptyState text="当前没有待处理的歌曲候选。" success />
        ) : (
          <div className="space-y-2">
            {visible.map((item) => {
              const key = keyFor(item);
              return (
                <div
                  key={key}
                  className="rounded-xl border border-border bg-background p-3"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <Music2 className="size-4 shrink-0 text-accent-foreground" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[13px] font-semibold">
                        {displayName(item.original_track_name)}
                      </p>
                      <p className="truncate text-[11px] text-muted-foreground">
                        候选：{displayName(item.candidate_track_name)}
                      </p>
                    </div>
                    <Badge variant="secondary">
                      {scope === "recording" ? "L2" : "L3"}
                    </Badge>
                  </div>
                  <div className="mt-3 flex justify-end gap-2">
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() =>
                        setIgnored((current) => new Set(current).add(key))
                      }
                      className="min-h-11"
                    >
                      忽略
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => confirm(item)}
                      disabled={confirming !== null}
                      className="min-h-11 gap-1.5"
                    >
                      {confirming === key ? (
                        <RefreshCw className="size-3.5 animate-spin" />
                      ) : (
                        <CheckCircle2 className="size-3.5" />
                      )}
                      确认归并
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
        {message && <StatusMessage message={message} />}
      </WorkflowBlock>
    </div>
  );
}

function AlbumAutoDetection({
  vm,
}: {
  vm: ReturnType<typeof useVersionMerge>;
}) {
  const [threshold, setThreshold] = useState(0.4);
  const [results, setResults] = useState<DetectionResult[] | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [message, setMessage] = useState("");
  const [rebuilding, setRebuilding] = useState(false);
  const keyFor = (item: DetectionResult, index: number) =>
    `${item.artist_id}-${item.canonical_name}-${index}`;
  const detect = () => {
    setLoading(true);
    setResults(null);
    setSelected(new Set());
    setMessage("");
    Promise.all([vm.detectGroups(threshold), vm.fetchGroups()])
      .then(([detected, saved]) => {
        const savedPrimaryIds = new Set(
          saved.map((group) => group.primary_album_id),
        );
        setResults(
          detected.filter(
            (item) => !savedPrimaryIds.has(item.primary_album_id),
          ),
        );
      })
      .finally(() => setLoading(false));
  };
  const apply = () => {
    if (!results) return;
    const confirmed = results.filter((item, index) =>
      selected.has(keyFor(item, index)),
    );
    setApplying(true);
    vm.applyDetected(confirmed)
      .then((result) =>
        setMessage(
          `已创建 ${result.created_count} 个分组，跳过 ${result.skipped_count} 个`,
        ),
      )
      .finally(() => setApplying(false));
  };
  return (
    <div className="space-y-4">
      <WorkflowBlock
        number={1}
        title="设置检测规则"
        helper="专辑自动检测按曲目重叠率寻找同一发行的版本；作品级关系需在手动创建中确认。"
      >
        <ScopeSelector
          objectType="album"
          value="release"
          onChange={() => undefined}
          autoMode
        />
        <div className="mt-4 max-w-sm space-y-2">
          <FieldLabel
            label="曲目重叠率"
            badge={`${Math.round(threshold * 100)}%`}
          />
          <Slider
            aria-label="曲目重叠率"
            value={[threshold]}
            onValueChange={(value) => setThreshold((value as number[])[0])}
            min={0.1}
            max={1}
            step={0.05}
          />
        </div>
        <Button
          type="button"
          onClick={detect}
          disabled={loading}
          className="mt-4 min-h-11 gap-2"
        >
          {loading ? (
            <RefreshCw className="size-4 animate-spin" />
          ) : (
            <Search className="size-4" />
          )}
          {loading ? "正在检测…" : "检测专辑候选"}
        </Button>
      </WorkflowBlock>
      <WorkflowBlock
        number={2}
        title="审核候选结果"
        helper="勾选确认无误的版本家族，再统一保存。"
      >
        {results === null ? (
          <EmptyState text="尚未开始检测。" />
        ) : results.length === 0 ? (
          <EmptyState text="当前没有待处理的专辑候选。" success />
        ) : (
          <div className="space-y-3">
            {results.map((item, index) => {
              const key = keyFor(item, index);
              return (
                <AlbumDetectionCard
                  key={key}
                  result={item}
                  selected={selected.has(key)}
                  onToggle={() =>
                    setSelected((current) => {
                      const next = new Set(current);
                      if (next.has(key)) next.delete(key);
                      else next.add(key);
                      return next;
                    })
                  }
                  compareAlbums={vm.compareAlbums}
                />
              );
            })}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
              <span className="text-[12px] text-muted-foreground">
                已选 {selected.size} / {results.length}
              </span>
              <Button
                type="button"
                onClick={apply}
                disabled={selected.size === 0 || applying}
                className="min-h-11 gap-2"
              >
                {applying ? (
                  <RefreshCw className="size-4 animate-spin" />
                ) : (
                  <Plus className="size-4" />
                )}
                保存选中分组
              </Button>
            </div>
          </div>
        )}
        {message && <StatusMessage message={message} />}
      </WorkflowBlock>
      <details className="group rounded-2xl border border-border bg-muted/10">
        <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between px-4 text-[12px] font-semibold marker:hidden">
          维护工具
          <ChevronDown className="size-4 text-muted-foreground transition group-open:rotate-180" />
        </summary>
        <div className="flex flex-col gap-3 border-t border-border p-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-[11px] leading-relaxed text-muted-foreground">
            按当前已保存关系重新生成 Album Projects 归属。
          </p>
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setRebuilding(true);
              vm.rebuildAlbumProjects()
                .then(() => setMessage("专辑项目已重建"))
                .finally(() => setRebuilding(false));
            }}
            disabled={rebuilding}
            className="min-h-11 gap-2"
          >
            <RefreshCw
              className={cn("size-3.5", rebuilding && "animate-spin")}
            />
            重建专辑项目
          </Button>
        </div>
      </details>
    </div>
  );
}

function AlbumDetectionCard({
  result,
  selected,
  onToggle,
  compareAlbums,
}: {
  result: DetectionResult;
  selected: boolean;
  onToggle: () => void;
  compareAlbums: (a: number, b: number) => Promise<TrackComparison>;
}) {
  const [compareOpen, setCompareOpen] = useState(false);
  const [comparison, setComparison] = useState<TrackComparison | null>(null);
  const [loading, setLoading] = useState(false);
  const openComparison = () => {
    if (!compareOpen && !comparison) {
      setLoading(true);
      compareAlbums(
        result.primary_album_id,
        result.members.find((item) => item.album_id !== result.primary_album_id)
          ?.album_id ?? result.primary_album_id,
      )
        .then(setComparison)
        .finally(() => setLoading(false));
    }
    setCompareOpen((current) => !current);
  };
  return (
    <div
      className={cn(
        "rounded-xl border p-3 transition",
        selected
          ? "border-accent-foreground bg-accent-foreground/5"
          : "border-border bg-background",
      )}
    >
      <div className="flex items-start gap-3">
        <button
          type="button"
          aria-label={`选择 ${result.canonical_name}`}
          aria-pressed={selected}
          onClick={onToggle}
          className={cn(
            "mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-md border",
            selected
              ? "border-accent-foreground bg-accent-foreground text-primary-foreground"
              : "border-border",
          )}
        >
          {selected && <CheckCircle2 className="size-4" />}
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="truncate text-[13px] font-semibold">
              {displayName(result.canonical_name)}
            </p>
            <Badge variant="secondary">L2</Badge>
            <Badge variant="outline">
              {result.confidence === "high" ? "高置信" : "需复核"}
            </Badge>
          </div>
          <p className="mt-0.5 text-[11px] text-muted-foreground">
            {displayName(result.artist_name)} · {result.member_count} 个版本 ·{" "}
            {result.reason}
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {result.members.map((member) => (
              <span
                key={member.album_id}
                className="rounded-md bg-muted px-2 py-1 text-[10px] text-muted-foreground"
              >
                {displayName(member.album_name)}
              </span>
            ))}
          </div>
          <button
            type="button"
            onClick={openComparison}
            className="mt-2 flex min-h-9 items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
          >
            <ChevronDown
              className={cn("size-3.5 transition", compareOpen && "rotate-180")}
            />
            对比曲目
          </button>
          {compareOpen && (
            <div className="rounded-lg border border-border bg-background p-3">
              {loading ? (
                <Skeleton className="h-16 w-full" />
              ) : (
                <TrackComparePanel data={comparison} />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SavedGroupsTab({
  vm,
  objectType,
}: {
  vm: ReturnType<typeof useVersionMerge>;
  objectType: ObjectType;
}) {
  const { fetchGroups, fetchTrackGroups } = vm;
  useEffect(() => {
    if (objectType === "track") void fetchTrackGroups();
    else void fetchGroups();
  }, [fetchGroups, fetchTrackGroups, objectType]);
  const loading =
    objectType === "track" ? vm.trackGroupsLoading : vm.groupsLoading;
  const groups = objectType === "track" ? vm.trackGroups : vm.groups;
  if (loading)
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((item) => (
          <Skeleton key={item} className="h-24 rounded-xl" />
        ))}
      </div>
    );
  if (groups.length === 0)
    return (
      <EmptyState text={`暂无已保存的${OBJECT_COPY[objectType].label}分组。`} />
    );
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-[12px] text-muted-foreground">
          共 {groups.length} 个分组
        </p>
        <Badge variant="outline">按代表名称排序</Badge>
      </div>
      {objectType === "track"
        ? (groups as TrackGroup[]).map((group) => (
            <TrackSavedGroupCard key={group.group_id} group={group} vm={vm} />
          ))
        : (groups as ReleaseGroup[]).map((group) => (
            <AlbumSavedGroupCard key={group.group_id} group={group} vm={vm} />
          ))}
    </div>
  );
}

function TrackSavedGroupCard({
  group,
  vm,
}: {
  group: TrackGroup;
  vm: ReturnType<typeof useVersionMerge>;
}) {
  const [members, setMembers] = useState<TrackGroupMember[]>([]);
  const [open, setOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const load = () => {
    if (!open) vm.getTrackGroupMembers(group.group_id).then(setMembers);
    setOpen((current) => !current);
  };
  return (
    <SavedGroupShell
      icon={
        group.primary_album_id ? (
          <CoverCell
            index={0}
            coverUrl={`/covers/albums/${group.primary_album_id}.jpg`}
            label={group.primary_track_name ?? group.canonical_name}
            className="size-10 rounded-lg"
          />
        ) : (
          <Music2 className="size-4" />
        )
      }
      title={group.canonical_name}
      subtitle={`${group.artist_name ? `${displayName(group.artist_name)} · ` : ""}${group.member_count} 个成员`}
      scope={group.scope === "recording" ? "L2 同一录音" : "L3 同一作品"}
      manual={Boolean(group.is_manual)}
      open={open}
      onToggle={load}
      confirmDelete={confirmDelete}
      onAskDelete={() => setConfirmDelete(true)}
      onCancelDelete={() => setConfirmDelete(false)}
      onDelete={() =>
        vm.deleteTrackGroup(group.group_id).then(() => vm.fetchTrackGroups())
      }
    >
      {members.map((member) => (
        <MemberRow
          key={member.l1_id ?? member.track_id}
          primary={Boolean(member.is_primary)}
          title={member.track_name}
          subtitle={`${member.artist_name ? displayName(member.artist_name) : "艺人信息待修复"} · ${member.spotify_track_id ? `Spotify ${member.spotify_track_id}` : `#${member.l1_id ?? member.track_id}`}${(member.source_record_count ?? 1) > 1 ? ` · ${member.source_record_count} 条历史来源` : ""}${member.metadata_conflict ? " · 元数据待审核" : ""}`}
          coverUrl={
            member.album_id
              ? `/covers/albums/${member.album_id}.jpg`
              : undefined
          }
          onPrimary={() =>
            vm
              .setPrimaryTrack(group.group_id, member.l1_id ?? member.track_id)
              .then(() =>
                vm.getTrackGroupMembers(group.group_id).then(setMembers),
              )
          }
          onRemove={() =>
            vm
              .updateTrackMembers(group.group_id, undefined, [member.l1_id ?? member.track_id])
              .then(() =>
                setMembers((current) =>
                  current.filter(
                    (item) =>
                      (item.l1_id ?? item.track_id) !==
                      (member.l1_id ?? member.track_id),
                  ),
                ),
              )
          }
          details={
            (member.source_record_count ?? 1) > 1 ? (
              <TrackSourceDisclosure l1Id={member.l1_id ?? member.track_id} />
            ) : undefined
          }
        />
      ))}
    </SavedGroupShell>
  );
}

function AlbumSavedGroupCard({
  group,
  vm,
}: {
  group: ReleaseGroup;
  vm: ReturnType<typeof useVersionMerge>;
}) {
  const [members, setMembers] = useState<GroupMember[]>([]);
  const [open, setOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const load = () => {
    if (!open) vm.getGroupMembers(group.group_id).then(setMembers);
    setOpen((current) => !current);
  };
  return (
    <SavedGroupShell
      icon={
        group.primary_album_id ? (
          <CoverCell
            index={0}
            coverUrl={`/covers/albums/${group.primary_album_id}.jpg`}
            label={group.primary_album_name ?? group.canonical_name}
            className="size-10 rounded-lg"
          />
        ) : (
          <Disc3 className="size-4" />
        )
      }
      title={group.canonical_name}
      subtitle={displayName(group.artist_name)}
      scope={group.scope === "release" ? "L2 发行版本" : "L3 作品版本"}
      manual={Boolean(group.is_manual)}
      open={open}
      onToggle={load}
      confirmDelete={confirmDelete}
      onAskDelete={() => setConfirmDelete(true)}
      onCancelDelete={() => setConfirmDelete(false)}
      onDelete={() =>
        vm.deleteGroup(group.group_id).then(() => vm.fetchGroups())
      }
    >
      {members.map((member) => (
        <MemberRow
          key={member.album_id}
          primary={Boolean(
            member.is_primary || member.album_id === group.primary_album_id,
          )}
          title={member.album_name}
          subtitle={`专辑 #${member.album_id}`}
          coverUrl={`/covers/albums/${member.album_id}.jpg`}
          onPrimary={() =>
            vm
              .setPrimary(group.group_id, member.album_id)
              .then(() => vm.getGroupMembers(group.group_id).then(setMembers))
          }
          onRemove={() =>
            vm
              .updateMembers(group.group_id, undefined, [member.album_id])
              .then(() =>
                setMembers((current) =>
                  current.filter((item) => item.album_id !== member.album_id),
                ),
              )
          }
        />
      ))}
    </SavedGroupShell>
  );
}

function SavedGroupShell({
  icon,
  title,
  subtitle,
  scope,
  manual,
  open,
  onToggle,
  confirmDelete,
  onAskDelete,
  onCancelDelete,
  onDelete,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  scope: string;
  manual: boolean;
  open: boolean;
  onToggle: () => void;
  confirmDelete: boolean;
  onAskDelete: () => void;
  onCancelDelete: () => void;
  onDelete: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-border bg-background p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
        <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-muted text-muted-foreground">
          {icon}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="truncate text-[13px] font-semibold">
              {displayName(title)}
            </p>
            <Badge variant="secondary">{scope}</Badge>
            <Badge variant="outline">{manual ? "手动" : "自动"}</Badge>
          </div>
          <p className="mt-1 truncate text-[11px] text-muted-foreground">
            {subtitle}
          </p>
        </div>
        <div className="flex flex-wrap gap-1 sm:justify-end">
          <Button
            type="button"
            variant="ghost"
            onClick={onToggle}
            className="min-h-11"
          >
            {open ? "收起成员" : "查看成员"}
          </Button>
          {confirmDelete ? (
            <>
              <Button
                type="button"
                variant="destructive"
                onClick={onDelete}
                className="min-h-11"
              >
                确认删除
              </Button>
              <Button
                type="button"
                variant="ghost"
                onClick={onCancelDelete}
                className="min-h-11"
              >
                取消
              </Button>
            </>
          ) : (
            <Button
              type="button"
              aria-label={`删除 ${title}`}
              variant="ghost"
              onClick={onAskDelete}
              className="min-h-11 min-w-11 text-destructive hover:text-destructive"
            >
              <Trash2 className="size-4" />
            </Button>
          )}
        </div>
      </div>
      {open && (
        <div className="mt-4 space-y-2 border-t border-border pt-4">
          {children}
        </div>
      )}
    </div>
  );
}

function MemberRow({
  primary,
  title,
  subtitle,
  coverUrl,
  onPrimary,
  onRemove,
  details,
}: {
  primary: boolean;
  title: string;
  subtitle: string;
  coverUrl?: string;
  onPrimary: () => void;
  onRemove: () => void;
  details?: React.ReactNode;
}) {
  return (
    <div className="rounded-xl bg-muted/25">
      <div className="flex min-w-0 items-center gap-3 p-2.5">
      {coverUrl ? (
        <CoverCell
          index={0}
          coverUrl={coverUrl}
          label={title}
          className="size-9 rounded-lg"
        />
      ) : (
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-background">
          <Music2 className="size-3.5 text-muted-foreground" />
        </span>
      )}
      <div className="min-w-0 flex-1">
        <p className="truncate text-[12px] font-medium">{displayName(title)}</p>
        <p className="truncate text-[10px] text-muted-foreground">{subtitle}</p>
      </div>
      {primary ? (
        <Badge variant="outline">
          <Star className="mr-1 size-3 fill-current" />
          代表版本
        </Badge>
      ) : (
        <div className="flex shrink-0 gap-1">
          <Button
            type="button"
            variant="ghost"
            onClick={onPrimary}
            className="min-h-11 text-[11px]"
          >
            设为代表
          </Button>
          <Button
            type="button"
            aria-label={`移除 ${title}`}
            variant="ghost"
            onClick={onRemove}
            className="min-h-11 min-w-11 text-destructive hover:text-destructive"
          >
            <X className="size-3.5" />
          </Button>
        </div>
      )}
      </div>
      {details}
    </div>
  );
}

function TrackSourceDisclosure({ l1Id }: { l1Id: number }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [sources, setSources] = useState<TrackIdentitySource[]>([]);
  const [error, setError] = useState("");

  const toggle = async () => {
    if (!open && sources.length === 0) {
      setLoading(true);
      setError("");
      try {
        setSources(
          await api.get<TrackIdentitySource[]>(`/music/tracks/${l1Id}/sources`),
        );
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "来源记录加载失败");
      } finally {
        setLoading(false);
      }
    }
    setOpen((current) => !current);
  };

  return (
    <div className="border-t border-border/60 px-2.5 pb-2.5">
      <button
        type="button"
        onClick={() => void toggle()}
        aria-expanded={open}
        className="flex min-h-11 w-full items-center gap-1 text-left text-[10px] font-medium text-muted-foreground hover:text-foreground"
      >
        <ChevronDown className={cn("size-3.5 transition", open && "rotate-180")} />
        {open ? "收起来源记录" : "查看基础身份的来源记录"}
      </button>
      {open && (
        <div className="space-y-1.5 pb-1">
          {loading && <Skeleton className="h-12 w-full rounded-lg" />}
          {error && <p className="text-[10px] text-destructive">{error}</p>}
          {sources.map((source) => (
            <div
              key={source.track_id}
              className="flex min-w-0 items-center gap-2 rounded-lg border border-border/60 bg-background px-2 py-1.5"
            >
              {source.cover_url ? (
                <CoverCell
                  index={0}
                  coverUrl={source.cover_url}
                  label={source.track_name}
                  className="size-8 rounded-md"
                />
              ) : (
                <span className="size-8 shrink-0 rounded-md bg-muted" />
              )}
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[10px] font-medium">
                  {displayName(source.track_name)} · 原始记录 #{source.track_id}
                </span>
                <span className="block truncate text-[9px] text-muted-foreground">
                  {displayName(source.artist_name ?? "艺人待确认")}
                  {source.album_name ? ` · ${displayName(source.album_name)}` : ""}
                  {source.observed_plays ? ` · ${source.observed_plays} 次播放证据` : ""}
                </span>
              </span>
              {source.is_representative && <Badge variant="outline">展示来源</Badge>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ManualCreateTab({
  vm,
  objectType,
  initialArtistFilter,
  initialCanonicalName,
  initialTrackId,
}: {
  vm: ReturnType<typeof useVersionMerge>;
  objectType: ObjectType;
  initialArtistFilter: string;
  initialCanonicalName: string;
  initialTrackId: number | null;
}) {
  return objectType === "track" ? (
    <TrackManualWizard vm={vm} initialTrackId={initialTrackId} />
  ) : (
    <AlbumManualWizard
      vm={vm}
      initialArtistFilter={initialArtistFilter}
      initialCanonicalName={initialCanonicalName}
    />
  );
}

function StepIndicator({
  step,
  objectType,
}: {
  step: number;
  objectType: ObjectType;
}) {
  const noun = objectType === "track" ? "歌曲" : "专辑";
  return (
    <ol className="grid grid-cols-3 gap-1" aria-label="手动归并步骤">
      {[`选择${noun}`, "配置规则", "确认保存"].map((label, index) => {
        const value = index + 1;
        return (
          <li
            key={label}
            className={cn(
              "rounded-xl border px-2 py-2 text-center",
              step === value
                ? "border-accent-foreground bg-accent-foreground/5"
                : "border-border bg-muted/10",
            )}
          >
            <span
              className={cn(
                "mx-auto mb-1 flex size-6 items-center justify-center rounded-full text-[10px] font-bold",
                step > value
                  ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"
                  : step === value
                    ? "bg-accent-foreground text-primary-foreground"
                    : "bg-muted text-muted-foreground",
              )}
            >
              {step > value ? <CheckCircle2 className="size-3.5" /> : value}
            </span>
            <span className="block text-[10px] font-medium sm:text-[11px]">
              {label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function TrackManualWizard({
  vm,
  initialTrackId,
}: {
  vm: ReturnType<typeof useVersionMerge>;
  initialTrackId: number | null;
}) {
  const [step, setStep] = useState(1);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<TrackCreditTrackCandidate[]>([]);
  const [selected, setSelected] = useState<TrackCreditTrackCandidate[]>([]);
  const [primaryId, setPrimaryId] = useState<number | null>(null);
  const [scope, setScope] = useState<"recording" | "composition">("recording");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const searchTracks = vm.searchTracks;
  useEffect(() => {
    if (!initialTrackId) return;
    searchTracks(String(initialTrackId)).then((items) => {
      const match = items.find(
        (item) => (item.l1_id ?? item.track_id) === initialTrackId,
      );
      if (match) {
        setSelected([match]);
        setPrimaryId(match.l1_id ?? match.track_id);
      }
    });
  }, [initialTrackId, searchTracks]);
  const updateSearch = (nextQuery: string) => {
    setQuery(nextQuery);
    const normalized = nextQuery.trim();
    if (!normalized || selected.length >= 2) {
      setResults([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    searchTracks(normalized)
      .then(setResults)
      .finally(() => setLoading(false));
  };
  const save = () => {
    const candidate = selected.find(
      (item) => (item.l1_id ?? item.track_id) !== primaryId,
    );
    if (!primaryId || !candidate) return;
    setSaving(true);
    vm.confirmTrackCandidate(
      primaryId,
      candidate.l1_id ?? candidate.track_id,
      scope,
    )
      .then((result) =>
        setMessage(
          result.status === "ok"
            ? "歌曲版本分组已保存"
            : (result.message ?? "保存失败"),
        ),
      )
      .catch(() => setMessage("保存失败"))
      .finally(() => setSaving(false));
  };
  return (
    <div className="space-y-4">
      <StepIndicator step={step} objectType="track" />
      {step === 1 && (
        <WorkflowBlock
          number={1}
          title="选择要归并的歌曲"
          helper="选择两个不同的基础曲目身份；相同 Spotify ID 已在底层唯一归属，不需要再次归并。"
        >
          <EntitySearch
            value={query}
            onChange={updateSearch}
            label="搜索要归并的歌曲"
            placeholder="搜索歌名、艺人、专辑或稳定 ID"
            loading={loading}
            disabled={selected.length >= 2}
          />
          {query.trim() && !loading && (
            <div className="mt-2 max-h-64 space-y-1 overflow-y-auto rounded-xl border border-border bg-background p-1.5">
              {results.map((track) => {
                const identityId = track.l1_id ?? track.track_id;
                const chosen = selected.some(
                  (item) => (item.l1_id ?? item.track_id) === identityId,
                );
                return (
                  <button
                    key={identityId}
                    type="button"
                    disabled={chosen || selected.length >= 2}
                    onClick={() => {
                      setSelected((current) => [...current, track].slice(0, 2));
                      if (primaryId === null) setPrimaryId(identityId);
                      setQuery("");
                    }}
                    className="flex min-h-14 w-full min-w-0 items-center gap-3 rounded-lg px-2.5 py-2 text-left hover:bg-muted/60 disabled:opacity-50"
                  >
                    <Music2 className="size-4 shrink-0 text-muted-foreground" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[12px] font-semibold">
                        {displayName(track.track_name)}
                      </span>
                      <span className="block truncate text-[10px] text-muted-foreground">
                        {displayName(
                          track.effective_artist_names.join("、") ||
                            track.artist_name,
                        )}
                        {track.album_name
                          ? ` · ${displayName(track.album_name)}`
                          : ""}{" "}
                        · {track.spotify_track_id ? `Spotify ${track.spotify_track_id} · ` : ""}#{identityId}
                        {(track.source_record_count ?? 1) > 1
                          ? ` · ${track.source_record_count} 条历史来源`
                          : ""}
                      </span>
                    </span>
                    <Plus className="size-3.5 shrink-0" />
                  </button>
                );
              })}
              {results.length === 0 && (
                <EmptyState text="没有找到匹配的本地曲目。" />
              )}
            </div>
          )}
          <SelectedTrackCards
            tracks={selected}
            primaryId={primaryId}
            onPrimary={setPrimaryId}
            onRemove={(id) => {
              const remaining = selected.filter(
                (item) => (item.l1_id ?? item.track_id) !== id,
              );
              setSelected(remaining);
              if (primaryId === id)
                setPrimaryId(
                  remaining[0]?.l1_id ?? remaining[0]?.track_id ?? null,
                );
            }}
          />
          <WizardActions
            nextLabel="下一步：配置规则"
            onNext={() => setStep(2)}
            nextDisabled={selected.length < 2}
          />
        </WorkflowBlock>
      )}
      {step === 2 && (
        <WorkflowBlock
          number={2}
          title="配置代表版本与归并层级"
          helper="基础身份由系统治理；这里只配置不同曲目从 L2 或 L3 开始共享统计关系。"
        >
          <SelectedTrackCards
            tracks={selected}
            primaryId={primaryId}
            onPrimary={setPrimaryId}
            compact
          />
          <div className="mt-4">
            <ScopeSelector
              objectType="track"
              value={scope}
              onChange={(value) =>
                setScope(value as "recording" | "composition")
              }
            />
          </div>
          <WizardActions
            onBack={() => setStep(1)}
            nextLabel="下一步：确认保存"
            onNext={() => setStep(3)}
            nextDisabled={!primaryId}
          />
        </WorkflowBlock>
      )}
      {step === 3 && (
        <WorkflowBlock
          number={3}
          title="确认保存"
          helper="保存后可在“已保存分组”继续调整代表版本或成员。"
        >
          <MergeSummary
            objectType="track"
            scope={scope}
            items={selected.map((item) => ({
              id: item.l1_id ?? item.track_id,
              name: item.track_name,
              subtitle: displayName(
                item.effective_artist_names.join("、") || item.artist_name,
              ),
            }))}
            primaryId={primaryId}
          />
          {message && <StatusMessage message={message} />}
          <WizardActions
            onBack={() => setStep(2)}
            nextLabel={saving ? "正在保存…" : "保存歌曲分组"}
            onNext={save}
            nextDisabled={saving}
          />
        </WorkflowBlock>
      )}
    </div>
  );
}

function AlbumManualWizard({
  vm,
  initialArtistFilter,
  initialCanonicalName,
}: {
  vm: ReturnType<typeof useVersionMerge>;
  initialArtistFilter: string;
  initialCanonicalName: string;
}) {
  const [step, setStep] = useState(1);
  const [query, setQuery] = useState(initialArtistFilter);
  const [albums, setAlbums] = useState<UngroupedAlbum[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [primaryId, setPrimaryId] = useState<number | null>(null);
  const [canonicalName, setCanonicalName] = useState(initialCanonicalName);
  const [scope, setScope] = useState<"release" | "composition">("release");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const getUngroupedAlbums = vm.getUngroupedAlbums;
  const selectedAlbums = albums.filter((item) => selected.has(item.album_id));
  const load = () => {
    setLoading(true);
    getUngroupedAlbums(query || undefined)
      .then((items) => {
        setAlbums(items);
        if (!initialCanonicalName) return;
        const match = items.find(
          (item) =>
            item.album_name.toLocaleLowerCase() ===
            initialCanonicalName.toLocaleLowerCase(),
        );
        if (match) {
          setSelected(new Set([match.album_id]));
          setPrimaryId(match.album_id);
        }
      })
      .finally(() => setLoading(false));
  };
  useEffect(() => {
    if (!initialArtistFilter) return;
    getUngroupedAlbums(initialArtistFilter).then((items) => {
      setAlbums(items);
      if (!initialCanonicalName) return;
      const match = items.find(
        (item) =>
          item.album_name.toLocaleLowerCase() ===
          initialCanonicalName.toLocaleLowerCase(),
      );
      if (match) {
        setSelected(new Set([match.album_id]));
        setPrimaryId(match.album_id);
      }
    });
  }, [getUngroupedAlbums, initialArtistFilter, initialCanonicalName]);
  const save = () => {
    const primary = albums.find((item) => item.album_id === primaryId);
    if (!primaryId || !primary) return;
    setSaving(true);
    const name = canonicalName || primary.album_name;
    const ids = Array.from(selected);
    const request =
      scope === "composition"
        ? vm
            .confirmAlbumRelation(
              name,
              primaryId,
              ids.filter((id) => id !== primaryId),
              "composition",
              "rerecord",
              true,
            )
            .then((result) => ({
              message:
                result.status === "ok"
                  ? `专辑版本分组已保存 · 关联 ${result.confirmed_track_pair_count} 组歌曲`
                  : (result.message ?? "保存失败"),
            }))
        : vm
            .createGroup(name, 0, primaryId, ids, "release")
            .then((result) => ({
              message: result.group_id ? "专辑版本分组已保存" : "保存失败",
            }));
    request
      .then((result) => setMessage(result.message))
      .catch(() => setMessage("保存失败"))
      .finally(() => setSaving(false));
  };
  return (
    <div className="space-y-4">
      <StepIndicator step={step} objectType="album" />
      {step === 1 && (
        <WorkflowBlock
          number={1}
          title="选择要归并的专辑"
          helper="按艺人查找未分组发行，并明确勾选至少两个成员。"
        >
          <div className="flex flex-col gap-2 sm:flex-row">
            <EntitySearch
              value={query}
              onChange={setQuery}
              label="搜索要归并的专辑"
              placeholder="输入艺人名称"
              loading={loading}
            />
            <Button
              type="button"
              variant="outline"
              onClick={load}
              disabled={loading}
              className="min-h-11 shrink-0"
            >
              查询专辑
            </Button>
          </div>
          <div className="mt-3 max-h-72 space-y-1 overflow-y-auto rounded-xl border border-border bg-background p-1.5">
            {albums.length ? (
              albums.map((album) => (
                <button
                  key={album.album_id}
                  type="button"
                  aria-pressed={selected.has(album.album_id)}
                  onClick={() =>
                    setSelected((current) => {
                      const next = new Set(current);
                      if (next.has(album.album_id)) {
                        next.delete(album.album_id);
                        if (primaryId === album.album_id) setPrimaryId(null);
                      } else {
                        next.add(album.album_id);
                        if (primaryId === null) setPrimaryId(album.album_id);
                      }
                      return next;
                    })
                  }
                  className={cn(
                    "flex min-h-14 w-full min-w-0 items-center gap-3 rounded-lg px-2.5 py-2 text-left hover:bg-muted/60",
                    selected.has(album.album_id) && "bg-accent-foreground/5",
                  )}
                >
                  <span
                    className={cn(
                      "flex size-5 shrink-0 items-center justify-center rounded border",
                      selected.has(album.album_id)
                        ? "border-accent-foreground bg-accent-foreground text-primary-foreground"
                        : "border-border",
                    )}
                  >
                    {selected.has(album.album_id) && (
                      <CheckCircle2 className="size-3.5" />
                    )}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[12px] font-semibold">
                      {displayName(album.album_name)}
                    </span>
                    <span className="block truncate text-[10px] text-muted-foreground">
                      {displayName(album.artist_name)} · #{album.album_id}
                    </span>
                  </span>
                </button>
              ))
            ) : (
              <EmptyState text="输入艺人名称后查询可用专辑。" />
            )}
          </div>
          <WizardActions
            nextLabel="下一步：配置规则"
            onNext={() => setStep(2)}
            nextDisabled={selected.size < 2}
          />
        </WorkflowBlock>
      )}
      {step === 2 && (
        <WorkflowBlock
          number={2}
          title="配置代表版本与归并层级"
          helper="两种对象使用同一决策顺序：先选代表版本，再选开始共享统计身份的层级。"
        >
          <div className="grid gap-2 sm:grid-cols-2">
            {selectedAlbums.map((album) => (
              <button
                key={album.album_id}
                type="button"
                onClick={() => setPrimaryId(album.album_id)}
                className={cn(
                  "min-w-0 rounded-xl border p-3 text-left",
                  primaryId === album.album_id
                    ? "border-accent-foreground bg-accent-foreground/5"
                    : "border-border",
                )}
              >
                <span className="flex items-center gap-2 text-[11px] font-semibold">
                  <Star
                    className={cn(
                      "size-3.5",
                      primaryId === album.album_id &&
                        "fill-current text-accent-foreground",
                    )}
                  />
                  {primaryId === album.album_id ? "代表版本" : "设为代表版本"}
                </span>
                <span className="mt-2 block truncate text-[12px] font-medium">
                  {displayName(album.album_name)}
                </span>
              </button>
            ))}
          </div>
          <div className="mt-4 space-y-1.5">
            <FieldLabel label="分组显示名称" />
            <input
              value={canonicalName}
              onChange={(event) => setCanonicalName(event.target.value)}
              placeholder="留空则使用代表版本名称"
              className="h-11 w-full rounded-xl border border-input bg-background px-3 text-[13px] outline-none focus:border-accent-foreground"
            />
          </div>
          <div className="mt-4">
            <ScopeSelector
              objectType="album"
              value={scope}
              onChange={(value) => setScope(value as "release" | "composition")}
            />
          </div>
          <WizardActions
            onBack={() => setStep(1)}
            nextLabel="下一步：确认保存"
            onNext={() => setStep(3)}
            nextDisabled={!primaryId}
          />
        </WorkflowBlock>
      )}
      {step === 3 && (
        <WorkflowBlock
          number={3}
          title="确认保存"
          helper="确认成员、代表版本与统计层级后再写入覆盖关系。"
        >
          <MergeSummary
            objectType="album"
            scope={scope}
            canonicalName={canonicalName}
            items={selectedAlbums.map((item) => ({
              id: item.album_id,
              name: item.album_name,
              subtitle: displayName(item.artist_name),
            }))}
            primaryId={primaryId}
          />
          {message && <StatusMessage message={message} />}
          <WizardActions
            onBack={() => setStep(2)}
            nextLabel={saving ? "正在保存…" : "保存专辑分组"}
            onNext={save}
            nextDisabled={saving}
          />
        </WorkflowBlock>
      )}
    </div>
  );
}

function ScopeSelector({
  objectType,
  value,
  onChange,
  autoMode = false,
}: {
  objectType: ObjectType;
  value: MergeScope;
  onChange: (value: MergeScope) => void;
  autoMode?: boolean;
}) {
  const levels =
    objectType === "track"
      ? [
          {
            value: "recording",
            title: "L2 · 同一录音",
            helper: "同一母带在单曲、专辑或豪华版中的记录。",
            disabled: false,
          },
          {
            value: "composition",
            title: "L3 · 同一作品",
            helper: "重录、现场、原声或 Remix 等作品级版本。",
            disabled: false,
          },
        ]
      : [
          {
            value: "release",
            title: "L2 · 发行版本",
            helper: "原版、豪华版、加曲版等同一发行项目。",
            disabled: false,
          },
          {
            value: "composition",
            title: "L3 · 作品版本",
            helper: "重录或作品级不同版本；自动检测不直接写入。",
            disabled: autoMode,
          },
        ];
  return (
    <div className="space-y-2">
      <FieldLabel
        label="从哪个统计层级开始归并"
        badge={value === "composition" ? "L3" : "L2"}
      />
      <div
        className="grid gap-2 sm:grid-cols-2"
        role="radiogroup"
        aria-label={`${OBJECT_COPY[objectType].label}生效层级`}
      >
        {levels.map((level) => (
          <button
            key={level.value}
            type="button"
            role="radio"
            aria-checked={value === level.value}
            disabled={level.disabled}
            onClick={() => onChange(level.value as MergeScope)}
            className={cn(
              "min-h-24 rounded-xl border p-3 text-left transition",
              value === level.value
                ? "border-accent-foreground bg-accent-foreground/5"
                : "border-border bg-background hover:border-accent-foreground/35",
              level.disabled &&
                "cursor-not-allowed border-dashed bg-muted/15 opacity-60",
            )}
          >
            <span className="block text-[11px] font-semibold">
              {level.title}
            </span>
            <span className="mt-1 block text-[10px] leading-relaxed text-muted-foreground">
              {level.helper}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function EntitySearch({
  value,
  onChange,
  label,
  placeholder,
  loading,
  disabled = false,
}: {
  value: string;
  onChange: (value: string) => void;
  label: string;
  placeholder: string;
  loading: boolean;
  disabled?: boolean;
}) {
  return (
    <div className="relative min-w-0 flex-1">
      <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
      <input
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        placeholder={placeholder}
        className="h-11 w-full rounded-xl border border-input bg-background pl-9 pr-10 text-[13px] outline-none focus:border-accent-foreground disabled:opacity-60"
      />
      {loading && (
        <RefreshCw className="absolute right-3 top-1/2 size-4 -translate-y-1/2 animate-spin text-muted-foreground" />
      )}
    </div>
  );
}

function SelectedTrackCards({
  tracks,
  primaryId,
  onPrimary,
  onRemove,
  compact = false,
}: {
  tracks: TrackCreditTrackCandidate[];
  primaryId: number | null;
  onPrimary: (id: number) => void;
  onRemove?: (id: number) => void;
  compact?: boolean;
}) {
  return (
    <div className="mt-3 grid gap-2 sm:grid-cols-2">
      {[0, 1].map((slot) => {
        const track = tracks[slot];
        if (!track)
          return (
            <div
              key={slot}
              className="flex min-h-20 items-center justify-center rounded-xl border border-dashed border-border text-[11px] text-muted-foreground"
            >
              {slot === 0 ? "选择第一个版本" : "选择另一个版本"}
            </div>
          );
        const identityId = track.l1_id ?? track.track_id;
        const primary = identityId === primaryId;
        return (
          <div
            key={identityId}
            className={cn(
              "relative min-w-0 rounded-xl border p-3",
              primary
                ? "border-accent-foreground bg-accent-foreground/5"
                : "border-border",
            )}
          >
            <button
              type="button"
              onClick={() => onPrimary(identityId)}
              className="flex min-h-8 items-center gap-1 text-[10px] font-semibold"
            >
              <Star
                className={cn(
                  "size-3",
                  primary && "fill-current text-accent-foreground",
                )}
              />
              {primary ? "代表版本" : "设为代表版本"}
            </button>
            <p className="mt-1 truncate text-[12px] font-semibold">
              {displayName(track.track_name)}
            </p>
            <p className="truncate text-[10px] text-muted-foreground">
              {displayName(
                track.effective_artist_names.join("、") || track.artist_name,
              )}{" "}
              · {track.spotify_track_id ? `Spotify ${track.spotify_track_id} · ` : ""}#{identityId}
              {(track.source_record_count ?? 1) > 1
                ? ` · ${track.source_record_count} 条历史来源`
                : ""}
            </p>
            {onRemove && !compact && (
              <button
                type="button"
                aria-label={`移除 ${track.track_name}`}
                onClick={() => onRemove(identityId)}
                className="absolute right-2 top-2 flex size-11 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted"
              >
                <X className="size-3.5" />
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}

function MergeSummary({
  objectType,
  scope,
  items,
  primaryId,
  canonicalName,
}: {
  objectType: ObjectType;
  scope: MergeScope;
  items: Array<{ id: number; name: string; subtitle: string }>;
  primaryId: number | null;
  canonicalName?: string;
}) {
  const scopeName =
    objectType === "track"
      ? scope === "recording"
        ? "L2 同一录音"
        : "L3 同一作品"
      : scope === "release"
        ? "L2 发行版本"
        : "L3 作品版本";
  return (
    <div className="space-y-3 rounded-xl border border-border bg-background p-4">
      <div className="flex flex-wrap gap-2">
        <Badge variant="outline">{OBJECT_COPY[objectType].label}</Badge>
        <Badge variant="secondary">{scopeName}</Badge>
        <span className="text-[11px] text-muted-foreground">
          {items.length} 个成员
        </span>
      </div>
      {canonicalName && (
        <p className="text-[12px]">
          <span className="text-muted-foreground">显示名称：</span>
          {displayName(canonicalName)}
        </p>
      )}
      <div className="space-y-2">
        {items.map((item) => (
          <div
            key={item.id}
            className={cn(
              "flex min-w-0 items-center gap-2 rounded-lg px-3 py-2",
              item.id === primaryId ? "bg-accent-foreground/5" : "bg-muted/25",
            )}
          >
            <Star
              className={cn(
                "size-3.5 shrink-0",
                item.id === primaryId
                  ? "fill-current text-accent-foreground"
                  : "text-transparent",
              )}
            />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[12px] font-medium">
                {displayName(item.name)}
              </span>
              <span className="block truncate text-[10px] text-muted-foreground">
                {item.subtitle} · #{item.id}
              </span>
            </span>
            {item.id === primaryId && <Badge variant="outline">代表版本</Badge>}
          </div>
        ))}
      </div>
    </div>
  );
}

function WizardActions({
  onBack,
  nextLabel,
  onNext,
  nextDisabled = false,
}: {
  onBack?: () => void;
  nextLabel: string;
  onNext: () => void;
  nextDisabled?: boolean;
}) {
  return (
    <div
      className={cn(
        "mt-4 flex flex-wrap gap-2",
        onBack ? "justify-between" : "justify-end",
      )}
    >
      {onBack && (
        <Button
          type="button"
          variant="ghost"
          onClick={onBack}
          className="min-h-11"
        >
          上一步
        </Button>
      )}
      <Button
        type="button"
        onClick={onNext}
        disabled={nextDisabled}
        className="min-h-11 gap-2"
      >
        {nextLabel}
        <ChevronDown className="size-3.5 -rotate-90" />
      </Button>
    </div>
  );
}

function EmptyState({
  text,
  success = false,
}: {
  text: string;
  success?: boolean;
}) {
  return (
    <div className="flex min-h-24 flex-col items-center justify-center gap-2 text-center text-[12px] text-muted-foreground">
      {success && <CheckCircle2 className="size-6 text-emerald-600" />}
      <p>{text}</p>
    </div>
  );
}

function StatusMessage({ message }: { message: string }) {
  const success =
    message.includes("已") ||
    message.includes("创建") ||
    message.includes("保存");
  return (
    <p
      role="status"
      className={cn(
        "mt-3 rounded-xl border px-3 py-2.5 text-[12px]",
        success
          ? "border-emerald-500/25 bg-emerald-500/5 text-emerald-700 dark:text-emerald-300"
          : "border-destructive/25 bg-destructive/5 text-destructive",
      )}
    >
      {message}
    </p>
  );
}
