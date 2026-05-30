"""Common Pydantic models shared across API endpoints."""

from __future__ import annotations

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


class SettingsUpdateRequest(BaseModel):
    """Partial update for settings."""

    min_ms: int | None = None
    music_only: bool | None = None
    merge_enabled: bool | None = None
    bb_top_n: int | None = None
    bb_album_top_n: int | None = None
    bb_artist_top_n: int | None = None
    bb_week_start_dow: int | None = None
    bb_week_start_hour: int | None = None
    # LLM translation
    llm_enabled: bool | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_base_url: str | None = None


class ImportJobStatus(BaseModel):
    """Import job progress."""

    job_id: str
    status: str  # "running" | "done" | "error"
    progress_pct: float
    message: str
    result: dict | None = None


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
