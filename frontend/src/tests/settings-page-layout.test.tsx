import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { SettingsPage } from '@/pages/SettingsPage'

const { useSettingsMock } = vi.hoisted(() => ({
  useSettingsMock: vi.fn(),
}))

vi.mock('@/hooks/useSettings', () => ({
  useSettings: useSettingsMock,
}))

vi.mock('@/features/settings/components/SettingsOverview', () => ({
  SettingsOverview: () => <div data-testid="settings-overview">SettingsOverview</div>,
}))

vi.mock('@/features/settings/components/RebuildNotice', () => ({
  RebuildNotice: () => <div data-testid="rebuild-notice">RebuildNotice</div>,
}))

vi.mock('@/features/settings/components/SpotifyConnectionSection', () => ({
  SpotifyConnectionSection: () => <div data-testid="spotify-connection-section">SpotifyConnectionSection</div>,
}))

vi.mock('@/features/settings/components/DataImportSection', () => ({
  DataImportSection: () => <div data-testid="data-import-section">DataImportSection</div>,
}))

vi.mock('@/features/settings/components/DataFilteringSection', () => ({
  DataFilteringSection: () => <div data-testid="data-filtering-section">DataFilteringSection</div>,
}))

vi.mock('@/features/settings/components/BillboardParamsSection', () => ({
  BillboardParamsSection: () => <div data-testid="billboard-params-section">BillboardParamsSection</div>,
}))

vi.mock('@/features/settings/components/GenreDataHealthSection', () => ({
  GenreDataHealthSection: () => <div data-testid="genre-data-health-section">GenreDataHealthSection</div>,
}))

vi.mock('@/features/settings/components/VersionMergeSection', () => ({
  VersionMergeSection: () => <div data-testid="version-merge-section">VersionMergeSection</div>,
}))

vi.mock('@/features/settings/components/LLMTranslationSection', () => ({
  LLMTranslationSection: () => <div data-testid="llm-translation-section">LLMTranslationSection</div>,
}))

function mockLoadedSettings() {
  useSettingsMock.mockReturnValue({
    settings: {
      spotify_profile: null,
      min_ms: 30000,
      music_only: true,
      merge_enabled: true,
      bb_top_n: 30,
      bb_album_top_n: 20,
      bb_artist_top_n: 20,
      bb_week_start_dow: 4,
      bb_week_start_hour: 0,
      include_compilations: false,
      db_record_count: 1200,
      account_data_imported: true,
      spotify_connected: true,
      llm_enabled: true,
      llm_provider: 'openai',
      llm_model: 'gpt-4o-mini',
      has_llm_key: true,
      llm_active_profile_id: 1,
      llm_active_profile_name: 'OpenAI 主配置',
      rebuild_pending: false,
    },
    loading: false,
    error: null,
    refetch: vi.fn(),
    updateSettings: vi.fn(),
    clearTranslationCache: vi.fn(),
    rebuildAgg: vi.fn(),
    startStreamingImport: vi.fn(),
    startAccountImport: vi.fn(),
    streamingJob: null,
    accountJob: null,
    spotifyConnect: vi.fn(),
    spotifyDisconnect: vi.fn(),
    spotifySync: vi.fn(),
    fetchProfiles: vi.fn(),
    applyProfile: vi.fn(),
    createProfile: vi.fn(),
    deleteProfile: vi.fn(),
  })
}

describe('SettingsPage layout', () => {
  it('keeps the original flat settings sequence and inserts genre health before LLM settings', async () => {
    mockLoadedSettings()

    render(<SettingsPage />)

    await screen.findByTestId('version-merge-section')
    await screen.findByTestId('llm-translation-section')

    const orderedSections = [
      screen.getByTestId('settings-overview'),
      screen.getByTestId('rebuild-notice'),
      screen.getByTestId('spotify-connection-section'),
      screen.getByTestId('data-import-section'),
      screen.getByTestId('data-filtering-section'),
      screen.getByTestId('billboard-params-section'),
      screen.getByTestId('version-merge-section'),
      screen.getByTestId('genre-data-health-section'),
      screen.getByTestId('llm-translation-section'),
    ]

    orderedSections.slice(0, -1).forEach((section, index) => {
      expect(section.compareDocumentPosition(orderedSections[index + 1])).toBe(
        Node.DOCUMENT_POSITION_FOLLOWING,
      )
    })
    expect(screen.queryByRole('region', { name: '状态与导入' })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: '统计口径' })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: '元数据与 AI' })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: '高级维护' })).not.toBeInTheDocument()
  })
})
