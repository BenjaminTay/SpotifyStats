"""Shared project ownership for charting songs; source releases are display facts."""

from __future__ import annotations

import pandas as pd

from backend.core.db import get_db
from backend.domains.playback.album_projects import (
    apply_canonical_song_keys,
    load_album_project_membership,
)


def load_chart_album_membership(
    tracks: pd.DataFrame, merge_level: int, include_compilations: bool
) -> pd.DataFrame:
    """Bind canonical chart IDs to the same unique owner as album playback.

    A representative can come from a standalone single (including zero valid
    plays). Ownership must follow the complete song identity, never that
    representative's provider album or performer name.
    """
    columns = [
        "track_id",
        "canonical_song_key",
        "album_project_id",
        "album_name",
        "album_artist_name",
    ]
    if merge_level <= 1:
        from backend.domains.billboard.data_loader import load_track_album_map

        return load_track_album_map()
    if tracks.empty:
        return pd.DataFrame(columns=columns)
    conn = get_db()
    try:
        songs = apply_canonical_song_keys(tracks[["track_id", "track_name"]], conn, merge_level)
        membership = load_album_project_membership(conn, merge_level, include_compilations)
    finally:
        conn.close()
    if membership.empty:
        return pd.DataFrame(columns=columns)
    owners = membership.rename(
        columns={
            "project_id": "album_project_id",
            "album_project_name": "album_name",
            "artist_name": "album_artist_name",
        }
    )
    result = (
        songs[["track_id", "canonical_song_key"]]
        .drop_duplicates()
        .merge(
            owners[["canonical_song_key", "album_project_id", "album_name", "album_artist_name"]],
            on="canonical_song_key",
            how="inner",
            validate="many_to_one",
        )
    )
    return result[columns]


def album_identity_columns(frame: pd.DataFrame) -> list[str]:
    """L2/L3 use stable project IDs; L1 retains source-container semantics."""
    return ["album_project_id"] if "album_project_id" in frame else ["album_name", "artist_name"]


def album_rows_mask(frame, album_name, artist_name, project_ids=()):
    if project_ids and "album_project_id" in frame:
        return frame["album_project_id"].isin(project_ids)
    artist_column = "album_artist_name" if "album_artist_name" in frame else "artist_name"
    mask = frame["album_name"] == album_name
    if artist_name:
        mask &= frame[artist_column] == artist_name
    return mask
