"""Bounded artist-statistics maintenance for track-credit membership changes.

The mutation log contains canonical before/after credit membership.  This
module uses that evidence to recompute only the changed canonical-track
closure and the complete Billboard weeks touched by those tracks.  Publication
is one transaction: the old aggregate and all serving snapshot pointers remain
untouched when a bounded proof cannot be established.
"""

from __future__ import annotations

import logging
import sqlite3
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, cast

import pandas as pd

from backend.core import config
from backend.core.db import _agg_param_hash, _aggregation_semantic_dependencies
from backend.domains.billboard.data_loader import _track_identity_sql
from backend.domains.billboard.week_coverage import (
    open_billboard_week_for_latest_timestamp,
)
from backend.domains.metadata.artist_identity import get_identity_revision
from backend.domains.metadata.track_identity import get_track_identity_revision
from backend.domains.music_search.context import (
    MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
    MusicSearchFilterContext,
    music_search_snapshot_policy_key,
)
from backend.domains.music_search.contracts import make_music_search_entity_key
from backend.domains.music_search.index import get_music_search_index_state
from backend.domains.music_search.snapshot import (
    _activate_snapshot_variant,
    _assert_shared_full_publish_fence,
    _validate_context_rows,
    _validate_shared_full_contexts,
)
from backend.domains.music_search.snapshot_delta import (
    _base_weekly_ledger_rows,
    _candidate_keys_for_context,
)
from backend.domains.music_search.snapshot_ledger import (
    WeeklyLedgerValidationError,
    rebuild_context_rows_from_weekly_ledger,
)
from backend.domains.music_search.snapshot_lineage import (
    active_playback_lineage,
    music_search_snapshot_dependency_digest,
)
from backend.domains.music_search.snapshot_week_delta import (
    MusicSearchWeekDeltaIncompatibleError,
    _encode_ledger_rows,
    _load_bounded_tail_closure,
    _logical_events,
    _ranked_rows_for_context,
)
from backend.domains.music_search.year_end_projection import clear_year_end_projection
from backend.domains.playback.logical_timeline import (
    build_billboard_weighted_frame,
    reconstruct_logical_plays,
)

logger = logging.getLogger(__name__)

_EXPECTED_VARIANTS = {(level, dynamic) for level in (2, 3) for dynamic in (False, True)}
_DEFAULT_MAX_CHANGED_ROWS = 100_000
_DEFAULT_MAX_AFFECTED_WEEKS = 260


class TrackCreditDeltaIncompatibleError(RuntimeError):
    """A safe bounded proof is unavailable; the caller must use shared-full."""


@dataclass(frozen=True)
class _CreditScope:
    track_id: int
    canonical_track_ids: tuple[int, ...]
    before_artist_ids: tuple[int, ...]
    after_artist_ids: tuple[int, ...]


def _artist_ids(rows: object) -> tuple[int, ...]:
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise TrackCreditDeltaIncompatibleError("invalid credit membership evidence")
    result: set[int] = set()
    for row in rows:
        if not isinstance(row, Mapping) or "artist_id" not in row:
            raise TrackCreditDeltaIncompatibleError("invalid credit membership row")
        artist_id = int(row["artist_id"])
        if artist_id <= 0:
            raise TrackCreditDeltaIncompatibleError("invalid canonical artist identity")
        result.add(artist_id)
    return tuple(sorted(result))


def _credit_scopes(change_sets: Sequence[Mapping[str, Any]]) -> tuple[_CreditScope, ...]:
    """Collapse a contiguous revision range to one net scope per track."""
    if not change_sets:
        raise TrackCreditDeltaIncompatibleError("missing track-credit change-set evidence")
    ordered = sorted(change_sets, key=lambda row: int(row.get("to_revision") or -1))
    expected = int(ordered[0].get("from_revision") or -1)
    by_track: dict[int, dict[str, Any]] = {}
    for change in ordered:
        from_revision = int(change.get("from_revision") or -1)
        to_revision = int(change.get("to_revision") or -1)
        if from_revision != expected or to_revision != from_revision + 1:
            raise TrackCreditDeltaIncompatibleError("non-contiguous track-credit revision range")
        expected = to_revision
        track_id = int(change.get("track_id") or 0)
        canonical_ids = tuple(
            sorted({int(value) for value in change.get("canonical_track_ids", ())})
        )
        if track_id <= 0 or not canonical_ids or any(value <= 0 for value in canonical_ids):
            raise TrackCreditDeltaIncompatibleError("invalid changed canonical-track scope")
        before_ids = _artist_ids(change.get("before_credits"))
        after_ids = _artist_ids(change.get("after_credits"))
        current = by_track.get(track_id)
        if current is None:
            by_track[track_id] = {
                "canonical": canonical_ids,
                "before": before_ids,
                "after": after_ids,
            }
            continue
        if tuple(current["canonical"]) != canonical_ids:
            raise TrackCreditDeltaIncompatibleError(
                "canonical-track scope changed within revision range"
            )
        if tuple(current["after"]) != before_ids:
            raise TrackCreditDeltaIncompatibleError("credit before/after chain is incomplete")
        current["after"] = after_ids

    owners: dict[int, int] = {}
    scopes: list[_CreditScope] = []
    for track_id, values in sorted(by_track.items()):
        for canonical_id in values["canonical"]:
            previous = owners.setdefault(int(canonical_id), track_id)
            if previous != track_id:
                raise TrackCreditDeltaIncompatibleError("overlapping canonical-track change scopes")
        before_ids = tuple(values["before"])
        after_ids = tuple(values["after"])
        if before_ids == after_ids:
            continue
        scopes.append(
            _CreditScope(
                track_id=track_id,
                canonical_track_ids=tuple(values["canonical"]),
                before_artist_ids=before_ids,
                after_artist_ids=after_ids,
            )
        )
    return tuple(scopes)


def _validate_contexts(
    contexts: tuple[MusicSearchFilterContext, ...],
) -> MusicSearchFilterContext:
    try:
        _validate_shared_full_contexts(contexts)
    except ValueError as exc:
        raise TrackCreditDeltaIncompatibleError(str(exc)) from exc
    if {(item.merge_level, item.dynamic_threshold) for item in contexts} != _EXPECTED_VARIANTS:
        raise TrackCreditDeltaIncompatibleError("complete four-variant context set is required")
    representative = contexts[0]
    if not representative.merge_enabled or not representative.music_only:
        raise TrackCreditDeltaIncompatibleError(
            "credit delta currently requires merge-enabled music-only policy"
        )
    if representative.max_merge_gap_minutes < 0:
        raise TrackCreditDeltaIncompatibleError("logical merge closure is not bounded")
    return representative


def _load_changed_raw_rows(
    conn: sqlite3.Connection,
    scopes: tuple[_CreditScope, ...],
    *,
    max_source_rows: int,
) -> pd.DataFrame:
    """Load only changed identities, plus global adjacency proof per selected row."""
    if max_source_rows <= 0:
        raise ValueError("max_source_rows must be positive")
    representative_ids = sorted({scope.track_id for scope in scopes})
    canonical_ids = sorted(
        {canonical for scope in scopes for canonical in scope.canonical_track_ids}
    )
    identity_columns, identity_joins, spotify_id_expr = _track_identity_sql(conn)
    rep_marks = ",".join("?" for _ in representative_ids)
    canonical_marks = ",".join("?" for _ in canonical_ids)
    rows = conn.execute(
        f"""SELECT projected.*,
                   (SELECT prior.play_id FROM plays prior
                    WHERE prior.ts < projected.ts
                       OR (prior.ts=projected.ts AND prior.play_id<projected.play_id)
                    ORDER BY prior.ts DESC, prior.play_id DESC LIMIT 1) AS previous_play_id
              FROM (
                SELECT p.play_id, p.ts, p.ts_date, p.ts_dow, p.ts_hour,
                       p.ms_played, {identity_columns}, p.source_album_id,
                       t.album_id AS track_album_id, t.track_name, t.artist_id,
                       a.artist_name, al.album_name,
                       al_src.album_name AS source_album_name, stm.duration_ms
                  FROM plays p
                  {identity_joins}
                  LEFT JOIN artists a ON t.artist_id=a.artist_id
                  LEFT JOIN albums al ON t.album_id=al.album_id
                  LEFT JOIN albums al_src ON p.source_album_id=al_src.album_id
                  LEFT JOIN spotify_track_meta stm
                    ON {spotify_id_expr}=stm.spotify_track_id
              ) projected
             WHERE projected.representative_track_id IN ({rep_marks})
                OR projected.track_id IN ({canonical_marks})
             ORDER BY projected.ts, projected.play_id LIMIT ?""",
        (*representative_ids, *canonical_ids, max_source_rows + 1),
    ).fetchall()
    if len(rows) > max_source_rows:
        raise TrackCreditDeltaIncompatibleError("changed canonical-track row cap exceeded")
    if not rows:
        return pd.DataFrame()
    result = pd.DataFrame.from_records([dict(row) for row in rows])
    result = result.drop_duplicates("play_id", keep="first").reset_index(drop=True)

    scope_by_rep = {scope.track_id: index for index, scope in enumerate(scopes)}
    scope_ids: list[int] = []
    segments: list[int] = []
    segment = -1
    prior_selected: int | None = None
    prior_scope: int | None = None
    for row in result.itertuples(index=False):
        scope_id = scope_by_rep.get(int(cast(Any, row.representative_track_id)))
        if scope_id is None:
            raise TrackCreditDeltaIncompatibleError(
                "credit mutation does not target the effective representative track"
            )
        globally_adjacent = (
            prior_selected is not None
            and int(cast(Any, row.previous_play_id or 0)) == prior_selected
        )
        if not globally_adjacent or prior_scope != scope_id:
            segment += 1
        scope_ids.append(scope_id)
        segments.append(segment)
        prior_selected = int(cast(Any, row.play_id))
        prior_scope = scope_id
    result["_credit_scope"] = scope_ids
    result["_global_segment"] = segments
    return result


def _logical_by_threshold(
    raw: pd.DataFrame,
    representative: MusicSearchFilterContext,
) -> dict[bool, pd.DataFrame]:
    result: dict[bool, pd.DataFrame] = {}
    for dynamic in (False, True):
        logical = reconstruct_logical_plays(
            raw,
            representative.min_ms,
            dynamic_threshold=dynamic,
            max_gap_minutes=representative.max_merge_gap_minutes,
            boundary_column=("source_album_id", "_credit_scope", "_global_segment"),
        )
        result[dynamic] = logical
    return result


def _signed_artist_facts(
    logical: pd.DataFrame,
    scopes: tuple[_CreditScope, ...],
    *,
    week_start_dow: int,
    week_start_hour: int,
) -> tuple[dict[int, tuple[int, int]], dict[tuple[str, int], tuple[int, int]]]:
    lifetime: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    weekly: dict[tuple[str, int], list[int]] = defaultdict(lambda: [0, 0])
    if logical.empty:
        return {}, {}
    for scope_id, frame in logical.groupby("_credit_scope", sort=False):
        scope = scopes[int(cast(Any, scope_id))]
        signs: dict[int, int] = defaultdict(int)
        for artist_id in scope.before_artist_ids:
            signs[artist_id] -= 1
        for artist_id in scope.after_artist_ids:
            signs[artist_id] += 1
        signs = {artist_id: sign for artist_id, sign in signs.items() if sign}
        if not signs:
            continue
        plays = len(frame)
        total_ms = int(pd.to_numeric(frame["ms_played"], errors="coerce").fillna(0).sum())
        weighted = build_billboard_weighted_frame(
            frame,
            week_start_dow=week_start_dow,
            week_start_hour=week_start_hour,
        )
        per_week = (
            weighted.groupby("billboard_week", sort=False)[["play_count", "total_ms"]].sum()
            if not weighted.empty
            else pd.DataFrame()
        )
        for artist_id, sign in signs.items():
            lifetime[artist_id][0] += sign * plays
            lifetime[artist_id][1] += sign * total_ms
            for week, values in per_week.iterrows():
                key = (str(pd.Timestamp(cast(Any, week)).date()), artist_id)
                weekly[key][0] += sign * int(values.play_count)
                weekly[key][1] += sign * int(values.total_ms)
    return (
        {key: (value[0], value[1]) for key, value in lifetime.items() if value != [0, 0]},
        {key: (value[0], value[1]) for key, value in weekly.items() if value != [0, 0]},
    )


def _base_snapshot_keys(
    conn: sqlite3.Connection,
    contexts: tuple[MusicSearchFilterContext, ...],
    *,
    active_credit_revision: int,
    source_dataset_digest: str,
) -> dict[str, str]:
    result: dict[str, str] = {}
    for context in contexts:
        row = conn.execute(
            """SELECT state.active_snapshot_key, meta.status, meta.builder_version,
                      meta.merge_level, meta.dynamic_threshold, meta.policy_key,
                      meta.source_dataset_digest, meta.build_strategy
                 FROM music_search_snapshot_variant_state state
                 JOIN music_search_snapshot_meta meta
                   ON meta.snapshot_key=state.active_snapshot_key
                WHERE state.merge_level=? AND state.dynamic_threshold=?""",
            (context.merge_level, int(context.dynamic_threshold)),
        ).fetchone()
        if (
            row is None
            or str(row[1]) not in {"ready", "stale"}
            or str(row[2]) != MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION
            or int(row[3]) != context.merge_level
            or bool(row[4]) != context.dynamic_threshold
            or str(row[5] or "")
            != music_search_snapshot_policy_key(
                replace(context, track_credit_revision=active_credit_revision)
            )
            or str(row[6] or "") != source_dataset_digest
            or str(row[7] or "") not in {"shared_full", "delta", "credit_delta"}
        ):
            raise TrackCreditDeltaIncompatibleError("verified serving snapshot base is unavailable")
        base_key = str(row[0])
        if base_key == context.filter_fingerprint:
            raise TrackCreditDeltaIncompatibleError(
                "credit delta target already serves as its base"
            )
        if not conn.execute(
            "SELECT 1 FROM music_search_entity_context WHERE snapshot_key=? LIMIT 1",
            (base_key,),
        ).fetchone():
            raise TrackCreditDeltaIncompatibleError("serving snapshot payload is empty")
        ledger_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM music_search_weekly_chart_context WHERE snapshot_key=?",
                (base_key,),
            ).fetchone()[0]
        )
        has_chart_fact = conn.execute(
            """SELECT 1 FROM music_search_entity_context
                 WHERE snapshot_key=? AND peak_position IS NOT NULL LIMIT 1""",
            (base_key,),
        ).fetchone()
        if has_chart_fact is not None and ledger_count == 0:
            raise TrackCreditDeltaIncompatibleError(
                "serving snapshot lacks a reusable chart ledger"
            )
        result[context.filter_fingerprint] = base_key
    if len(set(result.values())) != 4:
        raise TrackCreditDeltaIncompatibleError("serving snapshot bases are incomplete")
    return result


def _clone_lifetime_with_artist_delta(
    conn: sqlite3.Connection,
    *,
    base_key: str,
    artist_delta: Mapping[int, tuple[int, int]],
    candidate_keys: set[str],
) -> dict[str, tuple[int, int]]:
    metrics = {
        str(row[0]): (int(row[1]), int(row[2]))
        for row in conn.execute(
            """SELECT entity_key, play_events, total_ms
                 FROM music_search_entity_context WHERE snapshot_key=?""",
            (base_key,),
        ).fetchall()
    }
    if not set(metrics) <= candidate_keys:
        raise TrackCreditDeltaIncompatibleError("serving facts are absent from candidate index")
    for artist_id, (play_delta, ms_delta) in artist_delta.items():
        entity_key = make_music_search_entity_key("artist", artist_id)
        if entity_key not in candidate_keys:
            raise TrackCreditDeltaIncompatibleError("changed artist is absent from candidate index")
        plays, total_ms = metrics.get(entity_key, (0, 0))
        updated = (plays + play_delta, total_ms + ms_delta)
        if updated[0] < 0 or updated[1] < 0:
            raise TrackCreditDeltaIncompatibleError("artist lifetime delta would become negative")
        if updated == (0, 0):
            metrics.pop(entity_key, None)
        else:
            metrics[entity_key] = updated
    return metrics


def _artist_replacement_ledger(
    conn: sqlite3.Connection,
    contexts: tuple[MusicSearchFilterContext, ...],
    weeks: set[str],
    *,
    candidate_generation: str,
    max_source_rows: int,
) -> dict[str, list[tuple[str, str, str, int, int, int, str]]]:
    result: dict[str, list[tuple[str, str, str, int, int, int, str]]] = {
        context.filter_fingerprint: [] for context in contexts
    }
    if not weeks:
        return result
    representative = contexts[0]
    contexts_by_threshold = {
        dynamic: [item for item in contexts if item.dynamic_threshold == dynamic]
        for dynamic in (False, True)
    }
    for week in sorted(weeks):
        try:
            raw = _load_bounded_tail_closure(
                conn,
                {week},
                week_start_hour=representative.bb_week_start_hour,
                max_gap_minutes=representative.max_merge_gap_minutes,
                max_source_rows=max_source_rows,
            )
            for dynamic, threshold_contexts in contexts_by_threshold.items():
                logical = _logical_events(
                    conn,
                    raw,
                    min_ms=representative.min_ms,
                    dynamic_threshold=dynamic,
                    max_gap_minutes=representative.max_merge_gap_minutes,
                )
                for context in threshold_contexts:
                    ranked = _ranked_rows_for_context(conn, context, logical, {week})
                    encoded = _encode_ledger_rows(
                        conn,
                        context,
                        {
                            "track": pd.DataFrame(),
                            "album": pd.DataFrame(),
                            "artist": ranked["artist"],
                        },
                        candidate_generation=candidate_generation,
                    )
                    result[context.filter_fingerprint].extend(encoded)
        except MusicSearchWeekDeltaIncompatibleError as exc:
            raise TrackCreditDeltaIncompatibleError(str(exc)) from exc
    return result


def _apply_aggregate_delta(
    conn: sqlite3.Connection,
    weekly_delta: Mapping[tuple[str, int], tuple[int, int]],
) -> None:
    for (week, artist_id), (play_delta, ms_delta) in weekly_delta.items():
        conn.execute(
            """INSERT INTO agg_weekly_artists(
                   billboard_week, artist_id, play_count, total_ms
               ) VALUES (?, ?, ?, ?)
               ON CONFLICT(billboard_week, artist_id) DO UPDATE SET
                   play_count=play_count+excluded.play_count,
                   total_ms=total_ms+excluded.total_ms""",
            (week, artist_id, play_delta, ms_delta),
        )
    invalid = conn.execute(
        "SELECT 1 FROM agg_weekly_artists WHERE play_count<0 OR total_ms<0 LIMIT 1"
    ).fetchone()
    if invalid is not None:
        raise TrackCreditDeltaIncompatibleError("artist aggregate delta would become negative")
    conn.execute("DELETE FROM agg_weekly_artists WHERE play_count=0 AND total_ms=0")


def _publish(
    conn: sqlite3.Connection,
    contexts: tuple[MusicSearchFilterContext, ...],
    base_keys: Mapping[str, str],
    rows_by_fingerprint: Mapping[str, list[tuple[Any, ...]]],
    ledgers_by_fingerprint: Mapping[str, list[tuple[str, str, str, int, int, int, str]]],
    weekly_aggregate_delta: Mapping[tuple[str, int], tuple[int, int]],
    *,
    base_credit_revision: int,
    target_revision: int,
    candidate_generation: str,
    playback_generation: str,
    dataset_digest: str,
) -> None:
    representative = contexts[0]
    conn.execute("BEGIN IMMEDIATE")
    try:
        _assert_shared_full_publish_fence(
            conn,
            contexts,
            source_generation_id=playback_generation,
            candidate_generation_id=candidate_generation,
            semantic_base_key=representative.semantic_base_key,
        )
        state = conn.execute(
            """SELECT current_revision, active_aggregate_revision
                 FROM track_credit_state WHERE state_id=1"""
        ).fetchone()
        if state is None or int(state[0]) != target_revision:
            raise RuntimeError("track-credit revision changed during delta publication")
        if int(state[1]) != base_credit_revision:
            raise RuntimeError("track-credit aggregate base changed during delta publication")

        _apply_aggregate_delta(conn, weekly_aggregate_delta)
        identity_revision = get_identity_revision(conn)
        track_identity_revision = get_track_identity_revision(conn)
        param_hash = _agg_param_hash(
            representative.min_ms,
            representative.music_only,
            representative.bb_week_start_dow,
            representative.bb_week_start_hour,
            dynamic_threshold=True,
            max_merge_gap_minutes=representative.max_merge_gap_minutes,
            identity_revision=identity_revision,
            track_credit_revision=target_revision,
            track_identity_revision=track_identity_revision,
        )
        semantic_dependencies = _aggregation_semantic_dependencies(
            conn,
            identity_revision=identity_revision,
            track_credit_revision=target_revision,
            track_identity_revision=track_identity_revision,
        )
        conn.execute(
            "INSERT OR REPLACE INTO agg_config(key, value) VALUES ('param_hash', ?)",
            (param_hash,),
        )
        conn.execute(
            "INSERT OR REPLACE INTO agg_config(key, value) VALUES ('build_strategy', 'credit_delta')"
        )
        for key, value in sorted(semantic_dependencies.items()):
            conn.execute(
                "INSERT OR REPLACE INTO agg_config(key, value) VALUES (?, ?)",
                (key, value),
            )
        dependency_digest = music_search_snapshot_dependency_digest(conn)
        for context in contexts:
            snapshot_key = context.filter_fingerprint
            clear_year_end_projection(conn, snapshot_key)
            conn.execute(
                "DELETE FROM music_search_entity_context WHERE snapshot_key=?", (snapshot_key,)
            )
            conn.execute(
                "DELETE FROM music_search_weekly_chart_context WHERE snapshot_key=?",
                (snapshot_key,),
            )
            conn.execute(
                "DELETE FROM music_search_snapshot_meta WHERE snapshot_key=?", (snapshot_key,)
            )
            conn.execute(
                """INSERT INTO music_search_snapshot_meta(
                       snapshot_key, filter_fingerprint, source_revision, status,
                       created_at, activated_at, last_error, semantic_base_key,
                       merge_level, dynamic_threshold, builder_version, policy_key,
                       source_generation_id, source_dataset_digest, base_snapshot_key,
                       build_strategy, dependency_digest, change_set_digest
                   ) VALUES (?, ?, ?, 'ready', datetime('now'), datetime('now'), NULL,
                             ?, ?, ?, ?, ?, ?, ?, ?, 'credit_delta', ?, ?)""",
                (
                    snapshot_key,
                    snapshot_key,
                    context.source_revision,
                    context.semantic_base_key,
                    context.merge_level,
                    int(context.dynamic_threshold),
                    MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
                    music_search_snapshot_policy_key(context),
                    playback_generation,
                    dataset_digest,
                    base_keys[snapshot_key],
                    dependency_digest,
                    f"track-credit:{target_revision}",
                ),
            )
            conn.executemany(
                """INSERT INTO music_search_entity_context(
                       snapshot_key, entity_key, play_events, total_ms,
                       peak_position, peak_weeks, weeks_on_chart, weeks_at_no1,
                       power_score, power_rank, first_week, latest_week, first_peak_week
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [(snapshot_key, *row) for row in rows_by_fingerprint[snapshot_key]],
            )
            conn.executemany(
                """INSERT INTO music_search_weekly_chart_context(
                       snapshot_key, family, week, entity_key, rank,
                       play_count, total_ms, stable_sort_key
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [(snapshot_key, *row) for row in ledgers_by_fingerprint[snapshot_key]],
            )
            _activate_snapshot_variant(conn, context, snapshot_key)

        conn.execute(
            """UPDATE track_credit_state
                  SET active_aggregate_revision=?, rebuild_status='ready', last_error=NULL,
                      updated_at=datetime('now') WHERE state_id=1""",
            (target_revision,),
        )
        conn.execute(
            """UPDATE track_credit_change_sets SET consumed_at=datetime('now')
                 WHERE to_revision>? AND to_revision<=? AND consumed_at IS NULL""",
            (base_credit_revision, target_revision),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def apply_track_credit_statistics_delta(
    conn: sqlite3.Connection,
    contexts: tuple[MusicSearchFilterContext, ...],
    change_sets: Sequence[Mapping[str, Any]],
    *,
    target_revision: int,
    max_changed_rows: int = _DEFAULT_MAX_CHANGED_ROWS,
    max_affected_weeks: int = _DEFAULT_MAX_AFFECTED_WEEKS,
) -> dict[str, Any]:
    """Apply one exact four-variant artist delta or raise an explicit fallback."""
    if not config.MUSIC_SEARCH_TRACK_CREDIT_DELTA:
        raise TrackCreditDeltaIncompatibleError("track-credit delta is disabled by kill switch")
    representative = _validate_contexts(contexts)
    scopes = _credit_scopes(change_sets)
    if not scopes:
        raise TrackCreditDeltaIncompatibleError("change range has no net membership delta")
    candidate_generation = str(get_music_search_index_state(conn).get("active_generation_id") or "")
    if not candidate_generation:
        raise TrackCreditDeltaIncompatibleError("candidate generation is unavailable")
    playback_generation, dataset_digest = active_playback_lineage(conn)
    if not playback_generation or not dataset_digest:
        raise TrackCreditDeltaIncompatibleError("playback lineage is unavailable")
    state = conn.execute(
        "SELECT active_aggregate_revision FROM track_credit_state WHERE state_id=1"
    ).fetchone()
    if state is None:
        raise TrackCreditDeltaIncompatibleError("track-credit aggregate state is unavailable")
    base_keys = _base_snapshot_keys(
        conn,
        contexts,
        active_credit_revision=int(state[0]),
        source_dataset_digest=dataset_digest,
    )

    raw = _load_changed_raw_rows(
        conn,
        scopes,
        max_source_rows=max_changed_rows,
    )
    logical = (
        _logical_by_threshold(raw, representative)
        if not raw.empty
        else {
            False: pd.DataFrame(),
            True: pd.DataFrame(),
        }
    )
    facts = {
        dynamic: _signed_artist_facts(
            frame,
            scopes,
            week_start_dow=representative.bb_week_start_dow,
            week_start_hour=representative.bb_week_start_hour,
        )
        for dynamic, frame in logical.items()
    }
    affected_weeks = {week for weekly in (facts[False][1], facts[True][1]) for week, _ in weekly}
    if len(affected_weeks) > max_affected_weeks:
        raise TrackCreditDeltaIncompatibleError("affected Billboard week cap exceeded")
    latest = conn.execute("SELECT MAX(ts) FROM plays").fetchone()
    open_week = open_billboard_week_for_latest_timestamp(
        latest[0] if latest is not None else None,
        week_start_dow=representative.bb_week_start_dow,
        week_start_hour=representative.bb_week_start_hour,
    )
    complete_weeks = {
        week for week in affected_weeks if open_week is None or week < open_week.isoformat()
    }
    replacement = _artist_replacement_ledger(
        conn,
        contexts,
        complete_weeks,
        candidate_generation=candidate_generation,
        max_source_rows=max_changed_rows,
    )

    rows_by_fingerprint: dict[str, list[tuple[Any, ...]]] = {}
    ledgers_by_fingerprint: dict[str, list[tuple[str, str, str, int, int, int, str]]] = {}
    for context in contexts:
        snapshot_key = context.filter_fingerprint
        candidate_keys = _candidate_keys_for_context(
            conn,
            context,
            candidate_generation=candidate_generation,
        )
        lifetime = _clone_lifetime_with_artist_delta(
            conn,
            base_key=base_keys[snapshot_key],
            artist_delta=facts[context.dynamic_threshold][0],
            candidate_keys=candidate_keys,
        )
        ledger = _base_weekly_ledger_rows(
            conn,
            base_keys[snapshot_key],
            excluded_weeks=complete_weeks,
        )
        # Only artist rankings depend on track-credit membership.  Track and
        # album facts for affected weeks are copied byte-for-byte from the LKG.
        for row in conn.execute(
            """SELECT family, week, entity_key, rank, play_count, total_ms,
                      stable_sort_key
                 FROM music_search_weekly_chart_context
                WHERE snapshot_key=? AND week IN ({}) AND family!='artist'""".format(
                ",".join("?" for _ in complete_weeks) or "NULL"
            ),
            (base_keys[snapshot_key], *sorted(complete_weeks)),
        ).fetchall():
            ledger.append(
                (
                    str(row[0]),
                    str(row[1]),
                    str(row[2]),
                    int(row[3]),
                    int(row[4]),
                    int(row[5]),
                    str(row[6]),
                )
            )
        ledger.extend(replacement[snapshot_key])
        try:
            rows = list(
                rebuild_context_rows_from_weekly_ledger(
                    ledger,
                    lifetime,
                    candidate_keys,
                    track_top_n=context.bb_top_n,
                    album_top_n=context.bb_album_top_n,
                    artist_top_n=context.bb_artist_top_n,
                )
            )
        except WeeklyLedgerValidationError as exc:
            raise TrackCreditDeltaIncompatibleError(str(exc)) from exc
        _validate_context_rows(rows)
        rows_by_fingerprint[snapshot_key] = rows
        ledgers_by_fingerprint[snapshot_key] = sorted(
            ledger, key=lambda row: (row[0], row[1], row[3], row[2])
        )

    _publish(
        conn,
        contexts,
        base_keys,
        rows_by_fingerprint,
        ledgers_by_fingerprint,
        facts[True][1],
        base_credit_revision=int(state[0]),
        target_revision=target_revision,
        candidate_generation=candidate_generation,
        playback_generation=playback_generation,
        dataset_digest=dataset_digest,
    )
    return {
        "status": "ready",
        "strategy": "track_credit_delta",
        "target_revision": target_revision,
        "changed_track_count": len(scopes),
        "changed_source_row_count": len(raw),
        "affected_week_count": len(affected_weeks),
        "affected_completed_week_count": len(complete_weeks),
        "lifetime_scan": False,
        "snapshot_count": len(contexts),
    }
