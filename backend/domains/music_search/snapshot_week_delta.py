"""Bounded complete-week replacement ledgers for incremental search snapshots.

This module deliberately stops at ranked weekly facts.  Lifetime metric deltas,
global chart-summary/Power recomputation, and the four-snapshot publication
transaction remain the responsibility of :mod:`snapshot_delta`.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from typing import Any, Literal, cast

import pandas as pd

from backend.domains.billboard.chart_ranking import _stable_weekly_sort
from backend.domains.imports.change_set import (
    _logical_billboard_contribution_signature,
    _rows_share_merge_run,
    build_billboard_tail_contribution_frames,
)
from backend.domains.metadata.artist_identity import canonicalize_artist_frame
from backend.domains.metadata.track_credits import get_effective_track_credit_frame
from backend.domains.music_search.context import MusicSearchFilterContext
from backend.domains.music_search.contracts import make_music_search_entity_key
from backend.domains.music_search.index import get_music_search_index_state
from backend.domains.playback.album_projects import compute_album_project_weekly_plays
from backend.domains.playback.counting import assign_logical_event_id, filter_effective_plays
from backend.domains.playback.logical_timeline import (
    PLAYBACK_TIMEZONE,
    build_billboard_weighted_frame,
    reconstruct_logical_plays,
)
from backend.domains.playback.track_groups import load_track_group_keys

WeeklyLedgerRow = tuple[str, str, str, int, int, int, str]

_EXPECTED_VARIANTS = {(level, dynamic) for level in (2, 3) for dynamic in (False, True)}
_CLOSURE_PAGE_SIZE = 256
_DEFAULT_MAX_SOURCE_ROWS = 100_000


class MusicSearchWeekDeltaIncompatibleError(RuntimeError):
    """The bounded proof is insufficient; the caller must use shared-full."""


def build_affected_complete_week_ledger_rows(
    conn: sqlite3.Connection,
    contexts: tuple[MusicSearchFilterContext, ...],
    *,
    change_generation_id: str,
    affected_weeks: Iterable[str],
    current_open_week: str,
    max_source_rows: int = _DEFAULT_MAX_SOURCE_ROWS,
) -> dict[str, list[WeeklyLedgerRow]]:
    """Build exact Top-N replacement rows for affected, completed weeks.

    Only the raw rows whose inferred listening intervals can overlap the
    affected range are selected.  The selected span is then extended to both
    ends of its adjacent logical merge run.  A cap turns unexpectedly broad
    scopes into an explicit shared-full fallback instead of a lifetime scan.
    """

    representative = _validate_context_set(contexts)
    if not change_generation_id.strip():
        raise MusicSearchWeekDeltaIncompatibleError("missing change generation")
    if max_source_rows <= 0:
        raise ValueError("max_source_rows must be positive")
    supplied_weeks = _normalise_week_keys(affected_weeks)
    complete_weeks = _complete_week_keys(supplied_weeks, current_open_week)
    _validate_week_scope(complete_weeks, representative.bb_week_start_dow)
    empty: dict[str, list[WeeklyLedgerRow]] = {
        context.filter_fingerprint: [] for context in contexts
    }
    if not complete_weeks:
        return empty

    _assert_tail_scope(
        conn,
        contexts,
        change_generation_id=change_generation_id,
        supplied_weeks=supplied_weeks,
    )
    raw = _load_bounded_tail_closure(
        conn,
        complete_weeks,
        week_start_hour=representative.bb_week_start_hour,
        max_gap_minutes=representative.max_merge_gap_minutes,
        max_source_rows=max_source_rows,
    )
    if raw.empty:
        return empty

    candidate_generation = str(get_music_search_index_state(conn).get("active_generation_id") or "")
    if not candidate_generation:
        raise MusicSearchWeekDeltaIncompatibleError("candidate generation is unavailable")

    logical_by_threshold: dict[bool, pd.DataFrame] = {}
    for dynamic_threshold in (False, True):
        logical_by_threshold[dynamic_threshold] = _logical_events(
            conn,
            raw,
            min_ms=representative.min_ms,
            dynamic_threshold=dynamic_threshold,
            max_gap_minutes=representative.max_merge_gap_minutes,
        )

    result: dict[str, list[WeeklyLedgerRow]] = {}
    for context in contexts:
        ranked = _ranked_rows_for_context(
            conn,
            context,
            logical_by_threshold[context.dynamic_threshold],
            complete_weeks,
        )
        result[context.filter_fingerprint] = _encode_ledger_rows(
            conn,
            context,
            ranked,
            candidate_generation=candidate_generation,
        )
    return result


def _validate_context_set(
    contexts: tuple[MusicSearchFilterContext, ...],
) -> MusicSearchFilterContext:
    if not contexts or {(c.merge_level, c.dynamic_threshold) for c in contexts} != (
        _EXPECTED_VARIANTS
    ):
        raise MusicSearchWeekDeltaIncompatibleError("complete four-variant context set is required")
    if len(contexts) != 4 or len({c.filter_fingerprint for c in contexts}) != 4:
        raise MusicSearchWeekDeltaIncompatibleError("snapshot contexts are not unique")
    if len({c.semantic_base_key for c in contexts}) != 1:
        raise MusicSearchWeekDeltaIncompatibleError(
            "snapshot contexts do not share one semantic base"
        )
    representative = contexts[0]
    common_fields = (
        "min_ms",
        "music_only",
        "merge_enabled",
        "max_merge_gap_minutes",
        "bb_week_start_dow",
        "bb_week_start_hour",
        "include_compilations",
        "bb_top_n",
        "bb_album_top_n",
        "bb_artist_top_n",
    )
    if any(
        any(getattr(context, field) != getattr(representative, field) for field in common_fields)
        for context in contexts[1:]
    ):
        raise MusicSearchWeekDeltaIncompatibleError("snapshot contexts have divergent policies")
    if not representative.merge_enabled or not representative.music_only:
        raise MusicSearchWeekDeltaIncompatibleError(
            "bounded week replacement currently requires merge-enabled music-only policy"
        )
    if representative.max_merge_gap_minutes is None or representative.max_merge_gap_minutes < 0:
        raise MusicSearchWeekDeltaIncompatibleError("merge closure is not bounded")
    return representative


def _normalise_week_keys(weeks: Iterable[str]) -> set[str]:
    result: set[str] = set()
    for raw in weeks:
        try:
            value = pd.Timestamp(str(raw)).date().isoformat()
        except (TypeError, ValueError):
            raise MusicSearchWeekDeltaIncompatibleError("invalid affected Billboard week") from None
        if value != str(raw):
            raise MusicSearchWeekDeltaIncompatibleError("non-canonical affected Billboard week")
        result.add(value)
    return result


def _complete_week_keys(affected_weeks: set[str], current_open_week: str) -> set[str]:
    try:
        open_key = pd.Timestamp(current_open_week).date().isoformat()
    except (TypeError, ValueError):
        raise MusicSearchWeekDeltaIncompatibleError("invalid current open week") from None
    if open_key != current_open_week:
        raise MusicSearchWeekDeltaIncompatibleError("non-canonical current open week")
    future = {week for week in affected_weeks if week > open_key}
    if future:
        raise MusicSearchWeekDeltaIncompatibleError("affected scope extends beyond the open week")
    return {week for week in affected_weeks if week < open_key}


def _validate_week_scope(complete_weeks: set[str], week_start_dow: int) -> None:
    ordered = sorted(pd.Timestamp(week) for week in complete_weeks)
    if any(int(week.dayofweek) != int(week_start_dow) for week in ordered):
        raise MusicSearchWeekDeltaIncompatibleError(
            "affected week violates the configured boundary"
        )
    if any(right - left != pd.Timedelta(days=7) for left, right in zip(ordered, ordered[1:])):
        raise MusicSearchWeekDeltaIncompatibleError(
            "non-contiguous affected-week scope is unbounded"
        )


def _assert_tail_scope(
    conn: sqlite3.Connection,
    contexts: tuple[MusicSearchFilterContext, ...],
    *,
    change_generation_id: str,
    supplied_weeks: set[str],
) -> None:
    representative = contexts[0]
    for dynamic_threshold in (False, True):
        old, new = build_billboard_tail_contribution_frames(
            conn,
            generation_id=change_generation_id,
            min_ms=representative.min_ms,
            music_only=representative.music_only,
            dynamic_threshold=dynamic_threshold,
            max_gap_minutes=int(representative.max_merge_gap_minutes),
        )
        old_signature = _logical_billboard_contribution_signature(
            old,
            week_start_dow=representative.bb_week_start_dow,
            week_start_hour=representative.bb_week_start_hour,
        )
        new_signature = _logical_billboard_contribution_signature(
            new,
            week_start_dow=representative.bb_week_start_dow,
            week_start_hour=representative.bb_week_start_hour,
        )
        changed = {
            str(key[0])
            for key in old_signature.keys() | new_signature.keys()
            if old_signature.get(key) != new_signature.get(key)
        }
        if not changed.issubset(supplied_weeks):
            raise MusicSearchWeekDeltaIncompatibleError(
                "tail contribution escaped the proven affected-week scope"
            )


_RAW_SELECT = """SELECT p.play_id, p.ts, p.ts_date, p.ts_dow, p.ts_hour,
                         p.ms_played, p.track_id, p.source_album_id,
                         t.album_id AS track_album_id, t.track_name, t.artist_id,
                         a.artist_name, al.album_name,
                         al_src.album_name AS source_album_name, stm.duration_ms
                  FROM plays p
                  JOIN tracks t ON p.track_id=t.track_id
                  JOIN artists a ON t.artist_id=a.artist_id
                  LEFT JOIN albums al ON t.album_id=al.album_id
                  LEFT JOIN albums al_src ON p.source_album_id=al_src.album_id
                  LEFT JOIN spotify_track_meta stm
                    ON t.spotify_track_id=stm.spotify_track_id"""


def _utc_week_boundary(week: str, week_start_hour: int) -> pd.Timestamp:
    local_boundary = pd.Timestamp(week).tz_localize(PLAYBACK_TIMEZONE)
    return (local_boundary + pd.Timedelta(hours=week_start_hour)).tz_convert("UTC")


def _load_bounded_tail_closure(
    conn: sqlite3.Connection,
    complete_weeks: set[str],
    *,
    week_start_hour: int,
    max_gap_minutes: int,
    max_source_rows: int,
) -> pd.DataFrame:
    earliest = min(complete_weeks)
    latest = max(complete_weeks)
    start = _utc_week_boundary(earliest, week_start_hour)
    end = _utc_week_boundary(latest, week_start_hour) + pd.Timedelta(days=7)
    start_text = start.isoformat().replace("+00:00", "Z")
    end_text = end.isoformat().replace("+00:00", "Z")

    # Every row ending inside the range overlaps it. Rows ending later are
    # selected only when their own inferred interval starts before range end.
    seeds = conn.execute(
        f"""{_RAW_SELECT}
             WHERE p.ts>=?
               AND julianday(p.ts) - MAX(COALESCE(p.ms_played, 0), 0) / 86400000.0
                   < julianday(?)
             ORDER BY p.ts, p.play_id LIMIT ?""",
        (start_text, end_text, max_source_rows + 1),
    ).fetchall()
    if len(seeds) > max_source_rows:
        raise MusicSearchWeekDeltaIncompatibleError("bounded week source row cap exceeded")
    if not seeds:
        return pd.DataFrame()

    first = dict(seeds[0])
    last = dict(seeds[-1])
    span = conn.execute(
        f"""{_RAW_SELECT}
             WHERE ((p.ts>? OR (p.ts=? AND p.play_id>=?))
               AND (p.ts<? OR (p.ts=? AND p.play_id<=?)))
             ORDER BY p.ts, p.play_id LIMIT ?""",
        (
            first["ts"],
            first["ts"],
            first["play_id"],
            last["ts"],
            last["ts"],
            last["play_id"],
            max_source_rows + 1,
        ),
    ).fetchall()
    if len(span) > max_source_rows:
        raise MusicSearchWeekDeltaIncompatibleError("bounded week source span cap exceeded")
    rows = [dict(row) for row in span]
    rows = _extend_preceding_chain(conn, rows, max_gap_minutes, max_source_rows)
    rows = _extend_following_chain(conn, rows, max_gap_minutes, max_source_rows)
    if len(rows) > max_source_rows:
        raise MusicSearchWeekDeltaIncompatibleError("logical merge closure row cap exceeded")
    return pd.DataFrame.from_records(rows)


def _extend_preceding_chain(
    conn: sqlite3.Connection,
    rows: list[dict[str, Any]],
    max_gap_minutes: int,
    cap: int,
) -> list[dict[str, Any]]:
    cursor = rows[0]
    preceding: list[dict[str, Any]] = []
    while len(rows) + len(preceding) <= cap:
        page = conn.execute(
            f"""{_RAW_SELECT}
                 WHERE p.ts<? OR (p.ts=? AND p.play_id<?)
                 ORDER BY p.ts DESC, p.play_id DESC LIMIT ?""",
            (cursor["ts"], cursor["ts"], cursor["play_id"], _CLOSURE_PAGE_SIZE),
        ).fetchall()
        if not page:
            break
        continued = False
        for raw in page:
            prior = dict(raw)
            if not _rows_share_merge_run(prior, cursor, max_gap_minutes=max_gap_minutes):
                return [*reversed(preceding), *rows]
            preceding.append(prior)
            cursor = prior
            continued = True
            if len(rows) + len(preceding) > cap:
                raise MusicSearchWeekDeltaIncompatibleError("preceding merge chain cap exceeded")
        if not continued or len(page) < _CLOSURE_PAGE_SIZE:
            break
    return [*reversed(preceding), *rows]


def _extend_following_chain(
    conn: sqlite3.Connection,
    rows: list[dict[str, Any]],
    max_gap_minutes: int,
    cap: int,
) -> list[dict[str, Any]]:
    cursor = rows[-1]
    following: list[dict[str, Any]] = []
    while len(rows) + len(following) <= cap:
        page = conn.execute(
            f"""{_RAW_SELECT}
                 WHERE p.ts>? OR (p.ts=? AND p.play_id>?)
                 ORDER BY p.ts, p.play_id LIMIT ?""",
            (cursor["ts"], cursor["ts"], cursor["play_id"], _CLOSURE_PAGE_SIZE),
        ).fetchall()
        if not page:
            break
        continued = False
        for raw in page:
            successor = dict(raw)
            if not _rows_share_merge_run(cursor, successor, max_gap_minutes=max_gap_minutes):
                return [*rows, *following]
            following.append(successor)
            cursor = successor
            continued = True
            if len(rows) + len(following) > cap:
                raise MusicSearchWeekDeltaIncompatibleError("following merge chain cap exceeded")
        if not continued or len(page) < _CLOSURE_PAGE_SIZE:
            break
    return [*rows, *following]


def _logical_events(
    conn: sqlite3.Connection,
    raw: pd.DataFrame,
    *,
    min_ms: int,
    dynamic_threshold: bool,
    max_gap_minutes: int,
) -> pd.DataFrame:
    events = reconstruct_logical_plays(
        raw,
        min_ms,
        dynamic_threshold=dynamic_threshold,
        max_gap_minutes=max_gap_minutes,
        boundary_column="source_album_id",
    )
    if min_ms > 0:
        events = filter_effective_plays(
            events,
            min_ms=min_ms,
            dynamic_threshold=dynamic_threshold,
        )
    return canonicalize_artist_frame(events, conn, dedupe=False)


def _ranked_rows_for_context(
    conn: sqlite3.Connection,
    context: MusicSearchFilterContext,
    logical: pd.DataFrame,
    complete_weeks: set[str],
) -> dict[str, pd.DataFrame]:
    if logical.empty:
        return {"track": pd.DataFrame(), "album": pd.DataFrame(), "artist": pd.DataFrame()}
    primary = logical.copy()
    if "source_album_name" in primary.columns:
        primary["album_name"] = primary["source_album_name"].fillna(primary["album_name"])
    from backend.domains.music_search.snapshot import _ordinary_album_chart_has_track_fallback

    if not _ordinary_album_chart_has_track_fallback(conn, context):
        primary = primary.drop(columns=["track_album_id"], errors="ignore")
    weighted = build_billboard_weighted_frame(
        primary,
        week_start_dow=context.bb_week_start_dow,
        week_start_hour=context.bb_week_start_hour,
    )
    weighted = weighted[weighted["billboard_week"].astype(str).isin(complete_weeks)].copy()

    artist_events = assign_logical_event_id(logical.copy())
    credits = get_effective_track_credit_frame(
        conn, {int(value) for value in artist_events["track_id"].dropna().unique()}
    )
    artist_events = artist_events.drop(
        columns=["artist_id", "artist_name", "raw_artist_id", "raw_artist_name"],
        errors="ignore",
    )
    artist_events = artist_events.merge(
        credits[["track_id", "artist_id", "raw_artist_id", "artist_name"]],
        on="track_id",
        how="inner",
    )
    artist_events["artist_id"] = artist_events["raw_artist_id"]
    artist_events = artist_events.drop(columns=["raw_artist_id"])
    artist_events = canonicalize_artist_frame(artist_events, conn)
    artist_weighted = build_billboard_weighted_frame(
        artist_events,
        week_start_dow=context.bb_week_start_dow,
        week_start_hour=context.bb_week_start_hour,
    )
    artist_weighted = artist_weighted[
        artist_weighted["billboard_week"].astype(str).isin(complete_weeks)
    ].copy()
    return {
        "track": _rank_track_weekly(conn, weighted, context),
        "album": _rank_album_weekly(conn, weighted, context),
        "artist": _rank_artist_weekly(artist_weighted, context),
    }


def _rank_track_weekly(
    conn: sqlite3.Connection,
    weighted: pd.DataFrame,
    context: MusicSearchFilterContext,
) -> pd.DataFrame:
    frame = weighted.copy()
    if frame.empty:
        return frame
    if context.merge_level > 1:
        keys = load_track_group_keys(conn, context.merge_level)
        if not keys.empty:
            conflicts = keys.groupby("track_id")["track_agg_id"].nunique()
            if (conflicts > 1).any():
                raise MusicSearchWeekDeltaIncompatibleError("conflicting track-group identity")
            keys = keys.drop_duplicates("track_id")
            frame = frame.merge(
                keys[["track_id", "track_agg_id", "track_agg_name"]],
                on="track_id",
                how="left",
                validate="many_to_one",
            )
            mapped = frame["track_agg_id"].notna()
            frame.loc[mapped, "track_id"] = frame.loc[mapped, "track_agg_id"].astype(int)
            frame.loc[mapped, "track_name"] = frame.loc[mapped, "track_agg_name"]
    group = ["billboard_week", "track_id", "track_name", "artist_name"]
    ranked = (
        frame.groupby(group)
        .agg(play_count=("play_count", "sum"), total_ms=("total_ms", "sum"))
        .reset_index()
    )
    ranked = ranked[ranked["play_count"] > 0]
    ranked = _stable_weekly_sort(
        ranked,
        id_columns=("track_id",),
        text_columns=("artist_name", "track_name"),
    )
    ranked["rank"] = ranked.groupby("billboard_week").cumcount() + 1
    return ranked[ranked["rank"] <= context.bb_top_n]


def _rank_album_weekly(
    conn: sqlite3.Connection,
    weighted: pd.DataFrame,
    context: MusicSearchFilterContext,
) -> pd.DataFrame:
    ranked = compute_album_project_weekly_plays(
        weighted,
        conn,
        merge_level=context.merge_level,
        include_compilations=context.include_compilations,
        billboard_mode=True,
    )
    if ranked.empty:
        return ranked
    ranked = ranked.rename(columns={"album_project_name": "album_name"})
    ranked = ranked[ranked["play_count"] > 0]
    ranked = _stable_weekly_sort(
        ranked,
        id_columns=("album_project_id", "album_id"),
        text_columns=("artist_name", "album_name"),
    )
    ranked["rank"] = ranked.groupby("billboard_week").cumcount() + 1
    return ranked[ranked["rank"] <= context.bb_album_top_n]


def _rank_artist_weekly(
    weighted: pd.DataFrame,
    context: MusicSearchFilterContext,
) -> pd.DataFrame:
    if weighted.empty:
        return weighted
    group = ["billboard_week", "artist_id", "artist_name"]
    ranked = (
        weighted.groupby(group)
        .agg(play_count=("play_count", "sum"), total_ms=("total_ms", "sum"))
        .reset_index()
    )
    ranked = ranked[ranked["play_count"] > 0]
    ranked = _stable_weekly_sort(
        ranked,
        id_columns=("artist_id",),
        text_columns=("artist_name",),
    )
    ranked["rank"] = ranked.groupby("billboard_week").cumcount() + 1
    return ranked[ranked["rank"] <= context.bb_artist_top_n]


def _candidate_keys(
    conn: sqlite3.Connection,
    context: MusicSearchFilterContext,
    candidate_generation: str,
) -> dict[str, set[str]]:
    album_kind = "album" if context.merge_level <= 1 else "album_project"
    rows = conn.execute(
        """SELECT entity_key, kind FROM music_search_documents
           WHERE generation_id=? AND kind IN ('track', ?, 'artist')
             AND (kind!='track' OR merge_level=?)""",
        (candidate_generation, album_kind, context.merge_level),
    ).fetchall()
    result: dict[str, set[str]] = {"track": set(), "album": set(), "artist": set()}
    for row in rows:
        family = "album" if str(row[1]) in {"album", "album_project"} else str(row[1])
        result[family].add(str(row[0]))
    return result


def _encode_ledger_rows(
    conn: sqlite3.Connection,
    context: MusicSearchFilterContext,
    ranked: dict[str, pd.DataFrame],
    *,
    candidate_generation: str,
) -> list[WeeklyLedgerRow]:
    candidates = _candidate_keys(conn, context, candidate_generation)
    album_kind: Literal["album", "album_project"] = (
        "album" if context.merge_level <= 1 else "album_project"
    )
    encoded: dict[tuple[str, str, str], WeeklyLedgerRow] = {}
    for family, frame in ranked.items():
        for row in frame.itertuples(index=False):
            entity_id = int(
                getattr(
                    row,
                    {"track": "track_id", "album": "album_project_id", "artist": "artist_id"}[
                        family
                    ],
                )
            )
            kind = family if family != "album" else album_kind
            entity_key = make_music_search_entity_key(cast(Any, kind), entity_id)
            if entity_key not in candidates[family]:
                raise MusicSearchWeekDeltaIncompatibleError(
                    f"ranked {family} identity is absent from the candidate generation"
                )
            payload: dict[str, Any] = {"entity_id": entity_id}
            if family == "track":
                payload.update(track_name=row.track_name, artist_name=row.artist_name)
            elif family == "album":
                payload.update(album_name=row.album_name, artist_name=row.artist_name)
            else:
                payload.update(artist_name=row.artist_name)
            ledger_row: WeeklyLedgerRow = (
                family,
                str(row.billboard_week),
                entity_key,
                int(cast(Any, row.rank)),
                int(cast(Any, row.play_count)),
                int(cast(Any, row.total_ms)),
                json.dumps(
                    payload,
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                ),
            )
            identity = ledger_row[:3]
            if identity in encoded and encoded[identity] != ledger_row:
                raise MusicSearchWeekDeltaIncompatibleError(
                    "one candidate identity has conflicting weekly ranking facts"
                )
            encoded[cast(tuple[str, str, str], identity)] = ledger_row
    rows = sorted(encoded.values(), key=lambda row: (row[0], row[1], row[3], row[2]))
    ranks = [(row[0], row[1], row[3]) for row in rows]
    if len(ranks) != len(set(ranks)):
        raise MusicSearchWeekDeltaIncompatibleError("duplicate weekly rank")
    return rows
