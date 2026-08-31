"""Stable L3 song-work keys shared by album planners and statistics.

L3 resolves an active L1 owner through the version graph in this order:
direct composition, a recording group's composition parent, the recording
group itself, then the singleton L1 owner. Keys use group/L1 identities rather
than a mutable representative track.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from typing import Any

import pandas as pd

L3_SONG_WORK_KEY_POLICY_VERSION = "l3_stable_work_key_v2"

_OUTPUT_COLUMNS = [
    "l1_id",
    "track_id",
    "representative_l1_id",
    "representative_track_id",
    "work_group_id",
    "composition_group_id",
    "recording_group_id",
    "canonical_song_key",
    "canonical_song_name",
    "track_group_scope",
    "track_identity_revision",
]


class L3SongWorkConflictError(RuntimeError):
    """An L1 owner belongs to several active groups at the same scope."""

    def __init__(self, l1_id: int, scope: str, group_ids: list[int]) -> None:
        self.l1_id = int(l1_id)
        self.scope = str(scope)
        self.group_ids = tuple(sorted({int(group_id) for group_id in group_ids}))
        super().__init__(
            f"L1 owner {self.l1_id} resolves to multiple active {self.scope} groups: "
            f"{list(self.group_ids)}"
        )


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(conn, table):
        return set()
    return {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')}


def _fetch_dicts(conn: sqlite3.Connection, query: str) -> list[dict[str, Any]]:
    cursor = conn.execute(query)
    columns = [str(item[0]) for item in cursor.description or ()]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _track_revision(conn: sqlite3.Connection) -> int:
    if not _table_exists(conn, "track_identity_state"):
        return 0
    row = conn.execute(
        "SELECT current_revision FROM track_identity_state WHERE state_id=1"
    ).fetchone()
    return int(row[0] or 0) if row is not None else 0


def _track_names(conn: sqlite3.Connection) -> dict[int, str]:
    columns = _table_columns(conn, "tracks")
    if "track_id" not in columns:
        return {}
    name_expression = "track_name" if "track_name" in columns else "''"
    return {
        int(row["track_id"]): str(row["track_name"] or "")
        for row in _fetch_dicts(
            conn,
            f"SELECT track_id, {name_expression} AS track_name FROM tracks ORDER BY track_id",
        )
    }


def _active_identities(
    conn: sqlite3.Connection,
) -> tuple[dict[int, int], dict[int, int]]:
    """Return representative track per L1 and an unambiguous track-to-L1 map."""

    identity_columns = _table_columns(conn, "track_l1_identities")
    if "l1_id" not in identity_columns:
        # Compact pre-L1 fixtures treat the historical track id as their owner.
        track_ids = sorted(_track_names(conn))
        return (
            {track_id: track_id for track_id in track_ids},
            {track_id: track_id for track_id in track_ids},
        )

    representative_expression = (
        "representative_track_id" if "representative_track_id" in identity_columns else "NULL"
    )
    fallback_expression = "fallback_track_id" if "fallback_track_id" in identity_columns else "NULL"
    status_filter = (
        "WHERE identity_status='active'" if "identity_status" in identity_columns else ""
    )
    rows = _fetch_dicts(
        conn,
        f"""SELECT l1_id,
                   {representative_expression} AS representative_track_id,
                   {fallback_expression} AS fallback_track_id
              FROM track_l1_identities
              {status_filter}
             ORDER BY l1_id""",
    )
    representatives: dict[int, int] = {}
    for row in rows:
        l1_id = int(row["l1_id"])
        representative = row["representative_track_id"]
        fallback = row["fallback_track_id"]
        if representative is not None:
            representatives[l1_id] = int(representative)
        elif fallback is not None:
            representatives[l1_id] = int(fallback)
        else:
            # Production identities always have a representative. This keeps
            # compact migration fixtures deterministic.
            representatives[l1_id] = l1_id

    owners_by_track: dict[int, set[int]] = defaultdict(set)
    for l1_id, track_id in representatives.items():
        owners_by_track[track_id].add(l1_id)
    source_columns = _table_columns(conn, "track_l1_source_links")
    if {"l1_id", "track_id"} <= source_columns:
        for row in _fetch_dicts(
            conn,
            "SELECT DISTINCT l1_id, track_id FROM track_l1_source_links ORDER BY l1_id, track_id",
        ):
            l1_id = int(row["l1_id"])
            if l1_id in representatives:
                owners_by_track[int(row["track_id"])].add(l1_id)
    track_to_l1 = {
        track_id: next(iter(l1_ids))
        for track_id, l1_ids in owners_by_track.items()
        if len(l1_ids) == 1
    }
    return representatives, track_to_l1


def _active_groups(conn: sqlite3.Connection) -> dict[int, dict[str, Any]]:
    columns = _table_columns(conn, "track_groups")
    if not {"group_id", "scope"} <= columns:
        return {}
    optional = {
        "canonical_name": "NULL",
        "primary_track_id": "NULL",
        "primary_l1_id": "NULL",
        "parent_group_id": "NULL",
    }
    expressions = [
        column if column in columns else f"{fallback} AS {column}"
        for column, fallback in optional.items()
    ]
    status_filter = "WHERE group_status='active'" if "group_status" in columns else ""
    rows = _fetch_dicts(
        conn,
        f"""SELECT group_id, scope, {", ".join(expressions)}
              FROM track_groups
              {status_filter}
             ORDER BY group_id""",
    )
    return {int(row["group_id"]): row for row in rows}


def _group_memberships(conn: sqlite3.Connection, *, modern: bool) -> dict[int, set[int]]:
    table = "track_group_l1_members" if modern else "track_group_members"
    member_column = "l1_id" if modern else "track_id"
    columns = _table_columns(conn, table)
    if not {"group_id", member_column} <= columns:
        return {}
    grouped: dict[int, set[int]] = defaultdict(set)
    for row in _fetch_dicts(
        conn,
        f"SELECT group_id, {member_column} AS l1_id FROM {table} "
        f"ORDER BY group_id, {member_column}",
    ):
        grouped[int(row["group_id"])].add(int(row["l1_id"]))
    return dict(grouped)


def _representative_l1_id(
    group: dict[str, Any],
    members: dict[int, set[int]],
    representatives: dict[int, int],
    track_to_l1: dict[int, int],
    fallback_l1_id: int,
) -> int:
    primary_l1_id = group.get("primary_l1_id")
    if primary_l1_id is not None and int(primary_l1_id) in representatives:
        return int(primary_l1_id)
    primary_track_id = group.get("primary_track_id")
    if primary_track_id is not None and int(primary_track_id) in track_to_l1:
        return int(track_to_l1[int(primary_track_id)])
    active_members = sorted(
        l1_id for l1_id in members.get(int(group["group_id"]), set()) if l1_id in representatives
    )
    return active_members[0] if active_members else int(fallback_l1_id)


def load_l3_song_work_keys(conn: sqlite3.Connection) -> pd.DataFrame:
    """Return exactly one deterministic L3 work key for every active L1 owner."""

    modern = _table_exists(conn, "track_l1_identities")
    representatives, track_to_l1 = _active_identities(conn)
    if not representatives:
        return pd.DataFrame(columns=_OUTPUT_COLUMNS)

    names = _track_names(conn)
    groups = _active_groups(conn)
    members = _group_memberships(conn, modern=modern)
    memberships_by_l1: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for group_id, l1_ids in members.items():
        group = groups.get(group_id)
        if group is None:
            continue
        for l1_id in l1_ids:
            if l1_id in representatives:
                memberships_by_l1[l1_id].append(group)

    revision = _track_revision(conn)
    public_rows: list[dict[str, object]] = []
    for l1_id in sorted(representatives):
        memberships = memberships_by_l1.get(l1_id, [])
        compositions = sorted(
            (group for group in memberships if group["scope"] == "composition"),
            key=lambda group: int(group["group_id"]),
        )
        recordings = sorted(
            (group for group in memberships if group["scope"] == "recording"),
            key=lambda group: int(group["group_id"]),
        )
        if len(compositions) > 1:
            raise L3SongWorkConflictError(
                l1_id, "composition", [int(group["group_id"]) for group in compositions]
            )
        if len(recordings) > 1:
            raise L3SongWorkConflictError(
                l1_id, "recording", [int(group["group_id"]) for group in recordings]
            )

        direct_composition = compositions[0] if compositions else None
        recording = recordings[0] if recordings else None
        parent_composition = None
        if recording is not None and recording.get("parent_group_id") is not None:
            candidate = groups.get(int(recording["parent_group_id"]))
            if candidate is not None and candidate["scope"] == "composition":
                parent_composition = candidate

        selected_group = direct_composition or parent_composition or recording
        if selected_group is None:
            representative_l1_id = l1_id
            representative_track_id = representatives[l1_id]
            work_group_id = None
            composition_group_id = None
            recording_group_id = None
            scope = "l1"
            key = f"l1:{l1_id}"
            canonical_name = names.get(representative_track_id, "")
        else:
            representative_l1_id = _representative_l1_id(
                selected_group, members, representatives, track_to_l1, l1_id
            )
            representative_track_id = representatives.get(representative_l1_id)
            if (
                representative_track_id is None
                and selected_group.get("primary_track_id") is not None
            ):
                representative_track_id = int(selected_group["primary_track_id"])
            if representative_track_id is None:
                representative_track_id = representatives[l1_id]
            work_group_id = int(selected_group["group_id"])
            scope = str(selected_group["scope"])
            composition_group_id = work_group_id if scope == "composition" else None
            recording_group_id = (
                int(recording["group_id"])
                if recording is not None
                else (work_group_id if scope == "recording" else None)
            )
            key = f"{scope}:{work_group_id}"
            canonical_name = str(
                selected_group.get("canonical_name") or names.get(representative_track_id, "")
            )

        public_rows.append(
            {
                "l1_id": l1_id,
                # Album-project membership is already L1-normalized and maps on
                # this compatibility column.
                "track_id": l1_id,
                "representative_l1_id": representative_l1_id,
                "representative_track_id": representative_track_id,
                "work_group_id": work_group_id,
                "composition_group_id": composition_group_id,
                "recording_group_id": recording_group_id,
                "canonical_song_key": key,
                "canonical_song_name": canonical_name,
                "track_group_scope": scope,
                "track_identity_revision": revision,
            }
        )
    return pd.DataFrame.from_records(public_rows, columns=_OUTPUT_COLUMNS)


def apply_l3_song_work_keys(df: pd.DataFrame, conn: sqlite3.Connection) -> pd.DataFrame:
    """Attach stable L3 keys to rows whose ``track_id`` is an L1 owner id."""

    out = df.copy()
    if out.empty:
        out["canonical_song_key"] = pd.Series(dtype="object")
        out["canonical_song_name"] = pd.Series(dtype="object")
        return out
    keys = load_l3_song_work_keys(conn)
    key_map = keys.set_index("l1_id") if not keys.empty else pd.DataFrame()
    if keys.empty:
        mapped_key = pd.Series(index=out.index, dtype="object")
        mapped_name = pd.Series(index=out.index, dtype="object")
    else:
        mapped_key = out["track_id"].map(key_map["canonical_song_key"])
        mapped_name = out["track_id"].map(key_map["canonical_song_name"])
    out["canonical_song_key"] = mapped_key.fillna(
        "l1:" + out["track_id"].astype("Int64").astype(str)
    )
    if "canonical_song_name" not in out.columns:
        out["canonical_song_name"] = out.get("track_name", "")
    out.loc[mapped_name.notna(), "canonical_song_name"] = mapped_name[mapped_name.notna()]
    return out


def resolve_l3_song_work_key(conn: sqlite3.Connection, l1_id: int) -> str:
    """Resolve one L1 owner to its stable L3 work key."""

    keys = load_l3_song_work_keys(conn)
    match = keys[keys["l1_id"] == int(l1_id)]
    if match.empty:
        return f"l1:{int(l1_id)}"
    return str(match.iloc[0]["canonical_song_key"])
