import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { DataImportWorkspace } from '@/features/settings/components/DataImportWorkspace'
import { importRunNeedsPolling } from '@/hooks/useDataImport'
import type { ImportRunDetail } from '@/types/data-import'

const useDataImportMock = vi.hoisted(() => vi.fn())

vi.mock('@/hooks/useDataImport', async (loadOriginal) => {
  const original = await loadOriginal<typeof import('@/hooks/useDataImport')>()
  return { ...original, useDataImport: useDataImportMock }
})

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <MemoryRouter><QueryClientProvider client={client}>{children}</QueryClientProvider></MemoryRouter>
}

function hookResult() {
  return {
    latestRun: null,
    run: {
      run_id: 'run-1',
      batch_id: 'batch-1',
      status: 'blocked',
      publication_state: 'facts_committed',
      progress_pct: 1,
      message: '播放事实已提交，统计仍需处理',
      error_code: 'provider_unavailable',
      retryable: true,
      report_status: 'ready',
      report_error_code: null,
      result: { quality_issue_count: 2 },
      plan: null,
      stages: [
        { stage: 'search_snapshot', status: 'failed', freshness: 'unavailable', retryable: true },
        { stage: 'cover_download', status: 'running', freshness: 'warming' },
      ],
      started_at: '2026-09-21T00:00:00Z',
      completed_at: null,
    } as ImportRunDetail,
    report: null,
    preflight: null,
    historyRuns: [],
    latestLoading: false,
    runLoading: false,
    preflightLoading: false,
    historyLoading: false,
    error: null,
    refetchRun: vi.fn(),
    refetchPreflight: vi.fn(),
    fetchNextHistoryPage: vi.fn(),
    hasNextHistoryPage: false,
    isFetchingNextHistoryPage: false,
    createBatch: vi.fn(),
    creatingBatch: false,
    uploadFile: vi.fn(),
    uploadingFile: false,
    finalizeBatch: vi.fn(),
    finalizingBatch: false,
    executeRun: vi.fn(),
    executingRun: false,
    retryStage: vi.fn(),
    retryingStage: false,
    recheckRun: vi.fn(),
    recheckingRun: false,
    startAccountImport: vi.fn(),
    accountImporting: false,
    accountJob: null,
  }
}

describe('data import workspace', () => {
  it('polls only non-terminal persistent runs', () => {
    expect(importRunNeedsPolling({ status: 'running' } as never)).toBe(true)
    expect(importRunNeedsPolling({ status: 'blocked' } as never)).toBe(false)
    expect(importRunNeedsPolling(null)).toBe(false)
  })

  it('keeps facts, statistics, quality and covers as separate outcomes on phone', () => {
    useDataImportMock.mockReturnValue(hookResult())
    render(<DataImportWorkspace presentation="phone" dbRecordCount={94760} accountImported />, { wrapper })

    expect(screen.getByText('播放事实已提交')).toBeVisible()
    expect(screen.getByText('部分统计不可用')).toBeVisible()
    expect(screen.getByText('2 项需要查看')).toBeVisible()
    expect(screen.getByText('封面补充任务')).toBeVisible()
    expect(screen.getByText('暂无可用结果，不能以 0 或旧状态代替')).toBeVisible()
    expect(screen.getByLabelText('导入步骤').closest('[data-import-presentation]')).toHaveAttribute('data-import-presentation', 'phone')
  })

  it('does not describe a no-op run as a facts update or rebuild', () => {
    const value = hookResult()
    value.run = {
      ...value.run,
      status: 'succeeded',
      publication_state: 'ready',
      message: '输入数据未变化，跳过导入',
      retryable: false,
      result: { executed_strategy: 'noop', noop: true },
      stages: [],
      completed_at: '2026-09-21T00:01:00Z',
    }
    useDataImportMock.mockReturnValue(value)

    render(<DataImportWorkspace presentation="desktop" dbRecordCount={94760} accountImported />, { wrapper })

    expect(screen.getByText('数据未变化')).toBeVisible()
    expect(screen.getByText('播放事实保持不变')).toBeVisible()
    expect(screen.getByText('无需重建')).toBeVisible()
    expect(screen.queryByText('播放事实已提交')).not.toBeInTheDocument()
  })

  it('clears the previous plan and binds upload/finalize to the newly created batch', async () => {
    const createBatch = vi.fn().mockResolvedValue({ batch_id: 'batch-new' })
    const uploadFile = vi.fn().mockResolvedValue({ batch_id: 'batch-new' })
    const finalizeBatch = vi.fn().mockResolvedValue({ batch_id: 'batch-new' })
    const value = {
      ...hookResult(),
      run: null,
      preflight: {
        status: 'healthy',
        streaming_files: [],
        account_files: [],
        duplicate_file_groups: [],
        date_overlaps: [],
        blockers: [],
        warnings: [],
        confirmation_token: 'old-token',
      },
      createBatch,
      uploadFile,
      finalizeBatch,
    }
    useDataImportMock.mockReturnValue(value)
    render(<DataImportWorkspace presentation="desktop" dbRecordCount={94760} accountImported />, { wrapper })

    const file = new File(['[]'], 'Streaming_History_Audio_2026.json', { type: 'application/json' })
    fireEvent.change(screen.getByLabelText(/选择 Spotify Extended Streaming History JSON/), {
      target: { files: [file] },
    })
    fireEvent.click(screen.getByRole('button', { name: '接收并检查' }))

    await waitFor(() => expect(uploadFile).toHaveBeenCalledWith({
      batchId: 'batch-new',
      file,
      sourceType: 'audio',
    }))
    expect(finalizeBatch).toHaveBeenCalledWith('batch-new')
    expect(useDataImportMock.mock.calls.some(([options]) => options.batchId === null)).toBe(true)
    await waitFor(() => expect(useDataImportMock.mock.calls.at(-1)?.[0].batchId).toBe('batch-new'))
  })
})
