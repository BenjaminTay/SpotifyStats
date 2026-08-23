"""Exact impact scope produced from one published playback import generation."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Any, Literal, cast

import pandas as pd

from backend.domains.billboard.week_coverage import (
    open_billboard_week_for_latest_timestamp,
)
from backend.domains.imports.incremental import FingerprintRecord, ImportPlan, dataset_digest
from backend.domains.metadata.artist_identity import get_identity_revision
from backend.domains.metadata.track_credits import get_track_credit_revision
from backend.domains.playback.logical_timeline import (
    OVERLAP_TOLERANCE_SECONDS,
    PLAYBACK_EVENT_POLICY_VERSION,
    PLAYBACK_TIMEZONE,
    billboard_week_for_timestamps,
)
from backend.domains.settings.repository import SettingsRepository

ImportWriteStrategy = Literal["incremental", "full"]

_CHANGE_SET_SCHEMA_VERSION = "playback_change_set_v2"
_CHANGE_SET_COLLECTION_LIMIT = 250_000
_MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlaybackChangeSet:
    """Bounded execution evidence for downstream import maintenance."""

    generation_id: str
    strategy: ImportWriteStrategy
    previous_dataset_digest: str | None
    added_count: int
    removed_count: int
    earliest_changed_ts: str | None
    latest_changed_ts: str | None
    track_ids: frozenset[int]
    album_ids: frozenset[int]
    source_album_ids: frozenset[int]
    artist_ids: frozenset[int]
    spotify_track_ids: frozenset[str]
    spotify_album_ids: frozenset[str]
    dates: frozenset[str]
    months: frozenset[str]
    years: frozenset[int]
    billboard_weeks: frozenset[str]
    billboard_scope_exact: bool
    previous_open_week: str | None
    current_open_week: str | None
    semantic_revisions: dict[str, str | int]

    @property
    def entity_count(self) -> int:
        return len(self.track_ids) + len(self.album_ids) + len(self.artist_ids)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in (
            "track_ids",
            "album_ids",
            "source_album_ids",
            "artist_ids",
            "spotify_track_ids",
            "spotify_album_ids",
            "dates",
            "months",
            "years",
            "billboard_weeks",
        ):
            payload[key] = sorted(payload[key])
        payload["schema_version"] = _CHANGE_SET_SCHEMA_VERSION
        payload["entity_count"] = self.entity_count
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> PlaybackChangeSet:
        """Decode persisted recovery evidence without accepting schema drift."""

        if not isinstance(payload, dict):
            raise ValueError("playback change set must be an object")
        expected_fields = {
            *cls.__dataclass_fields__,
            "schema_version",
            "entity_count",
        }
        if set(payload) != expected_fields:
            raise ValueError("playback change set fields do not match the current schema")
        if payload["schema_version"] != _CHANGE_SET_SCHEMA_VERSION:
            raise ValueError("unsupported playback change set schema version")

        generation_id = _required_string(payload["generation_id"], "generation_id")
        strategy = payload["strategy"]
        if strategy not in {"incremental", "full"}:
            raise ValueError("invalid playback change set strategy")
        previous_dataset_digest = _optional_string(
            payload["previous_dataset_digest"], "previous_dataset_digest"
        )
        added_count = _non_negative_int(payload["added_count"], "added_count")
        removed_count = _non_negative_int(payload["removed_count"], "removed_count")
        earliest_changed_ts = _optional_iso_timestamp(
            payload["earliest_changed_ts"], "earliest_changed_ts"
        )
        latest_changed_ts = _optional_iso_timestamp(
            payload["latest_changed_ts"], "latest_changed_ts"
        )
        track_ids = _integer_set(payload["track_ids"], "track_ids")
        album_ids = _integer_set(payload["album_ids"], "album_ids")
        source_album_ids = _integer_set(payload["source_album_ids"], "source_album_ids")
        artist_ids = _integer_set(payload["artist_ids"], "artist_ids")
        spotify_track_ids = _string_set(payload["spotify_track_ids"], "spotify_track_ids")
        spotify_album_ids = _string_set(payload["spotify_album_ids"], "spotify_album_ids")
        dates = _date_set(payload["dates"], "dates")
        months = _month_set(payload["months"], "months")
        years = _year_set(payload["years"], "years")
        billboard_weeks = _date_set(payload["billboard_weeks"], "billboard_weeks")
        billboard_scope_exact = payload["billboard_scope_exact"]
        if type(billboard_scope_exact) is not bool:
            raise ValueError("billboard_scope_exact must be a boolean")
        previous_open_week = _optional_date(payload["previous_open_week"], "previous_open_week")
        current_open_week = _optional_date(payload["current_open_week"], "current_open_week")
        semantic_revisions = _semantic_revision_map(payload["semantic_revisions"])

        entity_count = _non_negative_int(payload["entity_count"], "entity_count")
        if entity_count != len(track_ids) + len(album_ids) + len(artist_ids):
            raise ValueError("playback change set entity_count does not match its ID sets")
        return cls(
            generation_id=generation_id,
            strategy=cast(ImportWriteStrategy, strategy),
            previous_dataset_digest=previous_dataset_digest,
            added_count=added_count,
            removed_count=removed_count,
            earliest_changed_ts=earliest_changed_ts,
            latest_changed_ts=latest_changed_ts,
            track_ids=track_ids,
            album_ids=album_ids,
            source_album_ids=source_album_ids,
            artist_ids=artist_ids,
            spotify_track_ids=spotify_track_ids,
            spotify_album_ids=spotify_album_ids,
            dates=dates,
            months=months,
            years=years,
            billboard_weeks=billboard_weeks,
            billboard_scope_exact=billboard_scope_exact,
            previous_open_week=previous_open_week,
            current_open_week=current_open_week,
            semantic_revisions=semantic_revisions,
        )


def _required_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _optional_string(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _required_string(value, field)


def _non_negative_int(value: Any, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _bounded_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    if len(value) > _CHANGE_SET_COLLECTION_LIMIT:
        raise ValueError(f"{field} exceeds the recovery evidence limit")
    return value


def _integer_set(value: Any, field: str) -> frozenset[int]:
    values = _bounded_list(value, field)
    if any(type(item) is not int or item <= 0 for item in values):
        raise ValueError(f"{field} must contain positive integers")
    if len(set(values)) != len(values):
        raise ValueError(f"{field} must not contain duplicates")
    return frozenset(values)


def _string_set(value: Any, field: str) -> frozenset[str]:
    values = _bounded_list(value, field)
    if any(not isinstance(item, str) or not item.strip() for item in values):
        raise ValueError(f"{field} must contain non-empty strings")
    if len(set(values)) != len(values):
        raise ValueError(f"{field} must not contain duplicates")
    return frozenset(values)


def _optional_iso_timestamp(value: Any, field: str) -> str | None:
    encoded = _optional_string(value, field)
    if encoded is None:
        return None
    try:
        datetime.fromisoformat(encoded.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO timestamp") from exc
    return encoded


def _parse_date(value: Any, field: str) -> str:
    encoded = _required_string(value, field)
    try:
        date.fromisoformat(encoded)
    except ValueError as exc:
        raise ValueError(f"{field} must contain ISO dates") from exc
    return encoded


def _optional_date(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _parse_date(value, field)


def _date_set(value: Any, field: str) -> frozenset[str]:
    values = _bounded_list(value, field)
    parsed = [_parse_date(item, field) for item in values]
    if len(set(parsed)) != len(parsed):
        raise ValueError(f"{field} must not contain duplicates")
    return frozenset(parsed)


def _month_set(value: Any, field: str) -> frozenset[str]:
    values = _bounded_list(value, field)
    if any(not isinstance(item, str) or not _MONTH_PATTERN.fullmatch(item) for item in values):
        raise ValueError(f"{field} must contain YYYY-MM values")
    if len(set(values)) != len(values):
        raise ValueError(f"{field} must not contain duplicates")
    return frozenset(values)


def _year_set(value: Any, field: str) -> frozenset[int]:
    values = _bounded_list(value, field)
    if any(type(item) is not int or item < 1 or item > 9999 for item in values):
        raise ValueError(f"{field} must contain valid years")
    if len(set(values)) != len(values):
        raise ValueError(f"{field} must not contain duplicates")
    return frozenset(values)


def _semantic_revision_map(value: Any) -> dict[str, str | int]:
    if not isinstance(value, dict) or not value:
        raise ValueError("semantic_revisions must be a non-empty object")
    if len(value) > 64:
        raise ValueError("semantic_revisions exceeds the recovery evidence limit")
    result: dict[str, str | int] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("semantic_revisions keys must be non-empty strings")
        if not isinstance(item, (str, int)) or isinstance(item, bool):
            raise ValueError("semantic_revisions values must be strings or integers")
        if isinstance(item, str) and not item.strip():
            raise ValueError("semantic_revisions string values must not be empty")
        result[key] = item
    return result


def build_playback_change_set(
    conn: sqlite3.Connection,
    *,
    generation_id: str,
    strategy: ImportWriteStrategy,
    plan: ImportPlan,
) -> PlaybackChangeSet:
    """Derive downstream scope from rows actually written by this generation.

    Append imports select only the new generation. A full replacement treats
    the entire active dataset as changed and conservatively includes years
    present only in the previous coverage range.
    """
    if not generation_id.strip():
        raise ValueError("generation_id must not be empty")
    if strategy not in {"incremental", "full"}:
        raise ValueError(f"unsupported import strategy: {strategy}")

    rows = conn.execute(
        """SELECT play_id, ts, ts_date, ts_year, ts_month, track_id,
                  source_album_id, ms_played, spotify_track_id_at_play,
                  spotify_album_id_at_play
           FROM plays WHERE import_generation_id=? ORDER BY ts, play_id""",
        (generation_id,),
    ).fetchall()
    expected = plan.added_count if strategy == "incremental" else plan.incoming_count
    if len(rows) != expected:
        raise RuntimeError(
            f"import generation scope mismatch: expected {expected} rows, found {len(rows)}"
        )

    track_ids = {int(row["track_id"]) for row in rows if row["track_id"] is not None}
    source_album_ids = {
        int(row["source_album_id"]) for row in rows if row["source_album_id"] is not None
    }
    album_ids = source_album_ids | _album_ids_for_tracks(conn, track_ids)
    artist_ids = _artist_ids_for_tracks(conn, track_ids)
    spotify_track_ids = {
        str(row["spotify_track_id_at_play"])
        for row in rows
        if row["spotify_track_id_at_play"] is not None
        and str(row["spotify_track_id_at_play"]).strip()
    }
    spotify_track_ids.update(_spotify_track_ids_for_tracks(conn, track_ids))
    spotify_album_ids = {
        str(row["spotify_album_id_at_play"])
        for row in rows
        if row["spotify_album_id_at_play"] is not None
        and str(row["spotify_album_id_at_play"]).strip()
    }
    spotify_album_ids.update(_spotify_album_ids_for_tracks(conn, track_ids))
    spotify_album_ids.update(_spotify_album_ids_for_albums(conn, album_ids))
    timestamps = [str(row["ts"]) for row in rows if row["ts"]]
    changed_timestamps = list(timestamps)
    if strategy == "full":
        changed_timestamps.extend(
            value.isoformat()
            for value in (plan.existing_first_ts, plan.existing_latest_ts)
            if value is not None
        )
    dates = {str(row["ts_date"]) for row in rows if row["ts_date"]}
    months = {
        f"{int(row['ts_year']):04d}-{int(row['ts_month']):02d}"
        for row in rows
        if row["ts_year"] is not None and row["ts_month"] is not None
    }
    settings = SettingsRepository(conn).load_all()
    years = {int(row["ts_year"]) for row in rows if row["ts_year"] is not None}
    if strategy == "incremental":
        years.update(
            _logical_impact_years(
                conn,
                rows,
                generation_id=generation_id,
                max_gap_minutes=int(settings.get("max_merge_gap_minutes", 5)),
            )
        )
    if strategy == "full":
        years.update(_covered_years(plan.existing_first_ts, plan.existing_latest_ts))

    week_start_dow = int(settings.get("bb_week_start_dow", 4))
    week_start_hour = int(settings.get("bb_week_start_hour", 0))
    billboard_scope_exact = False
    if strategy == "incremental":
        try:
            weeks: set[str] = set()
            # Search snapshots publish both fixed and duration-aware threshold
            # variants.  The safe affected scope is the union of both proofs.
            for dynamic_threshold in (False, True):
                weeks.update(
                    _logical_billboard_contribution_weeks(
                        conn,
                        generation_id=generation_id,
                        min_ms=int(settings.get("min_ms", 30_000)),
                        music_only=bool(settings.get("music_only", True)),
                        dynamic_threshold=dynamic_threshold,
                        max_gap_minutes=int(settings.get("max_merge_gap_minutes", 5)),
                        week_start_dow=week_start_dow,
                        week_start_hour=week_start_hour,
                    )
                )
            billboard_scope_exact = True
        except Exception:
            logger.exception(
                "Unable to prove exact Billboard contribution scope for generation %s; "
                "downstream maintenance must use a full rebuild.",
                generation_id,
            )
            weeks = _billboard_weeks(
                timestamps,
                week_start_dow=week_start_dow,
                week_start_hour=week_start_hour,
            )
    else:
        weeks = _billboard_weeks(
            timestamps,
            week_start_dow=week_start_dow,
            week_start_hour=week_start_hour,
        )
    previous_open = open_billboard_week_for_latest_timestamp(
        plan.existing_latest_ts,
        week_start_dow=week_start_dow,
        week_start_hour=week_start_hour,
    )
    current_latest = conn.execute("SELECT MAX(ts) FROM plays").fetchone()[0]
    current_open = open_billboard_week_for_latest_timestamp(
        current_latest,
        week_start_dow=week_start_dow,
        week_start_hour=week_start_hour,
    )
    for boundary in (previous_open, current_open):
        if boundary is not None:
            weeks.add(boundary.isoformat())
    if current_open is not None and current_open != previous_open:
        weeks.add((current_open - timedelta(days=7)).isoformat())

    return PlaybackChangeSet(
        generation_id=generation_id,
        strategy=strategy,
        previous_dataset_digest=plan.previous_digest,
        added_count=plan.added_count if strategy == "incremental" else plan.incoming_count,
        removed_count=plan.removed_count,
        earliest_changed_ts=min(changed_timestamps) if changed_timestamps else None,
        latest_changed_ts=max(changed_timestamps) if changed_timestamps else None,
        track_ids=frozenset(track_ids),
        album_ids=frozenset(album_ids),
        source_album_ids=frozenset(source_album_ids),
        artist_ids=frozenset(artist_ids),
        spotify_track_ids=frozenset(spotify_track_ids),
        spotify_album_ids=frozenset(spotify_album_ids),
        dates=frozenset(dates),
        months=frozenset(months),
        years=frozenset(years),
        billboard_weeks=frozenset(weeks),
        billboard_scope_exact=billboard_scope_exact,
        previous_open_week=_date_string(previous_open),
        current_open_week=_date_string(current_open),
        semantic_revisions=_semantic_revisions(conn, settings),
    )


def _logical_billboard_contribution_weeks(
    conn: sqlite3.Connection,
    *,
    generation_id: str,
    min_ms: int,
    music_only: bool,
    dynamic_threshold: bool,
    max_gap_minutes: int,
    week_start_dow: int,
    week_start_hour: int,
) -> set[str]:
    """Compare a proven tail closure's old/new logical contributions."""
    old_events, new_events = build_billboard_tail_contribution_frames(
        conn,
        generation_id=generation_id,
        min_ms=min_ms,
        music_only=music_only,
        dynamic_threshold=dynamic_threshold,
        max_gap_minutes=max_gap_minutes,
    )
    old = _logical_billboard_contribution_signature(
        old_events,
        week_start_dow=week_start_dow,
        week_start_hour=week_start_hour,
    )
    new = _logical_billboard_contribution_signature(
        new_events,
        week_start_dow=week_start_dow,
        week_start_hour=week_start_hour,
    )
    changed_keys = {key for key in old.keys() | new.keys() if old.get(key) != new.get(key)}
    return {str(key[0]) for key in changed_keys}


def build_billboard_tail_contribution_frames(
    conn: sqlite3.Connection,
    *,
    generation_id: str,
    min_ms: int,
    music_only: bool,
    dynamic_threshold: bool,
    max_gap_minutes: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return exact old/new logical frames for one proven tail append."""
    new_rows = _generation_billboard_rows(
        conn,
        generation_id=generation_id,
        music_only=music_only,
    )
    if not new_rows:
        empty = pd.DataFrame()
        return empty, empty.copy()
    earliest = new_rows[0]
    if conn.execute(
        """SELECT 1
           FROM plays p JOIN tracks t ON p.track_id=t.track_id
           WHERE COALESCE(p.import_generation_id, '') != ?
             AND (p.ts > ? OR (p.ts = ? AND p.play_id > ?))
           LIMIT 1""",
        (generation_id, earliest["ts"], earliest["ts"], earliest["play_id"]),
    ).fetchone():
        raise RuntimeError("new playback generation is not a provable tail append")

    old_rows = _preceding_merge_chain(
        conn,
        earliest,
        generation_id=generation_id,
        max_gap_minutes=max_gap_minutes,
    )
    old_events = _logical_billboard_events(
        old_rows,
        min_ms=min_ms,
        dynamic_threshold=dynamic_threshold,
        max_gap_minutes=max_gap_minutes,
    )
    new_events = _logical_billboard_events(
        [*old_rows, *new_rows],
        min_ms=min_ms,
        dynamic_threshold=dynamic_threshold,
        max_gap_minutes=max_gap_minutes,
    )
    return old_events, new_events


_BILLBOARD_CHAIN_PAGE_SIZE = 256


def _generation_billboard_rows(
    conn: sqlite3.Connection,
    *,
    generation_id: str,
    music_only: bool,
) -> list[dict[str, Any]]:
    music_clause = "AND p.track_id IS NOT NULL" if music_only else ""
    rows = conn.execute(
        f"""SELECT p.play_id, p.ts, p.ts_date, p.ts_dow, p.ts_hour,
                   p.ms_played, p.track_id, p.source_album_id,
                   t.album_id, t.artist_id, stm.duration_ms
            FROM plays p
            JOIN tracks t ON p.track_id=t.track_id
            LEFT JOIN spotify_track_meta stm
              ON t.spotify_track_id=stm.spotify_track_id
            WHERE p.import_generation_id=? {music_clause}
            ORDER BY p.ts, p.play_id""",
        (generation_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _preceding_merge_chain(
    conn: sqlite3.Connection,
    earliest_new: dict[str, Any],
    *,
    generation_id: str,
    max_gap_minutes: int,
) -> list[dict[str, Any]]:
    """Walk backward until the first deterministic logical-run boundary."""
    cursor = earliest_new
    descending: list[dict[str, Any]] = []
    while True:
        rows = conn.execute(
            """SELECT p.play_id, p.ts, p.ts_date, p.ts_dow, p.ts_hour,
                      p.ms_played, p.track_id, p.source_album_id,
                      t.album_id, t.artist_id, stm.duration_ms
               FROM plays p
               JOIN tracks t ON p.track_id=t.track_id
               LEFT JOIN spotify_track_meta stm
                 ON t.spotify_track_id=stm.spotify_track_id
               WHERE COALESCE(p.import_generation_id, '') != ?
                 AND (p.ts < ? OR (p.ts = ? AND p.play_id < ?))
               ORDER BY p.ts DESC, p.play_id DESC
               LIMIT ?""",
            (
                generation_id,
                cursor["ts"],
                cursor["ts"],
                cursor["play_id"],
                _BILLBOARD_CHAIN_PAGE_SIZE,
            ),
        ).fetchall()
        if not rows:
            break
        page_exhausted = True
        for raw_prior in rows:
            prior = dict(raw_prior)
            if not _rows_share_merge_run(
                prior,
                cursor,
                max_gap_minutes=max_gap_minutes,
            ):
                page_exhausted = False
                break
            descending.append(prior)
            cursor = prior
        if not page_exhausted or len(rows) < _BILLBOARD_CHAIN_PAGE_SIZE:
            break
    descending.reverse()
    return descending


def _rows_share_merge_run(
    prior: dict[str, Any],
    following: dict[str, Any],
    *,
    max_gap_minutes: int,
) -> bool:
    if prior["track_id"] != following["track_id"]:
        return False
    if prior["source_album_id"] != following["source_album_id"]:
        return False
    prior_end = _timestamp(prior["ts"])
    following_end = _timestamp(following["ts"])
    if prior_end is None or following_end is None:
        return False
    following_start = following_end - pd.to_timedelta(
        max(int(following["ms_played"] or 0), 0), unit="ms"
    )
    gap_seconds = (following_start - prior_end).total_seconds()
    return gap_seconds <= max_gap_minutes * 60 and gap_seconds >= -OVERLAP_TOLERANCE_SECONDS


def _logical_billboard_events(
    rows: list[dict[str, Any]],
    *,
    min_ms: int,
    dynamic_threshold: bool,
    max_gap_minutes: int,
) -> pd.DataFrame:
    from backend.domains.playback.counting import filter_effective_plays
    from backend.domains.playback.logical_timeline import reconstruct_logical_plays

    frame = pd.DataFrame.from_records(rows)
    if frame.empty:
        return frame
    frame["_source_album_id"] = frame["source_album_id"].fillna(0).astype(int)
    events = reconstruct_logical_plays(
        frame,
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
    return events


def _logical_billboard_contribution_signature(
    events: pd.DataFrame,
    *,
    week_start_dow: int,
    week_start_hour: int,
) -> dict[tuple[str, str, int, int], tuple[int, int]]:
    from backend.domains.playback.logical_timeline import build_billboard_weighted_frame

    if events.empty:
        return {}
    weighted = build_billboard_weighted_frame(
        events,
        week_start_dow=week_start_dow,
        week_start_hour=week_start_hour,
    )
    weighted["_source_album_id"] = weighted["_source_album_id"].fillna(0).astype(int)
    grouped = (
        weighted.groupby(
            ["billboard_week", "ts_date", "track_id", "_source_album_id"],
            dropna=False,
        )
        .agg(play_count=("play_count", "sum"), total_ms=("total_ms", "sum"))
        .reset_index()
        .rename(columns={"_source_album_id": "source_album_id"})
    )
    return {
        (
            str(row.billboard_week),
            str(row.ts_date),
            int(cast(Any, row.track_id)),
            int(cast(Any, row.source_album_id)),
        ): (int(cast(Any, row.play_count)), int(cast(Any, row.total_ms)))
        for row in grouped.itertuples(index=False)
    }


def publish_year_partition_state(
    conn: sqlite3.Connection,
    change_set: PlaybackChangeSet,
) -> None:
    """Publish exact direct/prefix year digests in the facts transaction."""
    if not _table_exists(conn, "playback_year_partition_state"):
        return
    if change_set.strategy == "full":
        conn.execute("DELETE FROM playback_year_partition_state")
        start_year = None
    else:
        start_year = min(change_set.years) if change_set.years else None
    active_year_rows = conn.execute(
        """SELECT DISTINCT ts_year FROM plays
           WHERE ts_year BETWEEN 2000 AND 2100 ORDER BY ts_year"""
    ).fetchall()
    active_years = [int(row[0]) for row in active_year_rows]
    if not active_years:
        conn.execute("DELETE FROM playback_year_partition_state")
        return
    state_years = {
        int(row[0])
        for row in conn.execute("SELECT report_year FROM playback_year_partition_state").fetchall()
    }
    required_predecessors = {
        year for year in active_years if start_year is not None and year < start_year
    }
    if not required_predecessors.issubset(state_years):
        start_year = None
    if start_year is None:
        rebuild_years = active_years
    else:
        rebuild_years = [year for year in active_years if year >= start_year]
    generation = change_set.generation_id
    for year in rebuild_years:
        previous_state = conn.execute(
            """SELECT impact_revision FROM playback_year_partition_state
               WHERE report_year=?""",
            (year,),
        ).fetchone()
        impact_revision = int(previous_state[0] or 0) if previous_state else 0
        if change_set.strategy == "full" or year in change_set.years:
            impact_revision += 1
        rows = conn.execute(
            """SELECT content_type, source_fingerprint, MIN(ts), MAX(ts)
               FROM plays WHERE ts_year=?
                 AND source_fingerprint IS NOT NULL
               GROUP BY content_type, source_fingerprint
               ORDER BY content_type, source_fingerprint""",
            (year,),
        ).fetchall()
        direct = dataset_digest(
            FingerprintRecord(source_type=str(row[0]), fingerprint=str(row[1])) for row in rows
        )
        previous = conn.execute(
            """SELECT prefix_digest FROM playback_year_partition_state
               WHERE report_year < ? ORDER BY report_year DESC LIMIT 1""",
            (year,),
        ).fetchone()
        prefix = hashlib.sha256(b"spotifystats-year-prefix-v2\0")
        if previous is not None:
            prefix.update(str(previous[0]).encode("ascii"))
        prefix.update(str(year).encode("ascii"))
        prefix.update(direct.encode("ascii"))
        prefix.update(str(impact_revision).encode("ascii"))
        conn.execute(
            """INSERT INTO playback_year_partition_state(
                   report_year, direct_digest, prefix_digest, digest_version,
                   impact_revision, record_count,
                   first_ts, latest_ts, source_generation_id, updated_at
               ) VALUES (?, ?, ?, 'year-prefix-v2', ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(report_year) DO UPDATE SET
                   direct_digest=excluded.direct_digest,
                   prefix_digest=excluded.prefix_digest,
                   digest_version=excluded.digest_version,
                   impact_revision=excluded.impact_revision,
                   record_count=excluded.record_count,
                   first_ts=excluded.first_ts,
                   latest_ts=excluded.latest_ts,
                   source_generation_id=excluded.source_generation_id,
                   updated_at=datetime('now')""",
            (
                year,
                direct,
                prefix.hexdigest(),
                impact_revision,
                len(rows),
                min((str(row[2]) for row in rows if row[2]), default=None),
                max((str(row[3]) for row in rows if row[3]), default=None),
                generation,
            ),
        )
    if change_set.strategy == "incremental":
        placeholders = ",".join("?" for _ in active_years)
        conn.execute(
            f"DELETE FROM playback_year_partition_state WHERE report_year NOT IN ({placeholders})",
            active_years,
        )


def _logical_impact_years(
    conn: sqlite3.Connection,
    rows: list[sqlite3.Row],
    *,
    generation_id: str,
    max_gap_minutes: int,
) -> set[int]:
    """Close an append over listened intervals and its preceding merge run."""
    years: set[int] = set()
    for row in rows:
        years.update(_row_interval_years(row))
    if not rows:
        return years

    earliest = rows[0]
    next_row = earliest
    prior_rows = conn.execute(
        """SELECT play_id, ts, track_id, source_album_id, ms_played
           FROM plays
           WHERE COALESCE(import_generation_id, '') != ?
             AND (ts < ? OR (ts = ? AND play_id < ?))
           ORDER BY ts DESC, play_id DESC""",
        (generation_id, earliest["ts"], earliest["ts"], earliest["play_id"]),
    )
    for prior in prior_rows:
        if prior["track_id"] != next_row["track_id"]:
            break
        if prior["source_album_id"] != next_row["source_album_id"]:
            break
        prior_end = _timestamp(prior["ts"])
        next_end = _timestamp(next_row["ts"])
        if prior_end is None or next_end is None:
            break
        next_start = next_end - pd.to_timedelta(max(int(next_row["ms_played"] or 0), 0), unit="ms")
        gap_seconds = (next_start - prior_end).total_seconds()
        if gap_seconds > max_gap_minutes * 60:
            break
        if gap_seconds < -OVERLAP_TOLERANCE_SECONDS:
            break
        years.update(_row_interval_years(prior))
        next_row = prior
    return years


def _row_interval_years(row: sqlite3.Row) -> set[int]:
    end = _timestamp(row["ts"])
    if end is None:
        return set()
    start = end - pd.to_timedelta(max(int(row["ms_played"] or 0), 0), unit="ms")
    local_start = start.tz_convert(PLAYBACK_TIMEZONE)
    local_end = end.tz_convert(PLAYBACK_TIMEZONE)
    return set(range(int(local_start.year), int(local_end.year) + 1))


def _timestamp(value: object) -> pd.Timestamp | None:
    parsed = pd.to_datetime(cast(Any, value), utc=True, errors="coerce")
    return None if pd.isna(parsed) else pd.Timestamp(parsed)


def _artist_ids_for_tracks(conn: sqlite3.Connection, track_ids: set[int]) -> set[int]:
    if not track_ids:
        return set()
    result: set[int] = set()
    ordered = sorted(track_ids)
    for offset in range(0, len(ordered), 800):
        chunk = ordered[offset : offset + 800]
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"""SELECT artist_id FROM tracks WHERE track_id IN ({placeholders})
                UNION
                SELECT artist_id FROM track_artists WHERE track_id IN ({placeholders})""",
            (*chunk, *chunk),
        ).fetchall()
        result.update(int(row[0]) for row in rows if row[0] is not None)
    return result


def _album_ids_for_tracks(conn: sqlite3.Connection, track_ids: set[int]) -> set[int]:
    if not track_ids:
        return set()
    result: set[int] = set()
    ordered = sorted(track_ids)
    for offset in range(0, len(ordered), 800):
        chunk = ordered[offset : offset + 800]
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"SELECT album_id FROM tracks WHERE track_id IN ({placeholders})",
            chunk,
        ).fetchall()
        result.update(int(row[0]) for row in rows if row[0] is not None)
    return result


def _spotify_track_ids_for_tracks(
    conn: sqlite3.Connection,
    track_ids: set[int],
) -> set[str]:
    if not track_ids:
        return set()
    result: set[str] = set()
    ordered = sorted(track_ids)
    for offset in range(0, len(ordered), 800):
        chunk = ordered[offset : offset + 800]
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"""SELECT spotify_track_id FROM tracks
                WHERE track_id IN ({placeholders})
                  AND spotify_track_id IS NOT NULL AND spotify_track_id!=''""",
            chunk,
        ).fetchall()
        result.update(str(row[0]) for row in rows if row[0])
    return result


def _spotify_album_ids_for_tracks(
    conn: sqlite3.Connection,
    track_ids: set[int],
) -> set[str]:
    if not track_ids or not _table_exists(conn, "spotify_track_meta"):
        return set()
    result: set[str] = set()
    ordered = sorted(track_ids)
    for offset in range(0, len(ordered), 800):
        chunk = ordered[offset : offset + 800]
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"""SELECT DISTINCT stm.spotify_album_id
                FROM tracks t
                JOIN spotify_track_meta stm
                  ON stm.spotify_track_id=t.spotify_track_id
                WHERE t.track_id IN ({placeholders})
                  AND stm.spotify_album_id IS NOT NULL
                  AND stm.spotify_album_id!=''""",
            chunk,
        ).fetchall()
        result.update(str(row[0]) for row in rows if row[0])
    return result


def _spotify_album_ids_for_albums(
    conn: sqlite3.Connection,
    album_ids: set[int],
) -> set[str]:
    if not album_ids or not _table_exists(conn, "album_spotify_links"):
        return set()
    result: set[str] = set()
    ordered = sorted(album_ids)
    for offset in range(0, len(ordered), 800):
        chunk = ordered[offset : offset + 800]
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"""SELECT DISTINCT spotify_album_id FROM album_spotify_links
                WHERE album_id IN ({placeholders})
                  AND spotify_album_id IS NOT NULL AND spotify_album_id!=''""",
            chunk,
        ).fetchall()
        result.update(str(row[0]) for row in rows if row[0])
    return result


def _covered_years(first: datetime | None, latest: datetime | None) -> set[int]:
    if first is None or latest is None:
        return set()
    return set(range(first.year, latest.year + 1))


def _billboard_weeks(
    timestamps: list[str],
    *,
    week_start_dow: int,
    week_start_hour: int,
) -> set[str]:
    if not timestamps:
        return set()
    values = billboard_week_for_timestamps(
        pd.Series(timestamps, dtype=object),
        week_start_dow=week_start_dow,
        week_start_hour=week_start_hour,
    )
    return {value.isoformat() for value in values.dropna().tolist()}


def _semantic_revisions(
    conn: sqlite3.Connection,
    settings: dict[str, Any],
) -> dict[str, str | int]:
    setting_keys = (
        "min_ms",
        "music_only",
        "merge_enabled",
        "max_merge_gap_minutes",
        "bb_week_start_dow",
        "bb_week_start_hour",
        "include_compilations",
    )
    encoded = json.dumps(
        {key: settings.get(key) for key in setting_keys},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "playback_policy": PLAYBACK_EVENT_POLICY_VERSION,
        "settings": hashlib.sha256(encoded.encode()).hexdigest()[:20],
        "artist_identity": get_identity_revision(conn),
        "track_credit": get_track_credit_revision(conn),
    }


def _date_string(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        is not None
    )
