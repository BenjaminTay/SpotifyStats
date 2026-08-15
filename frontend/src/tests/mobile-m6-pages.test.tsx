import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ThemeProvider } from '@/hooks/useTheme'
import {
  MobileCommunityFilterBar,
  MobileCommunityFilters,
} from '@/features/mobile/community/MobileCommunityFilters'
import { ALL_PERIOD, PERIODS } from '@/features/community/TimeFilter'
import { MobileSettingsExperience } from '@/features/mobile/settings/MobileSettingsExperience'
import type { SettingsData } from '@/types/settings'

const settings: SettingsData = {
  spotify_profile: null,
  min_ms: 30_000,
  music_only: true,
  merge_enabled: true,
  max_merge_gap_minutes: 5,
  bb_top_n: 30,
  bb_album_top_n: 20,
  bb_artist_top_n: 20,
  bb_week_start_dow: 4,
  bb_week_start_hour: 0,
  include_compilations: false,
  db_record_count: 91_286,
  account_data_imported: true,
  spotify_connected: true,
  llm_enabled: true,
  llm_provider: 'openai',
  llm_model: 'gpt-5',
  has_llm_key: true,
  llm_active_profile_id: 2,
  llm_active_profile_name: '主配置',
  rebuild_pending: false,
}

beforeEach(() => {
  localStorage.clear()
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query.includes('max-width'),
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  })
})

function renderSettings(initialEntry = '/settings', rebuildPending = false) {
  const onUpdate = vi.fn().mockResolvedValue(undefined)
  const onRequiresRebuild = vi.fn()
  const onApplyProfile = vi.fn().mockResolvedValue({ status: 'ok', profile_id: 3 })
  render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/settings" element={(
            <MobileSettingsExperience
              settings={settings}
              rebuildPending={rebuildPending}
              chineseStyle="original"
              onChangeChineseStyle={vi.fn()}
              onUpdate={onUpdate}
              onRequiresRebuild={onRequiresRebuild}
              onSpotifyConnect={vi.fn().mockResolvedValue({ auth_url: '/oauth', state: 's' })}
              onSpotifyDisconnect={vi.fn().mockResolvedValue(undefined)}
              onSpotifySync={vi.fn().mockResolvedValue({ success: true, new_dates: 2 })}
              onFetchProfiles={vi.fn().mockResolvedValue([
                { id: 2, profile_name: '主配置', llm_provider: 'openai', llm_model: 'gpt-5', created_at: null, updated_at: null },
                { id: 3, profile_name: '备用配置', llm_provider: 'openai', llm_model: 'gpt-5-mini', created_at: null, updated_at: null },
              ])}
              onApplyProfile={onApplyProfile}
            />
          )} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  )
  return { onUpdate, onRequiresRebuild, onApplyProfile }
}

describe('M6 mobile pages', () => {
  it('opens community filters in a sheet and updates the selected period', async () => {
    const user = userEvent.setup()
    const onPeriodChange = vi.fn()
    const onSearchChange = vi.fn()
    const { rerender } = render(
      <>
        <MobileCommunityFilterBar search="" period={ALL_PERIOD} onOpen={vi.fn()} />
        <MobileCommunityFilters open onOpenChange={vi.fn()} search="" onSearchChange={onSearchChange} period={ALL_PERIOD} onPeriodChange={onPeriodChange} />
      </>,
    )
    const dialog = screen.getByRole('dialog', { name: '查找与筛选' })
    await user.type(within(dialog).getByRole('textbox', { name: '搜索社区' }), 'Taylor')
    expect(onSearchChange).toHaveBeenCalled()
    await user.click(within(dialog).getByRole('radio', { name: '2025' }))
    expect(onPeriodChange).toHaveBeenCalledWith(PERIODS.find((period) => period.label === '2025'))
    rerender(<MobileCommunityFilterBar search="Taylor" period={PERIODS[1]} onOpen={vi.fn()} />)
    expect(screen.getByRole('button', { name: '打开社区搜索与时间筛选' })).toHaveTextContent('Taylor')
  })

  it('shows settings categories first and exposes only lightweight playback controls', async () => {
    const user = userEvent.setup()
    const { onUpdate, onRequiresRebuild } = renderSettings()
    expect(screen.getByRole('heading', { name: '设置' })).toBeInTheDocument()
    expect(screen.queryByText('日常参数可直接调整，高级数据治理会引导到电脑端。')).not.toBeInTheDocument()
    expect(screen.queryByText('音乐源数据管理')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /播放统计/ }))
    expect(screen.getByRole('heading', { name: '播放统计' })).toBeInTheDocument()
    await user.click(screen.getByRole('switch', { name: '仅统计音乐' }))
    expect(onUpdate).toHaveBeenCalledWith({ music_only: false })
    expect(onRequiresRebuild).toHaveBeenCalled()
  })

  it('explains that pending rebuilds can leave mobile statistics stale', async () => {
    const user = userEvent.setup()
    renderSettings('/settings', true)
    expect(screen.getByText('等待重建 · 统计可能不是最新')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /数据状态/ }))
    expect(screen.getByText(/当前页面的聚合统计可能尚未反映最新参数/)).toBeInTheDocument()
  })

  it('turns metadata deep links into a target summary and preserves the return route', () => {
    renderSettings('/settings?metadata=track-credits&track_id=4551&return_to=%2Fmusic%2Ftracks%2F4551')
    expect(screen.getByRole('heading', { name: '高级数据管理' })).toBeInTheDocument()
    expect(screen.getByText(/曲目署名 · Track 4551/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /返回原页面/ })).toHaveAttribute('href', '/music/tracks/4551')
    expect(screen.getAllByText('在电脑上管理')).toHaveLength(4)
  })

  it('loads and switches the active AI profile without exposing credentials', async () => {
    const user = userEvent.setup()
    const { onApplyProfile } = renderSettings('/settings?panel=ai')
    const select = await screen.findByRole('combobox', { name: '当前 AI 配置档案' })
    await screen.findByRole('option', { name: '备用配置' })
    await user.selectOptions(select, '3')
    expect(onApplyProfile).toHaveBeenCalledWith(3)
    expect(await screen.findByText('当前配置档案已切换')).toBeInTheDocument()
    expect(screen.getByText(/新增档案、修改模型地址或 API 密钥/)).toBeInTheDocument()
  })
})
