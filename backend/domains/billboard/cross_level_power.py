"""Shared cross-level Billboard power aggregates.

These helpers deliberately consume the same project-aware ``track_per_album``
and credited/canonical ``artist_summary`` frames used by details and versus.
Ranks use competition ranking (``method='min'``) over the complete current
entity universe. Entities with no charting child contribution keep a zero sum
and no derived rank.
"""

from __future__ import annotations

import pandas as pd


def _rank_positive(frame: pd.DataFrame, value_col: str, rank_col: str) -> pd.DataFrame:
    result = frame.copy()
    result[rank_col] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    positive = result[value_col] > 0
    if positive.any():
        result.loc[positive, rank_col] = (
            result.loc[positive, value_col].rank(ascending=False, method="min").astype("Int64")
        )
    return result


def compute_album_track_power_metrics(
    album_entities: pd.DataFrame,
    track_per_album: pd.DataFrame,
    track_power_scores: pd.DataFrame,
) -> pd.DataFrame:
    """Return child-track power totals/ranks for every current album entity."""
    keys = ["album_name", "artist_name"]
    universe = album_entities[keys].drop_duplicates().copy()
    if universe.empty:
        return universe.assign(
            track_power_sum=pd.Series(dtype="int64"), track_power_rank=pd.Series(dtype="Int64")
        )

    if track_per_album.empty or track_power_scores.empty:
        universe["track_power_sum"] = 0
        return _rank_positive(universe, "track_power_sum", "track_power_rank")

    membership = track_per_album[["track_id", *keys]].drop_duplicates()
    scores = track_power_scores[["track_id", "power_score"]].drop_duplicates("track_id")
    aggregates = (
        membership.merge(scores, on="track_id", how="inner")
        .groupby(keys, as_index=False)["power_score"]
        .sum()
        .rename(columns={"power_score": "track_power_sum"})
    )
    result = universe.merge(aggregates, on=keys, how="left")
    result["track_power_sum"] = result["track_power_sum"].fillna(0).astype(int)
    return _rank_positive(result, "track_power_sum", "track_power_rank")


def compute_artist_track_power_metrics(
    artist_entities: pd.DataFrame,
    artist_summary: pd.DataFrame,
    track_power_scores: pd.DataFrame,
) -> pd.DataFrame:
    """Return credited canonical track power totals/ranks for each artist."""
    universe = artist_entities[["artist_name"]].drop_duplicates().copy()
    if universe.empty:
        return universe.assign(
            track_power_sum=pd.Series(dtype="int64"), track_power_rank=pd.Series(dtype="Int64")
        )

    if artist_summary.empty or track_power_scores.empty:
        universe["track_power_sum"] = 0
        return _rank_positive(universe, "track_power_sum", "track_power_rank")

    credits = artist_summary[["artist_name", "track_id"]].drop_duplicates()
    scores = track_power_scores[["track_id", "power_score"]].drop_duplicates("track_id")
    aggregates = (
        credits.merge(scores, on="track_id", how="inner")
        .groupby("artist_name", as_index=False)["power_score"]
        .sum()
        .rename(columns={"power_score": "track_power_sum"})
    )
    result = universe.merge(aggregates, on="artist_name", how="left")
    result["track_power_sum"] = result["track_power_sum"].fillna(0).astype(int)
    return _rank_positive(result, "track_power_sum", "track_power_rank")


def compute_artist_album_power_metrics(
    artist_entities: pd.DataFrame,
    album_power_scores: pd.DataFrame,
) -> pd.DataFrame:
    """Return album power totals/ranks for every current artist entity."""
    universe = artist_entities[["artist_name"]].drop_duplicates().copy()
    if universe.empty:
        return universe.assign(
            album_power_sum=pd.Series(dtype="int64"), album_power_rank=pd.Series(dtype="Int64")
        )

    if album_power_scores.empty:
        universe["album_power_sum"] = 0
        return _rank_positive(universe, "album_power_sum", "album_power_rank")

    aggregates = (
        album_power_scores.groupby("artist_name", as_index=False)["power_score"]
        .sum()
        .rename(columns={"power_score": "album_power_sum"})
    )
    result = universe.merge(aggregates, on="artist_name", how="left")
    result["album_power_sum"] = result["album_power_sum"].fillna(0).astype(int)
    return _rank_positive(result, "album_power_sum", "album_power_rank")


def attach_cross_level_power_metrics(
    album_power_scores: pd.DataFrame,
    artist_power_scores: pd.DataFrame,
    track_power_scores: pd.DataFrame,
    track_per_album: pd.DataFrame,
    artist_summary: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Attach all cross-level metrics to album and artist power frames."""
    albums = album_power_scores.merge(
        compute_album_track_power_metrics(album_power_scores, track_per_album, track_power_scores),
        on=["album_name", "artist_name"],
        how="left",
    )
    artists = artist_power_scores.merge(
        compute_artist_track_power_metrics(artist_power_scores, artist_summary, track_power_scores),
        on="artist_name",
        how="left",
    ).merge(
        compute_artist_album_power_metrics(artist_power_scores, album_power_scores),
        on="artist_name",
        how="left",
    )
    return albums, artists
