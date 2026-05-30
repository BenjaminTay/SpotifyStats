"""Full yearly Wrapped report — all 12 modules in a single response.

Replaces the older get_wrapped_data() with richer data covering hero,
personality (7-dim), top lists, genre panorama, time story, music map,
discovery & returns, listening depth, special moments, monthly drilldown,
and year-over-year comparison.
"""

from __future__ import annotations

import json
import sqlite3

import pandas as pd

from backend.core.db import load_plays

# ═══════════════════════════════════════════════════════════════════════════════
# helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _hour(ms_series):
    """Sum ms_played → hours."""
    return float(ms_series.sum() / 3_600_000)


def _total_minutes(ms_series):
    """Sum ms_played → minutes."""
    return float(ms_series.sum() / 60_000)


def _get_artist_cover(conn: sqlite3.Connection, artist_name: str) -> str:
    row = conn.execute(
        "SELECT image_url FROM spotify_artist_meta WHERE artist_name = ? LIMIT 1",
        (artist_name,),
    ).fetchone()
    return (row[0] or "") if row else ""


def _get_album_cover(conn: sqlite3.Connection, album_name: str) -> str:
    row = conn.execute(
        "SELECT image_url FROM spotify_album_meta WHERE album_name = ? LIMIT 1",
        (album_name,),
    ).fetchone()
    return (row[0] or "") if row else ""


def _get_track_cover(conn: sqlite3.Connection, track_name: str, artist_name: str) -> str:
    """Get album cover for a track — go through spotify_track_meta to spotify_album_meta.

    tracks.spotify_album_id is not reliably populated; the canonical path is
    tracks.spotify_track_uri → spotify_track_meta.spotify_track_id
     → spotify_track_meta.spotify_album_id → spotify_album_meta.image_url.
    Falls back to the albums dimension table when spotify_album_meta has no image.
    """
    row = conn.execute(
        "SELECT m.image_url "
        "FROM tracks t "
        "JOIN artists a ON t.artist_id = a.artist_id "
        "JOIN spotify_track_meta stm "
        "  ON REPLACE(t.spotify_track_uri, 'spotify:track:', '') = stm.spotify_track_id "
        "JOIN spotify_album_meta m ON stm.spotify_album_id = m.spotify_album_id "
        "WHERE t.track_name = ? AND a.artist_name = ? LIMIT 1",
        (track_name, artist_name),
    ).fetchone()
    if row and row[0]:
        return row[0]
    # fallback: use the dimension albums table (has image_url from ensure_schema)
    row2 = conn.execute(
        "SELECT al.image_url "
        "FROM tracks t "
        "JOIN artists a ON t.artist_id = a.artist_id "
        "JOIN albums al ON t.album_id = al.album_id "
        "WHERE t.track_name = ? AND a.artist_name = ? LIMIT 1",
        (track_name, artist_name),
    ).fetchone()
    return (row2[0] or "") if row2 else ""


def _batch_query(conn: sqlite3.Connection, sql_template: str, items: list, batch_size: int = 500):
    """Execute a parameterised query in batches for large IN(...) lists."""
    results = []
    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        ph = ",".join(["?"] * len(batch))
        results.extend(conn.execute(sql_template.format(placeholders=ph), batch).fetchall())
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# Personality mapping
# ═══════════════════════════════════════════════════════════════════════════════

PERSONALITY_MAP = {
    ("explorer", "globetrotter"): ("环球旅人", "你的播放列表就是一本没有签证的护照"),
    ("globetrotter", "explorer"): ("环球旅人", "你的播放列表就是一本没有签证的护照"),
    ("loyalist", "collector"): ("深度鉴赏家", "你不听歌，你研究歌。专辑是你的最小单位"),
    ("collector", "loyalist"): ("深度鉴赏家", "你不听歌，你研究歌。专辑是你的最小单位"),
    ("binger", "night_owl"): ("能量引擎", "音乐是你的日间燃料，从早燃到晚"),
    ("night_owl", "binger"): ("能量引擎", "音乐是你的日间燃料，从早燃到晚"),
    ("night_owl", "explorer"): ("午夜诗人", "凌晨两点，你和耳机里的世界清醒着"),
    ("explorer", "night_owl"): ("午夜诗人", "凌晨两点，你和耳机里的世界清醒着"),
    ("trend_chaser", "explorer"): ("潮流捕手", "新歌上线，你是朋友圈第一个听到的人"),
    ("explorer", "trend_chaser"): ("潮流捕手", "新歌上线，你是朋友圈第一个听到的人"),
    ("loyalist", "explorer"): ("忠实灯塔", "你知道自己要什么，一首歌可以循环一整年"),
    ("explorer", "loyalist"): ("忠实灯塔", "你知道自己要什么，一首歌可以循环一整年"),
}

PRIMARY_FALLBACKS = {
    "explorer": ("环球旅人", "你的播放列表就是一本没有签证的护照"),
    "loyalist": ("忠实灯塔", "你知道自己要什么，一首歌可以循环一整年"),
    "binger": ("能量引擎", "音乐是你的日间燃料，从早燃到晚"),
    "night_owl": ("午夜诗人", "凌晨两点，你和耳机里的世界清醒着"),
    "collector": ("深度鉴赏家", "你不听歌，你研究歌。专辑是你的最小单位"),
    "trend_chaser": ("潮流捕手", "新歌上线，你是朋友圈第一个听到的人"),
    "globetrotter": ("环球旅人", "你的播放列表就是一本没有签证的护照"),
}

DIMENSION_DESCS = {
    "explorer": "广泛涉猎不同曲目，保持音乐品味多样化",
    "loyalist": "对喜爱的艺人从一而终，深入了解他们的作品",
    "binger": "音乐是日常必需品，每天大量时间沉浸在旋律中",
    "night_owl": "深夜是你的音乐主场，黑暗中与旋律共鸣",
    "collector": "不听完所有曲目的专辑都不算听过，完整度是你的执念",
    "trend_chaser": "永远冲在新歌前线，第一时间尝鲜",
    "globetrotter": "音乐品味跨越国界，耳朵走遍世界每个角落",
}


def _resolve_personality(scores: dict) -> dict:
    """Given {dim: score} dict, return primary label + dimensions list."""
    sorted_dims = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top1, top2 = sorted_dims[0][0], sorted_dims[1][0] if len(sorted_dims) > 1 else None

    # Try combination first
    if top2 and (top1, top2) in PERSONALITY_MAP:
        primary_label, primary_desc = PERSONALITY_MAP[(top1, top2)]
    else:
        primary_label, primary_desc = PRIMARY_FALLBACKS.get(
            top1, ("环球旅人", "你的播放列表就是一本没有签证的护照")
        )

    dimensions = {}
    for dim, score in scores.items():
        dimensions[dim] = {
            "label": _dim_label(dim),
            "score": round(float(score), 1),
            "desc": DIMENSION_DESCS.get(dim, ""),
        }

    return {
        "primary": top1,
        "primary_label": primary_label,
        "primary_desc": primary_desc,
        "dimensions": dimensions,
    }


def _dim_label(dim: str) -> str:
    labels = {
        "explorer": "Explorer 探索者",
        "loyalist": "Loyalist 专一者",
        "binger": "Binger 狂听者",
        "night_owl": "Night Owl 夜猫子",
        "collector": "Collector 收藏家",
        "trend_chaser": "Trend Chaser 追新族",
        "globetrotter": "Globetrotter 环球旅人",
    }
    return labels.get(dim, dim)


# ═══════════════════════════════════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════════════════════════════════


def get_wrapped_full(
    conn: sqlite3.Connection,
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    year: int,
) -> dict:
    """Generate the full multi-module yearly Wrapped report.

    Returns a dict matching ``backend.models.wrapped.WrappedFullResponse``.
    """
    df = load_plays(
        conn,
        min_ms=min_ms,
        music_only=music_only,
        merge_enabled=merge_enabled,
    )
    year_df = df[df["ts_year"] == year]
    if year_df.empty:
        return {
            "year": year,
            "empty": True,
            "hero": None,
            "personality": None,
            "top_lists": None,
            "genre_panorama": None,
            "time_story": None,
            "music_map": None,
            "discovery_returns": None,
            "listening_depth": None,
            "special_moments": None,
            "monthly_drilldown": [],
            "comparison": None,
        }

    total_minutes = _total_minutes(year_df["ms_played"])
    total_plays = len(year_df)
    active_days = int(year_df["ts_date"].nunique())
    unique_tracks = int(year_df["track_id"].nunique())
    unique_artists = int(year_df["artist_name"].dropna().nunique())
    avg_hours_per_day = float(total_minutes / 60 / max(active_days, 1))

    # Pre-compute commonly needed aggregates
    artist_agg = (
        year_df.groupby("artist_name")
        .agg(plays=("play_id", "count"), hours=("ms_played", _hour))
        .sort_values(["plays", "hours"], ascending=False)
    )
    track_agg = (
        year_df.groupby(["track_name", "artist_name", "track_id"])
        .agg(plays=("play_id", "count"), hours=("ms_played", _hour))
        .sort_values(["plays", "hours"], ascending=False)
        .reset_index()
    )
    album_agg = (
        year_df.groupby(["album_name", "artist_name"])
        .agg(plays=("play_id", "count"), hours=("ms_played", _hour))
        .sort_values(["plays", "hours"], ascending=False)
        .reset_index()
    )

    return {
        "year": year,
        "empty": False,
        "hero": _build_hero(
            year_df, total_minutes, total_plays, unique_tracks, unique_artists, active_days
        ),
        "personality": _build_personality(
            conn, year_df, artist_agg, total_plays, avg_hours_per_day, unique_tracks
        ),
        "top_lists": _build_top_lists(conn, artist_agg, track_agg, album_agg),
        "genre_panorama": _build_genre_panorama(conn, year_df, artist_agg),
        "time_story": _build_time_story(conn, year_df),
        "music_map": _build_music_map(conn, year_df, artist_agg),
        "discovery_returns": _build_discovery_returns(conn, df, year_df, year),
        "listening_depth": _build_listening_depth(conn, year_df, track_agg, year),
        "special_moments": _build_special_moments(conn, year_df),
        "monthly_drilldown": _build_monthly_drilldown(conn, year_df),
        "comparison": _build_comparison(df, year_df, year, track_agg, artist_agg),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Hero
# ═══════════════════════════════════════════════════════════════════════════════


def _build_hero(year_df, total_minutes, total_plays, unique_tracks, unique_artists, active_days):
    avg_minutes_per_day = round(float(total_minutes / max(active_days, 1)), 1)
    return {
        "total_minutes": round(float(total_minutes), 0),
        "total_plays": int(total_plays),
        "unique_tracks": int(unique_tracks),
        "unique_artists": int(unique_artists),
        "active_days": int(active_days),
        "avg_minutes_per_day": avg_minutes_per_day,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Personality (7 dimensions)
# ═══════════════════════════════════════════════════════════════════════════════


def _build_personality(conn, year_df, artist_agg, total_plays, avg_hours_per_day, unique_tracks):
    # 1. explorer: unique tracks ratio
    explorer_raw = unique_tracks / max(total_plays, 1) * 100
    explorer_score = min(explorer_raw / 40 * 100, 100)

    # 2. loyalist: top artist play share
    top1_artist_plays = int(artist_agg.iloc[0]["plays"]) if len(artist_agg) > 0 else 0
    loyalist_raw = top1_artist_plays / max(total_plays, 1) * 100
    loyalist_score = min(loyalist_raw / 20 * 100, 100)

    # 3. binger: avg hours per day
    binger_score = min(avg_hours_per_day / 4 * 100, 100)

    # 4. night_owl: 0-5 AM play share
    night_mask = year_df["ts_hour"].between(0, 5)
    night_plays = int(night_mask.sum())
    night_owl_raw = night_plays / max(total_plays, 1) * 100
    night_owl_score = min(night_owl_raw / 50 * 100, 100)

    # 5. collector: album completion rate
    collector_score = _calc_collector_score(conn, year_df)

    # 6. trend_chaser: share of current-year releases
    trend_chaser_score = _calc_trend_chaser_score(conn, year_df)

    # 7. globetrotter: non-Chinese music share
    globetrotter_score = _calc_globetrotter_score(conn, year_df, artist_agg)

    scores = {
        "explorer": explorer_score,
        "loyalist": loyalist_score,
        "binger": binger_score,
        "night_owl": night_owl_score,
        "collector": collector_score,
        "trend_chaser": trend_chaser_score,
        "globetrotter": globetrotter_score,
    }
    return _resolve_personality(scores)


def _calc_collector_score(conn: sqlite3.Connection, year_df) -> float:
    """Albums where user played >= 70% of total_tracks (using spotify_album_id)."""
    track_ids = year_df["track_id"].dropna().unique().tolist()
    if not track_ids:
        return 0.0

    placeholders = ",".join("?" * len(track_ids))
    rows = conn.execute(
        f"""
        SELECT t.track_id, sam.spotify_album_id, sam.total_tracks
        FROM tracks t
        JOIN spotify_track_meta stm
          ON REPLACE(t.spotify_track_uri, 'spotify:track:', '') = stm.spotify_track_id
        JOIN spotify_album_meta sam ON stm.spotify_album_id = sam.spotify_album_id
        WHERE t.track_id IN ({placeholders})
          AND sam.total_tracks IS NOT NULL AND sam.total_tracks > 2
    """,
        track_ids,
    ).fetchall()

    if not rows:
        return 0.0

    album_tracks: dict[str, set] = {}
    album_tt: dict[str, int] = {}
    for r in rows:
        tid, aid, ttotal = r
        if aid not in album_tracks:
            album_tracks[aid] = set()
            album_tt[aid] = int(ttotal)
        album_tracks[aid].add(tid)

    completed = sum(1 for aid, tracks in album_tracks.items() if len(tracks) / album_tt[aid] >= 0.7)
    total_albums = len(album_tt)
    return min(completed / max(total_albums, 1) * 100, 100.0)


def _calc_trend_chaser_score(conn: sqlite3.Connection, year_df) -> float:
    """Share of plays on tracks released in the target year.

    Join path: unique (track_name, artist_name) pairs → tracks → spotify_track_meta
    → spotify_album_meta.release_date, matched against the year.
    """
    year = int(year_df["ts_year"].iloc[0])
    pairs = list(year_df[["track_name", "artist_name"]].drop_duplicates().itertuples(index=False))
    pairs = [(t, a) for t, a in pairs if pd.notna(t) and pd.notna(a)]
    if not pairs:
        return 0.0

    release_year_map = _fetch_track_release_years(conn, pairs)
    if not release_year_map:
        return 0.0

    # Sum plays where the track was released in the target year
    current_year_plays = 0
    for _, row in year_df.iterrows():
        key = (row["track_name"], row["artist_name"])
        if release_year_map.get(key) == year:
            current_year_plays += 1

    total_plays = len(year_df)
    if total_plays == 0:
        return 0.0
    raw = current_year_plays / total_plays * 100
    return min(raw / 50 * 100, 100.0)


def _fetch_track_release_years(
    conn: sqlite3.Connection, pairs: list[tuple[str, str]]
) -> dict[tuple[str, str], int]:
    """Resolve track → earliest album release year from spotify_album_meta.

    Uses tracks.spotify_track_uri → spotify_track_meta → spotify_album_meta.
    Returns {(track_name, artist_name): release_year_int}.
    """
    if not pairs:
        return {}

    # Use composite concatenation to handle (track_name, artist_name) pairs
    # in bulk, since SQLite IN only accepts scalar values per placeholder slot.
    composite_keys = [f"{t}|||{a}" for t, a in pairs]
    sql = (
        "SELECT t.track_name, a.artist_name, "
        "  MIN(CAST(SUBSTR(sam.release_date, 1, 4) AS INTEGER)) AS release_year "
        "FROM tracks t "
        "JOIN artists a ON t.artist_id = a.artist_id "
        "JOIN spotify_track_meta stm "
        "  ON REPLACE(t.spotify_track_uri, 'spotify:track:', '') = stm.spotify_track_id "
        "JOIN spotify_album_meta sam ON stm.spotify_album_id = sam.spotify_album_id "
        "WHERE (t.track_name || '|||' || a.artist_name) IN ({placeholders}) "
        "  AND sam.release_date IS NOT NULL "
        "GROUP BY t.track_name, a.artist_name"
    )
    rows = _batch_query(conn, sql, composite_keys, batch_size=500)
    result = {}
    for r in rows:
        key = (r[0], r[1])
        val = r[2]
        if val is not None:
            result[key] = int(val)
    return result


def _calc_globetrotter_score(conn: sqlite3.Connection, year_df, artist_agg) -> float:
    """Share of play time on non-Chinese-language music.

    An artist is considered "Chinese" if their genres contain any of:
    mandopop, cantopop, c-pop, chinese, taiwan, hokkien.
    """
    artist_names = list(artist_agg.index)
    if not artist_names:
        return 0.0

    # Fetch genres for these artists in batches
    placeholders = ",".join("?" * len(artist_names))
    rows = conn.execute(
        f"SELECT artist_name, genres FROM spotify_artist_meta "
        f"WHERE artist_name IN ({placeholders})",
        artist_names,
    ).fetchall()

    chinese_keywords = {
        "mandopop",
        "cantopop",
        "c-pop",
        "chinese",
        "taiwan",
        "hokkien",
        "chinese pop",
        "taiwanese",
        "singaporean",
    }
    is_chinese = {}
    for r in rows:
        name = r[0]
        genres_str = (r[1] or "").lower()
        try:
            genres_list = [g.strip().lower() for g in json.loads(genres_str)]
        except (json.JSONDecodeError, TypeError):
            genres_list = [g.strip().lower() for g in genres_str.split(",")]
        matched = any(kw in " ".join(genres_list) for kw in chinese_keywords)
        # Also check individual genre tokens
        if not matched:
            for g in genres_list:
                if any(kw in g for kw in chinese_keywords):
                    matched = True
                    break
        is_chinese[name] = matched

    # Sum play counts for Chinese vs non-Chinese artists
    chinese_plays = 0
    non_chinese_plays = 0
    for artist_name, row in artist_agg.iterrows():
        plays = int(row["plays"])
        if is_chinese.get(artist_name, False):
            chinese_plays += plays
        else:
            non_chinese_plays += plays

    total = chinese_plays + non_chinese_plays
    if total == 0:
        return 0.0
    return round(non_chinese_plays / total * 100, 1)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Top Lists
# ═══════════════════════════════════════════════════════════════════════════════


def _build_top_lists(conn, artist_agg, track_agg, album_agg):
    # artists (by plays)
    artists = []
    for i, (artist_name, row) in enumerate(artist_agg.head(5).iterrows()):
        artists.append(
            {
                "rank": i + 1,
                "name": artist_name or "",
                "plays": int(row["plays"]),
                "hours": round(float(row["hours"]), 1),
                "cover_url": _get_artist_cover(conn, artist_name),
            }
        )

    # tracks (by plays) - track_agg already sorted by plays
    tracks = []
    for i, r in enumerate(track_agg.head(5).itertuples(index=False)):
        name = r.track_name if pd.notna(r.track_name) else ""
        artist_name = r.artist_name if pd.notna(r.artist_name) else ""
        tracks.append(
            {
                "rank": i + 1,
                "track_id": int(r.track_id),
                "name": name,
                "artist_name": artist_name,
                "plays": int(r.plays),
                "hours": round(float(r.hours), 1),
                "cover_url": _get_track_cover(conn, name, artist_name),
            }
        )

    # albums (by plays)
    albums = []
    for i, r in enumerate(album_agg.head(5).itertuples(index=False)):
        name = r.album_name if pd.notna(r.album_name) else ""
        artist_name = r.artist_name if pd.notna(r.artist_name) else ""
        albums.append(
            {
                "rank": i + 1,
                "name": name,
                "artist_name": artist_name,
                "plays": int(r.plays),
                "hours": round(float(r.hours), 1),
                "cover_url": _get_album_cover(conn, name),
            }
        )

    return {"artists": artists, "tracks": tracks, "albums": albums}


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Genre Panorama
# ═══════════════════════════════════════════════════════════════════════════════


def _build_genre_panorama(conn, year_df, artist_agg):
    """Weighted genre distribution based on play time per artist."""
    artist_names = list(artist_agg.index)
    if not artist_names:
        return {"top_genres": [], "monthly_genres": [], "language_dist": None}

    # Fetch genres for all artists
    placeholders = ",".join("?" * len(artist_names))
    rows = conn.execute(
        f"SELECT artist_name, genres FROM spotify_artist_meta "
        f"WHERE artist_name IN ({placeholders})",
        artist_names,
    ).fetchall()

    artist_genres: dict[str, list[str]] = {}
    for r in rows:
        genres_str = (r[1] or "").strip()
        if not genres_str:
            continue
        try:
            parsed = json.loads(genres_str)
            if isinstance(parsed, list):
                artist_genres[r[0]] = [g.strip() for g in parsed if g.strip()]
        except (json.JSONDecodeError, TypeError):
            artist_genres[r[0]] = [g.strip() for g in genres_str.split(",") if g.strip()]

    # Weighted by play hours — track known vs unknown
    genre_weight: dict[str, float] = {}
    known_hours = 0.0
    for artist_name, row in artist_agg.iterrows():
        hours = float(row["hours"])
        gen = artist_genres.get(artist_name, [])
        if gen:
            for g in gen:
                genre_weight[g] = genre_weight.get(g, 0) + hours
            known_hours += hours

    total_hours = float(artist_agg["hours"].sum())
    unknown_hours = total_hours - known_hours
    if unknown_hours > 0:
        genre_weight["其他流派"] = genre_weight.get("其他流派", 0) + unknown_hours

    total_weight = sum(genre_weight.values()) or 1
    top_genres = sorted(genre_weight.items(), key=lambda x: x[1], reverse=True)[:10]
    top_genres_list = [
        {"name": g, "play_share": round(w / total_weight * 100, 1)} for g, w in top_genres
    ]

    # Monthly genres: for each month, top 5 genres by play hours
    monthly_genres_list = _build_monthly_genres(year_df, artist_genres)

    return {
        "top_genres": top_genres_list,
        "monthly_genres": monthly_genres_list,
        "language_dist": None,  # frontend infers from genre data
    }


def _build_monthly_genres(year_df, artist_genres: dict[str, list[str]]) -> list[dict]:
    """Per-month top 5 genres, weighted by play hours."""
    monthly = []
    for m in range(1, 13):
        month_df = year_df[year_df["ts_month"] == m]
        if month_df.empty:
            monthly.append({"month": m, "genres": {}})
            continue

        genre_hours: dict[str, float] = {}
        unknown_hours = 0.0
        for artist_name, grp in month_df.groupby("artist_name"):
            hours = float(grp["ms_played"].sum() / 3_600_000)
            gen = artist_genres.get(artist_name, [])
            if gen:
                for g in gen:
                    genre_hours[g] = genre_hours.get(g, 0) + hours
            else:
                unknown_hours += hours

        if unknown_hours > 0:
            genre_hours["其他流派"] = unknown_hours

        top5 = sorted(genre_hours.items(), key=lambda x: x[1], reverse=True)[:5]
        total_m = sum(h for _, h in top5) or 1
        monthly.append(
            {
                "month": m,
                "genres": {g: round(h / total_m * 100, 1) for g, h in top5},
            }
        )
    return monthly


# ═══════════════════════════════════════════════════════════════════════════════
# 4b. Music Map — genre-based region inference
# ═══════════════════════════════════════════════════════════════════════════════

# Genre → (language, region, flag) — mirrors frontend/src/lib/genre-regions.ts
GENRE_REGION_MAP = {
    "mandopop": ("chinese", "中国", "🇨🇳"),
    "cantopop": ("chinese", "中国香港", "🇭🇰"),
    "c-pop": ("chinese", "中国", "🇨🇳"),
    "chinese": ("chinese", "中国", "🇨🇳"),
    "taiwan": ("chinese", "中国台湾", "🇹🇼"),
    "taiwan pop": ("chinese", "中国台湾", "🇹🇼"),
    "singaporean": ("chinese", "新加坡", "🇸🇬"),
    "k-pop": ("korean", "韩国", "🇰🇷"),
    "korean": ("korean", "韩国", "🇰🇷"),
    "k-rap": ("korean", "韩国", "🇰🇷"),
    "k-indie": ("korean", "韩国", "🇰🇷"),
    "k-r&b": ("korean", "韩国", "🇰🇷"),
    "k-ballad": ("korean", "韩国", "🇰🇷"),
    "j-pop": ("japanese", "日本", "🇯🇵"),
    "japanese": ("japanese", "日本", "🇯🇵"),
    "j-rock": ("japanese", "日本", "🇯🇵"),
    "j-indie": ("japanese", "日本", "🇯🇵"),
    "j-rap": ("japanese", "日本", "🇯🇵"),
    "anime": ("japanese", "日本", "🇯🇵"),
    "anison": ("japanese", "日本", "🇯🇵"),
    "vocaloid": ("japanese", "日本", "🇯🇵"),
    "pop": ("english", "全球", "🌍"),
    "dance pop": ("english", "全球", "🌍"),
    "art pop": ("english", "全球", "🌍"),
    "synth-pop": ("english", "全球", "🌍"),
    "electropop": ("english", "全球", "🌍"),
    "dream pop": ("english", "全球", "🌍"),
    "chamber pop": ("english", "全球", "🌍"),
    "bedroom pop": ("english", "全球", "🌍"),
    "alt-pop": ("english", "全球", "🌍"),
    "hyperpop": ("english", "全球", "🌍"),
    "rock": ("english", "全球", "🌍"),
    "classic rock": ("english", "全球", "🌍"),
    "hard rock": ("english", "全球", "🌍"),
    "soft rock": ("english", "全球", "🌍"),
    "pop rock": ("english", "全球", "🌍"),
    "indie rock": ("english", "全球", "🌍"),
    "alt-rock": ("english", "全球", "🌍"),
    "psychedelic rock": ("english", "全球", "🌍"),
    "garage rock": ("english", "全球", "🌍"),
    "post-rock": ("english", "全球", "🌍"),
    "hip hop": ("english", "美国", "🇺🇸"),
    "rap": ("english", "美国", "🇺🇸"),
    "trap": ("english", "美国", "🇺🇸"),
    "drill": ("english", "美国", "🇺🇸"),
    "boom bap": ("english", "美国", "🇺🇸"),
    "conscious hip hop": ("english", "美国", "🇺🇸"),
    "gangsta rap": ("english", "美国", "🇺🇸"),
    "southern hip hop": ("english", "美国", "🇺🇸"),
    "east coast hip hop": ("english", "美国", "🇺🇸"),
    "west coast hip hop": ("english", "美国", "🇺🇸"),
    "r&b": ("english", "美国", "🇺🇸"),
    "contemporary r&b": ("english", "美国", "🇺🇸"),
    "neo soul": ("english", "美国", "🇺🇸"),
    "alternative r&b": ("english", "美国", "🇺🇸"),
    "edm": ("english", "全球", "🌍"),
    "electronic": ("english", "全球", "🌍"),
    "house": ("english", "全球", "🌍"),
    "deep house": ("english", "全球", "🌍"),
    "techno": ("english", "全球", "🌍"),
    "trance": ("english", "全球", "🌍"),
    "dubstep": ("english", "全球", "🌍"),
    "ambient": ("english", "全球", "🌍"),
    "downtempo": ("english", "全球", "🌍"),
    "idm": ("english", "全球", "🌍"),
    "latin": ("other", "拉美", "🌎"),
    "reggaeton": ("other", "拉美", "🌎"),
    "latin pop": ("other", "拉美", "🌎"),
    "latin rock": ("other", "拉美", "🌎"),
    "latin hip hop": ("other", "拉美", "🌎"),
    "salsa": ("other", "拉美", "🌎"),
    "bachata": ("other", "拉美", "🌎"),
    "dembow": ("other", "拉美", "🌎"),
    "bossa nova": ("other", "巴西", "🇧🇷"),
    "samba": ("other", "巴西", "🇧🇷"),
    "mpb": ("other", "巴西", "🇧🇷"),
    "indie": ("english", "全球", "🌍"),
    "indie pop": ("english", "全球", "🌍"),
    "indie folk": ("english", "全球", "🌍"),
    "indie soul": ("english", "全球", "🌍"),
    "folk": ("english", "全球", "🌍"),
    "folk rock": ("english", "全球", "🌍"),
    "neo-folk": ("english", "全球", "🌍"),
    "classical": ("instrumental", "全球", "🎼"),
    "orchestral": ("instrumental", "全球", "🎼"),
    "opera": ("instrumental", "全球", "🎼"),
    "baroque": ("instrumental", "全球", "🎼"),
    "instrumental": ("instrumental", "全球", "🎼"),
    "lo-fi": ("instrumental", "全球", "🎼"),
    "post-rock instrumental": ("instrumental", "全球", "🎼"),
    "jazz": ("instrumental", "美国", "🇺🇸"),
    "bebop": ("instrumental", "美国", "🇺🇸"),
    "cool jazz": ("instrumental", "美国", "🇺🇸"),
    "fusion": ("instrumental", "美国", "🇺🇸"),
    "smooth jazz": ("instrumental", "美国", "🇺🇸"),
    "acid jazz": ("instrumental", "美国", "🇺🇸"),
    "soul": ("english", "美国", "🇺🇸"),
    "funk": ("english", "美国", "🇺🇸"),
    "motown": ("english", "美国", "🇺🇸"),
    "disco": ("english", "美国", "🇺🇸"),
    "country": ("english", "美国", "🇺🇸"),
    "country pop": ("english", "美国", "🇺🇸"),
    "country rock": ("english", "美国", "🇺🇸"),
    "outlaw country": ("english", "美国", "🇺🇸"),
    "alt-country": ("english", "美国", "🇺🇸"),
    "americana": ("english", "美国", "🇺🇸"),
    "bluegrass": ("english", "美国", "🇺🇸"),
    "metal": ("english", "全球", "🌍"),
    "heavy metal": ("english", "全球", "🌍"),
    "death metal": ("english", "全球", "🌍"),
    "black metal": ("english", "全球", "🌍"),
    "thrash metal": ("english", "全球", "🌍"),
    "power metal": ("english", "全球", "🌍"),
    "doom metal": ("english", "全球", "🌍"),
    "progressive metal": ("english", "全球", "🌍"),
    "nu metal": ("english", "全球", "🌍"),
    "metalcore": ("english", "全球", "🌍"),
    "punk": ("english", "全球", "🌍"),
    "pop punk": ("english", "全球", "🌍"),
    "hardcore punk": ("english", "全球", "🌍"),
    "emo": ("english", "全球", "🌍"),
    "post-punk": ("english", "全球", "🌍"),
    "alternative": ("english", "全球", "🌍"),
    "grunge": ("english", "美国", "🇺🇸"),
    "shoegaze": ("english", "全球", "🌍"),
    "new wave": ("english", "全球", "🌍"),
    "post-punk revival": ("english", "全球", "🌍"),
    "britpop": ("english", "英国", "🇬🇧"),
    "uk garage": ("english", "英国", "🇬🇧"),
    "grime": ("english", "英国", "🇬🇧"),
    "drum and bass": ("english", "英国", "🇬🇧"),
    "dub": ("english", "英国", "🇬🇧"),
    "reggae": ("other", "牙买加", "🇯🇲"),
    "dancehall": ("other", "牙买加", "🇯🇲"),
    "ska": ("other", "牙买加", "🇯🇲"),
    "afrobeats": ("other", "非洲", "🌍"),
    "afrobeat": ("other", "非洲", "🌍"),
    "afropop": ("other", "非洲", "🌍"),
    "highlife": ("other", "非洲", "🌍"),
    "gospel": ("english", "美国", "🇺🇸"),
    "christian": ("english", "全球", "🌍"),
    "worship": ("english", "全球", "🌍"),
    "blues": ("english", "美国", "🇺🇸"),
    "delta blues": ("english", "美国", "🇺🇸"),
    "chicago blues": ("english", "美国", "🇺🇸"),
    "french": ("other", "法国", "🇫🇷"),
    "chanson": ("other", "法国", "🇫🇷"),
    "french pop": ("other", "法国", "🇫🇷"),
    "german": ("other", "德国", "🇩🇪"),
    "schlager": ("other", "德国", "🇩🇪"),
    "italian": ("other", "意大利", "🇮🇹"),
    "italo disco": ("other", "意大利", "🇮🇹"),
    "spanish": ("other", "西班牙", "🇪🇸"),
    "flamenco": ("other", "西班牙", "🇪🇸"),
    "indian": ("other", "印度", "🇮🇳"),
    "bollywood": ("other", "印度", "🇮🇳"),
    "bhangra": ("other", "印度", "🇮🇳"),
    "carnatic": ("other", "印度", "🇮🇳"),
    "arabic": ("other", "中东", "🌍"),
    "rai": ("other", "中东", "🌍"),
    "turkish": ("other", "土耳其", "🇹🇷"),
    "nordic": ("other", "北欧", "🌍"),
    "swedish": ("other", "瑞典", "🇸🇪"),
    "russian": ("other", "俄罗斯", "🇷🇺"),
    "world": ("other", "全球", "🌍"),
    "world fusion": ("other", "全球", "🌍"),
}
UNKNOWN_REGION = ("other", "未知", "🌍")


def _classify_genre_region(genre: str) -> tuple:
    key = genre.lower().strip()
    return GENRE_REGION_MAP.get(key, UNKNOWN_REGION)


def _build_music_map(conn, year_df, artist_agg) -> dict:
    artist_names = list(artist_agg.index)
    if not artist_names:
        return {"regions": [], "top_overseas_artists": []}

    placeholders = ",".join("?" * len(artist_names))
    rows = conn.execute(
        f"SELECT artist_name, genres FROM spotify_artist_meta "
        f"WHERE artist_name IN ({placeholders})",
        artist_names,
    ).fetchall()

    artist_genres: dict[str, list[str]] = {}
    for r in rows:
        genres_str = (r[1] or "").strip()
        if not genres_str:
            continue
        try:
            parsed = json.loads(genres_str)
            if isinstance(parsed, list):
                artist_genres[r[0]] = [g.strip() for g in parsed if g.strip()]
        except (json.JSONDecodeError, TypeError):
            artist_genres[r[0]] = [g.strip() for g in genres_str.split(",") if g.strip()]

    # Weighted region aggregation
    region_hours: dict[str, dict] = {}
    for artist_name, row in artist_agg.iterrows():
        hours = float(row["hours"])
        genres = artist_genres.get(artist_name, [])

        lang, region, flag = UNKNOWN_REGION
        if genres:
            for g in genres:
                lang, region, flag = _classify_genre_region(g)
                if region != "未知":
                    break

        if region not in region_hours:
            region_hours[region] = {"region": region, "flag": flag, "play_share": 0.0}
        region_hours[region]["play_share"] += hours

    total_h = sum(r["play_share"] for r in region_hours.values()) or 1
    regions = sorted(region_hours.values(), key=lambda x: x["play_share"], reverse=True)
    for r in regions:
        r["play_share"] = round(r["play_share"] / total_h * 100, 1)

    # Top overseas artists (non-Chinese)
    overseas_artists = []
    for artist_name, row in artist_agg.iterrows():
        genres = artist_genres.get(artist_name, [])
        is_chinese = False
        for g in genres:
            lang, _, _ = _classify_genre_region(g)
            if lang == "chinese":
                is_chinese = True
                break
        if not is_chinese and genres:
            overseas_artists.append(
                {
                    "name": artist_name,
                    "region": _classify_genre_region(genres[0])[1],
                    "cover_url": _get_artist_cover(conn, artist_name),
                }
            )
        if len(overseas_artists) >= 5:
            break

    return {"regions": regions[:10], "top_overseas_artists": overseas_artists}


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Time Story
# ═══════════════════════════════════════════════════════════════════════════════


def _build_time_story(conn, year_df):
    # daily_grid: 12 rows x 31 columns
    daily_grid = _build_daily_grid(year_df)

    # monthly_pulse
    monthly_pulse_df = year_df.groupby("ts_month").agg(hours=("ms_played", _hour)).reset_index()
    month_hours = {
        int(r.ts_month): round(float(r.hours), 1) for r in monthly_pulse_df.itertuples(index=False)
    }
    monthly_pulse = [
        {"month": month, "hours": month_hours.get(month, 0.0)} for month in range(1, 13)
    ]

    # hourly_dist
    hourly = year_df.groupby("ts_hour").size().reset_index(name="plays")
    hour_plays = {
        int(r.ts_hour): int(r.plays) for r in hourly.sort_values("ts_hour").itertuples(index=False)
    }
    hourly_dist = [{"hour": hour, "plays": hour_plays.get(hour, 0)} for hour in range(24)]

    # late_night
    late_night_info = _build_late_night(conn, year_df)

    return {
        "daily_grid": daily_grid,
        "monthly_pulse": monthly_pulse,
        "hourly_dist": hourly_dist,
        "late_night": late_night_info,
    }


def _build_daily_grid(year_df) -> list[list[int]]:
    """12 rows (months) x 31 columns (days) grid of play counts."""
    try:
        year_df = year_df.copy()
        year_df["_day"] = year_df["ts_date"].astype(str).str[-2:].astype(int)
        daily_grouped = year_df.groupby(["ts_month", "_day"]).size()
    except (ValueError, KeyError):
        return [[0] * 31 for _ in range(12)]

    daily_grid = []
    for m in range(1, 13):
        row = [0] * 31
        for (month, day), count in daily_grouped.items():
            if month == m and 1 <= day <= 31:
                row[day - 1] = int(count)
        daily_grid.append(row)
    return daily_grid


def _build_late_night(conn, year_df) -> dict:
    """Late night (0-5 AM) listening info."""
    night_mask = year_df["ts_hour"].between(0, 5)
    night_df = year_df[night_mask]

    if night_df.empty:
        return {"ratio": 0.0, "top_tracks": []}

    ratio = round(len(night_df) / max(len(year_df), 1) * 100, 1)

    # Top 3 tracks during late night
    night_tracks = (
        night_df.groupby(["track_name", "artist_name", "track_id"])
        .agg(plays=("play_id", "count"))
        .sort_values("plays", ascending=False)
        .head(3)
        .reset_index()
    )
    top_tracks = []
    for _, r in night_tracks.iterrows():
        name = r["track_name"] if pd.notna(r["track_name"]) else ""
        art = r["artist_name"] if pd.notna(r["artist_name"]) else ""
        top_tracks.append(
            {
                "track_id": int(r["track_id"]),
                "name": name,
                "artist_name": art,
                "plays": int(r["plays"]),
                "cover_url": _get_track_cover(conn, name, art),
            }
        )

    return {"ratio": ratio, "top_tracks": top_tracks}


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Discovery & Returns
# ═══════════════════════════════════════════════════════════════════════════════


def _build_discovery_returns(conn, df, year_df, year):
    all_previous_df = df[df["ts_year"] < year]
    previous_artists = set(all_previous_df["artist_name"].dropna().unique())

    # new_artists: first heard this year
    new_artists = _build_new_artists(conn, year_df, previous_artists)

    # returning_tracks: tracks released >5 years ago that got heavy play this year
    returning_tracks = _build_returning_tracks(conn, year_df, year)

    # longest_love: max date span for a single track
    longest_love = _build_longest_love(conn, df, year_df, year)

    return {
        "new_artists": new_artists,
        "returning_tracks": returning_tracks,
        "longest_love": longest_love,
    }


def _build_new_artists(conn, year_df, previous_artists: set) -> list[dict]:
    year_artists = (
        year_df.groupby("artist_name")
        .agg(plays=("play_id", "count"), first_date=("ts_date", "min"))
        .reset_index()
    )
    new_mask = ~year_artists["artist_name"].isin(previous_artists)
    new = year_artists[new_mask].sort_values("plays", ascending=False).head(3)

    results = []
    for _, r in new.iterrows():
        name = r["artist_name"]
        results.append(
            {
                "name": name,
                "plays": int(r["plays"]),
                "first_date": str(r["first_date"]),
                "cover_url": _get_artist_cover(conn, name),
            }
        )
    return results


def _build_returning_tracks(conn, year_df, year: int) -> list[dict]:
    """Tracks released >5 years before the target year, ranked by this year's plays."""
    # All (track_name, artist_name) played this year
    pairs = list(year_df[["track_name", "artist_name"]].drop_duplicates().itertuples(index=False))
    pairs = [(t, a) for t, a in pairs if pd.notna(t) and pd.notna(a)]
    if not pairs:
        return []

    release_year_map = _fetch_track_release_years(conn, pairs)
    if not release_year_map:
        return []

    cutoff = year - 5
    # Identify returning tracks
    returning_pairs = set()
    for (t_name, a_name), rel_year in release_year_map.items():
        if rel_year <= cutoff:
            returning_pairs.add((t_name, a_name))

    if not returning_pairs:
        return []

    # Count plays for these tracks this year
    track_plays = {}
    for _, row in year_df.iterrows():
        key = (row["track_name"], row["artist_name"])
        if key in returning_pairs:
            track_plays[key] = track_plays.get(key, 0) + 1

    # Build track_id lookup for the returning pairs
    track_id_map = (
        year_df[["track_name", "artist_name", "track_id"]]
        .drop_duplicates(subset=["track_name", "artist_name"])
        .set_index(["track_name", "artist_name"])["track_id"]
        .to_dict()
    )

    top5 = sorted(track_plays.items(), key=lambda x: x[1], reverse=True)[:5]
    results = []
    for (t_name, a_name), plays in top5:
        results.append(
            {
                "track_id": int(track_id_map.get((t_name, a_name), 0)),
                "name": t_name,
                "artist_name": a_name,
                "plays": plays,
                "release_year": release_year_map.get((t_name, a_name), 0),
                "cover_url": _get_track_cover(conn, t_name, a_name),
            }
        )
    return results


def _build_longest_love(conn, df, year_df, year) -> dict | None:
    """Find the track with the longest span between first and last appearance."""
    year_pairs = set(
        year_df[["track_name", "artist_name"]].dropna().itertuples(index=False, name=None)
    )
    if not year_pairs:
        return None

    # Consider the all-time span, but only for tracks heard in the target year.
    df_with_dates = df[["track_name", "artist_name", "ts_date"]].dropna()
    df_with_dates = df_with_dates[
        df_with_dates[["track_name", "artist_name"]].apply(tuple, axis=1).isin(year_pairs)
    ]
    if df_with_dates.empty:
        return None

    spans = (
        df_with_dates.groupby(["track_name", "artist_name"])
        .agg(first=("ts_date", "min"), last=("ts_date", "max"))
        .reset_index()
    )
    spans["span_days"] = (pd.to_datetime(spans["last"]) - pd.to_datetime(spans["first"])).dt.days

    best = spans.loc[spans["span_days"].idxmax()]
    name = best["track_name"]
    art = best["artist_name"]

    # Look up track_id for this track
    track_id_match = year_df[(year_df["track_name"] == name) & (year_df["artist_name"] == art)]
    track_id = int(track_id_match["track_id"].iloc[0]) if not track_id_match.empty else 0

    return {
        "track_id": track_id,
        "name": name,
        "artist_name": art,
        "span_days": int(best["span_days"]),
        "cover_url": _get_track_cover(conn, name, art),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Listening Depth
# ═══════════════════════════════════════════════════════════════════════════════


def _build_listening_depth(conn, year_df, track_agg, year):
    # listening_age
    listening_age = _calc_listening_age(conn, track_agg, year)

    # album_completion
    album_completion = _calc_album_completion(conn, year_df)

    # deep_listen_ratio: plays with >= 3 min of ms_played
    deep_mask = year_df["ms_played"] >= 180_000
    deep_listen_ratio = round(deep_mask.sum() / max(len(year_df), 1) * 100, 1)

    return {
        "listening_age": listening_age,
        "album_completion": album_completion,
        "deep_listen_ratio": deep_listen_ratio,
    }


def _calc_listening_age(conn, track_agg, year: int) -> dict | None:
    """Average release year of top tracks → listening age."""
    if track_agg.empty:
        return None

    # Top 50 tracks by plays
    top_tracks = track_agg.head(50)
    pairs = [
        (r.track_name, r.artist_name)
        for r in top_tracks.itertuples(index=False)
        if pd.notna(r.track_name) and pd.notna(r.artist_name)
    ]
    if not pairs:
        return None

    release_year_map = _fetch_track_release_years(conn, pairs)
    if not release_year_map:
        return None

    release_years = []
    for _, r in top_tracks.iterrows():
        ry = release_year_map.get((r["track_name"], r["artist_name"]))
        if ry is not None:
            release_years.append(ry)

    if not release_years:
        return None

    avg_release_year = int(round(sum(release_years) / len(release_years)))
    age = max(year - avg_release_year, 0)

    if age <= 5:
        desc = "你的耳朵追逐新潮，最爱的大部分都是近几年的新曲。"
    elif age <= 15:
        desc = "你有一双发现经典的耳朵，珍藏了不少世代佳作。"
    elif age <= 30:
        desc = "你的音乐品味跨越了多个年代，是真正的深度听众。"
    else:
        desc = "你是音乐考古学家——风格比时代更永恒。"

    return {
        "age": age,
        "avg_release_year": avg_release_year,
        "description": desc,
    }


def _calc_album_completion(conn, year_df) -> list[dict]:
    """Top 3 albums by completion rate (using spotify_album_id, min 50%)."""
    track_ids = year_df["track_id"].dropna().unique().tolist()
    if not track_ids:
        return []

    placeholders = ",".join("?" * len(track_ids))
    rows = conn.execute(
        f"""
        SELECT t.track_id, sam.spotify_album_id, sam.album_name,
               sam.total_tracks, sam.image_url
        FROM tracks t
        JOIN spotify_track_meta stm
          ON REPLACE(t.spotify_track_uri, 'spotify:track:', '') = stm.spotify_track_id
        JOIN spotify_album_meta sam ON stm.spotify_album_id = sam.spotify_album_id
        WHERE t.track_id IN ({placeholders})
          AND sam.total_tracks IS NOT NULL AND sam.total_tracks > 2
    """,
        track_ids,
    ).fetchall()

    if not rows:
        return []

    # Group by spotify_album_id
    album_tracks: dict[str, set] = {}
    album_info: dict[str, dict] = {}
    for r in rows:
        tid, aid, aname, ttotal, img = r
        if aid not in album_tracks:
            album_tracks[aid] = set()
            album_info[aid] = {
                "album_name": aname,
                "total_tracks": int(ttotal),
                "image_url": img or "",
            }
        album_tracks[aid].add(tid)

    completions = []
    for aid, tracks in album_tracks.items():
        info = album_info[aid]
        pct = min(round(len(tracks) / info["total_tracks"] * 100, 1), 100.0)
        if pct >= 50:
            artist_series = year_df[year_df["track_id"].isin(tracks)]["artist_name"].mode()
            art = artist_series.iloc[0] if not artist_series.empty else ""
            completions.append(
                {
                    "name": info["album_name"],
                    "artist_name": art if pd.notna(art) else "",
                    "completion_pct": pct,
                    "cover_url": info["image_url"],
                }
            )

    completions.sort(key=lambda x: x["completion_pct"], reverse=True)
    return completions[:3]


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Special Moments
# ═══════════════════════════════════════════════════════════════════════════════


def _build_special_moments(conn, year_df) -> dict:
    # most_active_day
    most_active_day = _find_most_active_day(conn, year_df)

    # earliest_listen
    earliest_listen = _find_edge_listen(conn, year_df, "min")

    # latest_listen
    latest_listen = _find_edge_listen(conn, year_df, "max")

    # longest_streak
    longest_streak = _find_longest_streak(year_df)

    return {
        "most_active_day": most_active_day,
        "earliest_listen": earliest_listen,
        "latest_listen": latest_listen,
        "longest_streak": longest_streak,
    }


def _find_most_active_day(conn, year_df) -> dict | None:
    daily = year_df.groupby("ts_date").size().reset_index(name="plays")
    if daily.empty:
        return None
    best = daily.loc[daily["plays"].idxmax()]
    date_str = str(best["ts_date"])
    # Find the top track for that day
    day_df = year_df[year_df["ts_date"] == best["ts_date"]]
    top_track_row = None
    if not day_df.empty:
        tt = day_df.groupby(["track_name", "artist_name"]).size().sort_values(ascending=False)
        if not tt.empty:
            name = tt.index[0][0]
            artist = tt.index[0][1]
            top_track_row = {
                "name": name,
                "artist_name": artist,
                "plays": int(tt.iloc[0]),
                "cover_url": _get_track_cover(conn, name, artist),
            }

    return {
        "date": date_str,
        "plays": int(best["plays"]),
        "top_track": top_track_row or {},
    }


def _find_edge_listen(conn, year_df, mode: str = "min") -> dict | None:
    """Earliest (min hour) or latest (max hour) listen of the year."""
    idx = year_df["ts_hour"].idxmin() if mode == "min" else year_df["ts_hour"].idxmax()
    row = year_df.loc[idx]
    hour = int(row["ts_hour"])
    track_name = row["track_name"] if pd.notna(row["track_name"]) else ""
    artist_name = row["artist_name"] if pd.notna(row["artist_name"]) else ""
    return {
        "hour": hour,
        "track": {
            "name": track_name,
            "artist_name": artist_name,
            "date": str(row["ts_date"]),
            "cover_url": _get_track_cover(conn, track_name, artist_name),
        },
    }


def _find_longest_streak(year_df) -> dict | None:
    """Longest consecutive-day listening streak."""
    dates = sorted(pd.to_datetime(year_df["ts_date"].unique()))
    if len(dates) < 1:
        return None

    max_streak = 1
    curr_streak = 1
    max_start = dates[0]
    max_end = dates[0]
    curr_start = dates[0]

    for i in range(1, len(dates)):
        if (dates[i] - dates[i - 1]).days == 1:
            curr_streak += 1
            if curr_streak > max_streak:
                max_streak = curr_streak
                max_start = curr_start
                max_end = dates[i]
        else:
            curr_streak = 1
            curr_start = dates[i]

    return {
        "days": max_streak,
        "start": max_start.strftime("%Y-%m-%d"),
        "end": max_end.strftime("%Y-%m-%d"),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Monthly Drilldown
# ═══════════════════════════════════════════════════════════════════════════════


def _build_monthly_drilldown(conn, year_df) -> list[dict]:
    """Per-month breakdown: total_hours + top 3 tracks + top 1 artist."""
    months = []
    for m in range(1, 13):
        month_df = year_df[year_df["ts_month"] == m]
        if month_df.empty:
            months.append(
                {
                    "month": m,
                    "total_hours": 0.0,
                    "top_tracks": [],
                    "top_artist": None,
                }
            )
            continue

        total_hours = round(float(month_df["ms_played"].sum() / 3_600_000), 1)

        # Top 3 tracks
        top_tracks_df = (
            month_df.groupby(["track_name", "artist_name", "track_id"])
            .agg(plays=("play_id", "count"))
            .sort_values("plays", ascending=False)
            .head(3)
            .reset_index()
        )
        top_tracks = []
        for _, r in top_tracks_df.iterrows():
            t_name = r["track_name"] if pd.notna(r["track_name"]) else ""
            a_name = r["artist_name"] if pd.notna(r["artist_name"]) else ""
            top_tracks.append(
                {
                    "track_id": int(r["track_id"]),
                    "name": t_name,
                    "artist_name": a_name,
                    "plays": int(r["plays"]),
                    "cover_url": _get_track_cover(conn, t_name, a_name),
                }
            )

        # Top 1 artist
        top_artist_name = (
            month_df.groupby("artist_name").size().sort_values(ascending=False).index[0]
        )
        top_artist = (
            {
                "name": top_artist_name,
                "cover_url": _get_artist_cover(conn, top_artist_name),
            }
            if top_artist_name
            else None
        )

        months.append(
            {
                "month": m,
                "total_hours": total_hours,
                "top_tracks": top_tracks,
                "top_artist": top_artist,
            }
        )
    return months


# ═══════════════════════════════════════════════════════════════════════════════
# 11. Comparison
# ═══════════════════════════════════════════════════════════════════════════════


def _build_comparison(df, year_df, year, track_agg, artist_agg):
    # last_year comparison
    last_year_df = df[df["ts_year"] == year - 1]
    last_year_cmp = None
    if not last_year_df.empty:
        this_hours = _hour(year_df["ms_played"])
        last_hours = _hour(last_year_df["ms_played"])
        this_plays = len(year_df)
        last_plays = len(last_year_df)
        this_artists = year_df["artist_name"].dropna().nunique()
        last_artists = last_year_df["artist_name"].dropna().nunique()
        this_tracks = year_df["track_id"].nunique()
        last_tracks = last_year_df["track_id"].nunique()

        def _pct_change(new_val, old_val) -> float | None:
            if old_val == 0:
                return None
            return round((new_val - old_val) / old_val * 100, 1)

        this_days = year_df["ts_date"].nunique()
        last_days = last_year_df["ts_date"].nunique()

        last_year_cmp = {
            "total_hours_change": _pct_change(this_hours, last_hours),
            "plays_change": _pct_change(this_plays, last_plays),
            "tracks_change": _pct_change(this_tracks, last_tracks),
            "artists_change": _pct_change(this_artists, last_artists),
            "active_days_change": _pct_change(this_days, last_days),
        }

    # top_vs_alltime: compare year's top 5 against all-time top 10
    alltime_tracks_df = (
        df.groupby(["track_name", "artist_name"]).size().sort_values(ascending=False).head(10)
    )
    alltime_artists_df = df.groupby("artist_name").size().sort_values(ascending=False).head(10)

    alltime_track_set = set(alltime_tracks_df.index.tolist())
    alltime_artist_set = set(alltime_artists_df.index.tolist())

    track_marks = []
    for _, r in track_agg.head(5).iterrows():
        key = (r["track_name"], r["artist_name"])
        track_marks.append(
            {
                "name": f"{r['track_name']} - {r['artist_name']}",
                "is_new": key not in alltime_track_set,
                "is_classic": key in alltime_track_set,
            }
        )

    artist_marks = []
    for artist_name in artist_agg.head(5).index:
        artist_marks.append(
            {
                "name": artist_name,
                "is_new": artist_name not in alltime_artist_set,
                "is_classic": artist_name in alltime_artist_set,
            }
        )

    return {
        "last_year": last_year_cmp,
        "top_vs_alltime": {
            "tracks": track_marks,
            "artists": artist_marks,
        },
    }
