import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { DataImportSection } from '@/features/settings/components/DataImportSection'
import { GovernanceSnapshotNotice } from '@/features/settings/components/GovernanceSnapshotNotice'
import { useArtistLanguageCoverage } from '@/hooks/useArtistLanguageMetadata'
import { api } from '@/lib/api'

function wrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
}
afterEach(() => vi.restoreAllMocks())

it('does not request health or file preflight until the import panel is opened', async () => {
  const get = vi.spyOn(api, 'get').mockRejectedValue(new Error('治理检查尚未发布，请在本机重建'))
  render(<DataImportSection dbRecordCount={100} accountImported streamingJob={null} accountJob={null} onStreamingImport={vi.fn()} onAccountImport={vi.fn()} />, { wrapper: wrapper() })
  expect(get).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: /02 · 数据导入/ }))
  await waitFor(() => expect(get).toHaveBeenCalledTimes(1))
  expect(get).toHaveBeenCalledWith('/import/health')
  expect(await screen.findByText(/治理检查尚未发布/)).toBeVisible()
})

it('enables language coverage only while its panel is open', async () => {
  const get = vi.spyOn(api, 'get').mockResolvedValue({ unknown_pct: 100 })
  const filters = { min_ms: 30000, music_only: true, merge_enabled: true, dynamic_threshold: true }
  const { rerender, result } = renderHook(({ open }) => useArtistLanguageCoverage(filters, open), { initialProps: { open: false }, wrapper: wrapper() })
  expect(get).not.toHaveBeenCalled()
  rerender({ open: true })
  await waitFor(() => expect(result.current.isSuccess).toBe(true))
  expect(get).toHaveBeenCalledTimes(1)
})

it('dates the previous result and distinguishes a failed rebuild', () => {
  render(<GovernanceSnapshotNotice snapshot={{ status: 'warming', freshness: 'last_known_good', checked_at: '2026-09-20T00:00:00Z', checked_revision: 'old', build_status: 'failed' }} />)
  expect(screen.getByRole('status')).toHaveTextContent('本次检查构建失败')
  expect(screen.getByRole('status')).toHaveTextContent('检查时间：')
})
