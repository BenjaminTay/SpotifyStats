"""Quirky and special-feat Billboard record families."""

import pandas as pd

from backend.core.db import fan_out_weekly_for_artists, primary_artist_names_for_tracks


def compute_quirky_records(records, weekly, weekly_album=None, weekly_artist=None):
    """Populate quirky records: double debut #1, triple #1."""

    # ── 13. Double Debut #1 (双空冠) ─────────────────────────────────────
    if weekly_album is not None:
        first_track_appear = (
            weekly.sort_values("billboard_week").groupby("track_id").first().reset_index()
        )
        debut_tracks = first_track_appear[first_track_appear["rank"] == 1][
            ["track_id", "track_name", "artist_name", "billboard_week"]
        ].copy()
        debut_tracks.columns = ["debut_track_id", "debut_track", "debut_artist", "debut_week"]
        debut_track_keys = first_track_appear[first_track_appear["rank"] == 1][
            [
                column
                for column in ["track_id", "artist_name", "artist_names"]
                if column in first_track_appear
            ]
        ]
        debut_tracks["debut_artist_key"] = primary_artist_names_for_tracks(debut_track_keys)[
            "artist_name"
        ].to_numpy()

        first_album_appear = (
            weekly_album.sort_values("billboard_week")
            .groupby(["album_name", "artist_name"])
            .first()
            .reset_index()
        )
        debut_albums = first_album_appear[first_album_appear["rank"] == 1][
            ["album_name", "artist_name", "billboard_week"]
        ].copy()
        debut_albums.columns = ["debut_album", "debut_artist", "debut_week"]
        debut_albums["debut_artist_key"] = debut_albums["debut_artist"]

        double_debut = debut_tracks.merge(
            debut_albums, on=["debut_artist_key", "debut_week"], how="inner"
        ).sort_values("debut_week", ascending=False)
        if not double_debut.empty:
            double_debut["debut_week"] = double_debut["debut_week"].astype(str)
        records["double_debut"] = double_debut
    else:
        records["double_debut"] = pd.DataFrame()

    # ── 28. Triple #1 (全榜单制霸) ──────────────────────────────────────
    if weekly_album is not None and weekly_artist is not None:
        track_no1_w = fan_out_weekly_for_artists(weekly[weekly["rank"] == 1])[
            ["billboard_week", "artist_name", "track_id", "track_name"]
        ].drop_duplicates(subset=["billboard_week", "artist_name"])
        album_no1_w = weekly_album[weekly_album["rank"] == 1][
            ["billboard_week", "artist_name", "album_name"]
        ].drop_duplicates(subset=["billboard_week", "artist_name"])
        artist_no1_w = weekly_artist[weekly_artist["rank"] == 1][
            ["billboard_week", "artist_name"]
        ].drop_duplicates()
        triple = track_no1_w.merge(album_no1_w, on=["billboard_week", "artist_name"]).merge(
            artist_no1_w, on=["billboard_week", "artist_name"]
        )
        triple = triple.rename(
            columns={
                "artist_name": "艺人",
                "track_name": "歌曲",
                "album_name": "专辑",
            }
        )
        triple["billboard_week"] = triple["billboard_week"].astype(str)
        records["triple_no1"] = triple.sort_values("billboard_week", ascending=False)
    else:
        records["triple_no1"] = pd.DataFrame()
