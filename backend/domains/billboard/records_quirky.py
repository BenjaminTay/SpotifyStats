"""Quirky and special-feat Billboard record families."""

import pandas as pd


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

        double_debut = debut_tracks.merge(
            debut_albums, on=["debut_artist", "debut_week"], how="inner"
        ).sort_values("debut_week", ascending=False)
        if not double_debut.empty:
            double_debut["debut_week"] = double_debut["debut_week"].astype(str)
        records["double_debut"] = double_debut
    else:
        records["double_debut"] = pd.DataFrame()

    # ── 28. Triple #1 (全榜单制霸) ──────────────────────────────────────
    if weekly_album is not None and weekly_artist is not None:
        track_no1_w = weekly[weekly["rank"] == 1][
            ["billboard_week", "artist_name"]
        ].drop_duplicates()
        album_no1_w = weekly_album[weekly_album["rank"] == 1][
            ["billboard_week", "artist_name"]
        ].drop_duplicates()
        artist_no1_w = weekly_artist[weekly_artist["rank"] == 1][
            ["billboard_week", "artist_name"]
        ].drop_duplicates()
        triple = track_no1_w.merge(
            album_no1_w, on="billboard_week", suffixes=("_track", "_album")
        ).merge(artist_no1_w, on="billboard_week")
        triple = triple[
            (triple["artist_name_track"] == triple["artist_name_album"])
            & (triple["artist_name_album"] == triple["artist_name"])
        ]
        triple = triple.rename(columns={"artist_name": "艺人"}).drop(
            columns=["artist_name_track", "artist_name_album"]
        )
        triple["billboard_week"] = triple["billboard_week"].astype(str)
        records["triple_no1"] = triple.sort_values("billboard_week", ascending=False)
    else:
        records["triple_no1"] = pd.DataFrame()
