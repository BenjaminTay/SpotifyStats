import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { DataImportWorkspace } from '@/features/settings/components/DataImportWorkspace'
import { importRunNeedsPolling } from '@/hooks/useDataImport'

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
      result: { quality_issue_count: 2 },
      plan: null,
      stages: [
        { stage: 'search_snapshot', status: 'failed', freshness: 'unavailable', retryable: true },
        { stage: 'cover_download', status: 'running', freshness: 'warming' },
      ],
      started_at: '2026-09-21T00:00:00Z',
      completed_at: null,
    },
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
})
