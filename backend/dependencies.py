"""FastAPI dependency injection: database connections, shared query parameters.

Connection management pattern:
  - API layer: inject conn via ``Depends(get_conn)`` for the request lifecycle
  - Non-cached services: receive ``conn`` as a parameter from the API layer
  - Cached services (lru_cache/ttl_cached): MUST call ``get_db()`` internally,
    since connection objects are not hashable for cache keys

This is a pragmatic choice for a single-user local app with SQLite WAL mode,
where concurrent reads are safe and connection overhead is negligible (~1ms).
"""

from __future__ import annotations

from fastapi import Query

from backend.core.db import get_db
from backend.domains.settings.repository import SETTINGS_DEFAULTS, SettingsRepository

# ═══════════════════════════════════════════════════════════════════════════
# Database connection
# ═══════════════════════════════════════════════════════════════════════════


def get_conn(readonly: bool = True):
    """Yield a database connection. Use readonly=True for all GET endpoints."""
    conn = get_db(readonly=readonly)
    try:
        yield conn
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# Shared query-parameter dependencies
# ═══════════════════════════════════════════════════════════════════════════


class PlayFilters:
    """Standard play-data filters — used by dashboard, timeline, leaderboard,
    behavior, listening-hours, artist, wrapped endpoints."""

    def __init__(
        self,
        min_ms: int = Query(default=30000, ge=0, description="最短播放时长 (毫秒)"),
        music_only: bool = Query(default=True, description="仅音乐"),
        merge_enabled: bool = Query(default=True, description="合并连续播放"),
        dynamic_threshold: bool = Query(default=True, description="使用动态有效播放阈值"),
        max_merge_gap_minutes: int | None = Query(
            default=None, ge=1, le=240, description="连续播放最大合并间隔 (分钟)"
        ),
    ):
        self.min_ms = min_ms
        self.music_only = music_only
        self.merge_enabled = merge_enabled
        self.dynamic_threshold = dynamic_threshold
        self.max_merge_gap_minutes = max_merge_gap_minutes


class BillboardFilters:
    """Billboard computation filters — used by /api/billboard/data and
    /api/billboard/release-cycle/* endpoints."""

    def __init__(
        self,
        min_ms: int | None = Query(default=None, ge=0, description="最短播放时长 (毫秒)"),
        music_only: bool | None = Query(default=None, description="仅音乐"),
        merge_enabled: bool | None = Query(default=None, description="合并连续播放"),
        bb_top_n: int | None = Query(default=None, ge=5, le=100, description="单曲榜 Top N"),
        bb_album_top_n: int | None = Query(default=None, ge=5, le=100, description="专辑榜 Top N"),
        bb_artist_top_n: int | None = Query(default=None, ge=5, le=100, description="艺人榜 Top N"),
        bb_week_start_dow: int | None = Query(
            default=None, ge=0, le=6, description="周起始星期 (0=周一)"
        ),
        bb_week_start_hour: int | None = Query(default=None, ge=0, le=23, description="周起始小时"),
        year_start: int | None = Query(default=None, description="起始年份 (含)"),
        year_end: int | None = Query(default=None, description="结束年份 (含)"),
        dynamic_threshold: bool = Query(default=True, description="使用动态有效播放阈值"),
        max_merge_gap_minutes: int | None = Query(
            default=None, ge=1, le=240, description="连续播放最大合并间隔 (分钟)"
        ),
    ):
        settings = _load_filter_settings()
        self.min_ms = _filter_value(min_ms, settings, "min_ms")
        self.music_only = _filter_value(music_only, settings, "music_only")
        self.merge_enabled = _filter_value(merge_enabled, settings, "merge_enabled")
        self.bb_top_n = _filter_value(bb_top_n, settings, "bb_top_n")
        self.bb_album_top_n = _filter_value(bb_album_top_n, settings, "bb_album_top_n")
        self.bb_artist_top_n = _filter_value(bb_artist_top_n, settings, "bb_artist_top_n")
        self.bb_week_start_dow = _filter_value(bb_week_start_dow, settings, "bb_week_start_dow")
        self.bb_week_start_hour = _filter_value(bb_week_start_hour, settings, "bb_week_start_hour")
        self.year_start = year_start
        self.year_end = year_end
        self.dynamic_threshold = dynamic_threshold
        self.max_merge_gap_minutes = max_merge_gap_minutes


class MergeConfig:
    """版本合并严格度 — L1=不合并, L2=录音版本合并(默认), L3=作曲版本合并."""

    def __init__(
        self,
        merge_level: int = Query(default=2, ge=1, le=3, description="版本合并严格度"),
    ):
        self.merge_level = merge_level


def _load_filter_settings() -> dict:
    """Load persisted settings used as defaults for omitted query params."""
    conn = get_db(readonly=True)
    try:
        return SettingsRepository(conn).load_all()
    except Exception:
        return dict(SETTINGS_DEFAULTS)
    finally:
        conn.close()


def _filter_value(value, settings: dict, key: str):
    if value is not None:
        return value
    return settings.get(key, SETTINGS_DEFAULTS[key])
