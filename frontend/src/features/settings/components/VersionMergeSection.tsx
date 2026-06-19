import { useState, useEffect } from 'react'
import { GlassCard } from '@/components/shared/GlassCard'
import { displayName } from '@/lib/chinese'
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
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { Star, Trash2, Plus, X, Search, ChevronDown, CheckCircle2, RefreshCw, GitMerge } from 'lucide-react'
import { useVersionMerge } from '@/hooks/useSettings'
import type { DetectionResult, DetectionMember, ReleaseGroup, GroupMember, UngroupedAlbum, TrackComparison, TrackGroupCandidate } from '@/types/settings'
import { SectionHeader, FieldLabel, TrackComparePanel } from '@/features/settings/components/SettingsHelpers'
import { getDefaultMergeLevel, setDefaultMergeLevel } from '@/lib/merge-level'

type MergeTabKey = 'detect' | 'saved' | 'create'
const MERGE_TABS: { key: MergeTabKey; label: string }[] = [
  { key: 'detect', label: '自动检测' },
  { key: 'saved', label: '已保存分组' },
  { key: 'create', label: '手动创建' },
]

const MERGE_LEVELS = [
  { value: 1, label: 'L1', desc: '不合并' },
  { value: 2, label: 'L2', desc: 'Recording' },
  { value: 3, label: 'L3', desc: 'Composition' },
] as const

export function VersionMergeSection() {
  const [activeTab, setActiveTab] = useState<MergeTabKey>('detect')
  const [mergeLevel, setMergeLevel] = useState(getDefaultMergeLevel)
  const vm = useVersionMerge()

  useEffect(() => {
    if (activeTab === 'saved') vm.fetchGroups()
  }, [activeTab, vm.fetchGroups])

  const handleMergeLevelChange = (v: number) => {
    setMergeLevel(v)
    setDefaultMergeLevel(v)
  }

  return (
    <GlassCard className="p-6">
      <SectionHeader num={3} title="Version Merge" desc="管理专辑版本合并规则，将同一专辑的不同版本（豪华版、Acoustic版等）合并为统一条目。" />

      {/* Merge Level selector */}
      <div className="mb-5 rounded-xl border border-border bg-muted/30 p-4">
        <FieldLabel label="默认合并严格度" badge={MERGE_LEVELS.find(l => l.value === mergeLevel)?.label} />
        <p className="mt-1 text-[12px] text-muted-foreground">
          控制所有榜单和统计中曲目/专辑版本合并的默认级别。各 Billboard 页面可通过 URL 参数临时覆盖。
        </p>
        <div className="mt-3 flex gap-2">
          {MERGE_LEVELS.map((l) => (
            <button
              key={l.value}
              type="button"
              onClick={() => handleMergeLevelChange(l.value)}
              className={cn(
                'flex-1 rounded-lg border px-3 py-2 text-center transition-all duration-200',
                mergeLevel === l.value
                  ? 'border-accent-foreground bg-accent-foreground text-primary-foreground shadow-sm'
                  : 'border-border bg-card hover:border-muted-foreground/30 hover:bg-muted/50',
              )}
            >
              <div className={cn('font-sans text-[13px] font-semibold', mergeLevel === l.value ? 'text-primary-foreground' : 'text-foreground')}>
                {l.label}
              </div>
              <div className={cn('font-sans text-[11px]', mergeLevel === l.value ? 'text-primary-foreground/70' : 'text-muted-foreground')}>
                {l.desc}
              </div>
            </button>
          ))}
        </div>
      </div>

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

function AutoDetectionTab({ vm }: { vm: ReturnType<typeof useVersionMerge> }) {
  const [threshold, setThreshold] = useState(0.4)
  const [results, setResults] = useState<DetectionResult[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [applying, setApplying] = useState(false)
  const [applyMsg, setApplyMsg] = useState('')
  const [candidates, setCandidates] = useState<TrackGroupCandidate[] | null>(null)
  const [candidateLoading, setCandidateLoading] = useState(false)
  const [candidateMsg, setCandidateMsg] = useState('')
  const [candidateMsgTone, setCandidateMsgTone] = useState<'success' | 'error'>('success')
  const [confirmingCandidateKey, setConfirmingCandidateKey] = useState<string | null>(null)
  const [ignoredCandidateKeys, setIgnoredCandidateKeys] = useState<Set<string>>(new Set())
  const [rebuildLoading, setRebuildLoading] = useState(false)
  const [maintenanceMsg, setMaintenanceMsg] = useState('')

  const candidateKey = (item: TrackGroupCandidate) => `${item.original_track_id}-${item.candidate_track_id}`
  const visibleCandidates = candidates?.filter((item) => !ignoredCandidateKeys.has(candidateKey(item))) ?? []

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

  const handleFetchCandidates = () => {
    setCandidateLoading(true)
    setCandidateMsg('')
    setCandidateMsgTone('success')
    setIgnoredCandidateKeys(new Set())
    vm.fetchCollaborationCandidates()
      .then(setCandidates)
      .finally(() => setCandidateLoading(false))
  }

  const handleConfirmCandidate = (item: TrackGroupCandidate) => {
    const key = candidateKey(item)
    setConfirmingCandidateKey(key)
    setCandidateMsg('')
    setCandidateMsgTone('success')
    vm.confirmTrackCandidate(item.original_track_id, item.candidate_track_id, 'composition')
      .then((res) => {
        if (res.status === 'ok') {
          setCandidateMsg(`已确认 L3 合并：${displayName(item.candidate_track_name)}`)
          setCandidates((prev) => prev?.filter((candidate) => candidateKey(candidate) !== key) ?? null)
          return
        }
        setCandidateMsgTone('error')
        setCandidateMsg(res.message ?? '确认失败')
      })
      .catch(() => {
        setCandidateMsgTone('error')
        setCandidateMsg('确认失败')
      })
      .finally(() => setConfirmingCandidateKey(null))
  }

  const handleIgnoreCandidate = (item: TrackGroupCandidate) => {
    const key = candidateKey(item)
    setIgnoredCandidateKeys((prev) => {
      const next = new Set(prev)
      next.add(key)
      return next
    })
  }

  const handleRebuildProjects = () => {
    setRebuildLoading(true)
    setMaintenanceMsg('')
    vm.rebuildAlbumProjects()
      .then((res) => setMaintenanceMsg(res.status === 'ok' ? '专辑项目已重建' : '重建失败'))
      .finally(() => setRebuildLoading(false))
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
              aria-label="重叠率阈值"
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

      <div className="grid gap-3 lg:grid-cols-2">
        <div className="rounded-xl border border-border p-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <FieldLabel label="Album Projects" />
              <p className="mt-1 text-[12px] text-muted-foreground">按当前版本分组重新生成专辑项目归属。</p>
            </div>
            <Button size="sm" variant="outline" onClick={handleRebuildProjects} disabled={rebuildLoading} className="gap-1.5">
              {rebuildLoading ? <RefreshCw className="size-3.5 animate-spin" /> : <RefreshCw className="size-3.5" />}
              重建
            </Button>
          </div>
          {maintenanceMsg && (
            <div className="mt-3 flex items-center gap-2 text-[13px] text-green-600 dark:text-green-400">
              <CheckCircle2 className="size-3.5" />
              {maintenanceMsg}
            </div>
          )}
        </div>

        <div className="rounded-xl border border-border p-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <FieldLabel label="合作版候选" />
              <p className="mt-1 text-[12px] text-muted-foreground">查找包含原主艺人的 remix / feat. 候选。</p>
            </div>
            <Button size="sm" variant="outline" onClick={handleFetchCandidates} disabled={candidateLoading} className="gap-1.5">
              {candidateLoading ? <RefreshCw className="size-3.5 animate-spin" /> : <GitMerge className="size-3.5" />}
              查询
            </Button>
          </div>
        </div>
      </div>

      {candidates !== null && (
        <div className="max-h-[220px] space-y-2 overflow-y-auto rounded-xl border border-border p-3">
          {visibleCandidates.length === 0 ? (
            <p className="py-4 text-center text-[13px] text-muted-foreground">暂无合作版候选。</p>
          ) : (
            visibleCandidates.map((item) => {
              const key = candidateKey(item)
              const confirming = confirmingCandidateKey === key
              return (
                <div key={key} className="flex items-center gap-3 rounded-lg bg-muted/30 px-3 py-2">
                  <GitMerge className="size-3.5 shrink-0 text-accent-foreground" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-medium">{displayName(item.original_track_name)}</p>
                    <p className="truncate text-[12px] text-muted-foreground">{displayName(item.candidate_track_name)}</p>
                  </div>
                  <Badge variant="outline" className="shrink-0 text-[10px]">#{item.primary_artist_id}</Badge>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleConfirmCandidate(item)}
                    disabled={confirmingCandidateKey !== null}
                    className="h-7 shrink-0 gap-1 text-[12px]"
                  >
                    {confirming ? <RefreshCw className="size-3 animate-spin" /> : <CheckCircle2 className="size-3" />}
                    确认 L3
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleIgnoreCandidate(item)}
                    disabled={confirmingCandidateKey !== null}
                    className="h-7 shrink-0 text-[12px]"
                  >
                    <X className="size-3" />
                  </Button>
                </div>
              )
            })
          )}
          {candidateMsg && (
            <div
              className={cn(
                'flex items-center gap-2 pt-1 text-[13px]',
                candidateMsgTone === 'success'
                  ? 'text-green-600 dark:text-green-400'
                  : 'text-destructive',
              )}
            >
              {candidateMsgTone === 'success' ? <CheckCircle2 className="size-3.5" /> : <X className="size-3.5" />}
              {candidateMsg}
            </div>
          )}
        </div>
      )}

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
              {displayName(r.canonical_name)}
            </span>
            <Badge variant={r.confidence === 'high' ? 'default' : 'secondary'} className="text-[11px]">
              {r.confidence === 'high' ? '高置信' : '低置信'}
            </Badge>
          </div>
          <p className="text-[12.5px] text-muted-foreground">
            {displayName(r.artist_name)} · {r.member_count} 个版本 · {r.reason}
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
                {displayName(m.album_name)}
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
            <span className="font-sans text-[14px] font-semibold text-foreground">{displayName(g.canonical_name)}</span>
            {g.is_manual ? (
              <Badge variant="outline" className="text-[10px]">手动</Badge>
            ) : (
              <Badge variant="outline" className="text-[10px]">自动</Badge>
            )}
            <Badge variant="secondary" className="text-[10px]">
              {g.scope === 'composition' ? 'L3 作品' : 'L2 发行'}
            </Badge>
          </div>
          <p className="text-[12.5px] text-muted-foreground">{displayName(g.artist_name)}</p>
          {g.primary_album_name && (
            <p className="mt-1 flex items-center gap-1 text-[12.5px] text-muted-foreground">
              <Star className="size-3 text-accent-foreground" />
              主版本：{displayName(g.primary_album_name)}
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
                {displayName(m.album_name)}
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

function ManualCreateTab({ vm }: { vm: ReturnType<typeof useVersionMerge> }) {
  const [albums, setAlbums] = useState<UngroupedAlbum[]>([])
  const [artistFilter, setArtistFilter] = useState('')
  const [canonicalName, setCanonicalName] = useState('')
  const [scope, setScope] = useState<'release' | 'composition'>('release')
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

    setCreating(true)
    const name = canonicalName || firstAlbum.album_name
    const selectedIds = Array.from(selectedAlbums)
    const request = scope === 'composition'
      ? vm.confirmAlbumRelation(
        name,
        primaryId,
        selectedIds.filter((id) => id !== primaryId),
        'composition',
        'rerecord',
        true,
      ).then((res) => {
        if (res.status !== 'ok') return { ok: false, message: res.message ?? '创建失败' }
        return {
          ok: true,
          message: `分组创建成功 (ID: ${res.release_group_id}) · 歌曲 ${res.confirmed_track_pair_count} 组 · 独有 ${res.exclusive_track_count} 首`,
        }
      })
      : vm.createGroup(
        name,
        0,
        primaryId,
        selectedIds,
        scope,
      ).then((res) => ({
        ok: Boolean(res.group_id),
        message: res.group_id ? `分组创建成功 (ID: ${res.group_id})` : '创建失败',
      }))

    request
      .then((res) => {
      if (res.ok) {
        setMsg(res.message)
        setSelectedAlbums(new Set())
        setPrimaryId(null)
        setCanonicalName('')
        setScope('release')
      } else {
        setMsg(res.message)
      }
      })
      .catch(() => setMsg('创建失败'))
      .finally(() => setCreating(false))
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
                  <span className="flex-1 truncate">{displayName(a.album_name)}</span>
                  <span className="text-[12px] text-muted-foreground">{displayName(a.artist_name)}</span>
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

              <div className="space-y-1.5">
                <FieldLabel label="合并语义" badge={scope === 'composition' ? 'L3' : 'L2'} />
                <Select
                  value={scope}
                  onValueChange={(v) => setScope(v as 'release' | 'composition')}
                >
                  <SelectTrigger className="w-[280px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="release">L2 发行版本</SelectItem>
                    <SelectItem value="composition">L3 作品版本</SelectItem>
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
