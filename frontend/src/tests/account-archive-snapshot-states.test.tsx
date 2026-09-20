import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SnapshotUnavailableError } from '@/api/errors'
import { api } from '@/lib/api'
import { AccountArchiveDesktopRoute } from '@/features/account-archive/route/AccountArchiveDesktopRoute'
import { AccountArchivePhoneRoute } from '@/features/account-archive/route/AccountArchivePhoneRoute'

afterEach(() => vi.restoreAllMocks())
describe('Archive unpublished and failed reads', () => {
  it.each([false, true])('offers local rebuild guidance without an empty archive (phone=%s)', async (phone) => {
    vi.spyOn(api, 'get').mockRejectedValue(new SnapshotUnavailableError({ error: 'snapshot_unavailable', status: 'unavailable', family: 'account_archive', message: 'unavailable' }))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><MemoryRouter>{phone ? <AccountArchivePhoneRoute /> : <AccountArchiveDesktopRoute />}</MemoryRouter></QueryClientProvider>)
    await screen.findByText('音乐档案数据正在准备，请稍后重新读取。')
    expect(screen.getByRole('button', { name: '重新读取' })).toBeInTheDocument()
    expect(screen.queryByText('档案柜还是空的')).not.toBeInTheDocument()
  })
  it('keeps failed local build details out of the user-facing archive', async () => {
    vi.spyOn(api, 'get').mockRejectedValue(new SnapshotUnavailableError({ error: 'snapshot_unavailable', status: 'unavailable', family: 'account_archive', message: '音乐档案构建失败，请检查本地重建任务后重新读取。' }))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><MemoryRouter><AccountArchiveDesktopRoute /></MemoryRouter></QueryClientProvider>)
    await screen.findByText('音乐档案数据正在准备，请稍后重新读取。')
    expect(screen.queryByText(/构建失败|重建任务/)).not.toBeInTheDocument()
  })
})
