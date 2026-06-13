"""Release group resolver for canonical album aggregation.

Provides scope-aware album-to-canonical-name mapping, supporting
L1 (no merge), L2 (scope='release'), and L3 (scope='composition').
"""

from __future__ import annotations

import sqlite3

import pandas as pd


def load_album_release_group_map(conn: sqlite3.Connection, merge_level: int = 2) -> pd.DataFrame:
    """Return a DataFrame mapping album_id → release group info for aggregation.

    merge_level=1 (L1): returns empty DataFrame (no merge)
    merge_level=2 (L2): scope='release' groups
    merge_level=3 (L3): scope='composition' groups
    """
    if merge_level <= 1:
        return pd.DataFrame(
            columns=["album_id", "release_group_id", "canonical_name", "primary_album_id", "scope"]
        )

    if merge_level >= 3:
        # L3: composition scope members with child release group resolution.
        # Release groups that have parent_group_id → composition group are
        # resolved to the composition canonical name (R10 child-group expansion).
        return pd.read_sql_query(
            """SELECT rgm.album_id,
                      COALESCE(parent_rg.group_id, rg.group_id) AS release_group_id,
                      COALESCE(parent_rg.canonical_name, rg.canonical_name) AS canonical_name,
                      COALESCE(parent_rg.primary_album_id, rg.primary_album_id) AS primary_album_id,
                      CASE WHEN parent_rg.group_id IS NOT NULL THEN 'composition'
                           ELSE rg.scope END AS scope
               FROM release_group_members rgm
               JOIN release_groups rg ON rgm.group_id = rg.group_id
               LEFT JOIN release_groups parent_rg
                 ON rg.parent_group_id = parent_rg.group_id
                AND parent_rg.scope = 'composition'
               WHERE rg.scope IN ('composition', 'release')""",
            conn,
        )

    scope = "release"
    return pd.read_sql_query(
        """SELECT rgm.album_id,
                  rg.group_id AS release_group_id,
                  rg.canonical_name,
                  rg.primary_album_id,
                  rg.scope
           FROM release_group_members rgm
           JOIN release_groups rg ON rgm.group_id = rg.group_id
           WHERE rg.scope = ?""",
        conn,
        params=(scope,),
    )


def apply_album_release_groups(
    df: pd.DataFrame,
    mapping: pd.DataFrame,
    album_col: str = "album_name",
    artist_col: str = "artist_name",
) -> pd.DataFrame:
    """Replace album_name with canonical_name for rows that belong to a release group.

    Returns a new DataFrame with the album_col replaced where a mapping exists.
    """
    if mapping.empty or df.empty:
        return df

    df = df.copy()
    # Get album_name → canonical_name lookup from mapping
    album_to_canonical = (
        mapping[["album_id", "canonical_name"]]
        .drop_duplicates(subset=["album_id"])
        .set_index("album_id")["canonical_name"]
    )

    # If df has album_id, map directly
    if "album_id" in df.columns:
        df["_canonical"] = df["album_id"].map(album_to_canonical)
        mask = df["_canonical"].notna()
        df.loc[mask, album_col] = df.loc[mask, "_canonical"]
        df = df.drop(columns=["_canonical"])

    return df
