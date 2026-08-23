"""Exact impact scope produced from one published playback import generation."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Any, Literal

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


@dataclass(frozen=True)
class PlaybackChangeSet:
    """Bounded execution evidence for downstream import maintenance."""

    generation_id: str
    strategy: ImportWriteStrategy
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
        payload["schema_version"] = "playback_change_set_v1"
        payload["entity_count"] = self.entity_count
        return payload


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
        billboard_scope_exact=False,
        previous_open_week=_date_string(previous_open),
        current_open_week=_date_string(current_open),
        semantic_revisions=_semantic_revisions(conn, settings),
    )


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
    parsed = pd.to_datetime(value, utc=True, errors="coerce")
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
