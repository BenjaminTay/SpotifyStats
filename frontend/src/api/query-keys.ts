/** Canonical query keys for TanStack Query, organized by domain. */

export const queryKeys = {
  dashboard: {
    all: ['dashboard'] as const,
    full: () => [...queryKeys.dashboard.all, 'full'] as const,
  },

  billboard: {
    all: ['billboard'] as const,
    data: (params: Record<string, unknown>) => ['billboard', 'data', params] as const,
    weekly: (params: Record<string, unknown>) => ['billboard', 'weekly', params] as const,
    records: (params: Record<string, unknown>) => ['billboard', 'records', params] as const,
    powerScores: (params: Record<string, unknown>) => ['billboard', 'power-scores', params] as const,
    summaries: (params: Record<string, unknown>) => ['billboard', 'summaries', params] as const,
    allTime: (params: Record<string, unknown>) => ['billboard', 'all-time', params] as const,
  },

  analysis: {
    all: ['analysis'] as const,
    overview: (filters: Record<string, unknown>) => ['analysis', 'overview', filters] as const,
    plays: (params: Record<string, unknown>, page: number) => ['analysis', 'plays', params, page] as const,
  },

  settings: {
    all: ['settings'] as const,
    data: () => ['settings', 'data'] as const,
    llmProfiles: () => ['settings', 'llm-profiles'] as const,
  },

  account: {
    all: ['account'] as const,
    summary: () => ['account', 'summary'] as const,
  },

  yearlyReview: {
    all: ['yearly-review'] as const,
    full: (year: number) => ['yearly-review', 'full', year] as const,
  },

  music: {
    all: ['music'] as const,
    artistDetail: (artistName: string) => ['music', 'artist-detail', artistName] as const,
    trackDetail: (trackId: string) => ['music', 'track-detail', trackId] as const,
    albumDetail: (albumName: string, artistName: string) => ['music', 'album-detail', albumName, artistName] as const,
    entityStats: (kind: string, id: string, params: Record<string, unknown>) => ['music', 'entity-stats', kind, id, params] as const,
    entityPlays: (kind: string, id: string, params: Record<string, unknown>, page: number) => ['music', 'entity-plays', kind, id, params, page] as const,
  },
} as const
