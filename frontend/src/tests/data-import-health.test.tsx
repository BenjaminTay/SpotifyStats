import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { DataHealthSummary } from '@/features/settings/components/DataHealthSummary'
import { ImportPreflightPanel } from '@/features/settings/components/ImportPreflightPanel'
import type { ImportHealthResponse, ImportPreflightResponse } from '@/types/data-import'

const health: ImportHealthResponse = {
  status: 'partial',
  checked_at: '2026-08-05T00:00:00Z',
  database: {
    play_count: 91286,
    audio_play_count: 90329,
    video_play_count: 957,
    valid_audio_play_count: 65072,
    active_day_count: 1471,
    first_play_date: '2022-07-01',
    last_play_date: '2026-07-24',
    null_track_audio_count: 237,
    negative_duration_count: 0,
    sqlite_integrity: 'ok',
    foreign_key_issue_count: 7831,
    foreign_key_issue_breakdown: { 'tracks -> artists': 3098 },
    artist_count: 1189,
    album_count: 5316,
    track_count: 12362,
  },
  relationships: {
    orphan_play_track_count: 0,
    orphan_play_album_count: 0,
    tracks_without_primary_credit_count: 0,
    orphan_track_artist_track_count: 0,
    orphan_track_artist_artist_count: 3098,
  },
  metadata: {
    since_date: '2026-04-25',
    recent_plays: 4796,
    recent_tracks: 1799,
    recent_source_albums: 688,
    unresolved_recent_tracks: 0,
    unresolved_recent_albums: 17,
  },
  derived: {
    weekly_track_rows: 36725,
    weekly_album_rows: 16758,
    weekly_artist_rows: 9969,
    album_project_count: 1741,
    album_projects_ready: true,
    billboard_aggregates_ready: true,
    rebuild_pending: false,
    stale_revision_count: 0,
    artist_identity: {},
    track_credits: {},
  },
  issues: [
    {
      code: 'foreign_key_orphans',
      category: 'relationship',
      severity: 'medium',
      title: '数据库存在外键关系残留',
      count: 7831,
      affected_play_count: 0,
      impact: '当前未发现播放记录使用这些残留实体。',
      recommended_action: '先导出关系明细和样本。',
      evidence: { 'tracks -> artists': 3098 },
    },
  ],
  blockers: [],
  warnings: ['发现 7831 个数据库外键关系问题'],
}

const preflight: ImportPreflightResponse = {
  status: 'partial',
  streaming_files: [
    {
      source_key: 'streaming_audio',
      label: '音频播放历史',
      file_name: 'Streaming_History_Audio_000.json',
      required: true,
      status: 'ok',
      size_bytes: 100,
      record_count: 4,
      duplicate_record_count: 0,
      first_date: '2026-01-01',
      last_date: '2026-01-02',
      errors: [],
      warnings: [],
    },
  ],
  account_files: [],
  duplicate_file_groups: [],
  date_overlaps: [],
  blockers: [],
  warnings: [],
}

const incrementalPreflight: ImportPreflightResponse = {
  ...preflight,
  account_identity_status: 'matched',
  fingerprint_baseline_status: 'ready',
  detected_relation: 'snapshot_superset',
  requested_mode: 'auto',
  requires_confirmation: false,
  existing_record_count: 91286,
  incoming_record_count: 93120,
  unchanged_record_count: 91286,
  added_record_count: 1834,
  removed_record_count: 0,
  existing_date_range: { first_date: '2022-07-01', last_date: '2026-07-24' },
  incoming_date_range: { first_date: '2022-07-01', last_date: '2026-08-21' },
  affected_weeks_count: 2,
  affected_years_count: 1,
  planned_actions: ['追加播放事实', '更新受影响榜单周'],
  estimated_strategy: 'incremental',
}

describe('data import health UI', () => {
  it('shows health metrics and read-only warnings', () => {
    render(<DataHealthSummary health={health} loading={false} error={null} onRefresh={vi.fn()} />)

    expect(screen.getByText('部分完成')).toBeInTheDocument()
    expect(screen.getByText('91,286')).toBeInTheDocument()
    expect(screen.getByText('2022-07-01 → 2026-07-24')).toBeInTheDocument()
    expect(screen.getByText(/数据库存在外键关系残留：7,831/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '查看问题详情（1）' }))
    expect(screen.getByText('当前未发现播放记录使用这些残留实体。')).toBeInTheDocument()
    expect(screen.getByText('当前播放影响：0 条')).toBeInTheDocument()
  })

  it('keeps preflight as an explicit read-only action', () => {
    const onRun = vi.fn()
    render(<ImportPreflightPanel preflight={preflight} loading={false} error={null} onRun={onRun} />)

    expect(screen.getByText('只读取本地 Spotify 数据包，不会修改数据库。')).toBeInTheDocument()
    expect(screen.getByText('已发现 · 4 条')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '开始检查' }))
    expect(onRun).toHaveBeenCalledOnce()
  })

  it('shows a natural-language incremental import plan', () => {
    render(<ImportPreflightPanel preflight={incrementalPreflight} loading={false} error={null} onRun={vi.fn()} />)

    expect(screen.getByText('播放事实增量')).toBeInTheDocument()
    expect(screen.getByText('检测到当前数据基础上的完整追加：新增 1,834 条记录，变化涉及 2 个榜单周和 1 个年度范围。')).toBeInTheDocument()
    expect(screen.getByText('当前仅播放事实增量写入；榜单、搜索和其他派生数据仍执行完整维护。')).toBeInTheDocument()
    expect(screen.getByText('当前 / 输入：91,286 / 93,120 条')).toBeInTheDocument()
    expect(screen.getByText('当前范围：2022-07-01 → 2026-07-24')).toBeInTheDocument()
    expect(screen.getByText('· 更新受影响榜单周')).toBeInTheDocument()
  })

  it('asks for confirmation when the input relationship is ambiguous', () => {
    render(
      <ImportPreflightPanel
        preflight={{
          ...incrementalPreflight,
          detected_relation: 'ambiguous',
          requires_confirmation: true,
          estimated_strategy: 'full',
        }}
        loading={false}
        error={null}
        onRun={vi.fn()}
      />,
    )

    expect(screen.getByText('需要确认')).toBeInTheDocument()
    expect(screen.getByText('无法证明输入包是完整快照还是尾部增量，需要确认导入方式。')).toBeInTheDocument()
  })
})
