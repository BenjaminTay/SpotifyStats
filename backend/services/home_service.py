"""Service facade for the personal music home page."""

from __future__ import annotations

import os
from datetime import date
from functools import lru_cache
from sqlite3 import Connection

from backend.core.cache import singleflight
from backend.core.db import DB_PATH, get_db
from backend.domains.billboard.latest_snapshot_cache import (
    latest_snapshot_revision,
    snapshot_key,
)
from backend.domains.home.overview import build_home_overview
from backend.models.home import HomeOverviewResponse
from backend.models.yearly_review import YearlyReviewFilterContext
from backend.services.yearly_review_service import database_revision, yearly_review_cache_state


def _is_primary_connection(conn: Connection) -> bool:
    row = conn.execute("PRAGMA database_list").fetchone()
    if row is None:
        return False
    path = str(row[2] or "")
    return bool(path) and os.path.realpath(path) == os.path.realpath(DB_PATH)


@singleflight
@lru_cache(maxsize=8)
def _get_home_overview_cached(
    context_json: str,
    source_revision: str,
    day_key: str,
    billboard_revision: int,
    yearly_cache_state: str,
) -> dict:
    """Cache the full payload by exact source facts, semantics, and calendar day."""
    del source_revision, day_key, billboard_revision, yearly_cache_state
    context = YearlyReviewFilterContext.model_validate_json(context_json)
    conn = get_db(readonly=True)
    try:
        return build_home_overview(conn, context)
    finally:
        conn.close()


def get_home_overview(conn: Connection, context: YearlyReviewFilterContext) -> HomeOverviewResponse:
    if _is_primary_connection(conn):
        billboard_key = snapshot_key(
            context.min_ms,
            context.music_only,
            context.bb_top_n,
            context.bb_album_top_n,
            context.bb_artist_top_n,
            context.bb_week_start_dow,
            context.bb_week_start_hour,
            None,
            None,
            context.merge_level,
            context.dynamic_threshold,
            context.max_merge_gap_minutes,
            context.include_compilations,
            context.merge_enabled,
        )
        payload = _get_home_overview_cached(
            context.model_dump_json(),
            database_revision(),
            date.today().isoformat(),
            latest_snapshot_revision(billboard_key),
            yearly_review_cache_state(context),
        )
    else:
        payload = build_home_overview(conn, context)
    return HomeOverviewResponse.model_validate(payload)


def prewarm_default_home_overview() -> HomeOverviewResponse:
    """Warm the default front-page payload after its Billboard snapshot exists."""
    from backend.services.yearly_review_service import build_default_yearly_review_context

    context = build_default_yearly_review_context()
    conn = get_db(readonly=True)
    try:
        return get_home_overview(conn, context)
    finally:
        conn.close()


from backend.core.cache_manager import register_lru  # noqa: E402

register_lru("analysis", "home_overview", _get_home_overview_cached)
