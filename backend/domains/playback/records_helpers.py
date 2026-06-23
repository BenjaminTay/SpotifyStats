"""Shared helpers for playback records computation."""

from __future__ import annotations


def unique_cols(*cols):
    """Return deduplicated column list — first occurrence wins."""
    seen = set()
    result = []
    for c in cols:
        if c not in seen:
            seen.add(c)
            result.append(c)
    return result


def safe_groupby_cols(base_cols, group_col, name_col, artist_col):
    """Build groupby column list, avoiding duplicates when group/name/artist overlap."""
    cols = list(base_cols)
    if group_col not in cols:
        cols.append(group_col)
    if name_col not in cols and name_col != group_col:
        cols.append(name_col)
    if artist_col not in cols and artist_col != group_col and artist_col != name_col:
        cols.append(artist_col)
    return cols


def safe_rename(df, name_col, artist_col):
    """Rename name_col/artist_col to standard 'name'/'artist_name' columns."""
    if name_col != "name" and name_col in df.columns:
        df = df.rename(columns={name_col: "name"})
    if "name" not in df.columns:
        df["name"] = ""
    if artist_col != "artist_name" and artist_col in df.columns:
        df = df.rename(columns={artist_col: "artist_name"})
    if "artist_name" not in df.columns:
        df["artist_name"] = ""
    return df
