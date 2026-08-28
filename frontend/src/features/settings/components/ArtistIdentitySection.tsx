import { useState, type ComponentProps } from 'react'
import { AlertTriangle, Check, Link2, Loader2, Plus, Search, ShieldCheck, UserRound, X } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useArtistIdentities } from '@/hooks/useArtistIdentities'
import { cn } from '@/lib/utils'
import type { ArtistIdentityCandidate, ArtistIdentityGroup } from '@/types/settings'
import { displayName as localizedName, useChineseTextVersion } from '@/lib/chinese'

type IdentityTab = 'create' | 'groups'

function Input({ className, ...props }: ComponentProps<'input'>) {
  return <input className={cn('h-10 w-full rounded-lg border border-input bg-background px-3 text-sm outline-none transition focus:border-accent-foreground focus:ring-2 focus:ring-accent-foreground/15', className)} {...props} />
}

function ArtistAvatar({ candidate, name }: { candidate?: { cover_url: string | null }; name: string }) {
  const [failed, setFailed] = useState(false)
  useChineseTextVersion()
  if (!candidate?.cover_url || failed) {
    return (
      <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-accent-foreground/10 font-serif text-sm font-bold text-accent-foreground">
        {localizedName(name).trim().slice(0, 1).toUpperCase() || <UserRound className="size-4" />}
      </span>
    )
  }
  return (
    <img
      src={candidate.cover_url}
      alt=""
      className="size-10 shrink-0 rounded-full object-cover"
      onError={() => setFailed(true)}
    />
  )
}

function mutationMessage(error: unknown): string {
  return error instanceof Error ? error.message : '操作失败，请检查选择后重试'
}

export function ArtistIdentitySection({ initialSearch = '' }: { initialSearch?: string }) {
  useChineseTextVersion()
  const [tab, setTab] = useState<IdentityTab>('create')
  const [search, setSearch] = useState(initialSearch)
  const [selected, setSelected] = useState<ArtistIdentityCandidate[]>([])
  const [canonicalId, setCanonicalId] = useState<number | null>(null)
  const [displayName, setDisplayName] = useState('')
  const [confirmConflict, setConfirmConflict] = useState(false)
  const identity = useArtistIdentities(search)
  const state = identity.overview.data?.state

  const selectCandidate = (candidate: ArtistIdentityCandidate) => {
    if (selected.some((item) => item.artist_id === candidate.artist_id)) return
    setSelected((items) => [...items, candidate])
    if (canonicalId == null) {
      setCanonicalId(candidate.artist_id)
      setDisplayName(candidate.canonical_display_name || candidate.artist_name)
    }
  }
  const removeCandidate = (artistId: number) => {
    const next = selected.filter((item) => item.artist_id !== artistId)
    setSelected(next)
    if (canonicalId === artistId) {
      setCanonicalId(next[0]?.artist_id ?? null)
      setDisplayName(next[0]?.canonical_display_name ?? next[0]?.artist_name ?? '')
    }
  }
  const draft = canonicalId == null ? null : {
    artist_ids: selected.map((item) => item.artist_id),
    canonical_artist_id: canonicalId,
    display_name: displayName,
  }
  const canPreview = Boolean(draft && selected.length >= 2 && displayName.trim())
  const preview = identity.preview.data
  const undoneEventIds = new Set(
    identity.events
      .map((event) => event.undo_of_event_id)
      .filter((eventId): eventId is number => eventId != null),
  )

  const confirmCreate = async () => {
    if (!draft || state == null) return
    const externalIds = selected.flatMap((candidate) =>
      candidate.external_ids.map((link) => ({
        artist_id: candidate.artist_id,
        provider: link.provider,
        external_id: link.external_id,
        evidence_type: link.evidence_type,
        evidence_source: 'artist_identity_candidate',
        confidence: link.confidence,
        verified: Boolean(link.verified),
      })),
    )
    await identity.create.mutateAsync({
      ...draft,
      expected_revision: state.current_revision,
      confirm_external_id_conflict: confirmConflict,
      external_ids: externalIds,
    })
    setSelected([])
    setCanonicalId(null)
    setDisplayName('')
    setConfirmConflict(false)
    identity.preview.reset()
    setTab('groups')
  }

  return (
    <section className="space-y-5" aria-label="艺人身份工作区">
        <div className="mb-5 flex flex-wrap items-center gap-2 rounded-xl border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
          <ShieldCheck className="size-4 text-accent-foreground" />
          <span>身份 revision {state?.current_revision ?? '—'}</span>
          <span aria-hidden>·</span>
          <span>聚合 revision {state?.active_aggregate_revision ?? '—'}</span>
          <span className={cn('rounded-full px-2 py-0.5', state?.rebuild_status === 'ready' ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300' : 'bg-amber-500/10 text-amber-700 dark:text-amber-300')}>
            {state?.rebuild_status === 'ready' ? '已同步' : state?.rebuild_status === 'failed' ? '重建失败，实时解析仍生效' : '聚合重建中，实时解析已生效'}
          </span>
        </div>

        <div className="mb-5 flex gap-6 border-b border-border" role="tablist" aria-label="艺人身份管理">
          {([
            ['create', '创建或合并'],
            ['groups', `人工修改（${identity.overview.data?.groups.length ?? 0}）`],
          ] as const).map(([key, label]) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={tab === key}
              onClick={() => setTab(key)}
              className={cn('-mb-px border-b-2 pb-2.5 text-[13px] font-medium', tab === key ? 'border-accent-foreground text-foreground' : 'border-transparent text-muted-foreground')}
            >
              {label}
            </button>
          ))}
        </div>

        {tab === 'create' && (
          <div className="space-y-5">
            <div>
              <label htmlFor="artist-identity-search" className="mb-2 block text-xs font-semibold text-foreground">搜索本地艺人</label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input id="artist-identity-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="输入艺人名称，可分多次搜索并保留选择" className="pl-9" />
              </div>
              {search.trim() && (
                <div className="mt-2 grid gap-2 sm:grid-cols-2">
                  {identity.candidates.map((candidate) => (
                    <button key={candidate.artist_id} type="button" onClick={() => selectCandidate(candidate)} className="flex min-w-0 items-center gap-3 rounded-xl border border-border bg-background p-3 text-left transition hover:border-accent-foreground/40">
                      <ArtistAvatar candidate={candidate} name={candidate.artist_name} />
                      <span className="min-w-0 flex-1">
                        <span className="block break-words text-sm font-semibold text-foreground">{localizedName(candidate.artist_name)}</span>
                        <span className="block text-[11px] text-muted-foreground">raw #{candidate.artist_id} · {candidate.play_count.toLocaleString()} 次 · {candidate.first_play_date ?? '无播放'}—{candidate.last_play_date ?? '无播放'}</span>
                      </span>
                      {selected.some((item) => item.artist_id === candidate.artist_id) ? <Check className="size-4 text-accent-foreground" /> : <Plus className="size-4 text-muted-foreground" />}
                    </button>
                  ))}
                  {!identity.candidatesLoading && identity.candidates.length === 0 && <p className="text-xs text-muted-foreground">没有匹配的本地艺人。</p>}
                </div>
              )}
            </div>

            {selected.length > 0 && (
              <div className="space-y-3 rounded-xl border border-border bg-muted/20 p-4">
                <div className="flex items-center justify-between gap-3">
                  <h4 className="text-sm font-semibold">待合并成员（{selected.length}）</h4>
                  <span className="text-[11px] text-muted-foreground">选择 canonical 只决定身份主键；显示名可独立设置</span>
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  {selected.map((candidate) => (
                    <div key={candidate.artist_id} className={cn('flex min-w-0 items-center gap-3 rounded-lg border p-3', canonicalId === candidate.artist_id ? 'border-accent-foreground bg-accent-foreground/5' : 'border-border bg-background')}>
                      <button type="button" aria-label={`将 ${localizedName(candidate.artist_name)} 设为 canonical`} onClick={() => { setCanonicalId(candidate.artist_id); setDisplayName(candidate.canonical_display_name || candidate.artist_name) }} className="flex min-w-0 flex-1 items-center gap-3 text-left">
                        <ArtistAvatar candidate={candidate} name={candidate.artist_name} />
                        <span className="min-w-0">
                          <span className="block break-words text-sm font-medium">{localizedName(candidate.artist_name)}</span>
                          <span className="text-[11px] text-muted-foreground">raw #{candidate.artist_id}{canonicalId === candidate.artist_id ? ' · canonical' : ''}</span>
                        </span>
                      </button>
                      <button type="button" aria-label={`移除 ${localizedName(candidate.artist_name)}`} onClick={() => removeCandidate(candidate.artist_id)} className="rounded-full p-1 text-muted-foreground hover:bg-muted hover:text-foreground"><X className="size-4" /></button>
                    </div>
                  ))}
                </div>
                <label className="block text-xs font-semibold">最终显示名<Input value={displayName} onChange={(event) => setDisplayName(event.target.value)} className="mt-2" /></label>
                <Button type="button" variant="outline" disabled={!canPreview || identity.preview.isPending} onClick={() => draft && identity.preview.mutate(draft)}>
                  {identity.preview.isPending ? <Loader2 className="size-4 animate-spin" /> : <Link2 className="size-4" />}预览全局影响
                </Button>
              </div>
            )}

            {preview && (
              <div className={cn('space-y-3 rounded-xl border p-4', preview.blocked ? 'border-destructive/40 bg-destructive/5' : 'border-emerald-500/30 bg-emerald-500/5')}>
                <div className="flex items-center gap-2 text-sm font-semibold">{preview.blocked ? <AlertTriangle className="size-4 text-destructive" /> : <ShieldCheck className="size-4 text-emerald-600" />}{preview.blocked ? '发现需人工确认的身份冲突' : '预览通过，可确认写入'}</div>
                <p className="text-xs leading-relaxed text-muted-foreground">合并前共 {preview.combined_play_count_before_dedupe.toLocaleString()} 次；同一播放事件重复署名 {preview.duplicate_play_events.toLocaleString()} 条将在 canonical fan-out 后去重。共享稳定曲目 {preview.shared_stable_tracks.length} 首。</p>
                <div className="flex flex-wrap gap-1.5">{preview.affected_scopes.map((scope) => <span key={scope} className="rounded-full border border-border bg-background px-2 py-1 text-[11px]">{scope}</span>)}</div>
                {preview.blocked && <label className="flex items-start gap-2 text-xs"><input type="checkbox" checked={confirmConflict} onChange={(event) => setConfirmConflict(event.target.checked)} className="mt-0.5" /><span>我已核对不同的 provider ID，确认这些条目属于同一艺人。</span></label>}
                <Button type="button" disabled={identity.create.isPending || (preview.blocked && !confirmConflict)} onClick={() => void confirmCreate()}>
                  {identity.create.isPending && <Loader2 className="size-4 animate-spin" />}确认并全局应用
                </Button>
              </div>
            )}
            {(identity.preview.error || identity.create.error) && <p className="text-xs text-destructive">{mutationMessage(identity.preview.error || identity.create.error)}</p>}
          </div>
        )}

        {tab === 'groups' && (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">当前仍生效的人工身份合并；可直接调整成员、canonical 与显示名。</p>
            {(identity.overview.data?.groups ?? []).map((group) => (
              <IdentityGroupCard
                key={group.identity_id}
                group={group}
                revision={state?.current_revision ?? 0}
                eventId={identity.events.find((event) => event.identity_id === group.identity_id && event.action !== 'undo' && !undoneEventIds.has(event.event_id))?.event_id ?? null}
                onUpdate={identity.update.mutateAsync}
                onUndo={identity.undo.mutateAsync}
              />
            ))}
            {!identity.overview.isLoading && (identity.overview.data?.groups.length ?? 0) === 0 && <p className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">尚无已合并的艺人身份。</p>}
          </div>
        )}

    </section>
  )
}

function IdentityGroupCard({ group, revision, eventId, onUpdate, onUndo }: { group: ArtistIdentityGroup; revision: number; eventId: number | null; onUpdate: ReturnType<typeof useArtistIdentities>['update']['mutateAsync']; onUndo: ReturnType<typeof useArtistIdentities>['undo']['mutateAsync'] }) {
  useChineseTextVersion()
  const [displayName, setDisplayName] = useState(group.display_name)
  const [canonicalId, setCanonicalId] = useState(group.canonical_artist_id)
  const [error, setError] = useState('')
  const changed = displayName.trim() !== group.display_name || canonicalId !== group.canonical_artist_id
  const save = async (removeIds: number[] = []) => {
    setError('')
    try {
      await onUpdate({ identityId: group.identity_id, payload: { remove_ids: removeIds, canonical_artist_id: canonicalId, display_name: displayName, expected_revision: revision } })
    } catch (value) { setError(mutationMessage(value)) }
  }
  const undo = async () => {
    if (eventId == null || !window.confirm(`撤销“${localizedName(group.display_name)}”最近一次人工身份修改？`)) return
    try { await onUndo({ eventId, revision }) } catch (value) { setError(mutationMessage(value)) }
  }
  return (
    <div className="space-y-3 rounded-xl border border-border bg-muted/20 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"><div><h4 className="font-serif text-lg font-bold">{localizedName(group.display_name)}</h4><p className="text-[11px] text-muted-foreground">身份组 #{group.identity_id} · canonical raw #{group.canonical_artist_id}</p></div><span className="self-start rounded-full border border-border bg-background px-2 py-1 text-[11px]">{group.members.length} 个成员</span></div>
      <div className="grid gap-2 sm:grid-cols-2">{group.members.map((member) => <div key={member.artist_id} className={cn('flex min-w-0 items-center gap-3 rounded-lg border p-3', canonicalId === member.artist_id ? 'border-accent-foreground bg-accent-foreground/5' : 'border-border bg-background')}><button type="button" onClick={() => setCanonicalId(member.artist_id)} className="flex min-w-0 flex-1 items-center gap-3 text-left"><ArtistAvatar candidate={member} name={member.artist_name} /><span className="min-w-0"><span className="block break-words text-sm font-medium">{localizedName(member.artist_name)}</span><span className="text-[11px] text-muted-foreground">raw #{member.artist_id} · {canonicalId === member.artist_id ? 'canonical' : member.evidence_type}</span></span></button>{group.members.length > 1 && canonicalId !== member.artist_id && <button type="button" aria-label={`从身份组移除 ${localizedName(member.artist_name)}`} onClick={() => void save([member.artist_id])} className="rounded-full p-1 text-muted-foreground hover:bg-muted hover:text-destructive"><X className="size-4" /></button>}</div>)}</div>
      <div className="grid gap-3 sm:grid-cols-[1fr_auto_auto] sm:items-end"><label className="text-xs font-semibold">最终显示名<Input value={displayName} onChange={(event) => setDisplayName(event.target.value)} className="mt-1.5" /></label><Button type="button" size="sm" disabled={!changed || !displayName.trim()} onClick={() => void save()}>保存修改</Button><Button type="button" size="sm" variant="outline" disabled={eventId == null} onClick={() => void undo()}>撤销最近修改</Button></div>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}
