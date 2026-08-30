"""Service facade for the personal music home page."""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import threading
import uuid
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path
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

_HOME_SNAPSHOT_DIR = Path(DB_PATH).parent / "cache" / "home-overview"
_HOME_FACTS_VERSION = "home-facts-v4"
logger = logging.getLogger(__name__)
_rebuild_guard = threading.Lock()
_rebuild_paths: set[Path] = set()


def _snapshot_path(parts: tuple[str, ...]) -> Path:
    digest = hashlib.sha256("\0".join(parts).encode()).hexdigest()
    return _HOME_SNAPSHOT_DIR / f"{digest}.json"


def _lkg_snapshot_path(context: YearlyReviewFilterContext) -> Path:
    semantic = {
        key: getattr(context, key)
        for key in (
            "min_ms",
            "music_only",
            "merge_enabled",
            "dynamic_threshold",
            "max_merge_gap_minutes",
            "merge_level",
            "include_compilations",
            "bb_top_n",
            "bb_album_top_n",
            "bb_artist_top_n",
            "bb_week_start_dow",
            "bb_week_start_hour",
            "display_taxonomy_version",
        )
    }
    digest = hashlib.sha256(
        json.dumps(semantic, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return _HOME_SNAPSHOT_DIR / f"lkg-{_HOME_FACTS_VERSION}-{digest}.json"


def _read_snapshot(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_snapshot(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        f".{path.name}.{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp"
    )
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _start_snapshot_rebuild(
    *,
    exact_path: Path,
    lkg_path: Path,
    context: YearlyReviewFilterContext,
) -> None:
    with _rebuild_guard:
        if exact_path in _rebuild_paths:
            return
        _rebuild_paths.add(exact_path)

    def rebuild() -> None:
        conn = get_db(readonly=True)
        try:
            payload = build_home_overview(conn, context)
            payload["cache_state"] = "fresh"
            _write_snapshot(exact_path, payload)
            _write_snapshot(lkg_path, payload)
        except Exception:
            logger.exception("Home overview snapshot rebuild failed")
        finally:
            conn.close()
            with _rebuild_guard:
                _rebuild_paths.discard(exact_path)
            _get_home_overview_cached.cache_clear()

    threading.Thread(
        target=rebuild,
        name="spotify-stats-home-snapshot-rebuild",
        daemon=True,
    ).start()


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
    """Cache exact home facts in memory and across backend restarts."""
    context = YearlyReviewFilterContext.model_validate_json(context_json)
    conn = get_db(readonly=True)
    persistent = _is_primary_connection(conn)
    try:
        path = _snapshot_path(
            (
                context_json,
                source_revision,
                day_key,
                str(billboard_revision),
                yearly_cache_state,
            )
        )
        if persistent:
            lkg_path = _lkg_snapshot_path(context)
            restored = _read_snapshot(path)
            if restored is not None:
                restored["cache_state"] = "fresh"
                if not lkg_path.exists():
                    try:
                        _write_snapshot(lkg_path, restored)
                    except OSError:
                        pass
                return restored
            last_good = _read_snapshot(lkg_path)
            if last_good is not None:
                _start_snapshot_rebuild(
                    exact_path=path,
                    lkg_path=lkg_path,
                    context=context,
                )
                last_good["cache_state"] = "warming"
                return last_good
        payload = build_home_overview(conn, context)
        if persistent:
            payload["cache_state"] = "fresh"
            try:
                _write_snapshot(path, payload)
                _write_snapshot(_lkg_snapshot_path(context), payload)
            except OSError:
                # Persistent restoration is an optimization; a read must still
                # succeed when the cache directory is temporarily unwritable.
                pass
        return payload
    finally:
        conn.close()


def _present_home_payload(payload: dict) -> dict:
    """Refresh only calendar-facing fields without rebuilding source facts."""
    result = copy.deepcopy(payload)
    result["generated_at"] = datetime.now(timezone.utc).isoformat()
    latest = (result.get("coverage") or {}).get("source_latest_date")
    if latest:
        age = (date.today() - date.fromisoformat(str(latest))).days
        result["coverage"]["freshness"] = "recent" if age <= 7 else "aging" if age <= 30 else "old"
    return result


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
            _HOME_FACTS_VERSION,
            latest_snapshot_revision(billboard_key),
            yearly_review_cache_state(context),
        )
    else:
        payload = build_home_overview(conn, context)
    return HomeOverviewResponse.model_validate(_present_home_payload(payload))


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
