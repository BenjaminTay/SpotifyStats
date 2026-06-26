"""Account center services — cross-analysis of saved tracks × play history."""

from __future__ import annotations

import datetime as _dt
import sqlite3
from collections import Counter
from pathlib import Path

from backend.core.cache import ttl_cached
from backend.core.cache_manager import register_ttl

ACCOUNT_SUMMARY_CACHE_TTL_SECONDS = 300


def _cover_url(image_path, image_url, cover_type: str, entity_id) -> str | None:
    """Return the smart local cover endpoint when any cover source exists."""
    if entity_id is None:
        return None
    if image_path or image_url:
        return f"/covers/{cover_type}/{int(entity_id)}.jpg"
    return None


def _artist_cover_map(conn: sqlite3.Connection) -> dict[str, str | None]:
    """Returns {artist_name: cover_url} for all artists."""
    rows = conn.execute(
        "SELECT artist_name, artist_id, image_path, image_url FROM artists"
    ).fetchall()
    return {
        r["artist_name"]: _cover_url(r["image_path"], r["image_url"], "artists", r["artist_id"])
        for r in rows
    }


def _track_album_cover_map(conn: sqlite3.Connection) -> dict[tuple[str, str], str | None]:
    """Returns {(track_name, artist_name): cover_url} via tracks→albums join."""
    rows = conn.execute(
        """SELECT t.track_name, a.artist_name, al.album_id, al.image_path, al.image_url
           FROM tracks t
           JOIN artists a ON t.artist_id = a.artist_id
           LEFT JOIN albums al ON t.album_id = al.album_id"""
    ).fetchall()
    return {
        (r["track_name"], r["artist_name"]): _cover_url(
            r["image_path"], r["image_url"], "albums", r["album_id"]
        )
        for r in rows
    }


def get_collection_insights(conn: sqlite3.Connection) -> dict:
    """返回收藏×播放交叉分析的所有洞察数据。

    性能优化：核心 saved_tracks×plays 交叉查询只执行一次，
    所有衍生计算（人格、生命周期、化学反应等）均在 Python 内存中完成。
    """
    import json
    import re

    import jieba

    cur = conn.execute("SELECT COUNT(*) FROM saved_tracks")
    saved_count = cur.fetchone()[0]
    if saved_count == 0:
        return {"available": False, "empty": True}

    # --- 封面图映射（2 次简单查询） ---
    track_cover_map = _track_album_cover_map(conn)
    artist_cover_map = _artist_cover_map(conn)

    # =====================================================================
    # 核心查询：saved_tracks × plays 交叉聚合 —— 整个函数只执行这一次 JOIN
    # =====================================================================
    master_rows = conn.execute("""
        SELECT
            st.track_name, st.artist_name, st.added_date,
            COUNT(CASE WHEN p.ts_date < st.added_date THEN 1 END) as before_save,
            COUNT(CASE WHEN p.ts_date >= st.added_date AND p.ts_date < date(st.added_date, '+7 days') THEN 1 END) as wk1,
            COUNT(CASE WHEN p.ts_date >= date(st.added_date, '+30 days') AND p.ts_date < date(st.added_date, '+90 days') THEN 1 END) as mo1_3,
            COUNT(CASE WHEN p.ts_date >= date(st.added_date, '+90 days') AND p.ts_date < date(st.added_date, '+365 days') THEN 1 END) as mo3_12,
            COUNT(CASE WHEN p.ts_date >= date(st.added_date, '+365 days') THEN 1 END) as after_1yr,
            COUNT(CASE WHEN p.ts_date >= st.added_date AND p.ts_date < date(st.added_date, '+180 days') THEN 1 END) as first_6mo,
            COUNT(CASE WHEN p.ts_date >= date(st.added_date, '+180 days') THEN 1 END) as after_6mo,
            MAX(p.ts_date) as last_play,
            COUNT(*) as total_plays
        FROM saved_tracks st
        LEFT JOIN tracks t ON st.track_uri = t.spotify_track_uri
        LEFT JOIN plays p ON p.track_id = t.track_id
        WHERE st.added_date IS NOT NULL AND st.added_date != ''
        GROUP BY st.track_name, st.artist_name
    """).fetchall()

    # 转为 dict 列表，后续纯 Python 计算
    stats = [dict(r) for r in master_rows]

    # =====================================================================
    # 1. 收藏人格 (Collection Personality)
    # =====================================================================
    total = len(stats)
    plays_after_save = [s["total_plays"] - s["before_save"] for s in stats]
    avg_before = sum(s["before_save"] for s in stats) / total if total else 0
    retention_count = sum(1 for v in plays_after_save if v > 0)
    retention_pct = retention_count / total * 100 if total else 0
    impulsive_count = sum(1 for s in stats if s["before_save"] <= 3)
    impulsive_pct = impulsive_count / total * 100 if total else 0

    if avg_before >= 10 and retention_pct >= 80:
        personality = {
            "type": "深海淘金者",
            "icon": "⛏️",
            "description": "你不会轻易收藏，平均听完多次后才按下那颗 ❤️。但一旦收藏，就几乎不再放手。",
        }
    elif avg_before <= 3 and retention_pct >= 70:
        personality = {
            "type": "冲动收藏家",
            "icon": "⚡",
            "description": "你相信第一感觉—绝大多数收藏都在 3 次播放内完成。",
        }
    elif avg_before >= 8 and saved_count < 500:
        personality = {
            "type": "精挑细选者",
            "icon": "💎",
            "description": "你的收藏夹小而精，每首歌都经过深思熟虑。",
        }
    else:
        personality = {
            "type": "均衡型收藏者",
            "icon": "🎵",
            "description": "你的收藏习惯介于冲动和谨慎之间，既有直觉选择也有深思熟虑。",
        }
    personality["metrics"] = {
        "avg_plays_before_save": round(avg_before, 1),
        "retention_pct": round(retention_pct, 1),
        "impulsive_pct": round(impulsive_pct, 1),
    }

    # =====================================================================
    # 2. 收藏纵览（简单聚合，用 SQL 最快）
    # =====================================================================
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
        SELECT SUBSTR(added_date, 1, 10) as save_date, COUNT(*) as cnt FROM saved_tracks
        WHERE added_date IS NOT NULL AND added_date != ''
        GROUP BY save_date ORDER BY cnt DESC LIMIT 1
    """)
    max_save_day = cur.fetchone()
    biggest_save_day = {"date": max_save_day[0], "count": max_save_day[1]} if max_save_day else None

    cur = conn.execute("""
        SELECT MIN(added_date), MAX(added_date)
        FROM saved_tracks WHERE added_date IS NOT NULL AND added_date != ''
    """)
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

    # =====================================================================
    # 3. 第一首收藏的故事（从内存数据取最早 added_date）
    # =====================================================================
    first = min(stats, key=lambda s: s["added_date"] or "z") if stats else None
    first_save_story = None
    if first and first["added_date"]:
        save_dt = _dt.datetime.strptime(first["added_date"][:10], "%Y-%m-%d")
        days_since = (_dt.date.today() - save_dt.date()).days
        total_plays_f = first["total_plays"] or 0
        interval = round(days_since / max(total_plays_f, 1), 1)
        first_save_story = {
            "track_name": first["track_name"],
            "artist_name": first["artist_name"],
            "save_date": first["added_date"],
            "total_plays": total_plays_f,
            "days_since": days_since,
            "avg_interval_days": interval,
            "cover_url": track_cover_map.get((first["track_name"], first["artist_name"])),
        }

    # =====================================================================
    # 4. 收藏生命周期 + 示例曲目（全部从内存计算）
    # =====================================================================
    t = total if total else 1
    avg_wk1 = sum(s["wk1"] for s in stats) / t
    avg_cooling = sum(s["mo1_3"] for s in stats) / (t * 8)  # 冷却期 8 周，折算周均
    avg_settling = sum(s["mo3_12"] for s in stats) / (t * 39)  # 沉淀期 39 周，折算周均

    evergreen = sum(1 for s in stats if s["after_1yr"] > 0)
    occasional = sum(
        1 for s in stats if s["after_1yr"] == 0 and (s["mo3_12"] > 0 or s["mo1_3"] > 0)
    )
    forgotten = sum(
        1
        for s in stats
        if s["after_1yr"] == 0 and s["mo3_12"] == 0 and s["mo1_3"] == 0 and s["wk1"] == 0
    )

    lifecycle = {
        "honeymoon": {"label": "蜜月期", "weeks": "0-1", "avg_per_week": round(avg_wk1, 1)},
        "cooling": {"label": "冷却期", "weeks": "1-12", "avg_per_week": round(avg_cooling, 1)},
        "settling": {"label": "沉淀期", "weeks": "12-52", "avg_per_week": round(avg_settling, 1)},
        "fate": {
            "evergreen_pct": round(evergreen / t * 100, 1),
            "occasional_pct": round(occasional / t * 100, 1),
            "forgotten_pct": round(forgotten / t * 100, 1),
        },
    }

    def _top_examples(key, n=3):
        """从内存 stats 中取指定指标最高的 n 首曲目。"""
        valid = [s for s in stats if s[key] > 0]
        valid.sort(key=lambda s: s[key], reverse=True)
        return [
            {
                "track_name": s["track_name"],
                "artist_name": s["artist_name"],
                "cover_url": track_cover_map.get((s["track_name"], s["artist_name"])),
            }
            for s in valid[:n]
        ]

    lifecycle["honeymoon_examples"] = _top_examples("wk1")
    lifecycle["cooling_examples"] = _top_examples("mo1_3")
    lifecycle["settling_examples"] = _top_examples("mo3_12")

    # --- 4b. 生命周期周均趋势 + Top 曲目个体趋势 ---
    trend_rows = conn.execute("""
        SELECT
            CAST((julianday(p.ts_date) - julianday(st.added_date)) / 7 AS INTEGER) as wk,
            COUNT(DISTINCT st.ROWID) as n_tracks,
            COUNT(*) as total_plays
        FROM saved_tracks st
        JOIN tracks t ON st.track_uri = t.spotify_track_uri
        JOIN plays p ON p.track_id = t.track_id
        WHERE st.added_date IS NOT NULL AND st.added_date != ''
          AND p.ts_date >= st.added_date
          AND CAST((julianday(p.ts_date) - julianday(st.added_date)) / 7 AS INTEGER) BETWEEN 0 AND 51
        GROUP BY wk ORDER BY wk
    """).fetchall()
    lifecycle_trend = [
        {"week": r[0], "avg_plays": round(r[2] / max(r[1], 1), 2), "track_count": r[1]}
        for r in trend_rows
    ]

    # Top 3 收藏曲目的个体周趋势
    top_tracks = sorted(stats, key=lambda s: s["total_plays"], reverse=True)[:3]
    lifecycle_top_tracks = []
    for tk in top_tracks:
        rows = conn.execute(
            """
            SELECT
                CAST((julianday(p.ts_date) - julianday(st.added_date)) / 7 AS INTEGER) as wk,
                COUNT(*) as plays
            FROM saved_tracks st
            JOIN tracks t ON st.track_uri = t.spotify_track_uri
            JOIN plays p ON p.track_id = t.track_id
            WHERE st.track_name = ? AND st.artist_name = ?
              AND st.added_date IS NOT NULL AND st.added_date != ''
              AND p.ts_date >= st.added_date
              AND CAST((julianday(p.ts_date) - julianday(st.added_date)) / 7 AS INTEGER) BETWEEN 0 AND 51
            GROUP BY wk ORDER BY wk
        """,
            [tk["track_name"], tk["artist_name"]],
        ).fetchall()
        lifecycle_top_tracks.append(
            {
                "track_name": tk["track_name"],
                "artist_name": tk["artist_name"],
                "cover_url": track_cover_map.get((tk["track_name"], tk["artist_name"])),
                "data": [{"week": r[0], "plays": r[1]} for r in rows],
            }
        )

    # =====================================================================
    # 5. 收藏×播放 化学反应（6 种类型）—— 从内存 stats 计算
    # =====================================================================
    three_months_ago = (_dt.date.today() - _dt.timedelta(days=90)).isoformat()
    chemistry_counts = {
        "love_at_first": sum(1 for s in stats if s["before_save"] <= 3),
        "slow_burn": sum(1 for s in stats if s["before_save"] >= 20),
        "flash_pan": sum(
            1
            for s in stats
            if s["wk1"] >= 10 and (s["last_play"] is None or s["last_play"] < three_months_ago)
        ),
        "late_bloomer": sum(
            1 for s in stats if s["after_6mo"] > s["first_6mo"] * 2 and s["first_6mo"] > 0
        ),
        "steady": sum(
            1
            for s in stats
            if s["before_save"] > 0
            and s["first_6mo"] > 0
            and abs(s["first_6mo"] / s["before_save"] - 1) < 0.5
        ),
        "shelf_sitter": sum(1 for s in stats if s["total_plays"] <= 3),
    }
    total_with_dates = total

    def _chemistry_examples(predicate):
        """从内存 stats 中筛选并返回全部匹配曲目（按 total_plays DESC），供前端轮播。"""
        matched = [s for s in stats if predicate(s)]
        matched.sort(key=lambda s: s["total_plays"], reverse=True)
        return [
            {
                "track_name": s["track_name"],
                "artist_name": s["artist_name"],
                "total_plays": s["total_plays"],
                "before_save": s["before_save"],
                "first_week": s["wk1"],
                "days_since_play": None,
                "cover_url": track_cover_map.get((s["track_name"], s["artist_name"])),
            }
            for s in matched
        ]

    chemistry = {
        "love_at_first_listen": {
            "count": chemistry_counts["love_at_first"],
            "label": "一见钟情",
            "description": "收藏时播放次数 ≤ 3",
            "icon": "💘",
            "examples": _chemistry_examples(lambda s: s["before_save"] <= 3),
        },
        "slow_burn": {
            "count": chemistry_counts["slow_burn"],
            "label": "慢热型",
            "description": "收藏时已播放 ≥ 20 次",
            "icon": "🔥",
            "examples": _chemistry_examples(lambda s: s["before_save"] >= 20),
        },
        "flash_in_the_pan": {
            "count": chemistry_counts["flash_pan"],
            "label": "昙花一现",
            "description": "收藏周播放 ≥ 10 次，现已 > 3 月未播",
            "icon": "🌠",
            "examples": _chemistry_examples(
                lambda s: (
                    s["wk1"] >= 10 and (s["last_play"] is None or s["last_play"] < three_months_ago)
                )
            ),
        },
        "late_bloomer": {
            "count": chemistry_counts["late_bloomer"],
            "label": "厚积薄发",
            "description": "收藏后 6 个月播放持续增长",
            "icon": "🌱",
            "examples": _chemistry_examples(
                lambda s: s["after_6mo"] > s["first_6mo"] * 2 and s["first_6mo"] > 0
            ),
        },
        "steady_favorite": {
            "count": chemistry_counts["steady"],
            "label": "细水长流",
            "description": "收藏前后播放频率稳定",
            "icon": "💪",
            "examples": _chemistry_examples(
                lambda s: (
                    s["before_save"] > 0
                    and s["first_6mo"] > 0
                    and abs(s["first_6mo"] / s["before_save"] - 1) < 0.5
                )
            ),
        },
        "shelf_sitter": {
            "count": chemistry_counts["shelf_sitter"],
            "label": "收藏夹吃灰",
            "description": "收藏后总播放 ≤ 3 次",
            "icon": "📌",
            "examples": _chemistry_examples(lambda s: s["total_plays"] <= 3),
        },
        "total_with_dates": total_with_dates,
    }

    # =====================================================================
    # 6. Flip Side: 播放多但未收藏
    # =====================================================================
    cur = conn.execute("""
        SELECT p_agg.track_name, p_agg.artist_name, p_agg.play_count
        FROM (
            SELECT t.track_name, a.artist_name, COUNT(*) as play_count
            FROM plays p
            JOIN tracks t ON p.track_id = t.track_id
            JOIN artists a ON t.artist_id = a.artist_id
            WHERE p.track_id IS NOT NULL
            GROUP BY t.track_name, a.artist_name
            HAVING play_count >= 20
        ) p_agg
        LEFT JOIN saved_tracks st
            ON st.track_name = p_agg.track_name AND st.artist_name = p_agg.artist_name
        WHERE st.track_uri IS NULL
        ORDER BY p_agg.play_count DESC
        LIMIT 20
    """)
    flip_side = [
        {
            "track_name": r[0],
            "artist_name": r[1],
            "play_count": r[2],
            "cover_url": track_cover_map.get((r[0], r[1])),
        }
        for r in cur.fetchall()
    ]

    # =====================================================================
    # 7. 收藏关键词变迁（词频 + 播放量加权）
    # =====================================================================
    # 查询每首歌的年份和播放量
    cur = conn.execute("""
        SELECT SUBSTR(st.added_date, 1, 4) as yr,
               st.track_name, st.artist_name,
               COUNT(p.play_id) as plays
        FROM saved_tracks st
        JOIN tracks t ON t.track_name = st.track_name
        JOIN artists a ON a.artist_id = t.artist_id AND a.artist_name = st.artist_name
        LEFT JOIN plays p ON p.track_id = t.track_id
        WHERE st.added_date IS NOT NULL AND st.added_date != ''
        GROUP BY yr, st.track_name, st.artist_name
        ORDER BY yr
    """)
    track_rows = cur.fetchall()

    # ── 歌名清洗 ────────────────────────────────────────────────────────
    def _clean_track_name(text: str) -> str:
        """去除歌名中常见的版本/合作/现场等元数据标记。"""
        text = re.sub(
            r"\([^)]*?(feat\.?|ft\.|with|prod\.|remix|live|acoustic|"
            r"version|edit|mix|bonus|demo|extended|original|radio|"
            r"from\s|OST|soundtrack|theme|intro|outro|interlude|"
            r"taylor|anniversary|deluxe|explicit|clean|single|"
            r"special|reprise|cover|instrumental|orchestral|"
            r"alternate|demo|session|take|remastered|"
            r"g.e.m|重制版|伴奏|翻唱|现场|主题曲|片尾曲|插曲|"
            r"完整版|纯音乐|试听|首播|抢先|独家|最新|"
            r"高清|无损|原版)[^)]*\)",
            " ",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"\[[^\]]*?(feat\.?|ft\.|with|prod\.|remix|live|acoustic|"
            r"version|edit|mix|bonus|demo|extended|original|radio|"
            r"from\s|OST|soundtrack|intro|outro|interlude|"
            r"version|edit|mix|clean|explicit|single|special|"
            r"reprise|cover|instrumental|orchestral|"
            r"alternate|demo|session|take|remastered|"
            r"主题曲|片尾曲|插曲|伴奏|现场)[^\]]*\]",
            " ",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"\s[-–—]\s*("
            r"live(\s(at|in|from|on)\s.+?)?|"
            r"radio\s?edit|remix|remastered|remaster|"
            r"acoustic(\sversion)?|instrumental|orchestral|"
            r"extended(\smix)?|original(\smix)?|"
            r"bonus\strack|deluxe(\sedition)?|"
            r"single(\sversion|edit)?|album\sversion|"
            r"studio(\sversion)?|clean(\sversion)?|explicit(\sversion)?|"
            r"alternate(\sversion|take|mix)?|demo(\sversion)?|"
            r"(\d+st|nd|rd|th)?\s?anniversary(\sedition)?|"
            r"reprise|intro|outro|interlude|"
            r"from\s.+?(soundtrack|OST)|original\s soundtrack|"
            r"重制版|伴奏|翻唱|现场版|主题曲|片尾曲|插曲|"
            r"完整版|纯音乐|试听|首发|抢先|独家|最新|"
            r"高清|无损|原版|新版"
            r")$",
            "",
            text,
            flags=re.IGNORECASE,
        )
        return re.sub(r"\s+", " ", text).strip()

    # ── 停用词 ──────────────────────────────────────────────────────────
    cn_stop = {
        # 虚词
        "的",
        "了",
        "在",
        "是",
        "我",
        "有",
        "和",
        "就",
        "不",
        "人",
        "都",
        "一",
        "一个",
        "上",
        "也",
        "很",
        "到",
        "说",
        "要",
        "去",
        "你",
        "会",
        "着",
        "没有",
        "看",
        "好",
        "自己",
        "这",
        "他",
        "她",
        "它",
        "们",
        "那",
        "些",
        "什么",
        "怎么",
        "如何",
        "可以",
        "这个",
        "那个",
        "还是",
        "因为",
        "所以",
        "但是",
        "如果",
        "虽然",
        "而且",
        "不过",
        "只",
        "把",
        "被",
        "让",
        "给",
        "对",
        "从",
        "向",
        "跟",
        "与",
        "或",
        "之",
        "为",
        "以",
        "及",
        "啊",
        "吧",
        "呢",
        "吗",
        "呀",
        "嘛",
        "哦",
        "嗯",
        "啦",
        "噢",
        "能",
        "会",
        "可",
        "想",
        "来",
        "去",
        "做",
        "没",
        "有",
        "知道",
        # 音乐元数据噪音
        "版",
        "原版",
        "伴奏",
        "纯音乐",
        "翻唱",
        "现场",
        "版",
        "试听",
        "专辑",
        "单曲",
        "主打",
        "首播",
        "主题曲",
        "片尾曲",
        "插曲",
        "最新",
        "独家",
        "首发",
        "抢先",
        "完整",
        "高清",
        "无损",
    }
    en_stop = {
        # NLTK-level common English stopwords (~150 words)
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "having",
        "do",
        "does",
        "did",
        "doing",
        "will",
        "would",
        "could",
        "should",
        "shall",
        "can",
        "may",
        "might",
        "must",
        "i",
        "me",
        "my",
        "myself",
        "we",
        "our",
        "ours",
        "ourselves",
        "you",
        "your",
        "yours",
        "yourself",
        "yourselves",
        "he",
        "him",
        "his",
        "himself",
        "she",
        "her",
        "hers",
        "herself",
        "it",
        "its",
        "itself",
        "they",
        "them",
        "their",
        "theirs",
        "themselves",
        "what",
        "which",
        "who",
        "whom",
        "this",
        "that",
        "these",
        "those",
        "am",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "having",
        "do",
        "does",
        "did",
        "doing",
        "a",
        "an",
        "the",
        "and",
        "but",
        "if",
        "or",
        "because",
        "as",
        "until",
        "while",
        "of",
        "at",
        "by",
        "for",
        "with",
        "about",
        "between",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "to",
        "from",
        "up",
        "down",
        "in",
        "out",
        "on",
        "off",
        "over",
        "under",
        "again",
        "further",
        "then",
        "once",
        "here",
        "there",
        "when",
        "where",
        "why",
        "how",
        "all",
        "both",
        "each",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "not",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        "just",
        "now",
        "still",
        "also",
        "any",
        "every",
        "really",
        "even",
        "already",
        "always",
        "never",
        "sometimes",
        "often",
        "yet",
        # 口语/缩写碎片
        "don",
        "re",
        "ve",
        "ll",
        "ain",
        "got",
        "get",
        "got",
        "dont",
        "isnt",
        "wasnt",
        "cant",
        "wont",
        "doesnt",
        "im",
        "ive",
        "youre",
        "theyre",
        "were",
        # 音乐制作噪音
        "remix",
        "feat",
        "mix",
        "edit",
        "version",
        "original",
        "radio",
        "live",
        "extended",
        "instrumental",
        "acoustic",
        "bonus",
        "track",
        "demo",
        "feat.",
        "(feat.",
        "version)",
        "(taylor's",
        "(from",
        "vault)",
        "(with",
        "(g.e.m.重生版)",
        # 数字/年份
        "2016",
        "2017",
        "2018",
        "2019",
        "2020",
        "2021",
        "2022",
        "2023",
        "2024",
        "2025",
        "2026",
        # 无意义常见英文词（补充）
        "well",
        "know",
        "say",
        "ever",
        "little",
        "hey",
        "man",
        "good",
        "bad",
        "long",
        "like",
        "days",
        "remember",
        "hero",
        "super",
        "brave",
        "sorry",
        "gonna",
        "wanna",
        "girl",
        "call",
        "end",
        "last",
        # 中文噪音补充
        "主題",
        "主题",
        "2999",
        "2998",
        "2997",
        "心地",
        "愛我別",
        "爱我别",
        # 无意义单音节/双音节常见词
        "na",
        "la",
        "da",
        "ba",
        "ta",
        "ka",
        "ma",
        "pa",
        "sa",
        "ha",
        "de",
        "en",
        "el",
        "le",
        "un",
        "il",
        "lo",
        "se",
        "si",
        "di",
        "una",
        "que",
        "los",
        "las",
        "del",
        "con",
        "por",
        "para",
        "como",
        "mas",
        "pero",
        "mis",
        "sus",
        "est",
        "les",
        "des",
        "das",
        "das",
        "und",
        "die",
        "der",
        "ist",
        "ein",
        "von",
        "chez",
        "sur",
        "dans",
        "avec",
        "pour",
        # 日/韩语常见碎片
        "no",
        "wa",
        "ga",
        "wo",
        "ni",
        "to",
        "de",
        "mo",
        "yo",
        "ne",
        "desu",
        "masu",
        "imas",
        "suru",
        "koto",
        "mono",
    }

    # ── 跨语言同义词归一化（统一到英文）────────────────────────────────
    synonym_map = {
        # Love / 爱
        "love": "Love",
        "loved": "Love",
        "lover": "Love",
        "爱": "Love",
        "爱情": "Love",
        "恋爱": "Love",
        "爱人": "Love",
        # Night / 夜
        "night": "Night",
        "nights": "Night",
        "夜": "Night",
        "夜晚": "Night",
        "深夜": "Night",
        # Heart / 心
        "heart": "Heart",
        "hearts": "Heart",
        "心": "Heart",
        "内心": "Heart",
        "心跳": "Heart",
        # Dream / 梦
        "dream": "Dream",
        "dreams": "Dream",
        "dreaming": "Dream",
        "梦": "Dream",
        "梦想": "Dream",
        # Time / 时光
        "time": "Time",
        "时光": "Time",
        "时间": "Time",
        # Dance / 舞
        "dance": "Dance",
        "dancing": "Dance",
        "舞": "Dance",
        "跳舞": "Dance",
        # Song / 歌
        "song": "Song",
        "songs": "Song",
        "歌": "Song",
        "歌曲": "Song",
        "首歌": "Song",
        # Rain / 雨
        "rain": "Rain",
        "raining": "Rain",
        "雨": "Rain",
        "下雨": "Rain",
        # Wind / 风
        "wind": "Wind",
        "风": "Wind",
        # Summer / 夏天
        "summer": "Summer",
        "夏": "Summer",
        "夏日": "Summer",
        # Winter / 冬天
        "winter": "Winter",
        "冬": "Winter",
        "冬日": "Winter",
        # Spring / 春天
        "spring": "Spring",
        "春": "Spring",
        "春日": "Spring",
        # Star / 星
        "star": "Star",
        "stars": "Star",
        "星": "Star",
        "星星": "Star",
        # Moon / 月
        "moon": "Moon",
        "月光": "Moon",
        # Light / 光
        "light": "Light",
        "lights": "Light",
        "光": "Light",
        "光芒": "Light",
        # Fire / 火
        "fire": "Fire",
        "flame": "Fire",
        "火": "Fire",
        "火焰": "Fire",
        # Flower / 花
        "flower": "Flower",
        "flowers": "Flower",
        "花": "Flower",
        # Sea / 海
        "sea": "Sea",
        "ocean": "Sea",
        "海": "Sea",
        "大海": "Sea",
        # Sky / 天空
        "sky": "Sky",
        "天空": "Sky",
        # Road / 路
        "road": "Road",
        "street": "Road",
        "path": "Road",
        "路": "Road",
        "路上": "Road",
        # World / 世界
        "world": "World",
        "世界": "World",
        # Life / 人生
        "life": "Life",
        "人生": "Life",
        # Tears / 泪
        "tear": "Tears",
        "tears": "Tears",
        "cry": "Tears",
        "crying": "Tears",
        "泪": "Tears",
        "眼泪": "Tears",
        "哭泣": "Tears",
        # Memory / 记忆
        "memory": "Memory",
        "memories": "Memory",
        "记忆": "Memory",
        "回忆": "Memory",
        # Alone / 孤独
        "alone": "Alone",
        "lonely": "Alone",
        "loneliness": "Alone",
        "孤独": "Alone",
        "寂寞": "Alone",
        "孤单": "Alone",
        # Goodbye / 再见
        "goodbye": "Goodbye",
        "farewell": "Goodbye",
        "再见": "Goodbye",
        "告别": "Goodbye",
        # Forever / 永远
        "forever": "Forever",
        "eternal": "Forever",
        "永远": "Forever",
        "永恒": "Forever",
        # Beautiful / 美丽
        "beautiful": "Beautiful",
        "beauty": "Beautiful",
        "美丽": "Beautiful",
        "美": "Beautiful",
        # Happy / 快乐
        "happy": "Happy",
        "happiness": "Happy",
        "快乐": "Happy",
        "幸福": "Happy",
        "开心": "Happy",
        # Sad / 悲伤
        "sad": "Sad",
        "sadness": "Sad",
        "悲伤": "Sad",
        "难过": "Sad",
        "伤心": "Sad",
    }
    all_stop = cn_stop | en_stop

    # ── 辅助函数 ────────────────────────────────────────────────────────
    def _contains_chinese(text: str) -> bool:
        return any("一" <= ch <= "鿿" for ch in text)

    def _normalize_word(w: str) -> str:
        """将同义词归一化到标准形式，去停用词，保留语义。"""
        w = w.strip().lower()
        if w in all_stop or len(w) < 2:
            return ""
        # 优先查 synonym_map
        if w in synonym_map:
            return synonym_map[w]
        # 英文最小长度 3，中文最小长度 2（已在上方处理）
        is_ascii = all(c < "一" for c in w)
        if is_ascii and len(w) < 3:
            return ""
        return w

    # ── 每年逐首分词 + 词频 & 播放量统计 ──────────────────────────────
    per_year: dict[str, dict[str, dict[str, object]]] = {}
    year_song_counts: dict[str, int] = {}
    for yr, track_name, artist_name, plays in track_rows:
        cleaned = _clean_track_name(track_name)
        plays = plays or 0
        year_song_counts[yr] = year_song_counts.get(yr, 0) + 1
        if yr not in per_year:
            per_year[yr] = {}
        # 提取词汇
        words: list[str] = []
        if _contains_chinese(cleaned):
            for w in jieba.cut(cleaned):
                nw = _normalize_word(w)
                if nw:
                    words.append(nw)
        for w in re.findall(r"[a-zA-Z]{3,}", cleaned.lower()):
            nw = _normalize_word(w)
            if nw:
                words.append(nw)
        # 去重：一首歌中同一个词只计一次 song_freq，但播放量照加
        seen = set()
        for w in words:
            if w in seen:
                continue
            seen.add(w)
            if w not in per_year[yr]:
                per_year[yr][w] = {"songs": 0, "plays": 0}
            per_year[yr][w]["songs"] = int(per_year[yr][w]["songs"]) + 1  # type: ignore[index]
            per_year[yr][w]["plays"] = int(per_year[yr][w]["plays"]) + plays  # type: ignore[index]

    # ── 评分：词频 70% + 播放量 30%，最低频次门槛 ──────────────────────
    keyword_migration: dict[str, list[dict[str, object]]] = {}
    for yr in sorted(per_year.keys()):
        word_stats = per_year[yr]
        min_songs = 2
        candidates = {w: d for w, d in word_stats.items() if int(d["songs"]) >= min_songs}  # type: ignore[arg-type]
        if not candidates:
            keyword_migration[yr] = []
            continue
        max_songs = max(int(d["songs"]) for d in candidates.values())
        max_plays = max(int(d["plays"]) for d in candidates.values()) or 1
        scored = []
        for word, d in candidates.items():
            songs = int(d["songs"])  # type: ignore[arg-type]
            plays = int(d["plays"])  # type: ignore[arg-type]
            norm_freq = songs / max(max_songs, 1)
            norm_plays = plays / max(max_plays, 1)
            score = norm_freq * 0.7 + (norm_plays**0.5) * 0.3
            scored.append({"word": word, "weight": round(score, 4)})
        scored.sort(key=lambda x: -x["weight"])
        keyword_migration[yr] = scored[:10]

    # ── 流派变迁 ────────────────────────────────────────────────────────
    cur = conn.execute("""
        SELECT SUBSTR(st.added_date, 1, 4) as yr, sam.genres, COUNT(*) as cnt
        FROM saved_tracks st
        JOIN spotify_artist_meta sam ON sam.artist_name = st.artist_name
        WHERE sam.genres IS NOT NULL AND sam.genres != ''
          AND st.added_date IS NOT NULL AND st.added_date != ''
        GROUP BY yr, sam.genres
        ORDER BY yr, cnt DESC
    """)
    genre_by_year: dict[str, Counter] = {}
    for yr, genres_json, cnt in cur.fetchall():
        if yr not in genre_by_year:
            genre_by_year[yr] = Counter()
        for g in json.loads(genres_json):
            genre_by_year[yr][g] += cnt
    genre_migration: dict[str, list[str]] = {}
    for yr in sorted(genre_by_year.keys()):
        genre_migration[yr] = [g for g, _ in genre_by_year[yr].most_common(4)]

    # =====================================================================
    # 8. 双厨时刻
    # =====================================================================
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

    # =====================================================================
    # 9. 排行榜 + 错位榜
    # =====================================================================
    # 从 saved_tracks 聚合 + 从 master stats 聚合播放量
    saved_artist_plays = {}
    for s in stats:
        key = s["artist_name"]
        saved_artist_plays[key] = saved_artist_plays.get(key, 0) + s["total_plays"]

    cur = conn.execute("""
        SELECT artist_name, COUNT(*) as saved_cnt
        FROM saved_tracks GROUP BY artist_name
        ORDER BY saved_cnt DESC LIMIT 15
    """)
    top_saved_artists = [
        {
            "artist_name": r[0],
            "saved_count": r[1],
            "total_plays": saved_artist_plays.get(r[0], 0),
            "cover_url": artist_cover_map.get(r[0]),
        }
        for r in cur.fetchall()
    ]

    # ── 收藏曲目最多的专辑 ─────────────────────────────────────────────
    # 聚合专辑播放量：从 saved_tracks 出发 JOIN plays
    album_plays = {}
    cur_ap = conn.execute("""
        SELECT st.album_name, st.artist_name, COUNT(p.play_id) as play_cnt
        FROM saved_tracks st
        JOIN tracks t ON st.track_uri = t.spotify_track_uri
        JOIN plays p ON p.track_id = t.track_id
        GROUP BY st.album_name, st.artist_name
    """)
    for r in cur_ap.fetchall():
        album_plays[(r["album_name"], r["artist_name"])] = r["play_cnt"]

    cur = conn.execute("""
        SELECT st.album_name, st.artist_name, COUNT(*) as saved_cnt
        FROM saved_tracks st
        GROUP BY st.album_name, st.artist_name
        ORDER BY saved_cnt DESC
        LIMIT 10
    """)
    # 通过 album_name + artist_name 匹配封面
    cur2 = conn.execute("""
        SELECT al.album_name, a.artist_name, al.image_path, al.image_url, al.album_id
        FROM albums al
        JOIN artists a ON a.artist_id = al.artist_id
    """)
    album_cover_lookup = {}
    for r in cur2.fetchall():
        key = (r["album_name"], r["artist_name"])
        cover = _cover_url(r["image_path"], r["image_url"], "albums", r["album_id"])
        if key not in album_cover_lookup:
            album_cover_lookup[key] = cover
    top_saved_albums = [
        {
            "album_name": r[0],
            "artist_name": r[1],
            "saved_count": r[2],
            "total_plays": album_plays.get((r[0], r[1]), 0),
            "cover_url": album_cover_lookup.get((r[0], r[1])),
        }
        for r in cur.fetchall()
    ]

    # =====================================================================
    # 10. 收藏夹档案
    # =====================================================================
    total_duration_hrs = round(saved_count * 3.5 / 60, 1)

    cur = conn.execute("""
        SELECT MIN(CAST(SUBSTR(COALESCE(alb.release_date, sam.release_date), 1, 4) AS INTEGER)),
               MAX(CAST(SUBSTR(COALESCE(alb.release_date, sam.release_date), 1, 4) AS INTEGER))
        FROM saved_tracks st
        LEFT JOIN tracks t ON st.track_uri = t.spotify_track_uri
        LEFT JOIN albums alb ON t.album_id = alb.album_id
        LEFT JOIN spotify_track_meta stm
            ON st.spotify_track_id = stm.spotify_track_id
        LEFT JOIN spotify_album_meta sam ON stm.spotify_album_id = sam.spotify_album_id
        WHERE COALESCE(alb.release_date, sam.release_date) IS NOT NULL
          AND COALESCE(alb.release_date, sam.release_date) != ''
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
                   CAST(SUBSTR(COALESCE(alb.release_date, sam.release_date), 1, 4) AS INTEGER) as release_year
            FROM saved_tracks st
            LEFT JOIN tracks t ON st.track_uri = t.spotify_track_uri
            LEFT JOIN albums alb ON t.album_id = alb.album_id
            LEFT JOIN spotify_track_meta stm
                ON st.spotify_track_id = stm.spotify_track_id
            LEFT JOIN spotify_album_meta sam ON stm.spotify_album_id = sam.spotify_album_id
            WHERE COALESCE(alb.release_date, sam.release_date) IS NOT NULL
              AND COALESCE(alb.release_date, sam.release_date) != ''
            ORDER BY release_year ASC LIMIT 1
        """)
        oldest = cur.fetchone()
        if oldest:
            archive_facts["oldest_track"] = {
                "track_name": oldest[0],
                "artist_name": oldest[1],
                "year": oldest[2],
            }

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
        "genre_migration": genre_migration,
        "co_saved_artists": co_saved,
        "top_saved_artists": top_saved_artists,
        "top_saved_albums": top_saved_albums,
        "archive_facts": archive_facts,
        "lifecycle_trend": lifecycle_trend,
        "lifecycle_top_tracks": lifecycle_top_tracks,
    }


def _database_file_path(conn: sqlite3.Connection) -> str | None:
    """Return a stable file-backed SQLite path for cache keys."""
    rows = conn.execute("PRAGMA database_list").fetchall()
    for row in rows:
        if row[1] != "main":
            continue
        raw_path = row[2]
        if not raw_path:
            return None
        return str(Path(raw_path).resolve())
    return None


def _open_cached_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@ttl_cached(ACCOUNT_SUMMARY_CACHE_TTL_SECONDS, namespace="account")
def _get_account_summary_cached(db_path: str) -> dict:
    conn = _open_cached_connection(db_path)
    try:
        return _build_account_summary(conn)
    finally:
        conn.close()


def get_account_summary(conn: sqlite3.Connection) -> dict:
    """聚合账号中心所有子服务的数据。"""
    db_path = _database_file_path(conn)
    if db_path is None:
        return _build_account_summary(conn)
    return _get_account_summary_cached(db_path)


def _build_account_summary(conn: sqlite3.Connection) -> dict:
    """聚合账号中心所有子服务的数据。"""
    from backend.services.insights_service import get_artist_tiers, get_marquee_conversion
    from backend.services.library_service import get_library_overview
    from backend.services.podcast_service import get_podcast_stats
    from backend.services.profile_service import get_inferences, get_profile, get_sound_capsule
    from backend.services.search_service import get_search_stats
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

    summary = {
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


register_ttl("account", "summary", _get_account_summary_cached)
