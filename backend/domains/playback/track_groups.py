"""Track version group key resolution for L1/L2/L3 merge levels.

At L1 (no merge): returns empty DataFrame.
At L2 (recording): maps remasters/alternate versions to canonical track.
At L3 (composition): maps acoustic/live/demo versions to canonical track (includes recording scope).
"""

from __future__ import annotations

import sqlite3

import pandas as pd


def load_track_group_keys(conn: sqlite3.Connection, merge_level: int) -> pd.DataFrame:
    """Return a DataFrame mapping track_id → canonical aggregation key.

    Columns: track_id, track_agg_id, track_agg_name, track_group_scope
    """
    has_l1_members = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='track_group_l1_members'"
    ).fetchone()
    if merge_level <= 1:
        if not has_l1_members:
            return pd.DataFrame(
                columns=["track_id", "track_agg_id", "track_agg_name", "track_group_scope"]
            )
        return pd.DataFrame(
            columns=[
                "l1_id",
                "track_agg_l1_id",
                "track_id",
                "track_agg_id",
                "track_agg_name",
                "track_group_scope",
            ]
        )

    if has_l1_members:
        scope_filter = "('composition', 'recording')" if merge_level >= 3 else "('recording')"
        df = pd.read_sql_query(
            f"""SELECT members.l1_id,
                       COALESCE(parent.primary_l1_id, groups.primary_l1_id) AS track_agg_l1_id,
                       members.l1_id AS track_id,
                       COALESCE(parent.primary_l1_id, groups.primary_l1_id) AS track_agg_id,
                       member_identity.representative_track_id AS representative_track_id,
                       primary_identity.representative_track_id AS representative_track_agg_id,
                       COALESCE(parent.canonical_name, groups.canonical_name) AS track_agg_name,
                       CASE WHEN parent.group_id IS NOT NULL THEN 'composition'
                            ELSE groups.scope END AS track_group_scope
                  FROM track_group_l1_members members
                  JOIN track_groups groups ON groups.group_id=members.group_id
                  LEFT JOIN track_groups parent
                    ON groups.parent_group_id=parent.group_id
                   AND parent.scope='composition'
                   AND parent.group_status='active'
                  LEFT JOIN track_l1_identities member_identity
                    ON member_identity.l1_id=members.l1_id
                  LEFT JOIN track_l1_identities primary_identity
                    ON primary_identity.l1_id=COALESCE(
                        parent.primary_l1_id, groups.primary_l1_id
                    )
                 WHERE groups.group_status='active'
                   AND groups.scope IN {scope_filter}""",
            conn,
        )
        if df.empty:
            return df
        df["_scope_rank"] = df["track_group_scope"].map({"composition": 0, "recording": 1})
        return (
            df.sort_values(["l1_id", "_scope_rank", "track_agg_l1_id"])
            .drop_duplicates("l1_id")
            .drop(columns=["_scope_rank"])
        )

    if merge_level >= 3:
        # L3: all recording + composition members, with parent resolution.
        # Recording groups that have parent_group_id → composition group are
        # resolved to the composition canonical name (R6 child-group expansion).
        # track_agg_id uses primary_track_id (a real track id) to avoid
        # group_id collisions with unrelated tracks.
        df = pd.read_sql_query(
            """SELECT tgm.track_id,
                      COALESCE(parent_tg.primary_track_id, tg.primary_track_id) AS track_agg_id,
                      COALESCE(parent_tg.canonical_name, tg.canonical_name) AS track_agg_name,
                      CASE WHEN parent_tg.group_id IS NOT NULL THEN 'composition'
                           ELSE tg.scope END AS track_group_scope
               FROM track_group_members tgm
               JOIN track_groups tg ON tgm.group_id = tg.group_id
               LEFT JOIN track_groups parent_tg
                 ON tg.parent_group_id = parent_tg.group_id
                AND parent_tg.scope = 'composition'
               WHERE tg.scope IN ('composition', 'recording')""",
            conn,
        )
        if df.empty:
            return df
        df["_scope_rank"] = df["track_group_scope"].map({"composition": 0, "recording": 1})
        return (
            df.sort_values(["track_id", "_scope_rank", "track_agg_id"])
            .drop_duplicates("track_id")
            .drop(columns=["_scope_rank"])
        )

    return pd.read_sql_query(
        """SELECT tgm.track_id,
                  tg.primary_track_id AS track_agg_id,
                  tg.canonical_name AS track_agg_name,
                  tg.scope AS track_group_scope
           FROM track_group_members tgm
           JOIN track_groups tg ON tgm.group_id = tg.group_id
           WHERE tg.scope = 'recording'""",
        conn,
    )
