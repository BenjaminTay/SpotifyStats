/** Canonical query keys for TanStack Query, organized by domain. */

export const queryKeys = {
  dashboard: {
    all: ['dashboard'] as const,
    full: () => [...queryKeys.dashboard.all, 'full'] as const,
  },

  billboard: {
    all: ['billboard'] as const,
    data: (params: Record<string, unknown> = {}) => ['billboard', 'data', params] as const,
    weekly: (params: Record<string, unknown> = {}) => ['billboard', 'weekly', params] as const,
    records: (params: Record<string, unknown> = {}) => ['billboard', 'records', params] as const,
    powerScores: (params: Record<string, unknown> = {}) => ['billboard', 'power-scores', params] as const,
    summaries: (params: Record<string, unknown> = {}) => ['billboard', 'summaries', params] as const,
    allTime: (params: Record<string, unknown> = {}) => ['billboard', 'all-time', params] as const,
    entityLists: (params: Record<string, unknown> = {}) => ['billboard', 'entity-lists', params] as const,
    versus: (kind: string, params: Record<string, unknown>) => ['billboard', 'versus', kind, params] as const,
    releaseCycleCompare: (params: Record<string, unknown>) => ['billboard', 'release-cycle', 'compare', params] as const,
  },

  analysis: {
    all: ['analysis'] as const,
    overview: (filters: Record<string, unknown>) => ['analysis', 'overview', filters] as const,
    stats: (params: Record<string, unknown>) => ['analysis', 'stats', params] as const,
    charts: (params: Record<string, unknown>) => ['analysis', 'charts', params] as const,
    plays: (params: Record<string, unknown>, page: number) => ['analysis', 'plays', params, page] as const,
    timeline: (kind: string, params: Record<string, unknown>) => ['analysis', 'timeline', kind, params] as const,
    leaderboard: (params: Record<string, unknown>) => ['analysis', 'leaderboard', params] as const,
    listeningHours: (kind: string, params: Record<string, unknown>) => ['analysis', 'listening-hours', kind, params] as const,
    artistDeepDive: (name: string, params: Record<string, unknown>) => ['analysis', 'artist-deep-dive', name, params] as const,
  },

  settings: {
    all: ['settings'] as const,
    data: () => ['settings', 'data'] as const,
    llmProfiles: () => ['settings', 'llm-profiles'] as const,
    llmProfile: (profileId: number) => ['settings', 'llm-profile', profileId] as const,
    spotifyStatus: () => ['settings', 'spotify-status'] as const,
  },

  account: {
    all: ['account'] as const,
    summary: () => ['account', 'summary'] as const,
  },

  yearlyReview: {
    all: ['yearly-review'] as const,
    full: (year: number) => ['yearly-review', 'full', year] as const,
    availableYears: () => ['yearly-review', 'available-years'] as const,
    hubAvailableYears: () => ['yearly-review', 'hub-available-years'] as const,
    hub: () => ['yearly-review', 'hub'] as const,
  },

  music: {
    all: ['music'] as const,
    artistDetail: (artistName: string) => ['music', 'artist-detail', artistName] as const,
    trackDetail: (trackId: string) => ['music', 'track-detail', trackId] as const,
    albumDetail: (albumName: string, artistName: string) => ['music', 'album-detail', albumName, artistName] as const,
    trackEnrichment: (trackName: string, artistName: string) => ['music', 'track-enrichment', trackName, artistName] as const,
    albumEnrichment: (albumName: string, artistName: string) => ['music', 'album-enrichment', albumName, artistName] as const,
    artistEnrichment: (artistName: string) => ['music', 'artist-enrichment', artistName] as const,
    albumReleaseCycle: (albumName: string, artistName: string, params: Record<string, unknown>) => ['music', 'album-release-cycle', albumName, artistName, params] as const,
    artistReleaseCycle: (artistName: string, params: Record<string, unknown>) => ['music', 'artist-release-cycle', artistName, params] as const,
    entityStats: (kind: string, id: string, params: Record<string, unknown>) => ['music', 'entity-stats', kind, id, params] as const,
    entityPlays: (kind: string, id: string, params: Record<string, unknown>, page: number) => ['music', 'entity-plays', kind, id, params, page] as const,
  },

  library: {
    all: ['library'] as const,
    playlists: () => ['library', 'playlists'] as const,
    playlistTracks: (playlistId: number | string) => ['library', 'playlist-tracks', playlistId] as const,
    savedTracks: (params: Record<string, unknown>) => ['library', 'saved-tracks', params] as const,
  },

  versionMerge: {
    all: ['version-merge'] as const,
    groups: () => ['version-merge', 'groups'] as const,
    members: (groupId: number) => ['version-merge', 'members', groupId] as const,
    ungrouped: (artistName?: string) => ['version-merge', 'ungrouped', artistName ?? ''] as const,
    comparison: (aId: number, bId: number) => ['version-merge', 'comparison', aId, bId] as const,
    albumTypes: (ids: number[]) => ['version-merge', 'album-types', ids.join(',')] as const,
  },
} as const
