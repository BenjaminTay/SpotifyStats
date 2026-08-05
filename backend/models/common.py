"""Common Pydantic models shared across API endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FilterParams(BaseModel):
    """Standard play-data filter parameters (used as query params)."""

    min_ms: int = Field(default=30000, ge=0, description="最短播放时长 (毫秒)")
    music_only: bool = Field(default=True, description="仅音乐 (排除播客/有声书)")
    merge_enabled: bool = Field(default=True, description="合并连续同曲目播放")


class BillboardConfig(BaseModel):
    """Billboard chart configuration."""

    top_n: int = Field(default=30, ge=5, le=100, alias="bb_top_n")
    album_top_n: int = Field(default=20, ge=5, le=100, alias="bb_album_top_n")
    artist_top_n: int = Field(default=20, ge=5, le=100, alias="bb_artist_top_n")
    week_start_dow: int = Field(default=4, ge=0, le=6, alias="bb_week_start_dow")
    week_start_hour: int = Field(default=0, ge=0, le=23, alias="bb_week_start_hour")


class SettingsResponse(BaseModel):
    """All application settings (API key excluded from response for security)."""

    min_ms: int
    music_only: bool
    merge_enabled: bool
    bb_top_n: int
    bb_album_top_n: int
    bb_artist_top_n: int
    bb_week_start_dow: int
    bb_week_start_hour: int
    include_compilations: bool = False
    db_record_count: int
    account_data_imported: bool
    # Spotify connection
    spotify_connected: bool = False
    spotify_profile: dict | None = None
    # LLM translation
    llm_enabled: bool = False
    llm_provider: str = "deepseek"
    llm_model: str = ""
    has_llm_key: bool = False
    llm_active_profile_id: int | None = None
    llm_active_profile_name: str | None = None
    rebuild_pending: bool = False


class RebuildAggregationsResponse(BaseModel):
    """Result returned after rebuilding pre-aggregated Billboard tables."""

    status: str
    dynamic_threshold: bool
    max_merge_gap_minutes: int | None = None
    tracks: int
    albums: int
    track_sources: int
    artists: int


class ClearTranslationCacheResponse(BaseModel):
    """Result returned after clearing cached Wikipedia translations."""

    status: str
    deleted_count: int


class SettingsUpdateRequest(BaseModel):
    """Partial update for settings."""

    min_ms: int | None = Field(default=None, ge=0)
    music_only: bool | None = None
    merge_enabled: bool | None = None
    bb_top_n: int | None = Field(default=None, ge=5, le=100)
    bb_album_top_n: int | None = Field(default=None, ge=5, le=100)
    bb_artist_top_n: int | None = Field(default=None, ge=5, le=100)
    bb_week_start_dow: int | None = Field(default=None, ge=0, le=6)
    bb_week_start_hour: int | None = Field(default=None, ge=0, le=23)
    include_compilations: bool | None = None
    # LLM translation
    llm_enabled: bool | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_base_url: str | None = None


class ImportJobStatus(BaseModel):
    """Import job progress and preflight gate state."""

    job_id: str
    status: str  # "running" | "done" | "error" | "blocked" | "needs_confirmation"
    progress_pct: float
    message: str
    result: dict | None = None


class ImportJobCreateResponse(BaseModel):
    """Response returned when an import job is scheduled."""

    job_id: str


class JobStatusResponse(BaseModel):
    """Background job status persisted by the job queue."""

    found: bool
    job_id: str | None = None
    job_type: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    status: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    error: str | None = None


class CacheStatsResponse(BaseModel):
    """Cache manager metrics grouped by namespace."""

    cache_stats: dict[str, dict[str, Any]]


class HealthResponse(BaseModel):
    """Lightweight app health response."""

    status: str


# ═══════════════════════════════════════════════════════════════════════════
# Spotify OAuth / Web API models
# ═══════════════════════════════════════════════════════════════════════════


class SpotifyAuthUrlResponse(BaseModel):
    """Spotify OAuth authorization URL and PKCE state."""

    auth_url: str
    state: str


class SpotifyStatusResponse(BaseModel):
    """Current Spotify connection status and locally persisted data summary."""

    connected: bool
    scope: str = ""
    connected_at: str = ""
    profile: dict[str, Any] | None = None
    available_data: dict[str, int] = Field(default_factory=dict)


class SpotifyDisconnectResponse(BaseModel):
    """Result returned after clearing stored Spotify tokens and data."""

    status: str


class SpotifySavedTracksSyncResponse(BaseModel):
    """Result returned after backfilling saved-track added dates."""

    success: bool
    total_in_spotify: int | None = None
    total_in_db: int | None = None
    matched: int | None = None
    new_dates: int | None = None
    error: str | None = None


class SpotifyDataResponse(BaseModel):
    """All locally persisted Spotify account data buckets."""

    artists: dict[str, list[dict[str, Any]]]
    tracks: dict[str, list[dict[str, Any]]]
    recently_played: list[dict[str, Any]]
    followed_artists: list[dict[str, Any]]
    playlists: list[dict[str, Any]]


class SpotifyPlaybackTrack(BaseModel):
    """Currently playing track details returned by Spotify."""

    name: str | None = None
    artists: list[str] = Field(default_factory=list)
    album: str | None = None
    duration_ms: int | None = None
    uri: str | None = None
    images: list[dict[str, Any]] = Field(default_factory=list)


class SpotifyPlaybackResponse(BaseModel):
    """Live Spotify playback state."""

    is_playing: bool | None = None
    progress_ms: int | None = None
    track: SpotifyPlaybackTrack | None = None
    error: str | None = None


class SpotifySyncAllResponse(BaseModel):
    """Summary returned after syncing all available Spotify account data."""

    profile: bool
    top_artists: list[str]
    top_tracks: list[str]
    recently_played: bool
    followed_artists: int
    playlists: int


# ═══════════════════════════════════════════════════════════════════════════
# LLM Profile models
# ═══════════════════════════════════════════════════════════════════════════


class LLMProfileResponse(BaseModel):
    """A saved LLM profile (without API key for list view)."""

    id: int
    profile_name: str
    llm_provider: str = "deepseek"
    llm_model: str = ""
    created_at: str | None = None
    updated_at: str | None = None


class LLMProfileDetailResponse(BaseModel):
    """A saved LLM profile with full details. API key is never returned — use has_llm_key instead."""

    id: int
    profile_name: str
    llm_provider: str = "deepseek"
    llm_model: str = ""
    llm_base_url: str = ""
    has_llm_key: bool = False
    created_at: str | None = None
    updated_at: str | None = None


class LLMProfileCreateResponse(BaseModel):
    """Result returned when an LLM profile is created."""

    id: int
    status: str


class LLMProfileApplyResponse(BaseModel):
    """Result returned when a saved LLM profile is applied."""

    status: str
    profile_id: int


class LLMProfileDeleteResponse(BaseModel):
    """Result returned when an LLM profile is deleted."""

    status: str


class LLMProfileCreateRequest(BaseModel):
    profile_name: str = Field(..., min_length=1)
    llm_provider: str = "deepseek"
    llm_model: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""


class LLMProfileUpdateRequest(BaseModel):
    profile_name: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_base_url: str | None = None
