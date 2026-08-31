#!/usr/bin/env python3
"""Read-only L1/L2/L3 identity and album-attribution integrity probe.

The probe deliberately opens the requested database through SQLite ``mode=ro``
and enables ``query_only`` before reading anything.  It never runs migrations,
schema ensure helpers, planners, or revision bumpers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domains.metadata.track_identity_risk import (  # noqa: E402
    build_l1_external_identity_risk_plan,
)
from backend.domains.playback.l3_album_attribution import (  # noqa: E402
    L3_ALBUM_ATTRIBUTION_POLICY_VERSION,
)
from backend.domains.playback.logical_timeline import (  # noqa: E402
    reconstruct_logical_plays,
)
from backend.domains.playback.song_work_keys import (  # noqa: E402
    load_l3_song_work_keys,
)

REPORT_SCHEMA_VERSION = "l2_l3_integrity_probe_v1"
RAW_FACT_TABLES = ("plays", "tracks", "track_artists")
FIXED_SAMPLE_SPECS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("anti_hero", "track", ("anti-hero",)),
    ("pure_sister", "track", ("纯妹妹", "純妹妹")),
    ("1989", "album", ("1989",)),
    ("speak_now", "album", ("speak now",)),
    ("the_show_live", "album", ("the show: live", "the show - live")),
    ("live_from_spotify_studios", "album", ("live from spotify studios",)),
)


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _digest(payload: Any) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _parse_bool(value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"expected boolean, got {value!r}")


def open_readonly_connection(db_path: Path) -> sqlite3.Connection:
    """Open one existing SQLite database without allowing any writes."""

    resolved = db_path.expanduser().resolve(strict=True)
    uri = f"{resolved.as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    if int(conn.execute("PRAGMA query_only").fetchone()[0]) != 1:
        conn.close()
        raise RuntimeError("SQLite query_only could not be enabled")
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        is not None
    )


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(conn, table):
        return set()
    return {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')}


def _table_digest(conn: sqlite3.Connection, table: str) -> dict[str, Any]:
    if not _table_exists(conn, table):
        return {"present": False, "rows": 0, "sha256": None}
    info = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    primary = [str(row[1]) for row in sorted(info, key=lambda row: int(row[5])) if int(row[5])]
    order_by = ", ".join(f'"{column}"' for column in primary) or "rowid"
    digest = hashlib.sha256()
    row_count = 0
    for row in conn.execute(f'SELECT * FROM "{table}" ORDER BY {order_by}'):
        digest.update(_canonical_bytes(tuple(row)))
        digest.update(b"\n")
        row_count += 1
    return {"present": True, "rows": row_count, "sha256": digest.hexdigest()}


def _scalar(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> int:
    row = conn.execute(sql, tuple(params)).fetchone()
    return int(row[0] or 0) if row is not None else 0


def _schema_and_revisions(conn: sqlite3.Connection) -> dict[str, Any]:
    schema_version = (
        _scalar(conn, "SELECT MAX(version) FROM schema_migrations")
        if _table_exists(conn, "schema_migrations")
        else 0
    )
    track_revision = (
        _scalar(conn, "SELECT current_revision FROM track_identity_state WHERE state_id=1")
        if _table_exists(conn, "track_identity_state")
        else 0
    )
    album_revision = (
        _scalar(conn, "SELECT current_revision FROM album_project_revision_state WHERE state_id=1")
        if _table_exists(conn, "album_project_revision_state")
        else 0
    )
    attribution_state: dict[str, Any]
    if _table_exists(conn, "l3_album_attribution_revision_state"):
        row = conn.execute(
            """SELECT current_revision, status, policy_version,
                      track_identity_revision, album_project_revision,
                      mapping_digest, attributed_count, conflict_count,
                      uncovered_count
                 FROM l3_album_attribution_revision_state WHERE state_id=1"""
        ).fetchone()
        attribution_state = dict(row) if row is not None else {}
    else:
        attribution_state = {"current_revision": 0, "status": "missing"}

    group_tables = {
        table: _table_digest(conn, table)
        for table in ("track_groups", "track_group_l1_members", "release_groups")
    }
    return {
        "schema_migration": schema_version,
        "sqlite_user_version": int(conn.execute("PRAGMA user_version").fetchone()[0]),
        "sqlite_schema_version": int(conn.execute("PRAGMA schema_version").fetchone()[0]),
        "track_identity_revision": track_revision,
        "album_project_revision": album_revision,
        "l3_album_attribution": attribution_state,
        "track_relationship_digest": _digest(group_tables),
    }


def _l2_health(conn: sqlite3.Connection, work_keys: pd.DataFrame) -> dict[str, Any]:
    required = {"track_groups", "track_group_l1_members"}
    missing = sorted(table for table in required if not _table_exists(conn, table))
    if missing:
        return {"status": "missing_schema", "missing_tables": missing}

    group_count = _scalar(
        conn,
        """SELECT COUNT(*) FROM track_groups
             WHERE scope='recording' AND group_status='active'""",
    )
    member_count = _scalar(
        conn,
        """SELECT COUNT(DISTINCT members.l1_id)
             FROM track_group_l1_members members
             JOIN track_groups groups ON groups.group_id=members.group_id
            WHERE groups.scope='recording' AND groups.group_status='active'""",
    )
    membership_count = _scalar(
        conn,
        """SELECT COUNT(*)
             FROM track_group_l1_members members
             JOIN track_groups groups ON groups.group_id=members.group_id
            WHERE groups.scope='recording' AND groups.group_status='active'""",
    )
    overlap_count = _scalar(
        conn,
        """SELECT COUNT(*) FROM (
               SELECT members.l1_id
                 FROM track_group_l1_members members
                 JOIN track_groups groups ON groups.group_id=members.group_id
                WHERE groups.scope='recording' AND groups.group_status='active'
                GROUP BY members.l1_id HAVING COUNT(DISTINCT groups.group_id)>1
           )""",
    )
    undersized_count = _scalar(
        conn,
        """SELECT COUNT(*) FROM (
               SELECT groups.group_id
                 FROM track_groups groups
                 LEFT JOIN track_group_l1_members members
                   ON members.group_id=groups.group_id
                WHERE groups.scope='recording' AND groups.group_status='active'
                GROUP BY groups.group_id HAVING COUNT(DISTINCT members.l1_id)<2
           )""",
    )
    invalid_primary_count = _scalar(
        conn,
        """SELECT COUNT(*) FROM track_groups groups
            WHERE groups.scope='recording' AND groups.group_status='active'
              AND (groups.primary_l1_id IS NULL OR NOT EXISTS (
                  SELECT 1 FROM track_group_l1_members members
                   WHERE members.group_id=groups.group_id
                     AND members.l1_id=groups.primary_l1_id
              ))""",
    )
    duplicate_identity_splits = conn.execute(
        """SELECT automatic_artist_id, automatic_title_key,
                  GROUP_CONCAT(group_id) AS group_ids, COUNT(*) AS group_count
             FROM track_groups
            WHERE scope='recording' AND group_status='active'
              AND automatic_artist_id IS NOT NULL
              AND automatic_title_key IS NOT NULL
            GROUP BY automatic_artist_id, automatic_title_key
           HAVING COUNT(*)>1
            ORDER BY automatic_artist_id, automatic_title_key"""
    ).fetchall()

    split_group_ids: list[int] = []
    if not work_keys.empty:
        member_rows = pd.read_sql_query(
            """SELECT groups.group_id, members.l1_id
                 FROM track_groups groups
                 JOIN track_group_l1_members members ON members.group_id=groups.group_id
                WHERE groups.scope='recording' AND groups.group_status='active'
                ORDER BY groups.group_id, members.l1_id""",
            conn,
        )
        if not member_rows.empty:
            keyed = member_rows.merge(
                work_keys[["l1_id", "canonical_song_key"]],
                on="l1_id",
                how="left",
            )
            split_group_ids = sorted(
                int(group_id)
                for group_id, frame in keyed.groupby("group_id")
                if frame["canonical_song_key"].nunique(dropna=False) > 1
            )

    return {
        "status": "ready",
        "active_group_count": group_count,
        "distinct_member_count": member_count,
        "membership_count": membership_count,
        "member_overlap_count": overlap_count,
        "undersized_group_count": undersized_count,
        "invalid_primary_count": invalid_primary_count,
        "duplicate_identity_split_count": len(duplicate_identity_splits),
        "duplicate_identity_split_samples": [dict(row) for row in duplicate_identity_splits[:20]],
        "recording_split_across_l3_count": len(split_group_ids),
        "recording_split_across_l3_group_ids": split_group_ids[:50],
    }


def _load_raw_play_frame(
    conn: sqlite3.Connection,
    *,
    music_only: bool,
    year_start: int | None,
    year_end: int | None,
) -> pd.DataFrame:
    play_columns = _columns(conn, "plays")
    if not play_columns:
        return pd.DataFrame()
    has_l1 = _table_exists(conn, "track_l1_identities")
    has_external = _table_exists(conn, "track_l1_external_ids")
    has_links = _table_exists(conn, "track_l1_source_links")
    has_spotify_meta = _table_exists(conn, "spotify_track_meta")
    spotify_at_play = "spotify_track_id_at_play" in play_columns

    spotify_token = (
        "COALESCE(NULLIF(p.spotify_track_id_at_play,''), NULLIF(source.spotify_track_id,''))"
        if spotify_at_play
        else "NULLIF(source.spotify_track_id,'')"
    )
    if has_l1 and has_external and has_links:
        l1_expr = f"""COALESCE(
            (SELECT external.l1_id FROM track_l1_external_ids external
              JOIN track_l1_identities identity ON identity.l1_id=external.l1_id
             WHERE external.provider='spotify'
               AND external.external_track_id={spotify_token}
               AND identity.identity_status='active'
             ORDER BY external.is_primary DESC, external.l1_id LIMIT 1),
            (SELECT links.l1_id FROM track_l1_source_links links
              JOIN track_l1_identities identity ON identity.l1_id=links.l1_id
             WHERE links.track_id=p.track_id AND identity.identity_status='active'
             ORDER BY CASE links.evidence_type WHEN 'play_at_time' THEN 0 ELSE 1 END,
                      links.l1_id LIMIT 1),
            p.track_id)"""
    else:
        l1_expr = "p.track_id"
    duration_expr = (
        f"(SELECT meta.duration_ms FROM spotify_track_meta meta "
        f"WHERE meta.spotify_track_id={spotify_token} LIMIT 1)"
        if has_spotify_meta
        else "NULL"
    )
    clauses: list[str] = []
    params: list[Any] = []
    if music_only:
        clauses.append("p.track_id IS NOT NULL")
    if year_start is not None:
        clauses.append("p.ts_year>=?")
        params.append(year_start)
    if year_end is not None:
        clauses.append("p.ts_year<=?")
        params.append(year_end)
    where = " AND ".join(clauses) or "1=1"
    return pd.read_sql_query(
        f"""SELECT p.play_id, p.ts, p.ms_played, p.track_id AS source_track_id,
                   p.source_album_id, {l1_expr} AS l1_id,
                   {duration_expr} AS duration_ms
              FROM plays p
              LEFT JOIN tracks source ON source.track_id=p.track_id
             WHERE {where}
             ORDER BY p.ts, p.play_id""",
        conn,
        params=params,
    )


def _logical_events(raw: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    if raw.empty:
        return raw.assign(canonical_song_key=pd.Series(dtype="object"))
    frame = raw.copy()
    frame["duration_ms"] = pd.to_numeric(frame["duration_ms"], errors="coerce")
    if params["merge_enabled"]:
        return reconstruct_logical_plays(
            frame,
            params["min_ms"],
            identity_column="l1_id",
            dynamic_threshold=params["dynamic_threshold"],
            max_gap_minutes=params["max_merge_gap_minutes"],
            boundary_column="source_album_id",
        )
    thresholds = pd.Series(params["min_ms"], index=frame.index, dtype="int64")
    if params["dynamic_threshold"]:
        durations = frame["duration_ms"].fillna(0).astype("int64")
        thresholds = pd.concat([thresholds, (durations * 0.1).astype("int64")], axis=1).max(axis=1)
    return frame[frame["ms_played"] >= thresholds].copy()


def _l3_attribution_health(
    conn: sqlite3.Connection,
    work_keys: pd.DataFrame,
    events: pd.DataFrame,
    *,
    include_compilations: bool,
    revisions: dict[str, Any],
) -> tuple[dict[str, Any], pd.DataFrame]:
    attribution_columns = [
        "canonical_song_key",
        "target_project_id",
        "origin_release_project_id",
        "attribution_kind",
        "decision_source",
        "confidence",
    ]
    if _table_exists(conn, "l3_song_album_attributions"):
        attributions = pd.read_sql_query(
            """SELECT attribution.canonical_song_key,
                      attribution.target_project_id,
                      attribution.origin_release_project_id,
                      attribution.attribution_kind,
                      attribution.decision_source,
                      attribution.confidence,
                      attribution.policy_version,
                      attribution.track_identity_revision,
                      attribution.album_project_revision,
                      target.canonical_name AS target_project_name,
                      target.project_type, target.include_in_charts
                 FROM l3_song_album_attributions attribution
                 LEFT JOIN album_projects target
                   ON target.project_id=attribution.target_project_id
                ORDER BY attribution.canonical_song_key""",
            conn,
        )
    else:
        attributions = pd.DataFrame(columns=attribution_columns)
    if _table_exists(conn, "l3_song_album_attribution_issues"):
        issues = pd.read_sql_query(
            """SELECT canonical_song_key, issue_kind
                 FROM l3_song_album_attribution_issues
                ORDER BY canonical_song_key, issue_kind""",
            conn,
        )
    else:
        issues = pd.DataFrame(columns=["canonical_song_key", "issue_kind"])
    if _table_exists(conn, "l3_song_album_attribution_exclusions"):
        exclusions = pd.read_sql_query(
            """SELECT canonical_song_key, reason_code
                 FROM l3_song_album_attribution_exclusions
                ORDER BY canonical_song_key""",
            conn,
        )
    else:
        exclusions = pd.DataFrame(columns=["canonical_song_key", "reason_code"])

    work_count = int(work_keys["canonical_song_key"].nunique()) if not work_keys.empty else 0
    attributed_keys = set(attributions.get("canonical_song_key", pd.Series(dtype=str)).astype(str))
    issue_keys = set(issues.get("canonical_song_key", pd.Series(dtype=str)).astype(str))
    exclusion_keys = set(exclusions.get("canonical_song_key", pd.Series(dtype=str)).astype(str))
    work_key_set = set(work_keys.get("canonical_song_key", pd.Series(dtype=str)).astype(str))
    uncovered_keys = sorted(work_key_set - attributed_keys)
    silent_uncovered_keys = sorted(set(uncovered_keys) - issue_keys - exclusion_keys)
    orphan_attribution_keys = sorted(attributed_keys - work_key_set)

    owner_counts = (
        attributions.groupby("canonical_song_key").size().to_dict()
        if not attributions.empty
        else {}
    )
    multi_owner_keys = sorted(str(key) for key, count in owner_counts.items() if int(count) > 1)

    keyed_events = events.copy()
    if not keyed_events.empty:
        key_map = work_keys.set_index("l1_id")["canonical_song_key"] if not work_keys.empty else {}
        keyed_events["canonical_song_key"] = keyed_events["l1_id"].map(key_map)
        keyed_events["canonical_song_key"] = keyed_events["canonical_song_key"].fillna(
            "l1:" + keyed_events["l1_id"].astype("Int64").astype(str)
        )
    else:
        keyed_events["canonical_song_key"] = pd.Series(dtype="object")
    play_counts = keyed_events.groupby("canonical_song_key").size().to_dict()
    play_bearing_silent = [key for key in silent_uncovered_keys if int(play_counts.get(key, 0)) > 0]

    eligible_attributions = attributions.copy()
    if not eligible_attributions.empty:
        eligible_attributions = eligible_attributions[eligible_attributions["include_in_charts"] == 1]
        if not include_compilations:
            eligible_attributions = eligible_attributions[
                eligible_attributions["project_type"] != "compilation_exclusive"
            ]
    eligible_owner_counts = (
        eligible_attributions.groupby("canonical_song_key").size().to_dict()
        if not eligible_attributions.empty
        else {}
    )
    event_keys = keyed_events["canonical_song_key"].astype(str).tolist()
    attributed_event_count = sum(int(eligible_owner_counts.get(key, 0)) == 1 for key in event_keys)
    multi_owner_event_count = sum(int(eligible_owner_counts.get(key, 0)) > 1 for key in event_keys)
    excluded_event_count = sum(
        int(owner_counts.get(key, 0)) == 1 and int(eligible_owner_counts.get(key, 0)) == 0
        for key in event_keys
    )
    policy_excluded_event_count = sum(
        int(owner_counts.get(key, 0)) == 0 and key in exclusion_keys for key in event_keys
    )
    uncovered_event_count = sum(
        int(owner_counts.get(key, 0)) == 0 and key not in exclusion_keys for key in event_keys
    )
    assignment_rows = sum(int(eligible_owner_counts.get(key, 0)) for key in event_keys)
    event_count = len(event_keys)
    conservation_delta = event_count - (
        attributed_event_count
        + multi_owner_event_count
        + excluded_event_count
        + policy_excluded_event_count
        + uncovered_event_count
    )

    state = revisions["l3_album_attribution"]
    row_policy_versions = sorted(
        set(attributions.get("policy_version", pd.Series(dtype=str)).astype(str))
    )
    row_track_revisions = sorted(
        int(value)
        for value in attributions.get("track_identity_revision", pd.Series(dtype=int)).dropna().unique()
    )
    row_album_revisions = sorted(
        int(value)
        for value in attributions.get("album_project_revision", pd.Series(dtype=int)).dropna().unique()
    )
    state_count_mismatches = {
        name: {"state": int(state.get(name) or 0), "observed": observed}
        for name, observed in (
            ("attributed_count", len(attributions)),
            ("conflict_count", int((issues.get("issue_kind") == "conflict").sum())),
            ("uncovered_count", int((issues.get("issue_kind") == "uncovered").sum())),
        )
        if int(state.get(name) or 0) != observed
    }
    policy_stale = bool(
        state.get("policy_version") != L3_ALBUM_ATTRIBUTION_POLICY_VERSION
        or row_policy_versions not in ([], [L3_ALBUM_ATTRIBUTION_POLICY_VERSION])
    )
    state_stale = bool(
        state.get("status") != "ready"
        or int(state.get("track_identity_revision") or 0)
        != int(revisions["track_identity_revision"])
        or int(state.get("album_project_revision") or 0)
        != int(revisions["album_project_revision"])
        or row_track_revisions not in ([], [int(revisions["track_identity_revision"])])
        or row_album_revisions not in ([], [int(revisions["album_project_revision"])])
        or policy_stale
        or bool(state_count_mismatches)
    )
    coverage = round(len(attributed_keys & work_key_set) / work_count, 6) if work_count else 1.0
    return (
        {
            "status": "ready" if _table_exists(conn, "l3_song_album_attributions") else "missing_schema",
            "work_count": work_count,
            "attributed_work_count": len(attributed_keys & work_key_set),
            "issue_work_count": len(issue_keys & work_key_set),
            "excluded_work_count": len(exclusion_keys & work_key_set),
            "uncovered_work_count": len(uncovered_keys),
            "silent_uncovered_work_count": len(silent_uncovered_keys),
            "play_bearing_silent_uncovered_count": len(play_bearing_silent),
            "play_bearing_silent_uncovered": [
                {"canonical_song_key": key, "logical_play_count": int(play_counts[key])}
                for key in play_bearing_silent[:50]
            ],
            "coverage_rate": coverage,
            "projection_row_count": len(attributions),
            "orphan_attribution_work_count": len(orphan_attribution_keys),
            "orphan_attribution_work_keys": orphan_attribution_keys[:50],
            "decision_source_counts": dict(
                sorted(Counter(attributions.get("decision_source", [])).items())
            ),
            "attribution_kind_counts": dict(
                sorted(Counter(attributions.get("attribution_kind", [])).items())
            ),
            "state_stale": state_stale,
            "expected_policy_version": L3_ALBUM_ATTRIBUTION_POLICY_VERSION,
            "row_policy_versions": row_policy_versions,
            "row_track_identity_revisions": row_track_revisions,
            "row_album_project_revisions": row_album_revisions,
            "policy_stale": policy_stale,
            "state_count_mismatches": state_count_mismatches,
            "multi_owner_work_count": len(multi_owner_keys),
            "multi_owner_work_keys": multi_owner_keys[:50],
            "logical_event_conservation": {
                "logical_event_count": event_count,
                "attributed_event_count": attributed_event_count,
                "uncovered_event_count": uncovered_event_count,
                "excluded_compilation_event_count": excluded_event_count,
                "policy_excluded_event_count": policy_excluded_event_count,
                "multi_owner_event_count": multi_owner_event_count,
                "assignment_row_count": assignment_rows,
                "conservation_delta": conservation_delta,
            },
        },
        keyed_events,
    )


def _l1_strong_conflicts(conn: sqlite3.Connection) -> dict[str, Any]:
    before_changes = conn.total_changes
    plan = build_l1_external_identity_risk_plan(conn, include_keep=False)
    if conn.total_changes != before_changes:
        raise RuntimeError("L1 risk audit mutated the database")
    if plan.get("status") != "ready":
        return {
            "status": str(plan.get("status") or "blocked"),
            "missing_tables": plan.get("missing_tables", []),
        }
    owners = list(plan.get("owners") or [])
    return {
        "status": "ready",
        "summary": plan.get("summary") or {},
        "strong_conflict_count": sum(
            owner.get("recommendation") in {"split", "review"} for owner in owners
        ),
        "samples": [
            {
                "l1_id": int(owner["l1_id"]),
                "recommendation": owner["recommendation"],
                "external_ids": [
                    {
                        "spotify_track_id": item.get("spotify_track_id"),
                        "recommendation": item.get("recommendation"),
                        "evidence": item.get("evidence") or [],
                        "blockers": item.get("blockers") or [],
                    }
                    for item in owner.get("external_ids", [])
                    if item.get("recommendation") != "keep"
                ],
            }
            for owner in owners[:20]
        ],
    }


def _fixed_samples(
    conn: sqlite3.Connection,
    work_keys: pd.DataFrame,
    events: pd.DataFrame,
) -> list[dict[str, Any]]:
    play_counts = events.groupby("canonical_song_key").size().to_dict() if not events.empty else {}
    attribution_by_key: dict[str, dict[str, Any]] = {}
    if _table_exists(conn, "l3_song_album_attributions"):
        for row in conn.execute(
            """SELECT attribution.canonical_song_key,
                      attribution.target_project_id, target.canonical_name,
                      attribution.attribution_kind, attribution.decision_source
                 FROM l3_song_album_attributions attribution
                 LEFT JOIN album_projects target
                   ON target.project_id=attribution.target_project_id
                ORDER BY attribution.canonical_song_key"""
        ):
            attribution_by_key[str(row[0])] = {
                "target_project_id": int(row[1]),
                "target_project_name": row[2],
                "attribution_kind": row[3],
                "decision_source": row[4],
            }

    samples: list[dict[str, Any]] = []
    for sample_id, kind, needles in FIXED_SAMPLE_SPECS:
        if kind == "track":
            matched = work_keys[
                work_keys["canonical_song_name"].fillna("").str.casefold().apply(
                    lambda value: any(needle in value for needle in needles)
                )
            ]
            keys = sorted(set(matched.get("canonical_song_key", [])))
            samples.append(
                {
                    "sample_id": sample_id,
                    "kind": kind,
                    "matched_work_count": len(keys),
                    "works": [
                        {
                            "canonical_song_key": key,
                            "canonical_song_name": str(
                                matched[matched["canonical_song_key"] == key].iloc[0][
                                    "canonical_song_name"
                                ]
                            ),
                            "logical_play_count": int(play_counts.get(key, 0)),
                            "attribution": attribution_by_key.get(key),
                        }
                        for key in keys[:30]
                    ],
                }
            )
        else:
            rows = []
            if _table_exists(conn, "album_projects"):
                for row in conn.execute(
                    """SELECT project_id, canonical_name, scope, project_type,
                              include_in_charts
                         FROM album_projects ORDER BY project_id"""
                ):
                    name = str(row[1]).casefold()
                    if any(needle in name for needle in needles):
                        target_count = _scalar(
                            conn,
                            "SELECT COUNT(*) FROM l3_song_album_attributions WHERE target_project_id=?",
                            (int(row[0]),),
                        ) if _table_exists(conn, "l3_song_album_attributions") else 0
                        origin_count = _scalar(
                            conn,
                            "SELECT COUNT(*) FROM l3_song_album_attributions WHERE origin_release_project_id=?",
                            (int(row[0]),),
                        ) if _table_exists(conn, "l3_song_album_attributions") else 0
                        rows.append(
                            {
                                "project_id": int(row[0]),
                                "canonical_name": row[1],
                                "scope": row[2],
                                "project_type": row[3],
                                "include_in_charts": int(row[4]),
                                "target_work_count": target_count,
                                "origin_work_count": origin_count,
                            }
                        )
            samples.append(
                {
                    "sample_id": sample_id,
                    "kind": kind,
                    "matched_project_count": len(rows),
                    "projects": rows[:30],
                }
            )
    return samples


def run_probe(db_path: Path, params: dict[str, Any]) -> dict[str, Any]:
    resolved_path = db_path.expanduser().resolve(strict=True)
    conn = open_readonly_connection(resolved_path)
    try:
        before_changes = conn.total_changes
        revisions = _schema_and_revisions(conn)
        raw_facts = {table: _table_digest(conn, table) for table in RAW_FACT_TABLES}
        work_keys = load_l3_song_work_keys(conn)
        raw_events = _load_raw_play_frame(
            conn,
            music_only=params["music_only"],
            year_start=params["year_start"],
            year_end=params["year_end"],
        )
        logical_events = _logical_events(raw_events, params)
        l3, keyed_events = _l3_attribution_health(
            conn,
            work_keys,
            logical_events,
            include_compilations=params["include_compilations"],
            revisions=revisions,
        )
        l2 = _l2_health(conn, work_keys)
        l1 = _l1_strong_conflicts(conn)
        samples = _fixed_samples(conn, work_keys, keyed_events)
        if conn.total_changes != before_changes:
            raise RuntimeError("integrity probe unexpectedly mutated the database")
        database_fingerprint_payload = {
            "resolved_path": str(resolved_path),
            "file_size": resolved_path.stat().st_size,
            "raw_facts": raw_facts,
            "revisions": revisions,
        }
        hard_issue_count = sum(
            int(value)
            for value in (
                int(l2.get("status") != "ready"),
                l2.get("member_overlap_count", 0),
                l2.get("undersized_group_count", 0),
                l2.get("invalid_primary_count", 0),
                l2.get("recording_split_across_l3_count", 0),
                int(l3.get("status") != "ready"),
                l3.get("orphan_attribution_work_count", 0),
                l3.get("multi_owner_work_count", 0),
                l3.get("logical_event_conservation", {}).get("multi_owner_event_count", 0),
                abs(l3.get("logical_event_conservation", {}).get("conservation_delta", 0)),
                int(bool(l3.get("state_stale"))),
                int(l1.get("status") != "ready"),
            )
        )
        warning_count = int(l3.get("play_bearing_silent_uncovered_count", 0)) + int(
            l1.get("strong_conflict_count", 0)
        )
        report: dict[str, Any] = {
            "schema_version": REPORT_SCHEMA_VERSION,
            "status": "fail" if hard_issue_count else "warning" if warning_count else "pass",
            "parameters": params,
            "database_fingerprint": {
                **database_fingerprint_payload,
                "sha256": _digest(database_fingerprint_payload),
            },
            "schema_and_revisions": revisions,
            "l2_recording_groups": l2,
            "l3_work_attribution": l3,
            "l1_strong_conflicts": l1,
            "fixed_samples": samples,
            "summary": {
                "hard_issue_count": hard_issue_count,
                "warning_count": warning_count,
            },
        }
        report["core_digest"] = _digest(report)
        return report
    finally:
        conn.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, required=True)
    parser.add_argument("--min-ms", type=int, default=30_000)
    parser.add_argument("--music-only", type=_parse_bool, default=True)
    parser.add_argument("--merge-enabled", type=_parse_bool, default=True)
    parser.add_argument("--dynamic-threshold", type=_parse_bool, default=True)
    parser.add_argument("--max-merge-gap-minutes", type=int, default=5)
    parser.add_argument("--include-compilations", type=_parse_bool, default=False)
    parser.add_argument("--year-start", type=int)
    parser.add_argument("--year-end", type=int)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args(argv)
    if args.min_ms < 0:
        parser.error("--min-ms must be non-negative")
    if args.max_merge_gap_minutes < 1:
        parser.error("--max-merge-gap-minutes must be at least 1")
    if args.year_start is not None and args.year_end is not None and args.year_start > args.year_end:
        parser.error("--year-start must not exceed --year-end")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    params = {
        "min_ms": args.min_ms,
        "music_only": args.music_only,
        "merge_enabled": args.merge_enabled,
        "dynamic_threshold": args.dynamic_threshold,
        "max_merge_gap_minutes": args.max_merge_gap_minutes,
        "include_compilations": args.include_compilations,
        "year_start": args.year_start,
        "year_end": args.year_end,
    }
    report = run_probe(args.db_path, params)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
