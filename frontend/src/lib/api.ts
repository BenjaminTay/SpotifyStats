import { apiClient } from '@/api/client'

/** @deprecated Import from `@/api/client` or `@/api/errors` instead. Kept for backwards compatibility. */
export const api = apiClient

export type { DashboardSummary, DashboardFullResponse, MonthlyTrendPoint, PlatformDist, TopTrack, DowDist, RandomTrack, AccountKpi } from '@/types/dashboard'
export type { AnalysisOverviewResponse, AnalysisFilters, AnalysisTimeRange, AnalysisPeriod, AnalysisMetric, LeaderboardEntity, AnalysisStatsResponse, AnalysisChartsResponse, EntityStatsResponse } from '@/types/analysis'
export type { BillboardDataResponse, BillboardWeeklyResponse, BillboardRecordsResponse, BillboardPowerScoresResponse, BillboardSummariesResponse, BillboardAllTimeResponse, BillboardYearEndResponse, BillboardYearEndMeta, BillboardYearEndRow, BillboardYearEndTrackRow, BillboardYearEndAlbumRow, BillboardYearEndArtistRow, BillboardYearEndHonors, BillboardRecords, BillboardMeta, WeeklyTrackEntry, WeeklyAlbumEntry, WeeklyArtistEntry, TrackSummary, AlbumTrackCounts, ArtistTrackCounts, PowerScoreEntry, AlbumPowerScoreEntry, ArtistPowerScoreEntry, TrackDetailResponse, ArtistDetailResponse, AlbumDetailResponse, AlbumEnrichmentResponse, ArtistEnrichmentResponse, TrackEnrichmentResponse, ReleaseCycleAlbumDetailResponse, ReleaseCycleArtistOverviewResponse, StructuredArtist, StructuredAlbum, KeyFact, StatItem, CareerEvent, Achievement, ChartEntry, VersusResponse, VersusEntityData, VersusRankPoint, EntityListsResponse, EntityListItem, ReleaseCycleCompareResponse, ReleaseCycleCompareItem } from '@/types/billboard'
export type { SettingsData, SettingsUpdatePayload, ImportJob, ReleaseGroup, GroupMember, UngroupedAlbum, DetectionResult, DetectionMember, TrackGroupCandidate, TrackGroupConfirmResult, AlbumRelationConfirmResult, TrackComparison, TrackRow, RebuildResult, VersionMergeScope, TrackGroupScope, LLMProfile, LLMProfileDetail, LLMProfileCreatePayload, LLMProfileUpdatePayload, LLMProfileCreateResult } from '@/types/settings'
export type {
  AccountSummary,
  CollectionInsights,
  CollectionPersonality,
  CollectionOverview,
  FirstSaveStory,
  SaveLifecycle,
  SavePlayChemistry,
  ChemistryType,
  FlipSideTrack,
  CoSavedPair,
  TopSavedArtist,
  SearchData,
  ArtistTiersData,
  MarqueeData,
  PodcastData,
  VideoData,
  ProfileData,
  WrappedHubData,
} from '@/types/account'
