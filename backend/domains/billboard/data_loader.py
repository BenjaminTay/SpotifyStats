"""Billboard data loading functions — cached raw data retrieval."""

from functools import lru_cache

import pandas as pd

from backend.core.db import _downcast_ints, base_filters, get_db, merge_consecutive_plays

# Weekday labels
DOW_NAMES = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
DOW_SHORT = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}


def _try_load_from_agg(
    min_ms,
    music_only,
    week_start_dow,
    week_start_hour,
    dynamic_threshold=False,
    max_merge_gap_minutes=None,
):
    """Try to load pre-aggregated weekly data from agg tables.

    Returns (tracks_df, albums_df, artists_df) if valid agg data exists,
    or (None, None, None) if parameters don't match or tables are empty.
    Each DataFrame is pre-grouped (play_count + total_ms) but NOT ranked.
    """
    from backend.core.db import (
        _agg_param_hash,
        check_agg_valid,
        load_agg_weekly_albums,
        load_agg_weekly_artists,
        load_agg_weekly_track_sources,
        load_agg_weekly_tracks,
    )
    from backend.domains.metadata.artist_identity import get_identity_revision
    from backend.domains.metadata.track_credits import (
        get_track_credit_revision,
        get_track_credit_state,
    )

    conn = get_db()

    credit_state = get_track_credit_state(conn)
    if credit_state.get("current_revision", 0) != credit_state.get("active_aggregate_revision", 0):
        conn.close()
        return None, None, None

    param_hash = _agg_param_hash(
        min_ms,
        music_only,
        week_start_dow,
        week_start_hour,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        identity_revision=get_identity_revision(conn),
        track_credit_revision=get_track_credit_revision(conn),
    )
    if not check_agg_valid(conn, param_hash):
        conn.close()
        return None, None, None

    try:
        tracks = load_agg_weekly_tracks(conn)
        album_sources = load_agg_weekly_track_sources(conn)
        albums = album_sources if len(album_sources) > 0 else load_agg_weekly_albums(conn)
        artists = load_agg_weekly_artists(conn)
        conn.close()
        if len(tracks) == 0:
            return None, None, None
        return tracks, albums, artists
    except Exception:
        conn.close()
        return None, None, None


@lru_cache(maxsize=8)
def load_billboard_raw(
    min_ms,
    music_only,
    week_start_dow,
    week_start_hour,
    dynamic_threshold=False,
    max_merge_gap_minutes=None,
):
    """Load filtered plays and compute billboard_week with configurable boundary."""
    conn = get_db()
    # Load with min_ms=0 to preserve short fragments for merge-then-filter
    _f, _fp = base_filters(min_ms=0, music_only=music_only)
    _w = f"WHERE {_f}" if _f else ""
    df = pd.read_sql_query(
        f"""SELECT p.play_id, p.ts, p.ts_date, p.ts_dow, p.ts_hour, p.ms_played, p.track_id,
                   p.source_album_id,
                   t.track_name, t.artist_id, a.artist_name,
                   COALESCE(al_src.album_name, al.album_name) AS album_name,
                   stm.duration_ms
            FROM plays p
            LEFT JOIN tracks t ON p.track_id = t.track_id
            LEFT JOIN artists a ON t.artist_id = a.artist_id
            LEFT JOIN albums al ON t.album_id = al.album_id
            LEFT JOIN albums al_src ON p.source_album_id = al_src.album_id
            LEFT JOIN spotify_track_meta stm
              ON t.spotify_track_id = stm.spotify_track_id
            {_w}
            ORDER BY p.ts""",
        conn,
        params=_fp,
    )
    # Billboard week: configurable boundary
    df["days_back"] = (df["ts_dow"] - week_start_dow) % 7
    mask_before = (df["ts_dow"] == week_start_dow) & (df["ts_hour"] < week_start_hour)
    df.loc[mask_before, "days_back"] = 7
    df["ts_date_dt"] = pd.to_datetime(df["ts_date"])
    df["billboard_week"] = (df["ts_date_dt"] - pd.to_timedelta(df["days_back"], unit="D")).dt.date

    # Merge consecutive same-track plays (with source_album + billboard_week boundary),
    # then apply ms_played threshold.  billboard_week prevents cross-week fragment merging (R23).
    df = merge_consecutive_plays(
        df,
        min_ms,
        max_gap_minutes=max_merge_gap_minutes,
        boundary_column=["source_album_id", "billboard_week"],
    )
    if min_ms > 0:
        from backend.domains.playback.counting import filter_effective_plays

        df = filter_effective_plays(df, min_ms=min_ms, dynamic_threshold=dynamic_threshold)

    from backend.domains.metadata.artist_identity import canonicalize_artist_frame

    df = canonicalize_artist_frame(df, conn, dedupe=False)
    conn.close()

    return _downcast_ints(df)


@lru_cache(maxsize=8)
def load_billboard_raw_for_artists(
    min_ms,
    music_only,
    week_start_dow,
    week_start_hour,
    dynamic_threshold=False,
    max_merge_gap_minutes=None,
):
    """Same as load_billboard_raw but fans out through track_artists for multi-artist
    attribution. Merge happens before fan-out to keep merge_consecutive_plays correct.

    Only use for artist-grouped Billboard computations.
    """
    conn = get_db()
    # Load with min_ms=0 to preserve short fragments for merge-then-filter
    _f, _fp = base_filters(min_ms=0, music_only=music_only)
    _w = f"WHERE {_f}" if _f else ""

    # Step 1: Load single-artist data (same as load_billboard_raw)
    df = pd.read_sql_query(
        f"""SELECT p.play_id, p.ts, p.ts_date, p.ts_dow, p.ts_hour, p.ms_played, p.track_id,
                   p.source_album_id,
                   t.track_name, a.artist_name,
                   COALESCE(al_src.album_name, al.album_name) AS album_name,
                   stm.duration_ms
            FROM plays p
            LEFT JOIN tracks t ON p.track_id = t.track_id
            LEFT JOIN artists a ON t.artist_id = a.artist_id
            LEFT JOIN albums al ON t.album_id = al.album_id
            LEFT JOIN albums al_src ON p.source_album_id = al_src.album_id
            LEFT JOIN spotify_track_meta stm
              ON t.spotify_track_id = stm.spotify_track_id
            {_w}
            ORDER BY p.ts""",
        conn,
        params=_fp,
    )

    # Billboard week computation
    df["days_back"] = (df["ts_dow"] - week_start_dow) % 7
    mask_before = (df["ts_dow"] == week_start_dow) & (df["ts_hour"] < week_start_hour)
    df.loc[mask_before, "days_back"] = 7
    df["ts_date_dt"] = pd.to_datetime(df["ts_date"])
    df["billboard_week"] = (df["ts_date_dt"] - pd.to_timedelta(df["days_back"], unit="D")).dt.date

    # Merge before fan-out, then filter to align with pre-aggregation path
    df = merge_consecutive_plays(
        df,
        min_ms,
        max_gap_minutes=max_merge_gap_minutes,
        boundary_column=["source_album_id", "billboard_week"],
    )
    if min_ms > 0:
        from backend.domains.playback.counting import filter_effective_plays

        df = filter_effective_plays(df, min_ms=min_ms, dynamic_threshold=dynamic_threshold)

    # Step 2: Fan out through raw + manual effective credits. Keep each effective output row
    # distinct even when consecutive-play expansion reused a source play_id.
    from backend.domains.playback.counting import assign_logical_event_id

    df = assign_logical_event_id(df)
    from backend.domains.metadata.track_credits import get_effective_track_credit_frame

    track_artists_df = get_effective_track_credit_frame(conn)
    df = df.drop(columns=["artist_name"], errors="ignore")
    df = df.merge(
        track_artists_df[["track_id", "artist_id", "raw_artist_id", "artist_name"]],
        on="track_id",
        how="inner",
    )
    df["artist_id"] = df["raw_artist_id"]
    df = df.drop(columns=["raw_artist_id"])

    from backend.domains.metadata.artist_identity import canonicalize_artist_frame

    df = canonicalize_artist_frame(df, conn)
    df = df.drop(columns=["_logical_event_id"], errors="ignore")
    conn.close()

    return _downcast_ints(df)


@lru_cache(maxsize=8)
def load_track_album_map():
    """Get all album names for each track_id (including track_albums junction)."""
    conn = get_db()
    rows = conn.execute(
        """SELECT t.track_id, al.album_name
           FROM tracks t
           JOIN albums al ON t.album_id = al.album_id
           UNION
           SELECT ta.track_id, al.album_name
           FROM track_albums ta
           JOIN albums al ON ta.album_id = al.album_id"""
    ).fetchall()
    conn.close()

    data = {}
    for tid, album in rows:
        data.setdefault(tid, []).append(album)

    # Build DataFrame: track_id → list of album names
    records = []
    for tid, albums in data.items():
        records.append({"track_id": tid, "album_list": sorted(set(albums))})
    return pd.DataFrame(records)


def _match_album_artist(artist_name, album_artists):
    """Check if artist_name appears in album_artists.

    album_artists may be a plain string (single artist), comma-separated
    ("Lady Gaga, Ariana Grande"), or a JSON array ('["Taylor Swift"]').
    NULL/empty album_artists matches all (safety: lack of artist info
    should not prevent metadata lookup).

    Matching is case-insensitive and diacritic-tolerant via NFKD
    normalization + combining-character stripping.
    """
    import json
    import unicodedata

    if album_artists is None:
        return True
    s = str(album_artists).strip()
    if not s:
        return True
    if artist_name is None:
        return False

    def _norm(name: str) -> str:
        nkd = unicodedata.normalize("NFKD", str(name))
        # Strip combining diacritical marks, then casefold
        return "".join(c for c in nkd if not unicodedata.combining(c)).casefold()

    target = _norm(artist_name)

    # JSON array: ["Artist A", "Artist B"]
    if s.startswith("["):
        try:
            arr = json.loads(s)
            if isinstance(arr, list):
                return any(_norm(n) == target for n in arr)
        except (json.JSONDecodeError, TypeError):
            pass

    # Comma-separated (or single artist)
    names = [n.strip() for n in s.split(",")]
    return any(_norm(n) == target for n in names)


@lru_cache(maxsize=8)
def _load_album_metadata():
    conn = get_db()
    # Join by album_name only; filter by artist in pandas to handle
    # multi-artist formats (comma-separated, JSON array).
    df = pd.read_sql_query(
        """SELECT DISTINCT al.album_name, a.artist_name, sam.album_artists,
               sam.album_type, sam.release_date, sam.total_tracks
           FROM albums al
           JOIN artists a ON al.artist_id = a.artist_id
           JOIN spotify_album_meta sam ON sam.album_name = al.album_name""",
        conn,
    )

    mask = df.apply(lambda r: _match_album_artist(r["artist_name"], r["album_artists"]), axis=1)
    df = df[mask]

    base = df[["album_name", "artist_name", "album_type", "total_tracks"]].copy()
    priority = {"album": 0, "compilation": 1, "single": 2}
    base["_pri"] = base["album_type"].map(priority)
    type_df = (
        base.sort_values("_pri")
        .drop_duplicates(subset=["album_name", "artist_name"], keep="first")
        .drop(columns=["_pri"])
    )

    date_df = df.dropna(subset=["release_date"])
    date_df = date_df.groupby(["album_name", "artist_name"], as_index=False)["release_date"].min()

    # 补充 release group canonical name 的元数据行
    _add_canonical_metadata(type_df, date_df, conn)

    conn.close()
    return {"type": type_df, "release_date": date_df}


def _add_canonical_metadata(type_df, date_df, conn):
    """为 release group 的 canonical_name 补充 album_type 和 release_date 行。

    将 canonical_name 映射到 primary_album 的 album_name，然后从现有 metadata
    中复制对应行。这样 release_date 过滤和 album_type 过滤能正确作用于合并后的名称。
    """
    mapping = pd.read_sql_query(
        """SELECT al.album_name, a.artist_name, rg.canonical_name,
                  rg.primary_album_id, pa.album_name AS primary_album_name
           FROM release_group_members rgm
           JOIN release_groups rg ON rgm.group_id = rg.group_id
           JOIN albums al ON rgm.album_id = al.album_id
           JOIN artists a ON al.artist_id = a.artist_id
           LEFT JOIN albums pa ON rg.primary_album_id = pa.album_id""",
        conn,
    )
    if mapping.empty:
        return

    # album_type: 从 primary_album 的 metadata 复制
    primary_types = type_df.merge(
        mapping[["primary_album_name", "artist_name", "canonical_name"]].drop_duplicates(),
        left_on=["album_name", "artist_name"],
        right_on=["primary_album_name", "artist_name"],
        how="inner",
    )[["canonical_name", "artist_name", "album_type", "total_tracks"]].rename(
        columns={"canonical_name": "album_name"}
    )
    if not primary_types.empty:
        existing = set(zip(type_df["album_name"], type_df["artist_name"]))
        for _, row in primary_types.iterrows():
            key = (row["album_name"], row["artist_name"])
            if key not in existing:
                type_df.loc[len(type_df)] = row

    # release_date: 取 primary_album 的最早发行日期
    primary_dates = (
        date_df.merge(
            mapping[["primary_album_name", "artist_name", "canonical_name"]].drop_duplicates(),
            left_on=["album_name", "artist_name"],
            right_on=["primary_album_name", "artist_name"],
            how="inner",
        )
        .groupby(["canonical_name", "artist_name"], as_index=False)["release_date"]
        .min()
        .rename(columns={"canonical_name": "album_name"})
    )
    if not primary_dates.empty:
        existing = set(zip(date_df["album_name"], date_df["artist_name"]))
        for _, row in primary_dates.iterrows():
            key = (row["album_name"], row["artist_name"])
            if key not in existing:
                date_df.loc[len(date_df)] = row


def _get_album_canonical_map():
    """获取所有 release group 成员的 (album_name, artist_name) → canonical_name 映射。"""
    try:
        conn = get_db()
        mapping = pd.read_sql_query(
            """SELECT al.album_name, a.artist_name, rg.canonical_name
               FROM release_group_members rgm
               JOIN release_groups rg ON rgm.group_id = rg.group_id
               JOIN albums al ON rgm.album_id = al.album_id
               JOIN artists a ON al.artist_id = a.artist_id""",
            conn,
        )
        conn.close()
        return mapping
    except Exception:
        return pd.DataFrame(columns=["album_name", "artist_name", "canonical_name"])


# ── Cache registration ─────────────────────────────────────────────────
from backend.core.cache_manager import register_lru  # noqa: E402

register_lru("billboard", "raw_data", load_billboard_raw)
register_lru("billboard", "raw_data_artists", load_billboard_raw_for_artists)
register_lru("billboard", "canonical_map", load_track_album_map)
register_lru("billboard", "album_meta", _load_album_metadata)
