"""Helpers for choosing display album labels in track-level Billboard data."""

from __future__ import annotations

import pandas as pd


def choose_representative_album(
    df: pd.DataFrame,
    group_cols: list[str],
    album_col: str = "album_name",
) -> pd.DataFrame:
    """Return one stable display album per grouped track entity.

    Track rankings must not split a song by source album, but downstream UI still
    needs one album label. Prefer the album source that spans more chart weeks,
    then more plays, then more listening time, with a stable name tiebreaker.
    """
    if df.empty or album_col not in df.columns:
        return pd.DataFrame(columns=group_cols + [album_col])

    missing = [col for col in group_cols if col not in df.columns]
    if missing:
        return pd.DataFrame(columns=group_cols + [album_col])

    tmp = df[group_cols + [album_col]].copy()
    tmp["_album_name"] = tmp[album_col].fillna("").astype(str)

    if "billboard_week" in df.columns:
        tmp["_billboard_week"] = df["billboard_week"]
    else:
        tmp["_billboard_week"] = ""

    if "play_count" in df.columns:
        tmp["_play_count"] = pd.to_numeric(df["play_count"], errors="coerce").fillna(0)
    else:
        tmp["_play_count"] = 1

    if "total_ms" in df.columns:
        tmp["_total_ms"] = pd.to_numeric(df["total_ms"], errors="coerce").fillna(0)
    elif "ms_played" in df.columns:
        tmp["_total_ms"] = pd.to_numeric(df["ms_played"], errors="coerce").fillna(0)
    else:
        tmp["_total_ms"] = 0

    stats = (
        tmp.groupby(group_cols + ["_album_name"], dropna=False)
        .agg(
            _album_weeks=("_billboard_week", "nunique"),
            _album_play_count=("_play_count", "sum"),
            _album_total_ms=("_total_ms", "sum"),
        )
        .reset_index()
    )
    stats["_album_is_empty"] = stats["_album_name"].eq("")
    stats = stats.sort_values(
        group_cols
        + [
            "_album_is_empty",
            "_album_weeks",
            "_album_play_count",
            "_album_total_ms",
            "_album_name",
        ],
        ascending=[True] * len(group_cols) + [True, False, False, False, True],
    )
    choice = stats.drop_duplicates(group_cols)[group_cols + ["_album_name"]].rename(
        columns={"_album_name": album_col}
    )
    return choice
