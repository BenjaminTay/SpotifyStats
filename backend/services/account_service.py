"""Account center services — cross-analysis of saved tracks × play history."""
import sqlite3
from collections import Counter


def get_collection_insights(conn: sqlite3.Connection) -> dict:
    """返回收藏×播放交叉分析的所有洞察数据。"""

    cur = conn.execute("SELECT COUNT(*) FROM saved_tracks")
    saved_count = cur.fetchone()[0]
    if saved_count == 0:
        return {"available": False, "empty": True}

    # --- 1. 收藏人格 (Collection Personality) ---
    cur = conn.execute("""
        WITH save_play_stats AS (
            SELECT
                st.track_name, st.artist_name, st.added_date,
                COUNT(CASE WHEN p.ts_date < st.added_date THEN 1 END) as plays_before_save,
                COUNT(CASE WHEN p.ts_date >= st.added_date THEN 1 END) as plays_after_save,
                COUNT(*) as total_plays
            FROM saved_tracks st
            LEFT JOIN tracks t ON st.track_uri = t.spotify_track_uri
            LEFT JOIN plays p ON p.track_id = t.track_id
            WHERE st.added_date IS NOT NULL AND st.added_date != ''
            GROUP BY st.track_name, st.artist_name
        )
        SELECT
            AVG(plays_before_save) as avg_before,
            AVG(plays_after_save) as avg_after,
            COUNT(CASE WHEN plays_after_save > 0 THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0) as retention_pct,
            COUNT(CASE WHEN plays_before_save <= 3 THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0) as impulsive_pct
        FROM save_play_stats
    """)
    row = cur.fetchone()
    avg_before = row[0] or 0
    retention_pct = row[2] or 0
    impulsive_pct = row[3] or 0

    # 人格判定
    if avg_before >= 10 and retention_pct >= 80:
        personality = {"type": "深海淘金者", "icon": "⛏️", "description": "你不会轻易收藏，平均听完多次后才按下那颗 ❤️。但一旦收藏，就几乎不再放手。"}
    elif avg_before <= 3 and retention_pct >= 70:
        personality = {"type": "冲动收藏家", "icon": "⚡", "description": "你相信第一感觉—绝大多数收藏都在 3 次播放内完成。"}
    elif avg_before >= 8 and saved_count < 500:
        personality = {"type": "精挑细选者", "icon": "💎", "description": "你的收藏夹小而精，每首歌都经过深思熟虑。"}
    else:
        personality = {"type": "均衡型收藏者", "icon": "🎵", "description": "你的收藏习惯介于冲动和谨慎之间，既有直觉选择也有深思熟虑。"}

    personality["metrics"] = {
        "avg_plays_before_save": round(avg_before, 1),
        "retention_pct": round(retention_pct, 1),
        "impulsive_pct": round(impulsive_pct, 1),
    }

    # --- 2. 收藏纵览 ---
    cur = conn.execute("SELECT COUNT(*) FROM saved_albums")
    saved_albums = cur.fetchone()[0]
    cur = conn.execute("SELECT COUNT(*) FROM saved_artists")
    saved_artists = cur.fetchone()[0]
    cur = conn.execute("SELECT COUNT(*) FROM playlists")
    playlist_count = cur.fetchone()[0]

    cur = conn.execute("""
        SELECT SUBSTR(added_date, 1, 4) as yr, COUNT(*) as cnt
        FROM saved_tracks WHERE added_date IS NOT NULL AND added_date != ''
        GROUP BY yr ORDER BY yr
    """)
    save_timeline = [{"year": int(r[0]), "count": r[1]} for r in cur.fetchall()]

    cur = conn.execute("""
        SELECT added_date, COUNT(*) as cnt FROM saved_tracks
        WHERE added_date IS NOT NULL AND added_date != ''
        GROUP BY added_date ORDER BY cnt DESC LIMIT 1
    """)
    max_save_day = cur.fetchone()
    biggest_save_day = {"date": max_save_day[0], "count": max_save_day[1]} if max_save_day else None

    cur = conn.execute("SELECT MIN(added_date), MAX(added_date) FROM saved_tracks WHERE added_date IS NOT NULL AND added_date != ''")
    first_last = cur.fetchone()

    overview = {
        "saved_tracks": saved_count,
        "saved_albums": saved_albums,
        "saved_artists": saved_artists,
        "playlists": playlist_count,
        "save_timeline": save_timeline,
        "biggest_save_day": biggest_save_day,
        "first_save_date": first_last[0],
        "last_save_date": first_last[1],
    }

    # --- 3. 第一首收藏的故事 ---
    cur = conn.execute("""
        SELECT st.track_name, st.artist_name, st.added_date,
               COUNT(p.play_id) as total_plays,
               CAST(julianday('now') - julianday(st.added_date) AS INTEGER) as days_since
        FROM saved_tracks st
        LEFT JOIN tracks t ON st.track_uri = t.spotify_track_uri
        LEFT JOIN plays p ON p.track_id = t.track_id
        WHERE st.added_date IS NOT NULL AND st.added_date != ''
        GROUP BY st.track_name, st.artist_name
        ORDER BY st.added_date ASC LIMIT 1
    """)
    row = cur.fetchone()
    first_save_story = None
    if row:
        days = row[4] or 0
        plays = row[3] or 0
        interval = round(days / max(plays, 1), 1)
        first_save_story = {
            "track_name": row[0], "artist_name": row[1],
            "save_date": row[2], "total_plays": plays,
            "days_since": days, "avg_interval_days": interval,
        }

    # --- 4. 收藏生命周期 ---
    cur = conn.execute("""
        WITH save_week_stats AS (
            SELECT
                st.track_name, st.artist_name, st.added_date,
                COUNT(CASE WHEN p.ts_date >= st.added_date AND p.ts_date < date(st.added_date, '+7 days') THEN 1 END) as wk1,
                COUNT(CASE WHEN p.ts_date >= date(st.added_date, '+30 days') AND p.ts_date < date(st.added_date, '+90 days') THEN 1 END) as mo1_3,
                COUNT(CASE WHEN p.ts_date >= date(st.added_date, '+90 days') AND p.ts_date < date(st.added_date, '+365 days') THEN 1 END) as mo3_12,
                COUNT(CASE WHEN p.ts_date >= date(st.added_date, '+365 days') THEN 1 END) as after_1yr
            FROM saved_tracks st
            LEFT JOIN tracks t ON st.track_uri = t.spotify_track_uri
            LEFT JOIN plays p ON p.track_id = t.track_id
            WHERE st.added_date IS NOT NULL AND st.added_date != ''
            GROUP BY st.track_name, st.artist_name
        )
        SELECT
            ROUND(AVG(wk1), 1) as avg_honeymoon,
            ROUND(AVG(mo1_3 * 1.0 / 8), 1) as avg_cooling,
            ROUND(AVG(mo3_12 * 1.0 / 39), 1) as avg_settling,
            COUNT(CASE WHEN after_1yr > 0 THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0) as evergreen_pct,
            COUNT(CASE WHEN after_1yr = 0 AND (mo3_12 > 0 OR mo1_3 > 0) THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0) as occasional_pct,
            COUNT(CASE WHEN after_1yr = 0 AND mo3_12 = 0 AND mo1_3 = 0 AND wk1 = 0 THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0) as forgotten_pct
        FROM save_week_stats
    """)
    row = cur.fetchone()
    lifecycle = {
        "honeymoon": {"label": "蜜月期", "weeks": "0-1", "avg_per_week": row[0] or 0},
        "cooling": {"label": "冷却期", "weeks": "1-12", "avg_per_week": row[1] or 0},
        "settling": {"label": "沉淀期", "weeks": "12-52", "avg_per_week": row[2] or 0},
        "fate": {"evergreen_pct": round(row[3] or 0, 1), "occasional_pct": round(row[4] or 0, 1), "forgotten_pct": round(row[5] or 0, 1)},
    }

    # --- 5. 收藏×播放 化学反应（6 种类型） ---
    cur = conn.execute("""
        WITH stats AS (
            SELECT
                st.track_name, st.artist_name, st.added_date,
                COUNT(CASE WHEN p.ts_date < st.added_date THEN 1 END) as before_save,
                COUNT(CASE WHEN p.ts_date >= st.added_date AND p.ts_date < date(st.added_date, '+7 days') THEN 1 END) as first_week,
                COUNT(CASE WHEN p.ts_date >= st.added_date AND p.ts_date < date(st.added_date, '+180 days') THEN 1 END) as first_6mo,
                COUNT(CASE WHEN p.ts_date >= date(st.added_date, '+180 days') THEN 1 END) as after_6mo,
                MAX(p.ts_date) as last_play,
                COUNT(*) as total_plays
            FROM saved_tracks st
            LEFT JOIN tracks t ON st.track_uri = t.spotify_track_uri
            LEFT JOIN plays p ON p.track_id = t.track_id
            WHERE st.added_date IS NOT NULL AND st.added_date != ''
            GROUP BY st.track_name, st.artist_name
        )
        SELECT
            COUNT(CASE WHEN before_save <= 3 THEN 1 END) as love_at_first,
            COUNT(CASE WHEN before_save >= 20 THEN 1 END) as slow_burn,
            COUNT(CASE WHEN first_week >= 10 AND (last_play < date('now', '-90 days') OR last_play IS NULL) THEN 1 END) as flash_pan,
            COUNT(CASE WHEN after_6mo > first_6mo * 2 AND first_6mo > 0 THEN 1 END) as late_bloomer,
            COUNT(CASE WHEN before_save > 0 AND first_6mo > 0
                  AND ABS(1.0 * first_6mo / NULLIF(before_save, 0) - 1) < 0.5 THEN 1 END) as steady,
            COUNT(CASE WHEN total_plays <= 3 THEN 1 END) as shelf_sitter,
            COUNT(*) as total
        FROM stats
    """)
    row = cur.fetchone()
    total_with_dates = row[6]

    # Helper to fetch examples for each chemistry type
    def _fetch_examples(condition_sql, limit=3):
        cur = conn.execute(f"""
            WITH stats AS (
                SELECT st.track_name, st.artist_name, st.added_date,
                    COUNT(CASE WHEN p.ts_date < st.added_date THEN 1 END) as before_save,
                    COUNT(CASE WHEN p.ts_date >= st.added_date AND p.ts_date < date(st.added_date, '+7 days') THEN 1 END) as first_week,
                    COUNT(CASE WHEN p.ts_date >= st.added_date AND p.ts_date < date(st.added_date, '+180 days') THEN 1 END) as first_6mo,
                    COUNT(CASE WHEN p.ts_date >= date(st.added_date, '+180 days') THEN 1 END) as after_6mo,
                    MAX(p.ts_date) as last_play,
                    COUNT(*) as total_plays,
                    CAST(julianday('now') - julianday(MAX(p.ts_date)) AS INTEGER) as days_since_play
                FROM saved_tracks st
                LEFT JOIN tracks t ON st.track_uri = t.spotify_track_uri
                LEFT JOIN plays p ON p.track_id = t.track_id
                WHERE st.added_date IS NOT NULL AND st.added_date != ''
                GROUP BY st.track_name, st.artist_name
            )
            SELECT track_name, artist_name, total_plays, before_save, first_week, days_since_play
            FROM stats
            WHERE {condition_sql}
            ORDER BY total_plays DESC
            LIMIT {limit}
        """)
        return [{"track_name": r[0], "artist_name": r[1], "total_plays": r[2],
                 "before_save": r[3], "first_week": r[4], "days_since_play": r[5]} for r in cur.fetchall()]

    chemistry = {
        "love_at_first_listen": {
            "count": row[0] or 0, "label": "一见钟情",
            "description": "收藏时播放次数 ≤ 3", "icon": "💘",
            "examples": _fetch_examples("before_save <= 3"),
        },
        "slow_burn": {
            "count": row[1] or 0, "label": "慢热型",
            "description": "收藏时已播放 ≥ 20 次", "icon": "🔥",
            "examples": _fetch_examples("before_save >= 20"),
        },
        "flash_in_the_pan": {
            "count": row[2] or 0, "label": "昙花一现",
            "description": "收藏周播放 ≥ 10 次，现已 > 3 月未播", "icon": "🌠",
            "examples": _fetch_examples("first_week >= 10 AND (last_play < date('now', '-90 days') OR last_play IS NULL)"),
        },
        "late_bloomer": {
            "count": row[3] or 0, "label": "厚积薄发",
            "description": "收藏后 6 个月播放持续增长", "icon": "🌱",
            "examples": _fetch_examples("after_6mo > first_6mo * 2 AND first_6mo > 0"),
        },
        "steady_favorite": {
            "count": row[4] or 0, "label": "细水长流",
            "description": "收藏前后播放频率稳定", "icon": "💪",
            "examples": _fetch_examples("before_save > 0 AND first_6mo > 0 AND ABS(1.0 * first_6mo / NULLIF(before_save, 0) - 1) < 0.5"),
        },
        "shelf_sitter": {
            "count": row[5] or 0, "label": "收藏夹吃灰",
            "description": "收藏后总播放 ≤ 3 次", "icon": "📌",
            "examples": _fetch_examples("total_plays <= 3"),
        },
        "total_with_dates": total_with_dates,
    }

    # --- 6. Flip Side: 播放多但未收藏 ---
    cur = conn.execute("""
        SELECT p_agg.track_name, p_agg.artist_name, p_agg.play_count
        FROM (
            SELECT t.track_name, a.artist_name, COUNT(*) as play_count
            FROM plays p
            JOIN tracks t ON p.track_id = t.track_id
            JOIN artists a ON t.artist_id = a.artist_id
            WHERE p.track_id IS NOT NULL
            GROUP BY t.track_name, a.artist_name
            HAVING play_count >= 30
        ) p_agg
        LEFT JOIN saved_tracks st
            ON st.track_name = p_agg.track_name AND st.artist_name = p_agg.artist_name
        WHERE st.track_uri IS NULL
        ORDER BY p_agg.play_count DESC
        LIMIT 10
    """)
    flip_side = [{"track_name": r[0], "artist_name": r[1], "play_count": r[2]} for r in cur.fetchall()]

    # --- 7. 收藏关键词变迁 ---
    cur = conn.execute("""
        SELECT SUBSTR(added_date, 1, 4) as yr, GROUP_CONCAT(track_name, ' ') as all_names
        FROM saved_tracks
        WHERE added_date IS NOT NULL AND added_date != ''
        GROUP BY yr ORDER BY yr
    """)
    common_words = {"the", "a", "an", "is", "in", "of", "to", "and", "for", "on", "it", "remix", "feat", "mix", "edit", "version", "original", "radio", "live", "with", "you", "me", "my", "your", "no", "de", "la", "en", "el", "una", "que", "los", "las", "del", "con", "por", "para", "una", "como", "mas", "pero", "mis", "sus"}
    keyword_migration = {}
    for yr, names in cur.fetchall():
        words = names.lower().split()
        filtered = [w for w in words if len(w) > 2 and w not in common_words]
        top = [w for w, _ in Counter(filtered).most_common(8)]
        keyword_migration[yr] = top

    # --- 8. 双厨时刻 ---
    cur = conn.execute("""
        SELECT st1.artist_name as a1, st2.artist_name as a2, COUNT(*) as cnt
        FROM saved_tracks st1
        JOIN saved_tracks st2 ON st1.added_date = st2.added_date AND st1.artist_name < st2.artist_name
        WHERE st1.added_date IS NOT NULL AND st1.added_date != ''
        GROUP BY a1, a2
        ORDER BY cnt DESC
        LIMIT 10
    """)
    co_saved = [{"artist_a": r[0], "artist_b": r[1], "count": r[2]} for r in cur.fetchall()]

    # --- 9. 排行榜 ---
    cur = conn.execute("""
        SELECT st.artist_name, COUNT(*) as saved_cnt,
               COALESCE(SUM(p_stats.play_count), 0) as total_plays
        FROM saved_tracks st
        LEFT JOIN (
            SELECT t.track_name, a.artist_name, COUNT(*) as play_count
            FROM plays p JOIN tracks t ON p.track_id = t.track_id
            JOIN artists a ON t.artist_id = a.artist_id
            GROUP BY t.track_name, a.artist_name
        ) p_stats ON st.track_name = p_stats.track_name AND st.artist_name = p_stats.artist_name
        GROUP BY st.artist_name
        ORDER BY saved_cnt DESC
        LIMIT 15
    """)
    top_saved_artists = [{"artist_name": r[0], "saved_count": r[1], "total_plays": r[2]} for r in cur.fetchall()]

    # 错位榜
    over_saved = []
    under_saved = []
    for a in top_saved_artists:
        if a["saved_count"] >= 5 and a["total_plays"] < a["saved_count"] * 3:
            over_saved.append(a)
    cur = conn.execute("""
        SELECT a.artist_name, COUNT(DISTINCT p.play_id) as total_plays,
               COALESCE(st_cnt.saved, 0) as saved_count
        FROM plays p
        JOIN tracks t ON p.track_id = t.track_id
        JOIN artists a ON t.artist_id = a.artist_id
        LEFT JOIN (
            SELECT artist_name, COUNT(*) as saved FROM saved_tracks GROUP BY artist_name
        ) st_cnt ON st_cnt.artist_name = a.artist_name
        WHERE p.track_id IS NOT NULL
        GROUP BY a.artist_name
        HAVING total_plays >= 100 AND saved_count <= 3
        ORDER BY total_plays DESC
        LIMIT 5
    """)
    under_saved = [{"artist_name": r[0], "saved_count": r[2], "total_plays": r[1]} for r in cur.fetchall()]
    mismatch = {"over_saved": over_saved[:5], "under_saved": under_saved}

    # --- 10. 收藏夹档案 ---
    total_duration_min = saved_count * 3.5
    total_duration_hrs = round(total_duration_min / 60, 1)

    # 年代跨度：通过 albums 表获取发行年份
    cur = conn.execute("""
        SELECT MIN(CAST(SUBSTR(alb.release_date, 1, 4) AS INTEGER)),
               MAX(CAST(SUBSTR(alb.release_date, 1, 4) AS INTEGER))
        FROM saved_tracks st
        JOIN tracks t ON st.track_uri = t.spotify_track_uri
        JOIN albums alb ON t.album_id = alb.album_id
        WHERE alb.release_date IS NOT NULL AND alb.release_date != ''
    """)
    year_range = cur.fetchone()

    archive_facts = {
        "total_duration_hrs": total_duration_hrs,
        "year_span": f"{year_range[0]} – {year_range[1]}" if year_range and year_range[0] else None,
        "oldest_track": None,
    }
    if year_range and year_range[0]:
        cur = conn.execute("""
            SELECT st.track_name, st.artist_name,
                   CAST(SUBSTR(alb.release_date, 1, 4) AS INTEGER) as release_year
            FROM saved_tracks st
            JOIN tracks t ON st.track_uri = t.spotify_track_uri
            JOIN albums alb ON t.album_id = alb.album_id
            WHERE alb.release_date IS NOT NULL AND alb.release_date != ''
            ORDER BY release_year ASC LIMIT 1
        """)
        oldest = cur.fetchone()
        if oldest:
            archive_facts["oldest_track"] = {"track_name": oldest[0], "artist_name": oldest[1], "year": oldest[2]}

    return {
        "available": True,
        "empty": False,
        "personality": personality,
        "overview": overview,
        "first_save_story": first_save_story,
        "lifecycle": lifecycle,
        "chemistry": chemistry,
        "flip_side": flip_side,
        "keyword_migration": keyword_migration,
        "co_saved_artists": co_saved,
        "top_saved_artists": top_saved_artists,
        "mismatch": mismatch,
        "archive_facts": archive_facts,
    }


def get_account_summary(conn: sqlite3.Connection) -> dict:
    """聚合账号中心所有子服务的数据。"""
    from backend.services.library_service import get_library_overview
    from backend.services.profile_service import get_profile, get_inferences, get_sound_capsule
    from backend.services.search_service import get_search_stats
    from backend.services.insights_service import get_artist_tiers, get_marquee_conversion
    from backend.services.podcast_service import get_podcast_stats
    from backend.services.video_service import get_video_stats

    try:
        library = get_library_overview(conn)
    except Exception:
        library = {"available": False}
    try:
        profile = get_profile(conn)
    except Exception:
        profile = {"profile": {}, "follows": [], "prompts": [], "stats": {}, "banned_items": []}
    try:
        search = get_search_stats(conn)
    except Exception:
        search = {"available": False}
    try:
        insights_tiers = get_artist_tiers(conn)
    except Exception:
        insights_tiers = {"available": False}
    try:
        insights_marquee = get_marquee_conversion(conn)
    except Exception:
        insights_marquee = {"available": False}
    try:
        podcast = get_podcast_stats(conn)
    except Exception:
        podcast = {"available": False}
    try:
        video = get_video_stats(conn)
    except Exception:
        video = {"available": False}
    try:
        collection = get_collection_insights(conn)
    except Exception:
        collection = {"available": False}

    has_account_data = library.get("available", False)

    return {
        "has_account_data": has_account_data,
        "profile": profile,
        "library": library,
        "collection_insights": collection,
        "search": search,
        "insights_tiers": insights_tiers,
        "insights_marquee": insights_marquee,
        "podcast": podcast,
        "video": video,
        "inferences": {"available": False},
        "sound_capsule": {"available": False},
    }

    try:
        summary["inferences"] = get_inferences(conn)
    except Exception:
        pass
    try:
        summary["sound_capsule"] = get_sound_capsule(conn)
    except Exception:
        pass

    return summary
