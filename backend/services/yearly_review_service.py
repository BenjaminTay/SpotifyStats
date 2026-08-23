"""Cached service facade for the deterministic Yearly Review V2."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import sqlite3
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from types import SimpleNamespace
from typing import Any

from backend.core.db import get_db
from backend.domains.billboard.year_end import YEAR_END_SEMANTICS_VERSION
from backend.domains.metadata.artist_languages import artist_language_fact_revision
from backend.domains.settings.repository import SettingsRepository
from backend.domains.yearly_review.artifact_cache import (
    has_persisted_artifact,
    load_persisted_artifact,
    store_persisted_artifact,
)
from backend.domains.yearly_review.context import build_yearly_review_context
from backend.domains.yearly_review.orchestrator import build_yearly_review_artifact
from backend.domains.yearly_review.policies import (
    HIGHLIGHT_POLICY_VERSION,
    RELATIONSHIP_POLICY_VERSION,
    SEASON_STAGE_POLICY_VERSION,
)
from backend.domains.yearly_review.versions import (
    YEARLY_REVIEW_CONTENT_VERSION,
    YEARLY_REVIEW_SCHEMA_VERSION,
)
from backend.models.yearly_review import (
    YearlyReviewAvailableYearsResponse,
    YearlyReviewFilterContext,
    YearlyReviewGenerationResponse,
    YearlyReviewRecordsPage,
    YearlyReviewResponse,
)
from backend.services.yearly_review_generation import (
    PreparedYearlyReview,
    YearlyReviewGenerationCoordinator,
)

logger = logging.getLogger(__name__)
_persistent_cache_bypass: ContextVar[bool] = ContextVar(
    "yearly_review_persistent_cache_bypass",
    default=False,
)
_prewarm_lock = threading.Lock()
_prewarm_thread: threading.Thread | None = None


@contextmanager
def bypass_yearly_review_persistent_cache():
    """Force a true recompute while still refreshing the persistent artifact."""
    token = _persistent_cache_bypass.set(True)
    try:
        yield
    finally:
        _persistent_cache_bypass.reset(token)


def database_revision(year: int | None = None) -> str:
    """Fingerprint report source facts without reacting to unrelated SQLite writes.

    File mtimes and WAL sizes also change when jobs, task logs, or cache rows are
    written.  Keying the annual artifact on those physical details caused a hot
    request to rebuild even though no playback fact had changed.  Imports are
    append-only in normal operation, so stable core-table cardinalities, maxima,
    total duration, and the schema migration version form the source revision;
    governed metadata has its own explicit revisions in the cache key.
    """
    conn = get_db(readonly=True)
    try:
        if (
            year is not None
            and conn.execute(
                """SELECT 1 FROM sqlite_master
               WHERE type='table' AND name='playback_year_partition_state'"""
            ).fetchone()
        ):
            partition = conn.execute(
                """SELECT prefix_digest FROM playback_year_partition_state
                   WHERE report_year=?""",
                (year,),
            ).fetchone()
            if partition is not None:
                return str(partition[0])
        if (
            year is None
            and conn.execute(
                """SELECT 1 FROM sqlite_master
               WHERE type='table' AND name='playback_import_state'"""
            ).fetchone()
        ):
            state_columns = {
                str(row[1])
                for row in conn.execute("PRAGMA table_info(playback_import_state)").fetchall()
            }
            revision_column = "playback_revision" if "playback_revision" in state_columns else "0"
            state = conn.execute(
                f"""SELECT dataset_digest, {revision_column}
                    FROM playback_import_state WHERE state_id=1"""
            ).fetchone()
            if state is not None and state[0]:
                return f"{state[0]}:{int(state[1] or 0)}"
        year_filter = " WHERE ts_year<=?" if year is not None else ""
        params = (year,) if year is not None else ()
        row = conn.execute(
            f"""SELECT
                   (SELECT COUNT(*) FROM plays{year_filter}) AS play_count,
                   (SELECT COALESCE(MAX(play_id), 0) FROM plays{year_filter}) AS max_play_id,
                   (SELECT COALESCE(MAX(ts), '') FROM plays{year_filter}) AS latest_play_ts,
                   (SELECT COALESCE(SUM(ms_played), 0) FROM plays{year_filter}) AS total_ms,
                   (SELECT COUNT(*) FROM tracks) AS track_count,
                   (SELECT COALESCE(MAX(track_id), 0) FROM tracks) AS max_track_id,
                   (SELECT COUNT(*) FROM albums) AS album_count,
                   (SELECT COALESCE(MAX(album_id), 0) FROM albums) AS max_album_id,
                   (SELECT COUNT(*) FROM artists) AS artist_count,
                   (SELECT COALESCE(MAX(artist_id), 0) FROM artists) AS max_artist_id,
                   (SELECT COALESCE(MAX(version), 0) FROM schema_migrations)
                       AS schema_version""",
            params * 4,
        ).fetchone()
        encoded = json.dumps(list(row), ensure_ascii=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode()).hexdigest()[:20]
    finally:
        conn.close()


def _language_revision() -> str:
    conn = get_db(readonly=True)
    try:
        return artist_language_fact_revision(conn)
    except Exception:
        return "unavailable"
    finally:
        conn.close()


def build_yearly_review_cache_key(
    year: int,
    context: YearlyReviewFilterContext,
    *,
    language_revision: str,
    db_revision: str,
    scoped_dependency_revision: str | None = None,
) -> str:
    request_filter = {
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
        )
    }
    payload = {
        "year": year,
        "schema_version": YEARLY_REVIEW_SCHEMA_VERSION,
        "content_version": YEARLY_REVIEW_CONTENT_VERSION,
        "request_filter": request_filter,
        "relationship_policy_version": RELATIONSHIP_POLICY_VERSION,
        "highlight_policy_version": HIGHLIGHT_POLICY_VERSION,
        "season_stage_policy_version": SEASON_STAGE_POLICY_VERSION,
        "billboard_semantics_version": YEAR_END_SEMANTICS_VERSION,
        "display_taxonomy_version": context.display_taxonomy_version,
        "language_revision": language_revision,
        "artist_identity_revision": context.artist_identity_revision,
        "track_credit_revision": context.track_credit_revision,
        "scoped_dependency_revision": scoped_dependency_revision
        or _fallback_dependency_revision(context),
        "database_revision": db_revision,
    }
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


@lru_cache(maxsize=16)
def _build_cached_artifact(
    year: int,
    context_json: str,
    cache_key: str,
    db_revision: str,
) -> dict[str, Any]:
    context = YearlyReviewFilterContext.model_validate_json(context_json)
    if not _persistent_cache_bypass.get():
        try:
            persisted = load_persisted_artifact(cache_key)
        except Exception:
            logger.exception("Yearly Review persistent cache read failed")
        else:
            if persisted is not None:
                return persisted

    conn = get_db(readonly=True)
    try:
        artifact = build_yearly_review_artifact(conn, year, context)
        result = {
            "report": artifact.report.model_dump(mode="json"),
            "record_catalog": artifact.record_catalog,
        }
    finally:
        conn.close()
    try:
        store_persisted_artifact(
            cache_key,
            result,
            year=year,
            filter_fingerprint=context.filter_fingerprint,
            source_db_revision=db_revision,
        )
    except Exception:
        logger.exception("Yearly Review persistent cache write failed")
    return result


def _prepare_artifact(year: int, context: YearlyReviewFilterContext) -> PreparedYearlyReview:
    db_revision = database_revision(year)
    return _prepare_artifact_with_revisions(
        year,
        context,
        db_revision=db_revision,
        language_revision=_language_revision(),
        scoped_dependency_revision=_year_scoped_dependency_revision(year, context),
    )


def _prepare_artifact_with_revisions(
    year: int,
    context: YearlyReviewFilterContext,
    *,
    db_revision: str,
    language_revision: str,
    scoped_dependency_revision: str | None = None,
) -> PreparedYearlyReview:
    key = build_yearly_review_cache_key(
        year,
        context,
        language_revision=language_revision,
        db_revision=db_revision,
        scoped_dependency_revision=scoped_dependency_revision,
    )
    return PreparedYearlyReview(
        year=year,
        context=context,
        context_json=context.model_dump_json(),
        cache_key=key,
        db_revision=db_revision,
    )


def _prepare_artifacts(
    years: list[int], context: YearlyReviewFilterContext
) -> dict[int, PreparedYearlyReview]:
    language_revision = _language_revision()
    return {
        year: _prepare_artifact_with_revisions(
            year,
            context,
            db_revision=database_revision(year),
            language_revision=language_revision,
            scoped_dependency_revision=_year_scoped_dependency_revision(year, context),
        )
        for year in dict.fromkeys(years)
    }


def _fallback_dependency_revision(context: YearlyReviewFilterContext) -> str:
    value = (
        f"{context.artist_metadata_revision}:{context.track_group_revision}:"
        f"{context.album_project_revision}"
    )
    return hashlib.sha256(value.encode()).hexdigest()[:20]


def _year_scoped_dependency_revision(
    year: int,
    context: YearlyReviewFilterContext,
) -> str:
    """Hash metadata/group/project facts reachable from the report prefix."""
    conn = get_db(readonly=True)
    try:
        digest = hashlib.sha256(b"spotifystats-year-dependencies-v2\0")
        queries = (
            (
                "artists",
                """SELECT a.artist_id, a.artist_name, a.spotify_artist_id,
                      a.genres, a.popularity, a.followers, a.image_url
               FROM artists a
               WHERE EXISTS (
                   SELECT 1 FROM tracks t JOIN plays p ON p.track_id=t.track_id
                   WHERE t.artist_id=a.artist_id AND p.ts_year<=?
               ) OR EXISTS (
                   SELECT 1 FROM track_artists ta JOIN plays p ON p.track_id=ta.track_id
                   WHERE ta.artist_id=a.artist_id AND p.ts_year<=?
               )
               ORDER BY a.artist_id""",
                (year, year),
            ),
            (
                "spotify_artist_meta",
                """SELECT sam.spotify_artist_id, sam.artist_name, sam.popularity,
                          sam.followers, sam.genres, sam.image_url
                   FROM spotify_artist_meta sam
                   WHERE EXISTS (
                       SELECT 1
                       FROM artists a
                       JOIN tracks t ON t.artist_id=a.artist_id
                       JOIN plays p ON p.track_id=t.track_id
                       WHERE a.artist_name=sam.artist_name AND p.ts_year<=?
                   ) OR EXISTS (
                       SELECT 1
                       FROM artists a
                       JOIN track_artists ta ON ta.artist_id=a.artist_id
                       JOIN plays p ON p.track_id=ta.track_id
                       WHERE a.artist_name=sam.artist_name AND p.ts_year<=?
                   )
                   ORDER BY sam.spotify_artist_id""",
                (year, year),
            ),
            (
                "artist_genre_overrides",
                """SELECT ago.artist_name, ago.normalized_genres_json,
                          ago.primary_genre, ago.language, ago.region,
                          ago.confidence, ago.note
                   FROM artist_genre_overrides ago
                   WHERE EXISTS (
                       SELECT 1
                       FROM artists a
                       JOIN tracks t ON t.artist_id=a.artist_id
                       JOIN plays p ON p.track_id=t.track_id
                       WHERE a.artist_name=ago.artist_name AND p.ts_year<=?
                   ) OR EXISTS (
                       SELECT 1
                       FROM artists a
                       JOIN track_artists ta ON ta.artist_id=a.artist_id
                       JOIN plays p ON p.track_id=ta.track_id
                       WHERE a.artist_name=ago.artist_name AND p.ts_year<=?
                   )
                   ORDER BY ago.artist_name""",
                (year, year),
            ),
            (
                "artist_genre_sources",
                """SELECT ags.source_id, ags.artist_name, ags.spotify_artist_id,
                          ags.source, ags.source_key, ags.normalized_genres_json,
                          ags.primary_genre, ags.language, ags.region,
                          ags.confidence, ags.evidence_url, ags.evidence_summary,
                          ags.status
                   FROM artist_genre_sources ags
                   WHERE ags.status='approved' AND (
                       EXISTS (
                           SELECT 1
                           FROM artists a
                           JOIN tracks t ON t.artist_id=a.artist_id
                           JOIN plays p ON p.track_id=t.track_id
                           WHERE a.artist_name=ags.artist_name AND p.ts_year<=?
                       ) OR EXISTS (
                           SELECT 1
                           FROM artists a
                           JOIN track_artists ta ON ta.artist_id=a.artist_id
                           JOIN plays p ON p.track_id=ta.track_id
                           WHERE a.artist_name=ags.artist_name AND p.ts_year<=?
                       )
                   )
                   ORDER BY ags.artist_name, ags.source_id""",
                (year, year),
            ),
            (
                "tracks",
                """SELECT t.track_id, t.track_name, t.artist_id, t.album_id,
                          t.spotify_track_uri, t.spotify_track_id
                   FROM tracks t
                   WHERE EXISTS (
                       SELECT 1 FROM plays p
                       WHERE p.track_id=t.track_id AND p.ts_year<=?
                   )
                   ORDER BY t.track_id""",
                (year,),
            ),
            (
                "artist_metadata_attribution_overrides",
                """SELECT amao.track_id, amao.artist_id, amao.reason,
                          amao.evidence_url
                   FROM artist_metadata_attribution_overrides amao
                   WHERE EXISTS (
                       SELECT 1 FROM plays p
                       WHERE p.track_id=amao.track_id AND p.ts_year<=?
                   )
                   ORDER BY amao.track_id""",
                (year,),
            ),
            (
                "spotify_track_meta",
                """SELECT stm.spotify_track_id, stm.track_name, stm.duration_ms,
                          stm.popularity, stm.explicit, stm.track_number,
                          stm.disc_number, stm.isrc, stm.spotify_album_id
                   FROM spotify_track_meta stm
                   WHERE EXISTS (
                       SELECT 1
                       FROM tracks t JOIN plays p ON p.track_id=t.track_id
                       WHERE t.spotify_track_id=stm.spotify_track_id AND p.ts_year<=?
                   )
                   ORDER BY stm.spotify_track_id""",
                (year,),
            ),
            (
                "spotify_album_meta",
                """SELECT sam.spotify_album_id, sam.album_name, sam.album_type,
                          sam.release_date, sam.popularity, sam.label, sam.genres,
                          sam.image_url, sam.album_artists, sam.total_tracks,
                          sam.track_list
                   FROM spotify_album_meta sam
                   WHERE EXISTS (
                       SELECT 1
                       FROM spotify_track_meta stm
                       JOIN tracks t ON t.spotify_track_id=stm.spotify_track_id
                       JOIN plays p ON p.track_id=t.track_id
                       WHERE stm.spotify_album_id=sam.spotify_album_id
                         AND p.ts_year<=?
                   )
                   ORDER BY sam.spotify_album_id""",
                (year,),
            ),
            (
                "track_groups",
                """SELECT tg.scope, tg.canonical_name, tg.primary_track_id,
                      tg.is_manual, tgm.track_id
               FROM track_group_members tgm
               JOIN track_groups tg ON tg.group_id=tgm.group_id
               WHERE EXISTS (
                   SELECT 1 FROM plays p
                   WHERE p.track_id=tgm.track_id AND p.ts_year<=?
               )
               ORDER BY tg.scope, tg.canonical_name, tg.primary_track_id,
                        tg.is_manual, tgm.track_id""",
                (year,),
            ),
            (
                "album_project_tracks",
                """SELECT ap.canonical_name, ap.artist_id, ap.primary_album_id,
                      ap.release_date, ap.scope, ap.project_type,
                      ap.include_in_charts, ap.is_manual,
                      apt.track_id, apt.membership_role, apt.min_merge_level,
                      apt.source_album_id, apt.is_exclusive, apt.inferred
               FROM album_project_tracks apt
               JOIN album_projects ap ON ap.project_id=apt.project_id
               WHERE EXISTS (
                   SELECT 1 FROM plays p
                   WHERE p.track_id=apt.track_id AND p.ts_year<=?
               )
               ORDER BY ap.canonical_name, ap.artist_id, ap.scope,
                        apt.track_id, apt.min_merge_level""",
                (year,),
            ),
            (
                "album_project_albums",
                """SELECT ap.canonical_name, ap.artist_id, ap.primary_album_id,
                          ap.scope, apa.album_id, apa.role, apa.source_bucket,
                          apa.inferred
                   FROM album_project_albums apa
                   JOIN album_projects ap ON ap.project_id=apa.project_id
                   WHERE EXISTS (
                       SELECT 1
                       FROM album_project_tracks apt
                       JOIN plays p ON p.track_id=apt.track_id
                       WHERE apt.project_id=apa.project_id AND p.ts_year<=?
                   )
                   ORDER BY ap.canonical_name, ap.artist_id, ap.scope,
                            apa.album_id""",
                (year,),
            ),
            (
                "available_playback_years",
                """SELECT DISTINCT ts_year
                   FROM plays
                   WHERE ts_year BETWEEN 2000 AND 2100
                   ORDER BY ts_year""",
                (),
            ),
            (
                "available_billboard_years",
                """SELECT available_year FROM (
                       SELECT DISTINCT SUBSTR(billboard_week, 1, 4) AS available_year
                       FROM agg_weekly_tracks
                       UNION
                       SELECT DISTINCT SUBSTR(billboard_week, 1, 4) AS available_year
                       FROM agg_weekly_albums
                       UNION
                       SELECT DISTINCT SUBSTR(billboard_week, 1, 4) AS available_year
                       FROM agg_weekly_artists
                   )
                   WHERE available_year BETWEEN '2000' AND '2100'
                   ORDER BY available_year""",
                (),
            ),
        )
        for label, query, params in queries:
            digest.update(label.encode())
            digest.update(b"\0")
            try:
                rows = conn.execute(query, params).fetchall()
            except sqlite3.OperationalError:
                digest.update(b"unavailable\n")
                continue
            for row in rows:
                digest.update(
                    json.dumps(
                        list(row),
                        ensure_ascii=True,
                        separators=(",", ":"),
                        default=str,
                    ).encode()
                )
                digest.update(b"\n")
        return digest.hexdigest()[:20]
    except Exception:
        logger.exception("Yearly Review scoped dependency revision failed")
        return _fallback_dependency_revision(context)
    finally:
        conn.close()


def _refresh_prepared_artifact(prepared: PreparedYearlyReview) -> PreparedYearlyReview:
    filters = SimpleNamespace(
        min_ms=prepared.context.min_ms,
        music_only=prepared.context.music_only,
        merge_enabled=prepared.context.merge_enabled,
        dynamic_threshold=prepared.context.dynamic_threshold,
        max_merge_gap_minutes=prepared.context.max_merge_gap_minutes,
        merge_level=prepared.context.merge_level,
        include_compilations=prepared.context.include_compilations,
        bb_top_n=prepared.context.bb_top_n,
        bb_album_top_n=prepared.context.bb_album_top_n,
        bb_artist_top_n=prepared.context.bb_artist_top_n,
        bb_week_start_dow=prepared.context.bb_week_start_dow,
        bb_week_start_hour=prepared.context.bb_week_start_hour,
    )
    conn = get_db(readonly=True)
    try:
        context = build_yearly_review_context(conn, filters)
    finally:
        conn.close()
    return _prepare_artifact(prepared.year, context)


def _build_prepared_artifact(prepared: PreparedYearlyReview) -> dict[str, Any]:
    return _build_cached_artifact(
        prepared.year,
        prepared.context_json,
        prepared.cache_key,
        prepared.db_revision,
    )


_generation_coordinator = YearlyReviewGenerationCoordinator(
    prepare=_prepare_artifact,
    refresh=_refresh_prepared_artifact,
    build=_build_prepared_artifact,
    is_ready=has_persisted_artifact,
)


def _artifact(year: int, context: YearlyReviewFilterContext) -> dict[str, Any]:
    if _persistent_cache_bypass.get():
        return _build_prepared_artifact(_prepare_artifact(year, context))
    return _generation_coordinator.get_or_build(year, context)


def build_default_yearly_review_context() -> YearlyReviewFilterContext:
    """Build the same default context used by an omitted-query API request."""
    conn = get_db(readonly=True)
    try:
        settings = SettingsRepository(conn).load_all()
        filters = SimpleNamespace(
            min_ms=int(settings["min_ms"]),
            music_only=bool(settings["music_only"]),
            merge_enabled=bool(settings["merge_enabled"]),
            dynamic_threshold=True,
            max_merge_gap_minutes=5,
            merge_level=2,
            include_compilations=bool(settings["include_compilations"]),
            bb_top_n=int(settings["bb_top_n"]),
            bb_album_top_n=int(settings["bb_album_top_n"]),
            bb_artist_top_n=int(settings["bb_artist_top_n"]),
            bb_week_start_dow=int(settings["bb_week_start_dow"]),
            bb_week_start_hour=int(settings["bb_week_start_hour"]),
        )
        return build_yearly_review_context(conn, filters)
    finally:
        conn.close()


def prewarm_latest_yearly_review() -> int | None:
    """Persist the latest report in a background-safe, exact-key cache."""
    available = get_yearly_review_available_years()
    if available.latest_year is None:
        return None
    get_yearly_review(available.latest_year, build_default_yearly_review_context())
    return available.latest_year


def prewarm_yearly_reviews(
    years: list[int],
    context: YearlyReviewFilterContext,
    *,
    foreground_year: int | None = None,
) -> YearlyReviewGenerationResponse:
    """Queue exact-context reports, putting the visible year ahead of background work."""
    requested = list(dict.fromkeys(years))
    if foreground_year is not None and foreground_year not in requested:
        requested.append(foreground_year)
    available = set(get_yearly_review_available_years().years)
    unavailable = [year for year in requested if year not in available]
    if unavailable:
        joined = ",".join(str(year) for year in unavailable)
        raise ValueError(f"unavailable_years:{joined}")
    prepared = _prepare_artifacts(requested, context)
    if foreground_year is not None:
        _generation_coordinator.enqueue_prepared(
            prepared[foreground_year],
            foreground=True,
        )
    for year in sorted((year for year in requested if year != foreground_year), reverse=True):
        _generation_coordinator.enqueue_prepared(
            prepared[year],
            foreground=False,
        )
    tasks = []
    for year in requested:
        status = _generation_coordinator.status_prepared(prepared[year])
        if status is not None:
            tasks.append(status)
    return YearlyReviewGenerationResponse(tasks=tasks)


def get_yearly_review_generation_status(
    context: YearlyReviewFilterContext,
    *,
    years: list[int] | None = None,
) -> YearlyReviewGenerationResponse:
    requested = years if years is not None else get_yearly_review_available_years().years
    prepared = _prepare_artifacts(requested, context)
    tasks = []
    for year in dict.fromkeys(requested):
        status = _generation_coordinator.status_prepared(prepared[year])
        if status is not None:
            tasks.append(status)
    return YearlyReviewGenerationResponse(tasks=tasks)


def start_yearly_review_prewarm_thread() -> threading.Thread | None:
    """Start one deduplicated daemon rebuild for the latest default report."""
    global _prewarm_thread
    if "PYTEST_CURRENT_TEST" in os.environ:
        return None
    with _prewarm_lock:
        if _prewarm_thread is not None and _prewarm_thread.is_alive():
            return _prewarm_thread

        def run() -> None:
            try:
                year = prewarm_latest_yearly_review()
                if year is not None:
                    logger.info("Yearly Review persistent cache prewarmed for %d", year)
            except Exception:
                logger.exception("Yearly Review persistent cache prewarm failed")

        _prewarm_thread = threading.Thread(
            target=run,
            name="yearly-review-persistent-prewarm",
            daemon=True,
        )
        _prewarm_thread.start()
        return _prewarm_thread


def get_yearly_review(
    year: int,
    context: YearlyReviewFilterContext,
) -> YearlyReviewResponse:
    return YearlyReviewResponse.model_validate(_artifact(year, context)["report"])


def get_cached_yearly_review_artifact(
    year: int,
    context: YearlyReviewFilterContext,
) -> dict[str, Any] | None:
    """Return an exact persistent hit without queueing or building a report.

    Lightweight consumers such as the home page must never turn a preview read
    into a 10+ second annual-report generation.  This helper deliberately
    bypasses both the generation coordinator and the in-process builder cache.
    """
    prepared = _prepare_artifact(year, context)
    try:
        if not has_persisted_artifact(prepared.cache_key):
            return None
        return load_persisted_artifact(prepared.cache_key)
    except Exception:
        logger.exception("Yearly Review cache-only preview read failed")
        return None


def get_cached_yearly_review(
    year: int,
    context: YearlyReviewFilterContext,
) -> YearlyReviewResponse | None:
    artifact = get_cached_yearly_review_artifact(year, context)
    if artifact is None:
        return None
    return YearlyReviewResponse.model_validate(artifact["report"])


def yearly_review_cache_state(context: YearlyReviewFilterContext) -> str:
    """Cheap exact-key readiness token for lightweight composite caches."""
    latest = get_yearly_review_available_years().latest_year
    if latest is None:
        return "unavailable"
    prepared = _prepare_artifact(latest, context)
    try:
        ready = has_persisted_artifact(prepared.cache_key)
    except Exception:
        ready = False
    return f"{latest}:{prepared.cache_key}:{int(ready)}"


def get_yearly_review_records(
    year: int,
    context: YearlyReviewFilterContext,
    *,
    page: int,
    page_size: int,
) -> YearlyReviewRecordsPage:
    artifact = _artifact(year, context)
    return _records_page_from_artifact(
        artifact,
        year=year,
        context=context,
        page=page,
        page_size=page_size,
    )


def get_cached_yearly_review_records(
    year: int,
    context: YearlyReviewFilterContext,
    *,
    page: int,
    page_size: int,
) -> YearlyReviewRecordsPage | None:
    artifact = get_cached_yearly_review_artifact(year, context)
    if artifact is None:
        return None
    return _records_page_from_artifact(
        artifact,
        year=year,
        context=context,
        page=page,
        page_size=page_size,
    )


def _records_page_from_artifact(
    artifact: dict[str, Any],
    *,
    year: int,
    context: YearlyReviewFilterContext,
    page: int,
    page_size: int,
) -> YearlyReviewRecordsPage:
    catalog = list(artifact["record_catalog"])
    total = len(catalog)
    total_pages = math.ceil(total / page_size) if total else 0
    start = (page - 1) * page_size
    items = catalog[start : start + page_size] if start < total else []
    report = artifact["report"]
    return YearlyReviewRecordsPage(
        content_version=report.get("methodology", {}).get(
            "content_version", YEARLY_REVIEW_CONTENT_VERSION
        ),
        year=year,
        filter_fingerprint=context.filter_fingerprint,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
        items=items,
        catalog_counts=report.get("records", {}).get("catalog_counts", {}),
    )


def get_yearly_review_available_years() -> YearlyReviewAvailableYearsResponse:
    conn = get_db(readonly=True)
    try:
        rows = conn.execute(
            """SELECT DISTINCT ts_year FROM plays
               WHERE ts_year BETWEEN 2000 AND 2100
               ORDER BY ts_year"""
        ).fetchall()
    finally:
        conn.close()
    years = [int(row[0]) for row in rows]
    return YearlyReviewAvailableYearsResponse(
        years=years,
        latest_year=years[-1] if years else None,
    )


from backend.core.cache_manager import register_lru  # noqa: E402

register_lru("yearly_review", "report_artifact", _build_cached_artifact)
