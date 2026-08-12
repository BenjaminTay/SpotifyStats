/** Canonical query keys for TanStack Query, organized by domain. */

export const queryKeys = {
  dashboard: {
    all: ["dashboard"] as const,
    full: () => [...queryKeys.dashboard.all, "full"] as const,
  },

  billboard: {
    all: ["billboard"] as const,
    data: (params: Record<string, unknown> = {}) =>
      ["billboard", "data", params] as const,
    weekly: (params: Record<string, unknown> = {}) =>
      ["billboard", "weekly", params] as const,
    records: (params: Record<string, unknown> = {}) =>
      ["billboard", "records", params] as const,
    powerScores: (params: Record<string, unknown> = {}) =>
      ["billboard", "power-scores", params] as const,
    summaries: (params: Record<string, unknown> = {}) =>
      ["billboard", "summaries", params] as const,
    allTime: (params: Record<string, unknown> = {}) =>
      ["billboard", "all-time", params] as const,
    yearEnd: (params: Record<string, unknown> = {}) =>
      ["billboard", "year-end", params] as const,
    entityLists: (params: Record<string, unknown> = {}) =>
      ["billboard", "entity-lists", params] as const,
    versus: (kind: string, params: Record<string, unknown>) =>
      ["billboard", "versus", kind, params] as const,
    releaseCycleCompare: (params: Record<string, unknown>) =>
      ["billboard", "release-cycle", "compare", params] as const,
  },

  analysis: {
    all: ["analysis"] as const,
    overview: (filters: Record<string, unknown>) =>
      ["analysis", "overview", filters] as const,
    stats: (params: Record<string, unknown>) =>
      ["analysis", "stats", params] as const,
    charts: (params: Record<string, unknown>) =>
      ["analysis", "charts", params] as const,
    plays: (params: Record<string, unknown>, page: number) =>
      ["analysis", "plays", params, page] as const,
    timeline: (kind: string, params: Record<string, unknown>) =>
      ["analysis", "timeline", kind, params] as const,
    leaderboard: (params: Record<string, unknown>) =>
      ["analysis", "leaderboard", params] as const,
    listeningHours: (kind: string, params: Record<string, unknown>) =>
      ["analysis", "listening-hours", kind, params] as const,
    artistDeepDive: (name: string, params: Record<string, unknown>) =>
      ["analysis", "artist-deep-dive", name, params] as const,
    records: (params: Record<string, unknown>) =>
      ["analysis", "records", params] as const,
  },

  settings: {
    all: ["settings"] as const,
    data: () => ["settings", "data"] as const,
    llmProfiles: () => ["settings", "llm-profiles"] as const,
    llmProfile: (profileId: number) =>
      ["settings", "llm-profile", profileId] as const,
    spotifyStatus: () => ["settings", "spotify-status"] as const,
    artistIdentities: () => ["settings", "artist-identities"] as const,
    artistIdentityCandidates: (query: string) =>
      ["settings", "artist-identities", "candidates", query] as const,
    artistIdentityEvents: () =>
      ["settings", "artist-identities", "events"] as const,
    trackCredits: () =>
      ["settings", "music-metadata", "track-credits"] as const,
    trackCreditTracks: (query: string) =>
      ["settings", "music-metadata", "track-credits", "tracks", query] as const,
    trackCreditDetail: (trackId: number | null) =>
      [
        "settings",
        "music-metadata",
        "track-credits",
        "detail",
        trackId,
      ] as const,
    trackCreditArtistCandidates: (query: string) =>
      [
        "settings",
        "music-metadata",
        "track-credits",
        "artists",
        query,
      ] as const,
    trackCreditEvents: (trackId: number | null) =>
      [
        "settings",
        "music-metadata",
        "track-credits",
        "events",
        trackId,
      ] as const,
    trackCreditManualChanges: () =>
      ["settings", "music-metadata", "track-credits", "manual-changes"] as const,
  },

  dataImport: {
    all: ["data-import"] as const,
    health: () => ["data-import", "health"] as const,
    preflight: () => ["data-import", "preflight"] as const,
  },

  metadata: {
    all: ["metadata"] as const,
    artistGenres: {
      all: ["metadata", "artist-genres"] as const,
      coverage: (params: Record<string, unknown>) =>
        ["metadata", "artist-genres", "coverage", params] as const,
      taxonomy: (params: Record<string, unknown>) =>
        ["metadata", "artist-genres", "taxonomy", params] as const,
      axisGaps: (axis: string, params: Record<string, unknown>) =>
        ["metadata", "artist-genres", "axis-gaps", axis, params] as const,
      reviews: (status = "open", limit = 50) =>
        ["metadata", "artist-genres", "reviews", status, limit] as const,
    },
    artistLanguages: {
      all: ["metadata", "artist-languages"] as const,
      coverage: (params: Record<string, unknown>) =>
        ["metadata", "artist-languages", "coverage", params] as const,
      reviews: (status = "open", limit = 50) =>
        ["metadata", "artist-languages", "reviews", status, limit] as const,
    },
  },

  account: {
    all: ["account"] as const,
    summary: () => ["account", "summary"] as const,
    profile: () => ["account", "profile"] as const,
  },

  yearlyReview: {
    all: ["yearly-review"] as const,
    full: (year: number) => ["yearly-review", "full", year] as const,
    availableYears: () => ["yearly-review", "available-years"] as const,
    hubAvailableYears: () => ["yearly-review", "hub-available-years"] as const,
    hub: () => ["yearly-review", "hub"] as const,
    v2AvailableYears: () => ["yearly-review", "v2", "available-years"] as const,
    v2Report: (year: number, filterKey: string) =>
      ["yearly-review", "v2", "report", year, filterKey] as const,
    v2Records: (year: number, filterKey: string, page: number, pageSize: number) =>
      ["yearly-review", "v2", "records", year, filterKey, page, pageSize] as const,
  },

  music: {
    all: ["music"] as const,
    search: (params: Record<string, unknown>) =>
      ["music", "search", params] as const,
    artistDetail: (artistName: string, params: Record<string, unknown> = {}) =>
      ["music", "artist-detail", artistName, params] as const,
    artistRankings: (artistName: string, params: Record<string, unknown> = {}) =>
      ["music", "artist-rankings", artistName, params] as const,
    albumRankings: (
      albumName: string,
      artistName: string,
      params: Record<string, unknown> = {},
    ) => ["music", "album-rankings", albumName, artistName, params] as const,
    trackDetail: (
      trackId: string,
      mergeLevel?: number,
      params: Record<string, unknown> = {},
    ) => ["music", "track-detail", trackId, mergeLevel ?? 2, params] as const,
    albumDetail: (
      albumName: string,
      artistName: string,
      mergeLevel?: number,
      params: Record<string, unknown> = {},
    ) =>
      [
        "music",
        "album-detail",
        albumName,
        artistName,
        mergeLevel ?? 2,
        params,
      ] as const,
    trackEnrichment: (trackName: string, artistName: string) =>
      ["music", "track-enrichment", trackName, artistName] as const,
    trackLyrics: (trackId: string) =>
      ["music", "track-lyrics", trackId] as const,
    albumEnrichment: (albumName: string, artistName: string) =>
      ["music", "album-enrichment", albumName, artistName] as const,
    artistEnrichment: (artistName: string) =>
      ["music", "artist-enrichment", artistName] as const,
    albumReleaseCycle: (
      albumName: string,
      artistName: string,
      params: Record<string, unknown>,
    ) =>
      ["music", "album-release-cycle", albumName, artistName, params] as const,
    artistReleaseCycle: (artistName: string, params: Record<string, unknown>) =>
      ["music", "artist-release-cycle", artistName, params] as const,
    entityStats: (kind: string, id: string, params: Record<string, unknown>) =>
      ["music", "entity-stats", kind, id, params] as const,
    entityPlays: (
      kind: string,
      id: string,
      params: Record<string, unknown>,
      page: number,
    ) => ["music", "entity-plays", kind, id, params, page] as const,
  },

  library: {
    all: ["library"] as const,
    playlists: () => ["library", "playlists"] as const,
    playlistTracks: (playlistId: number | string) =>
      ["library", "playlist-tracks", playlistId] as const,
    savedTracks: (params: Record<string, unknown>) =>
      ["library", "saved-tracks", params] as const,
  },

  community: {
    all: ["community"] as const,
    feed: (filters: Record<string, unknown> = {}) =>
      ["community", "feed", filters] as const,
    trending: (filters: Record<string, unknown> = {}) =>
      ["community", "trending", filters] as const,
    post: (postId: string, filters: Record<string, unknown> = {}) =>
      ["community", "post", postId, filters] as const,
  },

  aiInsights: {
    all: ["ai-insights"] as const,
    weeklyDigest: (weekStart: string, weekEnd: string) =>
      ["ai-insights", "weekly-digest", weekStart, weekEnd] as const,
    monthlyPersonality: (month: string, year: number) =>
      ["ai-insights", "monthly-personality", month, year] as const,
    yearlyStory: (year: number) =>
      ["ai-insights", "yearly-story", year] as const,
    suggestedQuestions: (context?: string) =>
      ["ai-insights", "suggested-questions", context ?? ""] as const,
    chat: {
      all: ["ai-insights", "chat"] as const,
      sessions: () => ["ai-insights", "chat", "sessions"] as const,
      session: (sessionId: number) =>
        ["ai-insights", "chat", "session", sessionId] as const,
    },
  },

  aiTasks: {
    all: ["ai-tasks"] as const,
    task: (taskId: string) => ["ai-tasks", "task", taskId] as const,
    events: (taskId: string) => ["ai-tasks", "events", taskId] as const,
  },

  versionMerge: {
    all: ["version-merge"] as const,
    groups: () => ["version-merge", "groups"] as const,
    members: (groupId: number) =>
      ["version-merge", "members", groupId] as const,
    ungrouped: (artistName?: string) =>
      ["version-merge", "ungrouped", artistName ?? ""] as const,
    comparison: (aId: number, bId: number) =>
      ["version-merge", "comparison", aId, bId] as const,
    albumTypes: (ids: number[]) =>
      ["version-merge", "album-types", ids.join(",")] as const,
    collaborationCandidates: () =>
      ["version-merge", "collaboration-candidates"] as const,
  },
} as const;
