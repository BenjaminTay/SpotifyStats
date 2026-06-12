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
    if merge_level <= 1:
        return pd.DataFrame(
            columns=["track_id", "track_agg_id", "track_agg_name", "track_group_scope"]
        )

    scopes: tuple[str, ...] = ("composition", "recording") if merge_level >= 3 else ("recording",)

    placeholders = ",".join("?" for _ in scopes)
    return pd.read_sql_query(
        f"""SELECT tgm.track_id,
                  tg.group_id AS track_agg_id,
                  tg.canonical_name AS track_agg_name,
                  tg.scope AS track_group_scope
           FROM track_group_members tgm
           JOIN track_groups tg ON tgm.group_id = tg.group_id
           WHERE tg.scope IN ({placeholders})""",
        conn,
        params=scopes,
    )
