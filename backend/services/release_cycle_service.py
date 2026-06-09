"""Release cycle analysis service — migrated from app/pages/billboard/release_cycle/shared.py."""

import json
from functools import lru_cache

import numpy as np
import pandas as pd

from backend.core.cache import ttl_cached
from backend.core.db import get_db
from backend.core.version_merge import normalize_album_name
from backend.providers.spotify.client import SpotifyProvider

# ═══════════════════════════════════════════════════════════════════════════
# Spotify token
# ═══════════════════════════════════════════════════════════════════════════


@ttl_cached(3500, namespace="billboard")
def _get_spotify_token():
    """Get Spotify client_credentials token, cached ~58 minutes."""
    try:
        return SpotifyProvider().get_cc_token()
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Spotify API helpers
# ═══════════════════════════════════════════════════════════════════════════


def dedup_preserve_order(seq):
    """List deduplication preserving insertion order."""
    seen = set()
    return [x for x in seq if not (x in seen or seen.add(x))]


def _verify_album_artists(spotify_album_ids, artist_name):
    """Verify whether albums' main artists include the target artist.

    Returns set of verified spotify_album_ids.
    """
    if not spotify_album_ids:
        return set()

    conn = get_db()
    artist_lower = artist_name.lower()
    verified = set()
    need_api = []

    placeholders = ",".join("?" for _ in spotify_album_ids)
    rows = pd.read_sql_query(
        f"SELECT spotify_album_id, album_artists FROM spotify_album_meta "
        f"WHERE spotify_album_id IN ({placeholders})",
        conn,
        params=list(spotify_album_ids),
    )
    conn.close()

    db_ids = set()
    for _, row in rows.iterrows():
        db_id = row["spotify_album_id"]
        db_ids.add(db_id)
        artists_str = row.get("album_artists")
        if artists_str:
            artists = [a.strip().lower() for a in artists_str.split(",")]
            if artist_lower in artists:
                verified.add(db_id)
        else:
            need_api.append(db_id)

    for sid in spotify_album_ids:
        if sid not in db_ids:
            need_api.append(sid)

    if need_api:
        api_verified = _fetch_album_artists_from_api(need_api, artist_name)
        verified.update(api_verified)

    return verified


def _fetch_album_artists_from_api(spotify_album_ids, artist_name):
    """Batch fetch album artists via Spotify /v1/albums?ids= and persist to DB."""
    if not spotify_album_ids:
        return set()

    token = _get_spotify_token()
    if not token:
        return set(spotify_album_ids)

    verified = set()
    ids_list = list(dedup_preserve_order(spotify_album_ids))
    artist_lower = artist_name.lower()

    conn = get_db(readonly=False)

    for i in range(0, len(ids_list), 20):
        batch = ids_list[i : i + 20]
        try:
            data = SpotifyProvider().get_albums(batch, token)
            if not data:
                verified.update(batch)
                continue

            for album in data.get("albums", []):
                if album is None:
                    continue

                artist_names = [a["name"] for a in album.get("artists", [])]
                album_artists_str = ", ".join(artist_names)
                album_artists_lower = [n.lower() for n in artist_names]

                try:
                    genres = (
                        json.dumps(album.get("genres", []), ensure_ascii=False)
                        if album.get("genres")
                        else None
                    )
                    img_url = album["images"][0]["url"] if album.get("images") else None
                    conn.execute(
                        """INSERT INTO spotify_album_meta(
                               spotify_album_id, album_name, album_type, release_date,
                               popularity, label, genres, image_url, album_artists)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                           ON CONFLICT(spotify_album_id) DO UPDATE SET
                               album_name = excluded.album_name,
                               album_type = excluded.album_type,
                               release_date = excluded.release_date,
                               popularity = excluded.popularity,
                               label = excluded.label,
                               genres = excluded.genres,
                               image_url = excluded.image_url,
                               album_artists = excluded.album_artists""",
                        (
                            album["id"],
                            album["name"],
                            album.get("album_type"),
                            album.get("release_date"),
                            album.get("popularity"),
                            album.get("label"),
                            genres,
                            img_url,
                            album_artists_str,
                        ),
                    )
                except Exception:
                    pass

                if artist_lower in album_artists_lower:
                    verified.add(album["id"])

        except Exception:
            verified.update(batch)

    conn.commit()
    conn.close()
    return verified


def _save_album_meta_to_db(
    spotify_album_id, album_name, album_type, release_date, album_artists=None
):
    """Persist Spotify album metadata to spotify_album_meta table."""
    try:
        conn = get_db(readonly=False)
        conn.execute(
            """INSERT INTO spotify_album_meta(
                   spotify_album_id, album_name, album_type, release_date, album_artists)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(spotify_album_id) DO UPDATE SET
                   album_name = excluded.album_name,
                   album_type = excluded.album_type,
                   release_date = excluded.release_date,
                   album_artists = excluded.album_artists""",
            (spotify_album_id, album_name, album_type, release_date, album_artists),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


@ttl_cached(3600, namespace="billboard")
def _spotify_search_album(album_name, artist_name, skip_db_check=False):
    """Get album metadata — DB first, Spotify Search API fallback."""
    if not skip_db_check:
        try:
            conn = get_db()
            row = pd.read_sql_query(
                """SELECT spotify_album_id, album_name, album_type, release_date
                   FROM spotify_album_meta
                   WHERE album_name = ? AND album_type IS NOT NULL AND release_date IS NOT NULL
                   LIMIT 1""",
                conn,
                params=[album_name],
            )
            conn.close()
            if not row.empty:
                return {
                    "album_name": row["album_name"].iloc[0],
                    "album_type": row["album_type"].iloc[0],
                    "release_date": row["release_date"].iloc[0],
                    "spotify_album_id": row["spotify_album_id"].iloc[0],
                }
        except Exception:
            pass

    token = _get_spotify_token()
    if not token:
        return None

    try:
        data = SpotifyProvider().search_albums(album_name, artist_name, token, limit=5)
        if not data:
            return None

        for album in data.get("albums", {}).get("items", []):
            if album["name"].lower() == album_name.lower():
                artist_names = [a["name"] for a in album.get("artists", [])]
                album_artists = ", ".join(artist_names) if artist_names else None

                result = {
                    "album_name": album["name"],
                    "album_type": album.get("album_type"),
                    "release_date": album.get("release_date"),
                    "spotify_album_id": album["id"],
                }
                _save_album_meta_to_db(
                    album["id"],
                    album["name"],
                    album.get("album_type"),
                    album.get("release_date"),
                    album_artists=album_artists,
                )
                return result
    except Exception:
        pass

    return None


# ═══════════════════════════════════════════════════════════════════════════
# Data loading
# ═══════════════════════════════════════════════════════════════════════════


def load_artist_list(df_raw):
    """Extract sorted list of artists with track counts from play data."""
    artists = (
        df_raw.groupby("artist_name")["track_id"]
        .nunique()
        .sort_values(ascending=False)
        .reset_index()
    )
    artists.columns = ["artist_name", "track_count"]
    return artists.to_dict(orient="records")


@lru_cache(maxsize=4)
def load_artist_releases(artist_name):
    """Get all releases (albums + singles) for an artist with metadata.

    Returns DataFrame columns:
      album_name, album_type, release_date, spotify_album_id,
      db_album_id, db_album_name, artist_name, canonical_name, sub_albums
    """
    conn = get_db()
    df = pd.read_sql_query(
        """SELECT DISTINCT
               sam.album_name,
               sam.album_type,
               sam.release_date,
               sam.spotify_album_id,
               al.album_id AS db_album_id,
               al.album_name AS db_album_name,
               a.artist_name
           FROM artists a
           JOIN albums al ON al.artist_id = a.artist_id
           JOIN track_albums ta ON ta.album_id = al.album_id
           JOIN tracks t ON t.track_id = ta.track_id
           JOIN spotify_track_meta stm
             ON REPLACE(t.spotify_track_uri, 'spotify:track:', '') = stm.spotify_track_id
           JOIN spotify_album_meta sam
             ON stm.spotify_album_id = sam.spotify_album_id
           WHERE a.artist_name = ?
             AND sam.album_type IN ('album', 'single')
             AND sam.release_date IS NOT NULL
           ORDER BY sam.release_date""",
        conn,
        params=[artist_name],
    )
    conn.close()

    if df.empty:
        return df

    df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce")
    df = df.dropna(subset=["release_date"])
    df = df.sort_values("release_date", ascending=False).reset_index(drop=True)

    unique_album_ids = set(df["spotify_album_id"].dropna().unique())
    if unique_album_ids:
        valid_ids = _verify_album_artists(unique_album_ids, artist_name)
        df = df[df["spotify_album_id"].isin(valid_ids)]

    df = _filter_release_group_duplicates(df)

    df["_is_native"] = df["album_name"] == df["db_album_name"]
    df = df.sort_values("_is_native", ascending=False)
    df = df.drop_duplicates(subset=["spotify_album_id"], keep="first")
    df = df.drop(columns=["_is_native"])
    df = df.sort_values("release_date", ascending=False).reset_index(drop=True)

    return df


# ═══════════════════════════════════════════════════════════════════════════
# Release group filtering (migrated from shared.py)
# ═══════════════════════════════════════════════════════════════════════════


def _parse_sub_albums(raw):
    """Parse sub_albums JSON field."""
    if pd.isna(raw) or not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []


def _filter_release_group_duplicates(releases_df):
    """Remove non-primary release group members, collapsing to canonical entry."""
    releases_df["canonical_name"] = None
    releases_df["sub_albums"] = None

    if releases_df.empty:
        return releases_df

    artists = releases_df["artist_name"].dropna().unique().tolist()
    if not artists:
        return releases_df

    conn = get_db()
    artist_placeholders = ",".join("?" for _ in artists)

    members = pd.read_sql_query(
        f"""SELECT DISTINCT al.album_id, al.album_name, a.artist_name,
                   rg.canonical_name, rg.primary_album_id, sam.spotify_album_id
            FROM release_group_members rgm
            JOIN release_groups rg ON rgm.group_id = rg.group_id
            JOIN albums al ON rgm.album_id = al.album_id
            JOIN artists a ON al.artist_id = a.artist_id
            JOIN track_albums ta ON ta.album_id = al.album_id
            JOIN tracks t ON t.track_id = ta.track_id
            JOIN spotify_track_meta stm
              ON REPLACE(t.spotify_track_uri, 'spotify:track:', '') = stm.spotify_track_id
            JOIN spotify_album_meta sam ON stm.spotify_album_id = sam.spotify_album_id
            WHERE a.artist_name IN ({artist_placeholders})""",
        conn,
        params=list(artists),
    )
    conn.close()

    if members.empty:
        return releases_df

    # Build canonical → primary/non-primary maps
    groups = {}
    for _, row in members.iterrows():
        canonical = row["canonical_name"]
        sid = row["spotify_album_id"]
        aid = int(row["album_id"])
        primary_aid = int(row["primary_album_id"])

        if canonical not in groups:
            groups[canonical] = {"primary_sids": set(), "non_primary_sids": set()}
        if aid == primary_aid:
            groups[canonical]["primary_sids"].add(sid)
        else:
            groups[canonical]["non_primary_sids"].add(sid)

    for canonical, g in groups.items():
        g["non_primary_sids"] -= g["primary_sids"]

    # Resolve multiple primary sids per group
    sid_to_album_name = dict(zip(releases_df["spotify_album_id"], releases_df["album_name"]))
    for canonical, g in groups.items():
        if len(g["primary_sids"]) <= 1:
            continue
        best = None
        for sid in g["primary_sids"]:
            name = sid_to_album_name.get(sid, "")
            if name.lower() == canonical.lower():
                best = sid
                break
            if best is None:
                best = sid
        demoted = g["primary_sids"] - {best}
        g["primary_sids"] = {best}
        g["non_primary_sids"] |= demoted

    non_primary_sids = set()
    sid_to_canonical = {}
    primary_sid_to_canonical = {}

    for canonical, g in groups.items():
        for sid in g["primary_sids"]:
            primary_sid_to_canonical[sid] = canonical
        for sid in g["non_primary_sids"]:
            non_primary_sids.add(sid)
            sid_to_canonical[sid] = canonical

    # Don't swallow singles into album groups
    if non_primary_sids:
        sid_to_type = dict(zip(releases_df["spotify_album_id"], releases_df["album_type"]))
        filtered_sids = set()
        for sid in non_primary_sids:
            canonical = sid_to_canonical.get(sid)
            rel_type = sid_to_type.get(sid, "unknown")
            primary_sid = None
            for psid, canon in primary_sid_to_canonical.items():
                if canon == canonical:
                    primary_sid = psid
                    break
            primary_type = sid_to_type.get(primary_sid, "unknown") if primary_sid else "unknown"
            if rel_type == "single" and primary_type == "album":
                continue
            filtered_sids.add(sid)
        non_primary_sids = filtered_sids

    if not non_primary_sids:
        for sid, canonical in primary_sid_to_canonical.items():
            releases_df.loc[releases_df["spotify_album_id"] == sid, "canonical_name"] = canonical
        releases_df = releases_df.sort_values("release_date", ascending=False).reset_index(
            drop=True
        )
        return _ad_hoc_name_grouping(releases_df)

    # Collect sub-album metadata from non-primary rows
    sub_albums_by_canonical = {}
    non_primary_rows = releases_df[releases_df["spotify_album_id"].isin(non_primary_sids)]

    for _, rel in non_primary_rows.iterrows():
        sid = rel["spotify_album_id"]
        canonical = sid_to_canonical.get(sid)
        if not canonical:
            continue
        sub_albums_by_canonical.setdefault(canonical, []).append(
            {
                "album_name": rel["album_name"],
                "release_date": rel["release_date"].strftime("%Y-%m-%d")
                if pd.notna(rel["release_date"])
                else None,
                "album_type": rel.get("album_type", "unknown"),
            }
        )

    for canonical in sub_albums_by_canonical:
        deduped = []
        seen = set()
        for sa in sub_albums_by_canonical[canonical]:
            key = (sa["album_name"], sa["release_date"])
            if key not in seen:
                seen.add(key)
                deduped.append(sa)
        deduped.sort(key=lambda x: x["release_date"] or "9999")
        sub_albums_by_canonical[canonical] = deduped

    releases_df = releases_df[~releases_df["spotify_album_id"].isin(non_primary_sids)]

    for sid, canonical in primary_sid_to_canonical.items():
        mask = releases_df["spotify_album_id"] == sid
        releases_df.loc[mask, "canonical_name"] = canonical
        for idx in releases_df[mask].index:
            if releases_df.at[idx, "album_name"] != canonical:
                releases_df.at[idx, "album_name"] = canonical
        subs = sub_albums_by_canonical.get(canonical, [])
        if subs:
            releases_df.loc[mask, "sub_albums"] = json.dumps(subs, ensure_ascii=False)

    releases_df = releases_df.sort_values("release_date", ascending=False).reset_index(drop=True)
    return _ad_hoc_name_grouping(releases_df)


def _ad_hoc_name_grouping(releases_df):
    """Phase 2: ad-hoc name normalization grouping for ungrouped releases."""
    ungrouped_mask = releases_df["canonical_name"].isna()
    ungrouped = releases_df[ungrouped_mask]

    if len(ungrouped) < 2:
        return releases_df

    to_drop = []
    to_update = {}

    for artist in ungrouped["artist_name"].unique():
        artist_rows = ungrouped[ungrouped["artist_name"] == artist]
        if len(artist_rows) < 2:
            continue

        norms = artist_rows["album_name"].apply(normalize_album_name)
        for norm_name, count in norms.value_counts().items():
            if count < 2 or not norm_name:
                continue

            group_mask = norms == norm_name
            group = artist_rows[group_mask]
            if group["album_name"].nunique() < 2:
                continue

            exact = group[group["album_name"] == norm_name]
            if not exact.empty:
                native_exact = exact[exact["album_name"] == exact["db_album_name"]]
                if not native_exact.empty:
                    primary_idx = native_exact.index[0]
                else:
                    primary_idx = exact.index[0]
            else:
                native_group = group[group["album_name"] == group["db_album_name"]]
                if not native_group.empty:
                    primary_idx = native_group["release_date"].idxmin()
                else:
                    primary_idx = group["release_date"].idxmin()

            primary_name = releases_df.at[primary_idx, "album_name"]

            sub_albums = []
            for idx in group.index:
                if idx == primary_idx:
                    continue
                row = releases_df.loc[idx]
                if row["album_name"] == primary_name:
                    to_drop.append(idx)
                    continue
                sub_albums.append(
                    {
                        "album_name": row["album_name"],
                        "release_date": row["release_date"].strftime("%Y-%m-%d")
                        if pd.notna(row["release_date"])
                        else None,
                        "album_type": row.get("album_type", "unknown"),
                    }
                )
                to_drop.append(idx)

            existing = _parse_sub_albums(releases_df.at[primary_idx, "sub_albums"])
            all_subs = existing + sub_albums
            deduped = []
            seen = set()
            for sa in all_subs:
                key = (sa["album_name"], sa["release_date"])
                if key not in seen:
                    seen.add(key)
                    deduped.append(sa)
            deduped.sort(key=lambda x: x["release_date"] or "9999")
            to_update[primary_idx] = (norm_name, json.dumps(deduped, ensure_ascii=False))

    for idx, (canonical, subs_json) in to_update.items():
        releases_df.at[idx, "canonical_name"] = canonical
        releases_df.at[idx, "sub_albums"] = subs_json
        if releases_df.at[idx, "album_name"] != canonical:
            releases_df.at[idx, "album_name"] = canonical

    if to_drop:
        releases_df = releases_df.drop(to_drop)

    return releases_df


# ═══════════════════════════════════════════════════════════════════════════
# Play timelines
# ═══════════════════════════════════════════════════════════════════════════


def compute_artist_play_timeline(df_raw, artist_name):
    """Compute weekly play counts and track counts for an artist (all-time, full data)."""
    artist_df = df_raw[df_raw["artist_name"] == artist_name]
    if artist_df.empty:
        return pd.DataFrame()
    weekly = (
        artist_df.groupby("billboard_week")
        .agg(
            play_count=("ms_played", "count"),
            total_ms=("ms_played", "sum"),
            tracks_count=("track_id", "nunique"),
        )
        .reset_index()
    )
    return weekly.sort_values("billboard_week")


def _resolve_album_group(artist_name, album_name):
    """Resolve all album_names in a release group (including group members).

    Returns (album_names: list[str], canonical_name: str, primary_db_name: str)
    """
    conn = get_db()

    # Try 1: direct albums.album_name match
    row = conn.execute(
        """SELECT rg.canonical_name, pa.album_name AS primary_db_name
           FROM release_group_members rgm
           JOIN release_groups rg ON rgm.group_id = rg.group_id
           JOIN albums al ON rgm.album_id = al.album_id
           JOIN artists a ON al.artist_id = a.artist_id
           LEFT JOIN albums pa ON rg.primary_album_id = pa.album_id
           WHERE al.album_name = ? AND a.artist_name = ?""",
        [album_name, artist_name],
    ).fetchone()

    # Try 2: match via spotify_album_meta.album_name → track_albums chain
    if not row:
        row = conn.execute(
            """SELECT rg.canonical_name, pa.album_name AS primary_db_name
               FROM release_group_members rgm
               JOIN release_groups rg ON rgm.group_id = rg.group_id
               JOIN track_albums ta ON ta.album_id = rgm.album_id
               JOIN tracks t ON t.track_id = ta.track_id
               JOIN spotify_track_meta stm
                 ON REPLACE(t.spotify_track_uri, 'spotify:track:', '') = stm.spotify_track_id
               JOIN spotify_album_meta sam ON stm.spotify_album_id = sam.spotify_album_id
               JOIN artists a ON a.artist_name = ?
               LEFT JOIN albums pa ON rg.primary_album_id = pa.album_id
               WHERE sam.album_name = ? AND a.artist_name = ?
               LIMIT 1""",
            [artist_name, album_name, artist_name],
        ).fetchone()

    if not row:
        conn.close()
        return [album_name], album_name, album_name

    canonical = row[0]
    primary_db_name = row[1] or canonical
    members = conn.execute(
        """SELECT al.album_name
           FROM release_group_members rgm
           JOIN release_groups rg ON rgm.group_id = rg.group_id
           JOIN albums al ON rgm.album_id = al.album_id
           JOIN artists a ON al.artist_id = a.artist_id
           WHERE rg.canonical_name = ? AND a.artist_name = ?""",
        [canonical, artist_name],
    ).fetchall()
    conn.close()
    return [m[0] for m in members], canonical, primary_db_name


def compute_album_play_timeline(df_raw, artist_name, album_name):
    """Compute weekly play counts for an album (including all release group versions)."""
    album_names, _, _ = _resolve_album_group(artist_name, album_name)
    album_df = df_raw[
        (df_raw["artist_name"] == artist_name) & (df_raw["album_name"].isin(album_names))
    ]
    if album_df.empty:
        return pd.DataFrame()
    weekly = (
        album_df.groupby("billboard_week")
        .agg(
            play_count=("ms_played", "count"),
            total_ms=("ms_played", "sum"),
            tracks_count=("track_id", "nunique"),
        )
        .reset_index()
    )
    return weekly.sort_values("billboard_week")


def compute_track_timelines(df_raw, artist_name, album_name):
    """Get per-track weekly play counts for an album."""
    album_names, _, _ = _resolve_album_group(artist_name, album_name)
    album_df = df_raw[
        (df_raw["artist_name"] == artist_name) & (df_raw["album_name"].isin(album_names))
    ]
    if album_df.empty:
        return pd.DataFrame()
    weekly = (
        album_df.groupby(["billboard_week", "track_id", "track_name"])
        .agg(play_count=("ms_played", "count"))
        .reset_index()
    )
    return weekly.sort_values(["billboard_week", "play_count"], ascending=[True, False])


# ═══════════════════════════════════════════════════════════════════════════
# Time alignment utilities
# ═══════════════════════════════════════════════════════════════════════════


def align_to_release(weekly_df, release_date, weeks_before=12, weeks_after=24):
    """Align weekly data to release date, adding week_offset column."""
    if weekly_df.empty:
        return weekly_df

    release_date = pd.to_datetime(release_date)
    weekly_df = weekly_df.copy()
    weekly_df["bw_dt"] = pd.to_datetime(weekly_df["billboard_week"])
    weekly_df["week_offset"] = ((weekly_df["bw_dt"] - release_date).dt.days / 7.0).apply(
        lambda x: int(round(x))
    )

    weekly_df = weekly_df[
        (weekly_df["week_offset"] >= -weeks_before) & (weekly_df["week_offset"] <= weeks_after)
    ]
    return weekly_df.drop(columns=["bw_dt"])


def _group_by_release_week(df, release_date, weeks_before, weeks_after):
    """Aggregate plays by precise 7-day windows anchored to release date."""
    release_dt = pd.to_datetime(release_date)
    week_offset = (df["ts_date_dt"] - release_dt).dt.days // 7

    mask = (week_offset >= -weeks_before) & (week_offset <= weeks_after)
    if not mask.any():
        return pd.DataFrame()

    filtered = df.loc[mask]
    filtered_offsets = week_offset.loc[mask]

    weekly = (
        filtered.groupby(filtered_offsets)
        .agg(
            play_count=("ms_played", "count"),
            total_ms=("ms_played", "sum"),
            tracks_count=("track_id", "nunique"),
        )
        .reset_index()
    )
    weekly.columns = ["week_offset", "play_count", "total_ms", "tracks_count"]
    return weekly.sort_values("week_offset")


# ═══════════════════════════════════════════════════════════════════════════
# Core: compute_release_cycle
# ═══════════════════════════════════════════════════════════════════════════


def compute_release_cycle(
    df_raw,
    artist_name,
    album_name,
    release_date,
    weekly_artist=None,
    weekly_album=None,
    weeks_before=12,
    weeks_after=24,
    artist_df=None,
    artist_median=None,
    total_daily=None,
):
    """Compute all data within a release cycle anchored to release date.

    Play counts use precise 7-day windows; rankings use Billboard weeks.

    Optional precomputed args (for efficiency when called repeatedly for same artist):
        artist_df:     pre-filtered df_raw[df_raw["artist_name"] == artist_name]
        artist_median: all-time median weekly play count (float)
        total_daily:   df_raw aggregated by ts_date_dt as Series
    """
    album_info = _resolve_album_group(artist_name, album_name)
    canonical = album_info[1]
    album_names = album_info[0]
    release_dt = pd.to_datetime(release_date)

    result = {
        "release_date": release_dt,
        "artist_timeline": pd.DataFrame(),
        "album_timeline": pd.DataFrame(),
        "track_timelines": pd.DataFrame(),
        "artist_ranks": pd.DataFrame(),
        "album_ranks": pd.DataFrame(),
        "total_timeline": pd.DataFrame(),
        "artist_all_time_median": 0,
    }

    if artist_df is None:
        artist_df = df_raw[df_raw["artist_name"] == artist_name]

    # Artist all-time median
    if artist_median is not None:
        result["artist_all_time_median"] = artist_median
    elif not artist_df.empty:
        dow = artist_df["ts_date_dt"].dt.dayofweek
        week_start = artist_df["ts_date_dt"] - pd.to_timedelta(dow, unit="D")
        artist_all_agg = artist_df.groupby(week_start).agg(play_count=("ms_played", "count"))
        if not artist_all_agg.empty:
            result["artist_all_time_median"] = float(artist_all_agg["play_count"].median())

    # Artist timeline (precise 7-day windows)
    if not artist_df.empty:
        result["artist_timeline"] = _group_by_release_week(
            artist_df,
            release_date,
            weeks_before,
            weeks_after,
        )

    # Album timeline
    album_all = artist_df[artist_df["album_name"].isin(album_names)]
    if not album_all.empty:
        result["album_timeline"] = _group_by_release_week(
            album_all,
            release_date,
            weeks_before,
            weeks_after,
        )

    # Track timelines
    if not album_all.empty:
        track_offsets = (album_all["ts_date_dt"] - release_dt).dt.days // 7
        track_mask = (track_offsets >= -weeks_before) & (track_offsets <= weeks_after)
        if track_mask.any():
            track_filtered = album_all.loc[track_mask]
            track_offsets_f = track_offsets.loc[track_mask]
            result["track_timelines"] = (
                track_filtered.groupby([track_offsets_f, "track_id", "track_name"])
                .agg(play_count=("ms_played", "count"))
                .reset_index()
            )
            result["track_timelines"].columns = [
                "week_offset",
                "track_id",
                "track_name",
                "play_count",
            ]
            result["track_timelines"] = result["track_timelines"].sort_values(
                ["week_offset", "play_count"], ascending=[True, False]
            )

    # Total timeline
    if total_daily is not None:
        offsets = (total_daily.index - release_dt).days // 7
        mask = (offsets >= -weeks_before) & (offsets <= weeks_after)
        if mask.any():
            filtered = total_daily.loc[mask]
            filtered_offsets = offsets[mask]
            weekly = filtered.groupby(filtered_offsets).sum().reset_index()
            weekly.columns = ["week_offset", "play_count"]
            result["total_timeline"] = weekly.sort_values("week_offset")
    else:
        result["total_timeline"] = _group_by_release_week(
            df_raw,
            release_date,
            weeks_before,
            weeks_after,
        )

    # Ranking data (Billboard week alignment)
    if weekly_artist is not None:
        art_ranks = weekly_artist[weekly_artist["artist_name"] == artist_name][
            ["billboard_week", "rank", "play_count"]
        ].copy()
        result["artist_ranks"] = align_to_release(
            art_ranks, release_date, weeks_before, weeks_after
        )

    if weekly_album is not None:
        alb_ranks = weekly_album[
            (weekly_album["artist_name"] == artist_name) & (weekly_album["album_name"] == canonical)
        ][["billboard_week", "rank", "play_count"]].copy()
        result["album_ranks"] = align_to_release(alb_ranks, release_date, weeks_before, weeks_after)

    # Clean baseline window
    advance = get_advance_singles(artist_name, album_name)
    if advance:
        first_single_date = min(pd.to_datetime(s["release_date"]) for s in advance)
        anchor = min(release_dt, first_single_date)
    else:
        anchor = release_dt
    clean_start_offset = int((anchor - release_dt).days // 7) - 4
    result["clean_baseline_start"] = clean_start_offset

    return result


# ═══════════════════════════════════════════════════════════════════════════
# Impact scoring
# ═══════════════════════════════════════════════════════════════════════════


def _compute_artist_impact(cycle_data):
    """Compute artist listening impact score (three-factor weighted)."""
    artist_tl = cycle_data.get("artist_timeline", pd.DataFrame())
    album_tl = cycle_data.get("album_timeline", pd.DataFrame())
    artist_median = cycle_data.get("artist_all_time_median", 0)
    clean_start = cycle_data.get("clean_baseline_start", -4)
    _floor = 10.0

    if artist_tl.empty or album_tl.empty:
        return None, None

    post_artist = artist_tl[(artist_tl["week_offset"] >= 0) & (artist_tl["week_offset"] <= 3)]
    post_album = album_tl[(album_tl["week_offset"] >= 0) & (album_tl["week_offset"] <= 3)]
    if post_artist.empty or post_album.empty:
        return None, None

    post_artist_avg = float(post_artist["play_count"].sum()) / 4
    post_album_avg = float(post_album["play_count"].sum()) / 4

    if artist_median > 0 and post_album_avg > 0:
        magnitude = max(0.0, np.log2(post_album_avg / max(artist_median, _floor)))
    else:
        magnitude = 0.0

    baseline_source = "发行前4周"
    pre_artist_rows = artist_tl[(artist_tl["week_offset"] >= -4) & (artist_tl["week_offset"] <= -1)]
    pre_artist_avg = (
        float(pre_artist_rows["play_count"].sum()) / 4 if not pre_artist_rows.empty else 0.0
    )

    clean_artist_avg = 0.0
    used_clean = False
    if clean_start < -4:
        clean_end = clean_start + 4
        clean_rows = artist_tl[
            (artist_tl["week_offset"] >= clean_start) & (artist_tl["week_offset"] < clean_end)
        ]
        if not clean_rows.empty:
            clean_artist_avg = float(clean_rows["play_count"].sum()) / 4

    if clean_artist_avg > 0:
        baseline_avg = clean_artist_avg
        baseline_source = f"洁净期基线 ({clean_artist_avg:.0f}次/周)"
        used_clean = True
    elif pre_artist_avg > 0:
        baseline_avg = pre_artist_avg
    elif artist_median > 0:
        baseline_avg = float(artist_median)
        baseline_source = "全时段中位数"
    else:
        baseline_avg = 0.0

    if baseline_avg > 0 and post_artist_avg > 0:
        growth = max(0.0, np.log2(post_artist_avg / max(baseline_avg, _floor)))
        raw_boost = post_artist_avg / baseline_avg
    else:
        growth = 0.0
        raw_boost = 0

    attribution = min(1.0, post_album_avg / post_artist_avg) if post_artist_avg > 0 else 0.0

    score = 0.35 * magnitude + 0.35 * growth + 0.30 * attribution
    score = round(score, 2)

    factors = {
        "score": score,
        "magnitude": round(magnitude, 2),
        "growth": round(growth, 2),
        "attribution": round(attribution, 2),
        "baseline_avg": round(baseline_avg, 1),
        "pre_artist_avg": round(pre_artist_avg, 1),
        "clean_artist_avg": round(clean_artist_avg, 1) if used_clean else None,
        "post_artist_avg": round(post_artist_avg, 1),
        "post_album_avg": round(post_album_avg, 1),
        "artist_median": round(artist_median, 1),
        "raw_boost": round(raw_boost, 2),
        "baseline_source": baseline_source,
    }
    return score, factors


def _compute_market_impact(cycle_data):
    """Compute market impact score (three-factor weighted)."""
    album_tl = cycle_data.get("album_timeline", pd.DataFrame())
    total_tl = cycle_data.get("total_timeline", pd.DataFrame())
    _floor = 10.0

    if album_tl.empty:
        return None, None

    post_album = album_tl[(album_tl["week_offset"] >= 0) & (album_tl["week_offset"] <= 3)]
    if post_album.empty:
        return None, None

    post_album_avg = float(post_album["play_count"].sum()) / 4

    market_share = 0.0
    total_post_avg = None
    total_pre_avg = None
    if not total_tl.empty:
        post_total = total_tl[(total_tl["week_offset"] >= 0) & (total_tl["week_offset"] <= 3)]
        if not post_total.empty:
            total_post_avg = float(post_total["play_count"].sum()) / 4
            market_share = min(1.0, post_album_avg / max(1.0, total_post_avg))

    volume = max(0.0, np.log2(post_album_avg / _floor))

    market_shift = 0.0
    pre_album_avg = 0.0
    album_delta = 0.0
    if not total_tl.empty:
        pre_total_rows = total_tl[(total_tl["week_offset"] >= -4) & (total_tl["week_offset"] <= -1)]
        total_pre_for_shift = (
            float(pre_total_rows["play_count"].sum()) / 4 if not pre_total_rows.empty else 0.0
        )
        total_pre_avg = total_pre_for_shift

        pre_album_rows = album_tl[(album_tl["week_offset"] >= -4) & (album_tl["week_offset"] <= -1)]
        pre_album_avg = (
            float(pre_album_rows["play_count"].sum()) / 4 if not pre_album_rows.empty else 0.0
        )

        album_delta = max(0.0, post_album_avg - pre_album_avg)
        market_shift = max(0.0, np.log2(1 + album_delta / max(total_pre_for_shift, _floor)))

    score = 0.30 * market_share + 0.30 * volume + 0.40 * market_shift
    score = round(score, 2)

    factors = {
        "score": score,
        "market_share": round(market_share, 2),
        "volume": round(volume, 2),
        "market_shift": round(market_shift, 2),
        "post_album_avg": round(post_album_avg, 1),
        "total_pre_avg": round(total_pre_avg, 1) if total_pre_avg else None,
        "total_post_avg": round(total_post_avg, 1) if total_post_avg else None,
        "pre_album_avg": round(pre_album_avg, 1),
        "album_delta": round(album_delta, 1),
    }
    return score, factors


def format_artist_impact(score):
    if score is None:
        return "—"
    if score >= 0.8:
        return f"{score:.2f} · 现象级"
    if score >= 0.5:
        return f"{score:.2f} · 强冲击"
    if score >= 0.3:
        return f"{score:.2f} · 有冲击"
    return f"{score:.2f} · 微弱"


def format_market_impact(score):
    if score is None:
        return "—"
    if score >= 0.8:
        return f"{score:.2f} · 统治级"
    if score >= 0.5:
        return f"{score:.2f} · 强冲击"
    if score >= 0.3:
        return f"{score:.2f} · 有冲击"
    return f"{score:.2f} · 微弱"


# ═══════════════════════════════════════════════════════════════════════════
# Release metrics
# ═══════════════════════════════════════════════════════════════════════════


def compute_release_metrics(cycle_data, album_type="album"):
    """Extract metrics from a release cycle result dict."""
    metrics = {
        "debut_rank": None,
        "peak_rank": None,
        "weeks_to_peak": None,
        "weeks_on_chart": 0,
        "artist_impact": None,
        "market_impact": None,
        "artist_impact_detail": None,
        "market_impact_detail": None,
        "half_life": None,
        "peak_play_count": 0,
        "release_week_plays": 0,
        "pre_release_avg": 0,
    }

    atl = cycle_data.get("album_timeline", pd.DataFrame())
    if atl.empty:
        return metrics

    release_row = atl[atl["week_offset"] == 0]
    if not release_row.empty:
        metrics["release_week_plays"] = int(release_row["play_count"].iloc[0])

    pre_rows = atl[(atl["week_offset"] >= -4) & (atl["week_offset"] <= -1)]
    if not pre_rows.empty:
        metrics["pre_release_avg"] = float(pre_rows["play_count"].mean())

    post_rows = atl[(atl["week_offset"] >= 0) & (atl["week_offset"] <= 24)]
    if not post_rows.empty:
        peak_row = post_rows.loc[post_rows["play_count"].idxmax()]
        metrics["peak_play_count"] = int(peak_row["play_count"])

    metrics["artist_impact"], metrics["artist_impact_detail"] = _compute_artist_impact(cycle_data)
    metrics["market_impact"], metrics["market_impact_detail"] = _compute_market_impact(cycle_data)

    peak_plays = metrics["peak_play_count"]
    if peak_plays > 0 and not post_rows.empty:
        peak_offset = int(post_rows.loc[post_rows["play_count"].idxmax(), "week_offset"])
        decay_rows = atl[
            (atl["week_offset"] > peak_offset) & (atl["play_count"] <= peak_plays * 0.5)
        ]
        if not decay_rows.empty:
            decay_offset = int(decay_rows["week_offset"].min())
            metrics["half_life"] = decay_offset - peak_offset

    ar = cycle_data.get("album_ranks", pd.DataFrame())
    if not ar.empty:
        metrics["peak_rank"] = int(ar["rank"].min())
        metrics["weeks_on_chart"] = int(ar["billboard_week"].nunique())

        debut = ar[ar["week_offset"] == 0]
        if not debut.empty:
            metrics["debut_rank"] = int(debut["rank"].iloc[0])

        peak_rank = metrics["peak_rank"]
        peak_rows = ar[ar["rank"] == peak_rank]
        if not peak_rows.empty and peak_rank is not None:
            first_peak_offset = int(peak_rows["week_offset"].min())
            first_entry = int(ar["week_offset"].min())
            metrics["weeks_to_peak"] = first_peak_offset - first_entry

    return metrics


# ═══════════════════════════════════════════════════════════════════════════
# Artist summary & helpers
# ═══════════════════════════════════════════════════════════════════════════


def compute_artist_summary(artist_name, releases_df, weekly, weekly_artist, weekly_album):
    """Compute artist-level aggregate stats."""
    summary = {
        "total_albums": 0,
        "total_singles": 0,
        "album_debut_no1_count": 0,
        "single_debut_no1_count": 0,
        "double_debut_count": 0,
        "max_artist_impact": None,
        "max_artist_impact_album": "",
        "max_market_impact": None,
        "max_market_impact_album": "",
        "total_catalog_reentries": 0,
    }

    if releases_df.empty:
        return summary

    albums = releases_df[releases_df["album_type"] == "album"]
    singles = releases_df[releases_df["album_type"] == "single"]
    summary["total_albums"] = len(albums)
    summary["total_singles"] = len(singles)

    # Single debut #1
    if weekly is not None:
        artist_tracks = weekly[weekly["artist_name"] == artist_name]
        if not artist_tracks.empty:
            first_track_appear = (
                artist_tracks.sort_values("billboard_week")
                .groupby("track_id")
                .first()
                .reset_index()
            )
            summary["single_debut_no1_count"] = int((first_track_appear["rank"] == 1).sum())

    # Album debut #1
    if weekly_album is not None:
        artist_albums = weekly_album[weekly_album["artist_name"] == artist_name]
        if not artist_albums.empty:
            first_album_appear = (
                artist_albums.sort_values("billboard_week")
                .groupby(["album_name", "artist_name"])
                .first()
                .reset_index()
            )
            summary["album_debut_no1_count"] = int((first_album_appear["rank"] == 1).sum())

    # Double debut (track + album both #1 same week)
    if weekly is not None and weekly_album is not None:
        all_track_first = (
            weekly.sort_values("billboard_week").groupby("track_id").first().reset_index()
        )
        debut_tracks = all_track_first[all_track_first["rank"] == 1][
            ["track_id", "artist_name", "billboard_week"]
        ]

        all_album_first = (
            weekly_album.sort_values("billboard_week")
            .groupby(["album_name", "artist_name"])
            .first()
            .reset_index()
        )
        debut_albums = all_album_first[all_album_first["rank"] == 1][
            ["album_name", "artist_name", "billboard_week"]
        ]

        if not debut_tracks.empty and not debut_albums.empty:
            double = debut_tracks.merge(
                debut_albums, on=["artist_name", "billboard_week"], how="inner"
            )
            summary["double_debut_count"] = int((double["artist_name"] == artist_name).sum())

    return summary


def fill_summary_from_cycles(summary, artist_name, releases_df, all_cycles, df_raw):
    """Fill impact highs and catalog reentry stats from precomputed cycles."""

    for _, rel in releases_df.iterrows():
        album_name = rel["album_name"]
        album_type = rel["album_type"]

        cycle = all_cycles.get(album_name)
        if cycle is None:
            continue
        metrics = compute_release_metrics(cycle, album_type)

        if metrics["artist_impact"] is not None:
            if (
                summary["max_artist_impact"] is None
                or metrics["artist_impact"] > summary["max_artist_impact"]
            ):
                summary["max_artist_impact"] = metrics["artist_impact"]
                summary["max_artist_impact_album"] = album_name
        if metrics["market_impact"] is not None:
            if (
                summary["max_market_impact"] is None
                or metrics["market_impact"] > summary["max_market_impact"]
            ):
                summary["max_market_impact"] = metrics["market_impact"]
                summary["max_market_impact_album"] = album_name

        if album_type == "album":
            reentries = detect_catalog_reentries(
                df_raw, artist_name, rel["release_date"], album_name
            )
            summary["total_catalog_reentries"] += len(reentries)


# ═══════════════════════════════════════════════════════════════════════════
# Advance singles & catalog reentries
# ═══════════════════════════════════════════════════════════════════════════


def get_advance_singles(artist_name, album_name):
    """Find singles released before an album via three-tier strategy."""
    releases = load_artist_releases(artist_name)
    album_row = releases[releases["db_album_name"] == album_name]
    if album_row.empty:
        album_row = releases[releases["album_name"] == album_name]
    if album_row.empty:
        return []

    album_release_date = album_row["release_date"].iloc[0]
    db_name = (
        album_row["db_album_name"].iloc[0]
        if "db_album_name" in album_row.columns and pd.notna(album_row["db_album_name"].iloc[0])
        else album_name
    )

    conn = get_db()
    shared = pd.read_sql_query(
        """SELECT DISTINCT al_other.album_name, al_other.album_id
           FROM artists a
           JOIN albums al_target ON al_target.artist_id = a.artist_id AND al_target.album_name = ?
           JOIN track_albums ta_target ON ta_target.album_id = al_target.album_id
           JOIN track_albums ta_other
             ON ta_other.track_id = ta_target.track_id
             AND ta_other.album_id != ta_target.album_id
           JOIN albums al_other ON al_other.album_id = ta_other.album_id
           WHERE a.artist_name = ?""",
        conn,
        params=[db_name, artist_name],
    )

    if shared.empty:
        conn.close()
        return []

    results = []
    for _, row in shared.iterrows():
        candidate_name = row["album_name"]

        # Tier 1: DB lookup
        meta = pd.read_sql_query(
            "SELECT album_type, release_date FROM spotify_album_meta WHERE album_name = ? LIMIT 1",
            conn,
            params=[candidate_name],
        )

        release_date = None
        db_has_wrong_type = False
        if not meta.empty:
            db_type = meta["album_type"].iloc[0]
            if db_type == "single":
                db_rd = meta["release_date"].iloc[0]
                if pd.notna(db_rd):
                    release_date = pd.to_datetime(db_rd)
            elif pd.notna(db_type):
                db_has_wrong_type = True

        # Tier 2: Spotify API
        if release_date is None:
            spotify_meta = _spotify_search_album(
                candidate_name,
                artist_name,
                skip_db_check=db_has_wrong_type,
            )
            if spotify_meta and spotify_meta.get("album_type") == "single":
                release_date = pd.to_datetime(spotify_meta["release_date"])

        # Tier 3: earliest play date heuristic
        if release_date is None and not db_has_wrong_type:
            earliest = pd.read_sql_query(
                """SELECT MIN(p.ts_date) AS first_play
                   FROM track_albums ta
                   JOIN plays p ON p.track_id = ta.track_id
                   WHERE ta.album_id = ?""",
                conn,
                params=[int(row["album_id"])],
            )
            if not earliest.empty and earliest["first_play"].iloc[0] is not None:
                release_date = pd.to_datetime(earliest["first_play"].iloc[0])

        if (
            release_date is not None
            and pd.notna(release_date)
            and release_date < album_release_date
        ):
            results.append(
                {
                    "single_name": candidate_name,
                    "release_date": release_date,
                }
            )

    conn.close()

    if not results:
        return []

    results.sort(key=lambda x: x["release_date"])
    return results


def detect_catalog_reentries(
    df_raw, artist_name, release_date, current_album_name, pre_window=4, post_window=24
):
    """Detect old songs that re-enter listening after a new release."""
    release_date = pd.to_datetime(release_date)
    artist_df = df_raw[df_raw["artist_name"] == artist_name].copy()

    releases = load_artist_releases(artist_name)
    if releases.empty:
        return []

    current_rel = releases[releases["album_name"] == current_album_name]
    if current_rel.empty:
        return []

    current_rel_date = pd.to_datetime(current_rel["release_date"].iloc[0])
    earlier = releases[pd.to_datetime(releases["release_date"]) < current_rel_date]
    earlier_albums = (
        earlier["db_album_name"].tolist()
        if "db_album_name" in earlier.columns
        else earlier["album_name"].tolist()
    )

    old_songs = artist_df[artist_df["album_name"].isin(earlier_albums)].copy()
    if old_songs.empty:
        return []

    old_songs["bw_dt"] = pd.to_datetime(old_songs["billboard_week"])
    old_songs["week_offset"] = ((old_songs["bw_dt"] - release_date).dt.days / 7.0).apply(
        lambda x: int(round(x))
    )

    pre_mask = (old_songs["week_offset"] >= -pre_window) & (old_songs["week_offset"] <= -1)
    pre_active_tracks = set(old_songs[pre_mask]["track_id"].unique())

    post_mask = (old_songs["week_offset"] >= 1) & (old_songs["week_offset"] <= post_window)
    post_data = old_songs[post_mask]

    if post_data.empty:
        return []

    reentries = []
    for track_id, group in post_data.groupby("track_id"):
        if track_id in pre_active_tracks:
            continue

        track_name = group["track_name"].iloc[0]
        source_album = group["album_name"].iloc[0]
        reentry_offset = int(group["week_offset"].min())
        weeks_in_chart = int(group["billboard_week"].nunique())

        reentries.append(
            {
                "track_name": track_name,
                "source_album": source_album,
                "reentry_offset": reentry_offset,
                "weeks_in_chart": weeks_in_chart,
            }
        )

    return sorted(reentries, key=lambda x: x["reentry_offset"])


def get_bonus_tracks(df_raw, artist_name, group_albums, primary_name):
    """Find tracks unique to non-primary group versions (deluxe, acoustic, etc.)."""
    conn = get_db()
    all_tracks = set()
    primary_tracks = set()

    for album_name in group_albums:
        rows = conn.execute(
            """SELECT DISTINCT t.track_name
               FROM albums al
               JOIN track_albums ta ON ta.album_id = al.album_id
               JOIN tracks t ON t.track_id = ta.track_id
               WHERE al.album_name = ?""",
            [album_name],
        ).fetchall()
        names = {r[0] for r in rows}
        all_tracks |= names
        if album_name == primary_name:
            primary_tracks = names

    conn.close()

    bonus_names = all_tracks - primary_tracks
    if not bonus_names:
        return []

    result = []
    for name in bonus_names:
        bonus_df = df_raw[
            (df_raw["artist_name"] == artist_name)
            & (df_raw["track_name"] == name)
            & (df_raw["album_name"].isin(group_albums))
        ]
        if not bonus_df.empty:
            source = (
                bonus_df["album_name"].mode().iloc[0]
                if not bonus_df["album_name"].mode().empty
                else "unknown"
            )
            result.append(
                {
                    "track_name": name,
                    "play_count": int(len(bonus_df)),
                    "first_appearance": bonus_df["ts_date"].min().isoformat()
                    if hasattr(bonus_df["ts_date"].min(), "isoformat")
                    else str(bonus_df["ts_date"].min()),
                    "source_album": source,
                }
            )

    return sorted(result, key=lambda x: x["play_count"], reverse=True)


def get_single_track_ids(artist_name, single_name):
    """Get track_ids associated with a single."""
    conn = get_db()
    rows = conn.execute(
        """SELECT DISTINCT t.track_id
           FROM artists a
           JOIN albums al ON al.artist_id = a.artist_id AND al.album_name = ?
           JOIN track_albums ta ON ta.album_id = al.album_id
           JOIN tracks t ON t.track_id = ta.track_id
           WHERE a.artist_name = ?""",
        [single_name, artist_name],
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_chart_ranks_for_tracks(
    weekly, artist_name, track_ids, release_date, weeks_before=12, weeks_after=24
):
    """Get Billboard chart ranks for specific tracks, aligned to release date."""
    if weekly is None or not track_ids:
        return pd.DataFrame()

    ranks = weekly[weekly["track_id"].isin(track_ids)][
        ["billboard_week", "track_id", "track_name", "rank"]
    ].copy()

    if ranks.empty:
        return ranks

    release_date = pd.to_datetime(release_date)
    ranks = align_to_release(ranks, release_date, weeks_before, weeks_after)

    if not ranks.empty:
        ranks = ranks.groupby(["week_offset", "track_id", "track_name"])["rank"].min().reset_index()

    return ranks


# ── Cache registration ─────────────────────────────────────────────────
from backend.core.cache_manager import register_lru, register_ttl  # noqa: E402

register_lru("billboard", "release_cycle", load_artist_releases)
register_ttl("billboard", "release_token", _get_spotify_token)
register_ttl("billboard", "spotify_search", _spotify_search_album)
