"""Stable L3 song-work keys shared by album planners and statistics.

The public representative track may change without changing the underlying
composition group.  Album attribution therefore keys grouped works by the
active composition group id and singleton works by their stable L1 owner id.
"""

from __future__ import annotations

import sqlite3

import pandas as pd


def load_l3_song_work_keys(conn: sqlite3.Connection) -> pd.DataFrame:
    """Return one L3 work key for every active L1 owner."""

    has_l1 = conn.execute(
        """SELECT 1 FROM sqlite_master
            WHERE type='table' AND name='track_l1_identities'"""
    ).fetchone()
    if not has_l1:
        # Compatibility for compact contract fixtures and pre-L1 databases.
        # Production schema 59+ always takes the stable branch below.
        from backend.domains.playback.track_groups import load_track_group_keys

        legacy = load_track_group_keys(conn, merge_level=3)
        if legacy.empty:
            return pd.DataFrame(
                columns=[
                    "l1_id",
                    "track_id",
                    "representative_track_id",
                    "composition_group_id",
                    "canonical_song_key",
                    "canonical_song_name",
                ]
            )
        legacy = legacy.copy()
        legacy["l1_id"] = legacy["track_id"].astype(int)
        legacy["representative_track_id"] = legacy["track_agg_id"].astype(int)
        legacy["composition_group_id"] = pd.NA
        legacy["canonical_song_key"] = "legacy:" + legacy["track_agg_id"].astype(int).astype(str)
        legacy["canonical_song_name"] = legacy["track_agg_name"]
        return legacy[
            [
                "l1_id",
                "track_id",
                "representative_track_id",
                "composition_group_id",
                "canonical_song_key",
                "canonical_song_name",
            ]
        ]

    rows = conn.execute(
        """SELECT identities.l1_id,
                  identities.representative_track_id,
                  tracks.track_name,
                  direct.group_id AS direct_composition_id,
                  parent.group_id AS parent_composition_id,
                  COALESCE(direct.canonical_name, parent.canonical_name, tracks.track_name)
                      AS canonical_song_name
             FROM track_l1_identities identities
             JOIN tracks ON tracks.track_id=identities.representative_track_id
             LEFT JOIN track_group_l1_members direct_members
               ON direct_members.l1_id=identities.l1_id
             LEFT JOIN track_groups direct
               ON direct.group_id=direct_members.group_id
              AND direct.scope='composition'
              AND direct.group_status='active'
             LEFT JOIN track_group_l1_members recording_members
               ON recording_members.l1_id=identities.l1_id
             LEFT JOIN track_groups recording
               ON recording.group_id=recording_members.group_id
              AND recording.scope='recording'
              AND recording.group_status='active'
             LEFT JOIN track_groups parent
               ON parent.group_id=recording.parent_group_id
              AND parent.scope='composition'
              AND parent.group_status='active'
            WHERE identities.identity_status='active'
            ORDER BY identities.l1_id,
                     COALESCE(direct.group_id, parent.group_id)"""
    ).fetchall()
    grouped: dict[int, dict[str, object]] = {}
    composition_ids_by_l1: dict[int, set[int]] = {}
    for row in rows:
        l1_id = int(row["l1_id"])
        composition_ids = {
            int(value)
            for value in (row["direct_composition_id"], row["parent_composition_id"])
            if value is not None
        }
        item = grouped.setdefault(
            l1_id,
            {
                "l1_id": l1_id,
                "track_id": l1_id,
                "representative_track_id": int(row["representative_track_id"]),
                "canonical_song_name": str(row["canonical_song_name"]),
            },
        )
        composition_ids_by_l1.setdefault(l1_id, set()).update(composition_ids)
    public_rows: list[dict[str, object]] = []
    for l1_id, item in grouped.items():
        sorted_composition_ids = sorted(composition_ids_by_l1.get(l1_id, set()))
        if len(sorted_composition_ids) > 1:
            raise RuntimeError(
                f"L1 owner {item['l1_id']} resolves to multiple active composition groups: "
                f"{sorted_composition_ids}"
            )
        item["composition_group_id"] = sorted_composition_ids[0] if sorted_composition_ids else None
        item["canonical_song_key"] = (
            f"composition:{sorted_composition_ids[0]}"
            if sorted_composition_ids
            else f"l1:{item['l1_id']}"
        )
        public_rows.append(item)
    return pd.DataFrame.from_records(
        public_rows,
        columns=[
            "l1_id",
            "track_id",
            "representative_track_id",
            "composition_group_id",
            "canonical_song_key",
            "canonical_song_name",
        ],
    )


def apply_l3_song_work_keys(df: pd.DataFrame, conn: sqlite3.Connection) -> pd.DataFrame:
    """Attach the stable L3 key to rows whose ``track_id`` is an L1 owner id."""

    out = df.copy()
    if out.empty:
        out["canonical_song_key"] = pd.Series(dtype="object")
        out["canonical_song_name"] = pd.Series(dtype="object")
        return out
    keys = load_l3_song_work_keys(conn)
    if keys.empty:
        out["canonical_song_key"] = "l1:" + out["track_id"].astype("Int64").astype(str)
        if "canonical_song_name" not in out.columns:
            out["canonical_song_name"] = out.get("track_name", "")
        return out
    key_map = keys.set_index("track_id")
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
    keys = load_l3_song_work_keys(conn)
    match = keys[keys["l1_id"] == int(l1_id)]
    if match.empty:
        return f"l1:{int(l1_id)}"
    return str(match.iloc[0]["canonical_song_key"])
