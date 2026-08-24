"""Compact, versioned Year-End projections for music-detail surfaces.

The projection is derived only from an exact music-search weekly chart ledger.
Request handlers read the persisted rows; they never build a complete
Billboard or Year-End payload on demand.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Collection, Iterable, Mapping
from typing import Any, Literal, Optional, cast

import pandas as pd

from backend.domains.billboard.year_end import (
    YEAR_END_ALBUM_TOP_N,
    YEAR_END_ARTIST_TOP_N,
    YEAR_END_TRACK_TOP_N,
    _annual_window,
    _coverage_meta,
    _int_value,
    _iso,
    available_years_from_weekly,
    build_year_end_metric_frame,
    sort_year_end_rows,
)
from backend.domains.music_search.context import (
    MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
    MusicSearchFilterContext,
)
from backend.domains.music_search.snapshot_ledger import (
    LedgerFamily,
    WeeklyLedgerRow,
    _validated_frames,
)

YEAR_END_PROJECTION_BUILDER_VERSION = "music_search_year_end_projection_v1"
logger = logging.getLogger(__name__)

ProjectionStatus = Literal["ready", "warming", "unavailable"]
ProjectionMetaRow = tuple[
    int,
    str,
    int,
    int,
    int,
    Optional[str],
    Optional[str],
]
ProjectionEntityRow = tuple[
    str,
    str,
    int,
    int,
    int,
    int,
    int,
    int,
    int,
    int,
    int,
    int,
    Optional[str],
    Optional[str],
]

_FAMILY_TOP_N: Mapping[LedgerFamily, int] = {
    "track": YEAR_END_TRACK_TOP_N,
    "album": YEAR_END_ALBUM_TOP_N,
    "artist": YEAR_END_ARTIST_TOP_N,
}


def _projection_rows_for_family(
    family: LedgerFamily,
    frame: pd.DataFrame,
    year: int,
) -> list[dict[str, Any]]:
    annual = _annual_window(frame, year)
    if annual.empty:
        return []
    annual = annual.sort_values(["billboard_week", "rank"], kind="stable")
    metrics = build_year_end_metric_frame(annual, "entity_key")
    result = []
    for row in metrics.to_dict("records"):
        result.append(
            {
                "family": family,
                "entity_key": str(row["entity_key"]),
                "year": year,
                "year_end_score": _int_value(row.get("year_end_score")),
                "year_end_rank": 0,
                "peak_position": _int_value(row.get("peak_position")),
                "weeks_on_chart": _int_value(row.get("weeks_on_chart")),
                "weeks_at_peak": _int_value(row.get("weeks_at_peak")),
                "weeks_at_no1": _int_value(row.get("weeks_at_no1")),
                "weeks_top5": _int_value(row.get("weeks_top5")),
                "weeks_top10": _int_value(row.get("weeks_top10")),
                "chart_plays": _int_value(row.get("chart_plays")),
                "first_week": _iso(row.get("first_week")),
                "last_week": _iso(row.get("last_week")),
            }
        )
    return sort_year_end_rows(result)[: _FAMILY_TOP_N[family]]


def build_year_end_projection_rows(
    weekly_rows: Iterable[WeeklyLedgerRow],
    candidate_keys: Collection[str],
    *,
    track_top_n: int,
    album_top_n: int,
    artist_top_n: int,
    week_start_dow: int,
) -> tuple[list[ProjectionMetaRow], list[ProjectionEntityRow]]:
    """Build all available annual rows from one exact compact ledger."""
    top_n_by_family: dict[LedgerFamily, int] = {
        "track": int(track_top_n),
        "album": int(album_top_n),
        "artist": int(artist_top_n),
    }
    frames = _validated_frames(
        weekly_rows,
        set(candidate_keys),
        top_n_by_family=top_n_by_family,
    )
    years = available_years_from_weekly(*frames.values())
    meta_rows: list[ProjectionMetaRow] = []
    entity_rows: list[ProjectionEntityRow] = []

    for year in years:
        annual_frames = [_annual_window(frame, year) for frame in frames.values()]
        coverage = _coverage_meta(year, week_start_dow, *annual_frames)
        meta_rows.append(
            (
                year,
                str(coverage["coverage_status"]),
                int(bool(coverage["is_complete_year"])),
                int(coverage["observed_weeks"]),
                int(coverage["expected_weeks"]),
                cast(Optional[str], coverage["first_billboard_week"]),
                cast(Optional[str], coverage["last_billboard_week"]),
            )
        )
        for family in ("track", "album", "artist"):
            family_rows = _projection_rows_for_family(
                cast(LedgerFamily, family),
                frames[cast(LedgerFamily, family)],
                year,
            )
            entity_rows.extend(
                (
                    family,
                    str(row["entity_key"]),
                    year,
                    int(row["year_end_rank"]),
                    int(row["year_end_score"]),
                    int(row["peak_position"]),
                    int(row["weeks_on_chart"]),
                    int(row["weeks_at_peak"]),
                    int(row["weeks_at_no1"]),
                    int(row["weeks_top5"]),
                    int(row["weeks_top10"]),
                    int(row["chart_plays"]),
                    cast(Optional[str], row["first_week"]),
                    cast(Optional[str], row["last_week"]),
                )
                for row in family_rows
            )
    return meta_rows, entity_rows


def projection_tables_available(conn: sqlite3.Connection) -> bool:
    required = {
        "music_search_year_end_projection_state",
        "music_search_year_end_meta",
        "music_search_entity_year_end",
    }
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN (?, ?, ?)",
        tuple(sorted(required)),
    ).fetchall()
    return {str(row[0]) for row in rows} == required


def year_end_projection_set_status(
    conn: sqlite3.Connection,
    contexts: tuple[MusicSearchFilterContext, ...],
) -> dict[str, Any]:
    """Inspect the current projection set without starting any computation."""
    if not projection_tables_available(conn):
        return {
            "status": "unavailable",
            "ready_count": 0,
            "warming_count": 0,
            "incomplete_count": len(contexts),
            "variants": [],
            "builder_version": YEAR_END_PROJECTION_BUILDER_VERSION,
        }

    variants: list[dict[str, Any]] = []
    for context in contexts:
        snapshot = conn.execute(
            """SELECT snapshot_key FROM music_search_snapshot_meta
               WHERE filter_fingerprint=? AND status='ready' AND builder_version=?""",
            (context.filter_fingerprint, MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION),
        ).fetchone()
        if snapshot is None:
            variants.append(
                {
                    "snapshot_key": context.filter_fingerprint,
                    "status": "unavailable",
                    "reason": "snapshot_unavailable",
                }
            )
            continue

        snapshot_key = str(snapshot[0])
        state = conn.execute(
            """SELECT builder_version, status
               FROM music_search_year_end_projection_state WHERE snapshot_key=?""",
            (snapshot_key,),
        ).fetchone()
        if state is None:
            variants.append(
                {
                    "snapshot_key": snapshot_key,
                    "status": "missing",
                    "reason": "projection_missing",
                }
            )
            continue

        builder_version = str(state[0])
        raw_status = str(state[1])
        if builder_version != YEAR_END_PROJECTION_BUILDER_VERSION:
            status = "stale"
            reason = "builder_version_mismatch"
        elif raw_status in {"ready", "pending", "running", "failed"}:
            status = raw_status
            reason = None if raw_status == "ready" else f"projection_{raw_status}"
        else:
            status = "unavailable"
            reason = "projection_status_invalid"
        variants.append(
            {
                "snapshot_key": snapshot_key,
                "status": status,
                "reason": reason,
                "builder_version": builder_version,
            }
        )

    ready_count = sum(row["status"] == "ready" for row in variants)
    warming_count = sum(row["status"] in {"pending", "running"} for row in variants)
    incomplete_count = len(contexts) - ready_count - warming_count
    if ready_count == len(contexts):
        status = "ready"
    elif incomplete_count == 0 and warming_count > 0:
        status = "warming"
    else:
        status = "incomplete"
    return {
        "status": status,
        "ready_count": ready_count,
        "warming_count": warming_count,
        "incomplete_count": incomplete_count,
        "variants": variants,
        "builder_version": YEAR_END_PROJECTION_BUILDER_VERSION,
    }


def mark_year_end_projection_set_pending(
    conn: sqlite3.Connection,
    contexts: tuple[MusicSearchFilterContext, ...],
) -> int:
    """Mark missing/stale/failed projections pending after a job is queued.

    Existing current-version ``running`` or ``ready`` states win races with a
    worker that starts immediately after the queue write.
    """
    if not projection_tables_available(conn):
        return 0
    marked = 0
    for context in contexts:
        snapshot = conn.execute(
            """SELECT snapshot_key FROM music_search_snapshot_meta
               WHERE filter_fingerprint=? AND status='ready' AND builder_version=?""",
            (context.filter_fingerprint, MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION),
        ).fetchone()
        if snapshot is None:
            continue
        snapshot_key = str(snapshot[0])
        state = conn.execute(
            """SELECT builder_version, status
               FROM music_search_year_end_projection_state WHERE snapshot_key=?""",
            (snapshot_key,),
        ).fetchone()
        if (
            state is not None
            and str(state[0]) == YEAR_END_PROJECTION_BUILDER_VERSION
            and str(state[1]) in {"pending", "running", "ready"}
        ):
            continue
        conn.execute(
            """INSERT INTO music_search_year_end_projection_state(
                   snapshot_key, builder_version, status, built_at, last_error
               ) VALUES (?, ?, 'pending', NULL, NULL)
               ON CONFLICT(snapshot_key) DO UPDATE SET
                   builder_version=excluded.builder_version,
                   status='pending', built_at=NULL, last_error=NULL""",
            (snapshot_key, YEAR_END_PROJECTION_BUILDER_VERSION),
        )
        marked += 1
    return marked


def fail_pending_year_end_projection_set(
    conn: sqlite3.Connection,
    contexts: tuple[MusicSearchFilterContext, ...],
    *,
    error_type: str,
) -> int:
    """Expose queued projections as failed when their maintenance job aborts."""
    if not projection_tables_available(conn):
        return 0
    failed = 0
    for context in contexts:
        snapshot = conn.execute(
            """SELECT snapshot_key FROM music_search_snapshot_meta
               WHERE filter_fingerprint=? AND status='ready' AND builder_version=?""",
            (context.filter_fingerprint, MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION),
        ).fetchone()
        if snapshot is None:
            continue
        cursor = conn.execute(
            """UPDATE music_search_year_end_projection_state
               SET status='failed', built_at=datetime('now'), last_error=?
               WHERE snapshot_key=? AND builder_version=? AND status='pending'""",
            (
                error_type,
                str(snapshot[0]),
                YEAR_END_PROJECTION_BUILDER_VERSION,
            ),
        )
        failed += max(0, int(cursor.rowcount))
    return failed


def clear_year_end_projection(conn: sqlite3.Connection, snapshot_key: str) -> None:
    """Invalidate one projection inside the caller's core publish transaction."""
    if not projection_tables_available(conn):
        return
    conn.execute(
        "DELETE FROM music_search_entity_year_end WHERE snapshot_key=?",
        (snapshot_key,),
    )
    conn.execute(
        "DELETE FROM music_search_year_end_meta WHERE snapshot_key=?",
        (snapshot_key,),
    )
    conn.execute(
        "DELETE FROM music_search_year_end_projection_state WHERE snapshot_key=?",
        (snapshot_key,),
    )


def publish_year_end_projection(
    conn: sqlite3.Connection,
    snapshot_key: str,
    meta_rows: Iterable[ProjectionMetaRow],
    entity_rows: Iterable[ProjectionEntityRow],
) -> None:
    """Replace one snapshot's projection inside the caller's transaction."""
    if not projection_tables_available(conn):
        return
    conn.execute(
        "DELETE FROM music_search_entity_year_end WHERE snapshot_key=?",
        (snapshot_key,),
    )
    conn.execute(
        "DELETE FROM music_search_year_end_meta WHERE snapshot_key=?",
        (snapshot_key,),
    )
    conn.executemany(
        """INSERT INTO music_search_year_end_meta(
               snapshot_key, year, coverage_status, is_complete_year,
               observed_weeks, expected_weeks,
               first_billboard_week, last_billboard_week
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [(snapshot_key, *row) for row in meta_rows],
    )
    conn.executemany(
        """INSERT INTO music_search_entity_year_end(
               snapshot_key, family, entity_key, year,
               year_end_rank, year_end_score, peak_position,
               weeks_on_chart, weeks_at_peak, weeks_at_no1,
               weeks_top5, weeks_top10, chart_plays,
               first_week, last_week
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [(snapshot_key, *row) for row in entity_rows],
    )
    conn.execute(
        """INSERT INTO music_search_year_end_projection_state(
               snapshot_key, builder_version, status, built_at, last_error
           ) VALUES (?, ?, 'ready', datetime('now'), NULL)
           ON CONFLICT(snapshot_key) DO UPDATE SET
               builder_version=excluded.builder_version,
               status='ready', built_at=excluded.built_at, last_error=NULL""",
        (snapshot_key, YEAR_END_PROJECTION_BUILDER_VERSION),
    )


def rebuild_year_end_projection(
    conn: sqlite3.Connection,
    context: MusicSearchFilterContext,
) -> dict[str, Any]:
    """Rebuild one annual projection from its already-published exact ledger.

    State changes commit independently from the core search snapshot.  A
    projection failure is therefore observable and retryable without turning
    a valid statistics snapshot into a failed one.
    """
    if not projection_tables_available(conn):
        return {
            "status": "unavailable",
            "snapshot_key": context.filter_fingerprint,
            "row_count": 0,
        }
    snapshot_row = conn.execute(
        """SELECT snapshot_key FROM music_search_snapshot_meta
           WHERE filter_fingerprint=? AND status='ready'""",
        (context.filter_fingerprint,),
    ).fetchone()
    if snapshot_row is None:
        return {
            "status": "unavailable",
            "snapshot_key": context.filter_fingerprint,
            "row_count": 0,
        }
    snapshot_key = str(snapshot_row[0])
    conn.execute(
        """INSERT INTO music_search_year_end_projection_state(
               snapshot_key, builder_version, status, built_at, last_error
           ) VALUES (?, ?, 'running', NULL, NULL)
           ON CONFLICT(snapshot_key) DO UPDATE SET
               builder_version=excluded.builder_version,
               status='running', built_at=NULL, last_error=NULL""",
        (snapshot_key, YEAR_END_PROJECTION_BUILDER_VERSION),
    )
    conn.commit()
    try:
        candidate_keys = {
            str(row[0])
            for row in conn.execute(
                """SELECT entity_key FROM music_search_entity_context
                   WHERE snapshot_key=?""",
                (snapshot_key,),
            ).fetchall()
        }
        weekly_rows = [
            cast(WeeklyLedgerRow, tuple(row))
            for row in conn.execute(
                """SELECT family, week, entity_key, rank,
                          play_count, total_ms, stable_sort_key
                   FROM music_search_weekly_chart_context
                   WHERE snapshot_key=?
                   ORDER BY week, family, rank""",
                (snapshot_key,),
            ).fetchall()
        ]
        has_chart_facts = conn.execute(
            """SELECT 1 FROM music_search_entity_context
               WHERE snapshot_key=? AND peak_position IS NOT NULL LIMIT 1""",
            (snapshot_key,),
        ).fetchone()
        if not weekly_rows and has_chart_facts is not None:
            # Older ready snapshots may predate the compact ledger.  Backfill
            # only inside this explicit maintenance path, never from detail GET.
            from backend.domains.music_search.snapshot import (
                build_exact_weekly_ledger_for_context,
            )

            weekly_rows = build_exact_weekly_ledger_for_context(conn, context)
            with conn:
                conn.executemany(
                    """INSERT INTO music_search_weekly_chart_context(
                           snapshot_key, family, week, entity_key, rank,
                           play_count, total_ms, stable_sort_key
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    [(snapshot_key, *row) for row in weekly_rows],
                )
        meta_rows, entity_rows = build_year_end_projection_rows(
            weekly_rows,
            candidate_keys,
            track_top_n=context.bb_top_n,
            album_top_n=context.bb_album_top_n,
            artist_top_n=context.bb_artist_top_n,
            week_start_dow=context.bb_week_start_dow,
        )
        with conn:
            publish_year_end_projection(conn, snapshot_key, meta_rows, entity_rows)
        return {
            "status": "ready",
            "snapshot_key": snapshot_key,
            "year_count": len(meta_rows),
            "row_count": len(entity_rows),
            "revalidated": False,
        }
    except Exception as exc:
        conn.rollback()
        conn.execute(
            """UPDATE music_search_year_end_projection_state
               SET status='failed', built_at=datetime('now'), last_error=?
               WHERE snapshot_key=?""",
            (type(exc).__name__, snapshot_key),
        )
        conn.commit()
        raise


def ensure_year_end_projection_set(
    conn: sqlite3.Connection,
    contexts: tuple[MusicSearchFilterContext, ...],
) -> dict[str, Any]:
    """Ensure all current variants have the independently versioned projection."""
    if not projection_tables_available(conn):
        return {
            "status": "unavailable",
            "ready_count": 0,
            "failed_count": 0,
            "variants": [],
        }
    reports: list[dict[str, Any]] = []
    failed_count = 0
    for context in contexts:
        snapshot_key = context.filter_fingerprint
        row = conn.execute(
            """SELECT state.builder_version, state.status,
                      (SELECT COUNT(*) FROM music_search_entity_year_end annual
                       WHERE annual.snapshot_key=state.snapshot_key) AS row_count,
                      (SELECT COUNT(*) FROM music_search_year_end_meta meta
                       WHERE meta.snapshot_key=state.snapshot_key) AS year_count
               FROM music_search_year_end_projection_state state
               WHERE state.snapshot_key=?""",
            (snapshot_key,),
        ).fetchone()
        if (
            row is not None
            and str(row[0]) == YEAR_END_PROJECTION_BUILDER_VERSION
            and str(row[1]) == "ready"
        ):
            reports.append(
                {
                    "status": "ready",
                    "snapshot_key": snapshot_key,
                    "row_count": int(row[2]),
                    "year_count": int(row[3]),
                    "revalidated": True,
                }
            )
            continue
        try:
            reports.append(rebuild_year_end_projection(conn, context))
        except Exception as exc:
            failed_count += 1
            logger.exception("Music-search Year-End projection rebuild failed")
            reports.append(
                {
                    "status": "failed",
                    "snapshot_key": snapshot_key,
                    "row_count": 0,
                    "error_type": type(exc).__name__,
                    "revalidated": False,
                }
            )
    ready_count = sum(report["status"] == "ready" for report in reports)
    return {
        "status": "ready" if failed_count == 0 and ready_count == len(contexts) else "partial",
        "ready_count": ready_count,
        "failed_count": failed_count,
        "variants": reports,
        "builder_version": YEAR_END_PROJECTION_BUILDER_VERSION,
    }


def load_entity_year_end(
    conn: sqlite3.Connection,
    *,
    snapshot_key: str,
    family: LedgerFamily,
    entity_key: str,
    include_history: bool,
) -> dict[str, Any]:
    """Read a persisted entity projection without triggering any computation."""
    if not projection_tables_available(conn):
        return {"status": "unavailable", "summary": None, "history": []}
    state = conn.execute(
        """SELECT builder_version, status
           FROM music_search_year_end_projection_state WHERE snapshot_key=?""",
        (snapshot_key,),
    ).fetchone()
    if state is None:
        ledger_exists = conn.execute(
            "SELECT 1 FROM music_search_weekly_chart_context WHERE snapshot_key=? LIMIT 1",
            (snapshot_key,),
        ).fetchone()
        return {
            "status": "warming" if ledger_exists is not None else "unavailable",
            "summary": None,
            "history": [],
        }
    if str(state[0]) != YEAR_END_PROJECTION_BUILDER_VERSION:
        return {"status": "unavailable", "summary": None, "history": []}
    if str(state[1]) in {"pending", "running"}:
        return {"status": "warming", "summary": None, "history": []}
    if str(state[1]) != "ready":
        return {"status": "unavailable", "summary": None, "history": []}

    rows = conn.execute(
        """SELECT annual.year, annual.year_end_rank, annual.year_end_score,
                  annual.peak_position, annual.weeks_on_chart,
                  annual.weeks_at_peak, annual.weeks_at_no1,
                  annual.weeks_top5, annual.weeks_top10,
                  annual.chart_plays, annual.first_week, annual.last_week,
                  meta.coverage_status, meta.is_complete_year
           FROM music_search_entity_year_end annual
           JOIN music_search_year_end_meta meta
             ON meta.snapshot_key=annual.snapshot_key AND meta.year=annual.year
           WHERE annual.snapshot_key=? AND annual.family=? AND annual.entity_key=?
           ORDER BY annual.year DESC""",
        (snapshot_key, family, entity_key),
    ).fetchall()
    history = [dict(row) for row in rows]
    if not history:
        return {"status": "ready", "summary": None, "history": []}
    best = min(
        history,
        key=lambda row: (
            int(row["year_end_rank"]),
            -int(bool(row["is_complete_year"])),
            -int(row["year"]),
        ),
    )
    latest = history[0]
    summary = {
        "best_year": int(best["year"]),
        "best_rank": int(best["year_end_rank"]),
        "best_year_is_complete": bool(best["is_complete_year"]),
        "latest_year": int(latest["year"]),
        "latest_rank": int(latest["year_end_rank"]),
        "latest_year_is_complete": bool(latest["is_complete_year"]),
        "ranked_years": len(history),
    }
    if not include_history:
        history = []
    else:
        for row in history:
            row["is_complete_year"] = bool(row["is_complete_year"])
    return {"status": "ready", "summary": summary, "history": history}
