"""Billboard entity versus comparison endpoints."""

import pandas as pd

from backend.core.db import fan_out_weekly_for_artists, get_db
from backend.domains.billboard.chart_compute import compute_billboard_data
from backend.domains.metadata.artist_genres import resolve_artist_genres
from backend.domains.metadata.artist_identity import resolve_artist_name
from backend.domains.metadata.artist_spotify_meta import resolve_artist_spotify_meta


def _vs_spotify_track_meta(track_id):
    """Fetch popularity for a track."""
    conn = get_db()
    row = conn.execute(
        """SELECT stm.popularity
           FROM tracks t
           JOIN spotify_track_meta stm
             ON t.spotify_track_id = stm.spotify_track_id
           WHERE t.track_id = ? LIMIT 1""",
        (track_id,),
    ).fetchone()
    conn.close()
    return int(row["popularity"]) if row and row["popularity"] is not None else None


def _vs_spotify_album_meta(album_name, artist_name):
    """Fetch popularity for an album."""
    conn = get_db()
    row = conn.execute(
        """SELECT DISTINCT sam.popularity
           FROM albums al
           JOIN artists a ON al.artist_id = a.artist_id
           JOIN track_albums ta ON ta.album_id = al.album_id
           JOIN tracks t ON ta.track_id = t.track_id
           JOIN spotify_track_meta stm
             ON t.spotify_track_id = stm.spotify_track_id
           JOIN spotify_album_meta sam ON stm.spotify_album_id = sam.spotify_album_id
           LEFT JOIN release_group_members rgm ON al.album_id = rgm.album_id
           LEFT JOIN release_groups rg ON rgm.group_id = rg.group_id
           WHERE (al.album_name = ? OR rg.canonical_name = ?)
             AND a.artist_name = ? LIMIT 1""",
        (album_name, album_name, artist_name),
    ).fetchone()
    conn.close()
    return int(row["popularity"]) if row and row["popularity"] is not None else None


def _vs_spotify_artist_meta(artist_name):
    """Fetch cover_url, popularity and genres for an artist."""
    conn = get_db()
    try:
        provider = resolve_artist_spotify_meta(conn, artist_name)
        resolved_genres = resolve_artist_genres(conn, artist_name)
    finally:
        conn.close()
    metadata = provider.metadata or {}
    pop = int(metadata["popularity"]) if metadata.get("popularity") is not None else None
    if metadata.get("genres"):
        genres = metadata["genres"]
        genre_source = "spotify"
        genre_confidence = 1.0
    else:
        genres = resolved_genres.genres or None
        genre_source = resolved_genres.source if resolved_genres.genres else None
        genre_confidence = resolved_genres.confidence if resolved_genres.genres else None
    cover = metadata.get("image_url") or None
    return pop, genres, cover, genre_source, genre_confidence


def _get_ps_rank(power_scores_df, key_col, key_val, artist_val=None):
    """Look up power score and rank for an entity in a power_scores DataFrame."""
    if power_scores_df is None or len(power_scores_df) == 0:
        return None, None
    ps = power_scores_df.sort_values("power_score", ascending=False).reset_index(drop=True)
    if artist_val is not None:
        mask = (ps[key_col] == key_val) & (ps["artist_name"] == artist_val)
    else:
        mask = ps[key_col] == key_val
    match = ps[mask]
    if len(match) == 0:
        return None, None
    idx = int(match.index[0])
    return int(match.iloc[0]["power_score"]), idx + 1


def _resolve_album_members_vs(album_name, artist_name):
    """Resolve all member album names in a release group."""
    conn = get_db()
    row = conn.execute(
        """SELECT a.album_name FROM release_group_members rgm
           JOIN release_groups rg ON rg.group_id = rgm.group_id
           JOIN albums a ON a.album_id = rgm.album_id
           JOIN artists ar ON a.artist_id = ar.artist_id
           WHERE rg.canonical_name = ? AND ar.artist_name = ?
           UNION SELECT ?""",
        (album_name, artist_name, album_name),
    ).fetchall()
    conn.close()
    if row:
        return [r["album_name"] for r in row]
    return [album_name]


def get_versus_track(
    tid_a,
    tid_b,
    min_ms,
    music_only,
    bb_top_n,
    bb_album_top_n,
    bb_artist_top_n,
    bb_week_start_dow,
    bb_week_start_hour,
    year_start,
    year_end,
):
    """Compare two tracks side-by-side."""
    data = compute_billboard_data(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
    )
    weekly = pd.DataFrame(data["weekly"])
    power_scores = pd.DataFrame(data["power_scores"])

    def _track_data(tid):
        grp = weekly[weekly["track_id"] == tid].sort_values("billboard_week")
        if grp.empty:
            return None
        ps_val, ps_rank = _get_ps_rank(power_scores, "track_id", tid)
        cover_url = None
        if "cover_url" in grp.columns:
            cv = grp["cover_url"].dropna()
            cover_url = str(cv.iloc[0]) if len(cv) > 0 else None
        popularity = _vs_spotify_track_meta(tid)
        return {
            "name": f"{grp['track_name'].iloc[0]} — {grp['artist_name'].iloc[0]}",
            "track_name": str(grp["track_name"].iloc[0]),
            "artist_name": str(grp["artist_name"].iloc[0]),
            "cover_url": cover_url,
            "popularity": popularity,
            "rank_history": [
                {
                    "week": str(r["billboard_week"]),
                    "rank": int(r["rank"]),
                    "play_count": int(r["play_count"]),
                }
                for _, r in grp.iterrows()
            ],
            "metrics": {
                "power_score": ps_val,
                "power_rank": ps_rank,
                "peak_position": int(grp["rank"].min()),
                "weeks_on_chart": int(grp["billboard_week"].nunique()),
                "no1_weeks": int((grp["rank"] == 1).sum()),
                "top5_weeks": int((grp["rank"] <= 5).sum()),
                "total_chart_plays": int(grp["play_count"].sum()),
            },
        }

    result_a = _track_data(tid_a)
    result_b = _track_data(tid_b)
    if result_a is None or result_b is None:
        return {"found": False, "reason": "其中一首歌在选定的年份范围内没有入榜记录"}
    return {"found": True, "entity_a": result_a, "entity_b": result_b, "head_to_head": []}


def get_versus_album(
    aname_a,
    aart_a,
    aname_b,
    aart_b,
    min_ms,
    music_only,
    bb_top_n,
    bb_album_top_n,
    bb_artist_top_n,
    bb_week_start_dow,
    bb_week_start_hour,
    year_start,
    year_end,
):
    """Compare two albums side-by-side."""
    data = compute_billboard_data(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
    )
    weekly = pd.DataFrame(data["weekly"])
    weekly_album = pd.DataFrame(data["weekly_album"])
    album_power_scores = pd.DataFrame(data["album_power_scores"])
    track_power_scores = pd.DataFrame(data["power_scores"])

    def _album_data(aname, aart):
        grp = weekly_album[
            (weekly_album["album_name"] == aname) & (weekly_album["artist_name"] == aart)
        ].sort_values("billboard_week")
        if grp.empty:
            return None
        aps_val, aps_rank = _get_ps_rank(album_power_scores, "album_name", aname, aart)

        # Track-level stats via release group members
        member_names = _resolve_album_members_vs(aname, aart)
        album_tracks = weekly[weekly["album_name"].isin(member_names)]
        num_tracks = int(album_tracks["track_id"].nunique())
        num_no1_tracks = int(album_tracks[album_tracks["rank"] == 1]["track_id"].nunique())
        total_no1_weeks = int((album_tracks["rank"] == 1).sum())

        # Sum of track power scores
        album_track_ids = album_tracks["track_id"].unique()
        track_ps_sum = 0
        if track_power_scores is not None and len(track_power_scores) > 0:
            track_ps_sum = int(
                track_power_scores[track_power_scores["track_id"].isin(album_track_ids)][
                    "power_score"
                ].sum()
            )

        cover_url = None
        if "cover_url" in grp.columns:
            cv = grp["cover_url"].dropna()
            cover_url = str(cv.iloc[0]) if len(cv) > 0 else None
        popularity = _vs_spotify_album_meta(aname, aart)
        return {
            "name": f"{aname} — {aart}",
            "album_name": aname,
            "artist_name": aart,
            "cover_url": cover_url,
            "popularity": popularity,
            "rank_history": [
                {
                    "week": str(r["billboard_week"]),
                    "rank": int(r["rank"]),
                    "play_count": int(r["play_count"]),
                }
                for _, r in grp.iterrows()
            ],
            "metrics": {
                "power_score": aps_val,
                "power_rank": aps_rank,
                "peak_position": int(grp["rank"].min()),
                "weeks_on_chart": int(grp["billboard_week"].nunique()),
                "no1_weeks": int((grp["rank"] == 1).sum()),
                "num_tracks": num_tracks,
                "num_no1_tracks": num_no1_tracks,
                "total_no1_track_weeks": total_no1_weeks,
                "track_power_sum": track_ps_sum,
                "total_plays": int(grp["play_count"].sum()),
            },
        }

    result_a = _album_data(aname_a, aart_a)
    result_b = _album_data(aname_b, aart_b)
    if result_a is None or result_b is None:
        return {"found": False, "reason": "其中一张专辑在选定的年份范围内没有入榜记录"}
    return {"found": True, "entity_a": result_a, "entity_b": result_b, "head_to_head": []}


def get_versus_artist(
    sel_a,
    sel_b,
    min_ms,
    music_only,
    bb_top_n,
    bb_album_top_n,
    bb_artist_top_n,
    bb_week_start_dow,
    bb_week_start_hour,
    year_start,
    year_end,
):
    """Compare two artists side-by-side."""
    identity_conn = get_db()
    try:
        resolved_a = resolve_artist_name(identity_conn, sel_a)
        resolved_b = resolve_artist_name(identity_conn, sel_b)
        sel_a = resolved_a.display_name if resolved_a else sel_a
        sel_b = resolved_b.display_name if resolved_b else sel_b
    finally:
        identity_conn.close()
    data = compute_billboard_data(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
    )
    weekly = pd.DataFrame(data["weekly"])
    weekly_artist = pd.DataFrame(data["weekly_artist"])
    weekly_album = pd.DataFrame(data["weekly_album"])
    artist_power_scores = pd.DataFrame(data["artist_power_scores"])
    track_power_scores = pd.DataFrame(data["power_scores"])
    album_power_scores = pd.DataFrame(data["album_power_scores"])

    def _artist_data(artist_name):
        grp = weekly_artist[weekly_artist["artist_name"] == artist_name].sort_values(
            "billboard_week"
        )
        if grp.empty:
            return None
        aps_val, aps_rank = _get_ps_rank(artist_power_scores, "artist_name", artist_name)

        # Track-level stats — use fanned-out weekly for multi-artist matching
        weekly_fanned = fan_out_weekly_for_artists(weekly)
        artist_tracks = weekly_fanned[weekly_fanned["artist_name"] == artist_name]
        num_tracks = int(artist_tracks["track_id"].nunique())
        num_no1_tracks = int(artist_tracks[artist_tracks["rank"] == 1]["track_id"].nunique())
        total_no1_track_weeks = int((artist_tracks["rank"] == 1).sum())

        # Sum of track power scores
        artist_track_ids = artist_tracks["track_id"].unique()
        track_ps_sum = 0
        if track_power_scores is not None and len(track_power_scores) > 0:
            track_ps_sum = int(
                track_power_scores[track_power_scores["track_id"].isin(artist_track_ids)][
                    "power_score"
                ].sum()
            )

        # Album-level stats
        artist_albums = weekly_album[weekly_album["artist_name"] == artist_name]
        num_albums = int(artist_albums["album_name"].dropna().nunique())
        num_no1_albums = int(artist_albums[artist_albums["rank"] == 1]["album_name"].nunique())
        total_no1_album_weeks = int((artist_albums["rank"] == 1).sum())

        # Spotify metadata
        (
            artist_pop,
            artist_genres,
            artist_cover,
            artist_genre_source,
            artist_genre_confidence,
        ) = _vs_spotify_artist_meta(artist_name)

        # Sum of album power scores
        album_ps_sum = 0
        if album_power_scores is not None and len(album_power_scores) > 0:
            album_ps_sum = int(
                album_power_scores[album_power_scores["artist_name"] == artist_name][
                    "power_score"
                ].sum()
            )

        return {
            "name": artist_name,
            "cover_url": artist_cover,
            "popularity": artist_pop,
            "genres": artist_genres,
            "genre_source": artist_genre_source,
            "genre_confidence": artist_genre_confidence,
            "rank_history": [
                {
                    "week": str(r["billboard_week"]),
                    "rank": int(r["rank"]),
                    "play_count": int(r["play_count"]),
                }
                for _, r in grp.iterrows()
            ],
            "metrics": {
                "power_score": aps_val,
                "power_rank": aps_rank,
                "peak_position": int(grp["rank"].min()),
                "weeks_on_chart": int(grp["billboard_week"].nunique()),
                "no1_weeks": int((grp["rank"] == 1).sum()),
                "num_tracks": num_tracks,
                "num_no1_tracks": num_no1_tracks,
                "total_no1_track_weeks": total_no1_track_weeks,
                "track_power_sum": track_ps_sum,
                "num_albums": num_albums,
                "num_no1_albums": num_no1_albums,
                "total_no1_album_weeks": total_no1_album_weeks,
                "album_power_sum": album_ps_sum,
                "total_plays": int(grp["play_count"].sum()),
            },
        }

    result_a = _artist_data(sel_a)
    result_b = _artist_data(sel_b)
    if result_a is None or result_b is None:
        return {"found": False, "reason": "其中一位艺人在选定的年份范围内没有入榜记录"}
    return {"found": True, "entity_a": result_a, "entity_b": result_b, "head_to_head": []}


# ── Multi-entity helper: global rankings ────────────────────────────────────


def _compute_album_track_ranks(weekly, power_scores):
    """Compute track_power_rank / track_peak_position / total_track_weeks per album.

    Groups by album_name only (not artist_name) because in weekly, collaborative
    tracks have a combined artist_name string (e.g. "Artist A, Artist B") which
    would split the same album's tracks into separate groups and produce ranks
    inconsistent with the entity-level track_power_sum that includes all tracks.
    """
    track_album = weekly[["track_id", "album_name"]].drop_duplicates()
    ps = power_scores[["track_id", "power_score", "peak_position", "weeks_on_chart"]]
    merged = track_album.merge(ps, on="track_id", how="inner")
    agg = (
        merged.groupby("album_name")
        .agg(
            track_power_sum=("power_score", "sum"),
            track_peak_position=("peak_position", "min"),
            total_track_weeks=("weeks_on_chart", "sum"),
        )
        .reset_index()
    )
    agg["track_power_rank"] = agg["track_power_sum"].rank(ascending=False, method="min").astype(int)
    return agg


def _compute_artist_track_ranks(weekly_fanned, power_scores):
    """Compute track_power_rank / track_peak_position / total_track_weeks per artist."""
    track_artist = weekly_fanned[["track_id", "artist_name"]].drop_duplicates()
    ps = power_scores[["track_id", "power_score", "peak_position", "weeks_on_chart"]]
    merged = track_artist.merge(ps, on="track_id", how="inner")
    agg = (
        merged.groupby("artist_name")
        .agg(
            track_power_sum=("power_score", "sum"),
            track_peak_position=("peak_position", "min"),
            total_track_weeks=("weeks_on_chart", "sum"),
        )
        .reset_index()
    )
    agg["track_power_rank"] = agg["track_power_sum"].rank(ascending=False, method="min").astype(int)
    return agg


def _compute_artist_album_ranks(album_power_scores):
    """Compute album_power_rank / album_peak_position / total_album_weeks per artist."""
    agg = (
        album_power_scores.groupby("artist_name")
        .agg(
            album_power_sum=("power_score", "sum"),
            album_peak_position=("peak_position", "min"),
            total_album_weeks=("weeks_on_chart", "sum"),
        )
        .reset_index()
    )
    agg["album_power_rank"] = agg["album_power_sum"].rank(ascending=False, method="min").astype(int)
    return agg


def _lookup_album_track_rank(ranks_df, member_names, artist_name):
    """Look up track_power_rank for an album, trying each member name.

    artist_name is accepted for signature compatibility but not used for filtering:
    ranks are computed per album_name (not per artist) so the lookup only needs
    album name matching.  See _compute_album_track_ranks for rationale.
    """
    for name in member_names:
        row = ranks_df[ranks_df["album_name"] == name]
        if not row.empty:
            return int(row.iloc[0]["track_power_rank"])
    return None


def _lookup_artist_track_metrics(ranks_df, artist_name):
    """Look up track-level artist metrics from pre-computed ranks DataFrame."""
    row = ranks_df[ranks_df["artist_name"] == artist_name]
    if row.empty:
        return {"track_power_rank": None, "track_peak_position": None, "total_track_weeks": None}
    r = row.iloc[0]
    return {
        "track_power_rank": int(r["track_power_rank"]),
        "track_peak_position": int(r["track_peak_position"]),
        "total_track_weeks": int(r["total_track_weeks"]),
    }


def _lookup_artist_album_metrics(ranks_df, artist_name):
    """Look up album-level artist metrics from pre-computed ranks DataFrame."""
    row = ranks_df[ranks_df["artist_name"] == artist_name]
    if row.empty:
        return {"album_power_rank": None, "album_peak_position": None, "total_album_weeks": None}
    r = row.iloc[0]
    return {
        "album_power_rank": int(r["album_power_rank"]),
        "album_peak_position": int(r["album_peak_position"]),
        "total_album_weeks": int(r["total_album_weeks"]),
    }


# ── Multi-entity versus (POST, 2–5 entities) ──────────────────────────────────


def _build_track_entity(tid, weekly, power_scores):
    """Build a single track entity dict from pre-computed DataFrames."""
    grp = weekly[weekly["track_id"] == tid].sort_values("billboard_week")
    if grp.empty:
        return None
    ps_val, ps_rank = _get_ps_rank(power_scores, "track_id", tid)
    cover_url = None
    if "cover_url" in grp.columns:
        cv = grp["cover_url"].dropna()
        cover_url = str(cv.iloc[0]) if len(cv) > 0 else None
    popularity = _vs_spotify_track_meta(tid)
    return {
        "name": f"{grp['track_name'].iloc[0]} — {grp['artist_name'].iloc[0]}",
        "track_name": str(grp["track_name"].iloc[0]),
        "artist_name": str(grp["artist_name"].iloc[0]),
        "cover_url": cover_url,
        "popularity": popularity,
        "rank_history": [
            {
                "week": str(r["billboard_week"]),
                "rank": int(r["rank"]),
                "play_count": int(r["play_count"]),
            }
            for _, r in grp.iterrows()
        ],
        "metrics": {
            "power_score": ps_val,
            "power_rank": ps_rank,
            "peak_position": int(grp["rank"].min()),
            "weeks_on_chart": int(grp["billboard_week"].nunique()),
            "no1_weeks": int((grp["rank"] == 1).sum()),
            "top5_weeks": int((grp["rank"] <= 5).sum()),
            "total_chart_plays": int(grp["play_count"].sum()),
        },
    }


def get_versus_track_multi(
    track_ids,
    min_ms,
    music_only,
    bb_top_n,
    bb_album_top_n,
    bb_artist_top_n,
    bb_week_start_dow,
    bb_week_start_hour,
    year_start,
    year_end,
):
    """Compare multiple tracks.  track_ids is a list of int (2–5)."""
    if len(track_ids) < 2:
        return {"found": False, "reason": "请至少选择 2 首单曲进行对比"}

    data = compute_billboard_data(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
    )
    weekly = pd.DataFrame(data["weekly"])
    power_scores = pd.DataFrame(data["power_scores"])

    entities = []
    for tid in track_ids:
        ent = _build_track_entity(tid, weekly, power_scores)
        if ent is not None:
            entities.append(ent)
    if len(entities) < 2:
        return {"found": False, "reason": "选中的单曲在选定年份范围内入榜数量不足 2 首"}
    return {"found": True, "entities": entities}


def get_versus_album_multi(
    albums,
    min_ms,
    music_only,
    bb_top_n,
    bb_album_top_n,
    bb_artist_top_n,
    bb_week_start_dow,
    bb_week_start_hour,
    year_start,
    year_end,
):
    """Compare multiple albums.  albums is a list of {album_name, artist_name} (2–5)."""
    if len(albums) < 2:
        return {"found": False, "reason": "请至少选择 2 张专辑进行对比"}

    data = compute_billboard_data(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
    )
    weekly = pd.DataFrame(data["weekly"])
    weekly_album = pd.DataFrame(data["weekly_album"])
    album_power_scores = pd.DataFrame(data["album_power_scores"])
    track_power_scores = pd.DataFrame(data["power_scores"])

    # Pre-compute global track-level rankings per album
    album_track_ranks = _compute_album_track_ranks(weekly, track_power_scores)

    entities = []
    for alb in albums:
        aname = alb["album_name"]
        aart = alb["artist_name"]
        grp = weekly_album[
            (weekly_album["album_name"] == aname) & (weekly_album["artist_name"] == aart)
        ].sort_values("billboard_week")
        if grp.empty:
            continue

        aps_val, aps_rank = _get_ps_rank(album_power_scores, "album_name", aname, aart)

        member_names = _resolve_album_members_vs(aname, aart)
        album_tracks = weekly[weekly["album_name"].isin(member_names)]
        num_tracks = int(album_tracks["track_id"].nunique())
        num_no1_tracks = int(album_tracks[album_tracks["rank"] == 1]["track_id"].nunique())
        total_no1_weeks = int((album_tracks["rank"] == 1).sum())

        album_track_ids = album_tracks["track_id"].unique()
        track_ps_sum = 0
        track_peak_position = None
        total_track_weeks = None
        if track_power_scores is not None and len(track_power_scores) > 0:
            tps_filtered = track_power_scores[track_power_scores["track_id"].isin(album_track_ids)]
            if len(tps_filtered) > 0:
                track_ps_sum = int(tps_filtered["power_score"].sum())
                track_peak_position = int(tps_filtered["peak_position"].min())
                total_track_weeks = int(tps_filtered["weeks_on_chart"].sum())

        # Track power rank (global) — resolve via member names
        track_power_rank = _lookup_album_track_rank(album_track_ranks, member_names, aart)

        cover_url = None
        if "cover_url" in grp.columns:
            cv = grp["cover_url"].dropna()
            cover_url = str(cv.iloc[0]) if len(cv) > 0 else None
        popularity = _vs_spotify_album_meta(aname, aart)

        entities.append(
            {
                "name": f"{aname} — {aart}",
                "album_name": aname,
                "artist_name": aart,
                "cover_url": cover_url,
                "popularity": popularity,
                "rank_history": [
                    {
                        "week": str(r["billboard_week"]),
                        "rank": int(r["rank"]),
                        "play_count": int(r["play_count"]),
                    }
                    for _, r in grp.iterrows()
                ],
                "metrics": {
                    "power_score": aps_val,
                    "power_rank": aps_rank,
                    "peak_position": int(grp["rank"].min()),
                    "weeks_on_chart": int(grp["billboard_week"].nunique()),
                    "no1_weeks": int((grp["rank"] == 1).sum()),
                    "num_tracks": num_tracks,
                    "num_no1_tracks": num_no1_tracks,
                    "total_no1_track_weeks": total_no1_weeks,
                    "track_power_sum": track_ps_sum,
                    "track_power_rank": track_power_rank,
                    "track_peak_position": track_peak_position,
                    "total_track_weeks": total_track_weeks,
                    "total_plays": int(grp["play_count"].sum()),
                },
            }
        )

    if len(entities) < 2:
        return {"found": False, "reason": "选中的专辑在选定年份范围内入榜数量不足 2 张"}
    return {"found": True, "entities": entities}


def get_versus_artist_multi(
    artist_names,
    min_ms,
    music_only,
    bb_top_n,
    bb_album_top_n,
    bb_artist_top_n,
    bb_week_start_dow,
    bb_week_start_hour,
    year_start,
    year_end,
):
    """Compare multiple artists.  artist_names is a list of str (2–5)."""
    if len(artist_names) < 2:
        return {"found": False, "reason": "请至少选择 2 位艺人进行对比"}

    identity_conn = get_db()
    try:
        artist_names = [
            resolved.display_name
            if (resolved := resolve_artist_name(identity_conn, name))
            else name
            for name in artist_names
        ]
        artist_names = list(dict.fromkeys(artist_names))
    finally:
        identity_conn.close()
    if len(artist_names) < 2:
        return {"found": False, "reason": "选中的艺人规范化后不足 2 位"}

    data = compute_billboard_data(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
    )
    weekly = pd.DataFrame(data["weekly"])
    weekly_artist = pd.DataFrame(data["weekly_artist"])
    weekly_album = pd.DataFrame(data["weekly_album"])
    artist_power_scores = pd.DataFrame(data["artist_power_scores"])
    track_power_scores = pd.DataFrame(data["power_scores"])
    album_power_scores = pd.DataFrame(data["album_power_scores"])

    weekly_fanned = fan_out_weekly_for_artists(weekly)

    # Pre-compute global rankings
    artist_track_ranks = _compute_artist_track_ranks(weekly_fanned, track_power_scores)
    artist_album_ranks = _compute_artist_album_ranks(album_power_scores)

    entities = []
    for artist_name in artist_names:
        grp = weekly_artist[weekly_artist["artist_name"] == artist_name].sort_values(
            "billboard_week"
        )
        if grp.empty:
            continue

        aps_val, aps_rank = _get_ps_rank(artist_power_scores, "artist_name", artist_name)

        artist_tracks = weekly_fanned[weekly_fanned["artist_name"] == artist_name]
        num_tracks = int(artist_tracks["track_id"].nunique())
        num_no1_tracks = int(artist_tracks[artist_tracks["rank"] == 1]["track_id"].nunique())
        total_no1_track_weeks = int((artist_tracks["rank"] == 1).sum())

        artist_track_ids = artist_tracks["track_id"].unique()
        track_ps_sum = 0
        if track_power_scores is not None and len(track_power_scores) > 0:
            track_ps_sum = int(
                track_power_scores[track_power_scores["track_id"].isin(artist_track_ids)][
                    "power_score"
                ].sum()
            )

        artist_albums = weekly_album[weekly_album["artist_name"] == artist_name]
        num_albums = int(artist_albums["album_name"].dropna().nunique())
        num_no1_albums = int(artist_albums[artist_albums["rank"] == 1]["album_name"].nunique())
        total_no1_album_weeks = int((artist_albums["rank"] == 1).sum())

        (
            artist_pop,
            artist_genres,
            artist_cover,
            artist_genre_source,
            artist_genre_confidence,
        ) = _vs_spotify_artist_meta(artist_name)

        # Track-level global rankings for this artist
        trmetrics = _lookup_artist_track_metrics(artist_track_ranks, artist_name)
        # Album-level global rankings for this artist
        almetrics = _lookup_artist_album_metrics(artist_album_ranks, artist_name)

        album_ps_sum = 0
        if album_power_scores is not None and len(album_power_scores) > 0:
            album_ps_sum = int(
                album_power_scores[album_power_scores["artist_name"] == artist_name][
                    "power_score"
                ].sum()
            )

        entities.append(
            {
                "name": artist_name,
                "cover_url": artist_cover,
                "popularity": artist_pop,
                "genres": artist_genres,
                "genre_source": artist_genre_source,
                "genre_confidence": artist_genre_confidence,
                "rank_history": [
                    {
                        "week": str(r["billboard_week"]),
                        "rank": int(r["rank"]),
                        "play_count": int(r["play_count"]),
                    }
                    for _, r in grp.iterrows()
                ],
                "metrics": {
                    "power_score": aps_val,
                    "power_rank": aps_rank,
                    "peak_position": int(grp["rank"].min()),
                    "weeks_on_chart": int(grp["billboard_week"].nunique()),
                    "no1_weeks": int((grp["rank"] == 1).sum()),
                    "num_tracks": num_tracks,
                    "num_no1_tracks": num_no1_tracks,
                    "total_no1_track_weeks": total_no1_track_weeks,
                    "track_power_sum": track_ps_sum,
                    "track_power_rank": trmetrics["track_power_rank"],
                    "track_peak_position": trmetrics["track_peak_position"],
                    "total_track_weeks": trmetrics["total_track_weeks"],
                    "num_albums": num_albums,
                    "num_no1_albums": num_no1_albums,
                    "total_no1_album_weeks": total_no1_album_weeks,
                    "album_power_sum": album_ps_sum,
                    "album_power_rank": almetrics["album_power_rank"],
                    "album_peak_position": almetrics["album_peak_position"],
                    "total_album_weeks": almetrics["total_album_weeks"],
                    "total_plays": int(grp["play_count"].sum()),
                },
            }
        )

    if len(entities) < 2:
        return {"found": False, "reason": "选中的艺人在选定年份范围内入榜数量不足 2 位"}
    return {"found": True, "entities": entities}
