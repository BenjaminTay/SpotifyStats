"""SQLite database layer: schema, connection, and common query helpers."""

import hashlib
import json
import sqlite3
import os
from typing import Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "spotify_stats.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS artists (
    artist_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS albums (
    album_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    album_name  TEXT NOT NULL,
    artist_id   INTEGER NOT NULL REFERENCES artists(artist_id)
);

CREATE TABLE IF NOT EXISTS tracks (
    track_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    track_name        TEXT NOT NULL,
    artist_id         INTEGER NOT NULL REFERENCES artists(artist_id),
    album_id          INTEGER REFERENCES albums(album_id),
    spotify_track_uri TEXT
);

CREATE TABLE IF NOT EXISTS plays (
    play_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts               TEXT NOT NULL,
    ts_year          INTEGER NOT NULL,
    ts_month         INTEGER NOT NULL,
    ts_week          INTEGER NOT NULL,
    ts_dow           INTEGER NOT NULL,
    ts_hour          INTEGER NOT NULL,
    ts_date          TEXT NOT NULL,
    platform         TEXT NOT NULL,
    ms_played        INTEGER NOT NULL,
    conn_country     TEXT,
    track_id         INTEGER REFERENCES tracks(track_id),
    reason_start     TEXT,
    reason_end       TEXT,
    shuffle          INTEGER NOT NULL DEFAULT 0,
    skipped          INTEGER NOT NULL DEFAULT 0,
    offline          INTEGER NOT NULL DEFAULT 0,
    incognito_mode   INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_plays_year     ON plays(ts_year);
CREATE INDEX IF NOT EXISTS idx_plays_ym       ON plays(ts_year, ts_month);
CREATE INDEX IF NOT EXISTS idx_plays_date     ON plays(ts_date);
CREATE INDEX IF NOT EXISTS idx_plays_track    ON plays(track_id);
CREATE INDEX IF NOT EXISTS idx_plays_platform ON plays(platform);
CREATE INDEX IF NOT EXISTS idx_plays_skipped  ON plays(skipped);
CREATE INDEX IF NOT EXISTS idx_plays_dow_hour ON plays(ts_dow, ts_hour);
CREATE INDEX IF NOT EXISTS idx_plays_year_skipped_track ON plays(ts_year, skipped, track_id, ms_played);
CREATE INDEX IF NOT EXISTS idx_tracks_name ON tracks(track_name);
CREATE INDEX IF NOT EXISTS idx_albums_name ON albums(album_name);
CREATE TABLE IF NOT EXISTS track_albums (
    track_id INTEGER NOT NULL REFERENCES tracks(track_id),
    album_id INTEGER NOT NULL REFERENCES albums(album_id),
    UNIQUE(track_id, album_id)
);

CREATE INDEX IF NOT EXISTS idx_tracks_artist  ON tracks(artist_id);
CREATE INDEX IF NOT EXISTS idx_tracks_album   ON tracks(album_id);
CREATE INDEX IF NOT EXISTS idx_albums_artist  ON albums(artist_id);
CREATE INDEX IF NOT EXISTS idx_track_albums_track ON track_albums(track_id);
CREATE INDEX IF NOT EXISTS idx_track_albums_album ON track_albums(album_id);

-- Pre-aggregated weekly Billboard data (built after import, invalidated on param change)
CREATE TABLE IF NOT EXISTS agg_weekly_tracks (
    billboard_week TEXT NOT NULL,
    track_id INTEGER NOT NULL,
    play_count INTEGER NOT NULL,
    total_ms INTEGER NOT NULL,
    PRIMARY KEY (billboard_week, track_id)
);

CREATE TABLE IF NOT EXISTS agg_weekly_albums (
    billboard_week TEXT NOT NULL,
    album_id INTEGER NOT NULL,
    play_count INTEGER NOT NULL,
    total_ms INTEGER NOT NULL,
    PRIMARY KEY (billboard_week, album_id)
);

CREATE TABLE IF NOT EXISTS agg_weekly_artists (
    billboard_week TEXT NOT NULL,
    artist_id INTEGER NOT NULL,
    play_count INTEGER NOT NULL,
    total_ms INTEGER NOT NULL,
    PRIMARY KEY (billboard_week, artist_id)
);

CREATE TABLE IF NOT EXISTS agg_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agg_wt_week ON agg_weekly_tracks(billboard_week);
CREATE INDEX IF NOT EXISTS idx_agg_wa_week ON agg_weekly_albums(billboard_week);
CREATE INDEX IF NOT EXISTS idx_agg_war_week ON agg_weekly_artists(billboard_week);
"""


def get_db(readonly: bool = True) -> sqlite3.Connection:
    """Get a database connection. Thread-safe for Streamlit's execution model."""
    uri = f"file:{DB_PATH}?mode=ro" if readonly else DB_PATH
    conn = sqlite3.connect(uri, uri=True if readonly else False)
    conn.row_factory = sqlite3.Row
    if readonly:
        conn.execute("PRAGMA query_only = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db() -> None:
    """Create tables and indexes if they don't exist."""
    conn = get_db(readonly=False)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def ensure_schema() -> None:
    """Ensure all tables/indexes exist (safe to call repeatedly — uses IF NOT EXISTS)."""
    if not os.path.exists(DB_PATH):
        return
    conn = get_db(readonly=False)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def base_filters(
    min_ms: int = 30000,
    exclude_skipped: bool = True,
    music_only: bool = True,
    table_alias: str = "p",
) -> tuple[str, list[Any]]:
    """Return a WHERE clause fragment and parameters for the standard data filters.

    These filters are used by all music-statistics pages:
      - Exclude skipped if `exclude_skipped`
      - Minimum ms_played threshold
      - Exclude podcasts/audiobooks if `music_only` (track_id IS NOT NULL)

    Returns (sql_clause, params) that can be appended to a WHERE 1=1 query.
    """
    clauses = []
    params: list[Any] = []

    if exclude_skipped:
        clauses.append(f"{table_alias}.skipped = 0")

    if min_ms > 0:
        clauses.append(f"{table_alias}.ms_played >= ?")
        params.append(min_ms)

    if music_only:
        clauses.append(f"{table_alias}.track_id IS NOT NULL")

    return " AND ".join(clauses), params


def query_plays(
    conn: sqlite3.Connection,
    base_sql: str,
    extra_where: str = "",
    extra_params: Optional[list[Any]] = None,
    min_ms: int = 30000,
    exclude_skipped: bool = True,
    music_only: bool = True,
) -> list[sqlite3.Row]:
    """Execute a query against filtered plays.

    `base_sql` should contain the SELECT and FROM clauses.
    Filters are appended to WHERE 1=1.
    """
    filters, filter_params = base_filters(
        min_ms=min_ms, exclude_skipped=exclude_skipped, music_only=music_only
    )
    parts = [base_sql, "WHERE 1=1"]
    if filters:
        parts.append(f"AND {filters}")
    if extra_where:
        parts.append(f"AND {extra_where}")
        if extra_params:
            filter_params.extend(extra_params)

    sql = " ".join(parts)
    return conn.execute(sql, filter_params).fetchall()


def load_plays(
    conn: sqlite3.Connection,
    columns: str = "*",
    extra_where: str = "",
    extra_params: Optional[list[Any]] = None,
    min_ms: int = 30000,
    exclude_skipped: bool = True,
    music_only: bool = True,
    join_albums: bool = True,
):
    """统一的播放数据加载函数，所有统计页面复用。

    内部封装 base_filters() + 标准 JOIN，返回 pd.DataFrame。
    columns="*" 时自动选择完整列集合，也可传入自定义列字符串。
    join_albums=False 可跳过 albums JOIN 减少查询开销。
    """
    import pandas as pd

    f, fp = base_filters(min_ms, exclude_skipped, music_only)
    where = f"WHERE {f}" if f else ""
    if extra_where:
        where += f" AND {extra_where}" if where else f"WHERE {extra_where}"
    params = fp + (extra_params or [])

    if columns == "*":
        if join_albums:
            cols = "p.*, t.track_name, t.spotify_track_uri, a.artist_name, al.album_name"
        else:
            cols = "p.*, t.track_name, t.spotify_track_uri, a.artist_name"
    else:
        cols = columns

    if join_albums:
        from_clause = (
            "FROM plays p "
            "LEFT JOIN tracks t ON p.track_id = t.track_id "
            "LEFT JOIN artists a ON t.artist_id = a.artist_id "
            "LEFT JOIN albums al ON t.album_id = al.album_id"
        )
    else:
        from_clause = (
            "FROM plays p "
            "LEFT JOIN tracks t ON p.track_id = t.track_id "
            "LEFT JOIN artists a ON t.artist_id = a.artist_id"
        )

    sql = f"SELECT {cols} {from_clause} {where} ORDER BY p.ts"
    return pd.read_sql_query(sql, conn, params=params)

def db_exists() -> bool:
    """Check if the database file already exists and has data."""
    if not os.path.exists(DB_PATH):
        return False
    conn = get_db(readonly=True)
    try:
        count = conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
        return count > 0
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# Pre-aggregated Billboard weekly data
# ═══════════════════════════════════════════════════════════════════════════

def _agg_param_hash(
    min_ms: int,
    exclude_skipped: bool,
    music_only: bool,
    week_start_dow: int,
    week_start_hour: int,
) -> str:
    """Compute a content-hash of the parameters that affect aggregation results."""
    payload = json.dumps([min_ms, exclude_skipped, music_only, week_start_dow, week_start_hour], sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def check_agg_valid(conn: sqlite3.Connection, param_hash: str) -> bool:
    """Check if the stored aggregation matches the current parameter hash."""
    try:
        row = conn.execute(
            "SELECT value FROM agg_config WHERE key = 'param_hash'"
        ).fetchone()
        return row is not None and row[0] == param_hash
    except sqlite3.OperationalError:
        return False


def build_aggregations(
    min_ms: int = 30000,
    exclude_skipped: bool = True,
    music_only: bool = True,
    week_start_dow: int = 4,
    week_start_hour: int = 0,
    progress_callback=None,
) -> dict[str, int]:
    """Build all 3 pre-aggregated weekly Billboard tables from the plays table.

    Called after import_data() completes. Drops existing agg data and rebuilds.
    Returns row counts for each agg table.
    """
    conn = get_db(readonly=False)

    # Build filtered base query
    f, fp = base_filters(
        min_ms=min_ms, exclude_skipped=exclude_skipped, music_only=music_only
    )
    where = f"WHERE {f}" if f else ""

    # Compute billboard_week inline (same logic as load_billboard_raw)
    days_back_expr = f"(ts_dow - {week_start_dow} + 7) % 7"
    boundary_adj = (
        f"CASE WHEN ts_dow = {week_start_dow} AND ts_hour < {week_start_hour} "
        f"THEN 7 ELSE {days_back_expr} END"
    )
    bw_expr = f"date(ts_date, '-' || ({boundary_adj}) || ' days')"

    # Clear old aggregations
    conn.execute("DELETE FROM agg_weekly_tracks")
    conn.execute("DELETE FROM agg_weekly_albums")
    conn.execute("DELETE FROM agg_weekly_artists")
    conn.execute("DELETE FROM agg_config")

    steps = ["单曲", "专辑", "艺人"]
    results = {}

    if progress_callback:
        progress_callback("构建预聚合表...", 0.0)

    # 1. Tracks
    sql_tracks = f"""
        INSERT INTO agg_weekly_tracks (billboard_week, track_id, play_count, total_ms)
        SELECT {bw_expr} AS billboard_week,
               p.track_id,
               COUNT(*) AS play_count,
               SUM(p.ms_played) AS total_ms
        FROM plays p
        {where}
        AND p.track_id IS NOT NULL
        GROUP BY billboard_week, p.track_id
    """
    conn.execute(sql_tracks, fp)
    conn.commit()
    count_t = conn.execute("SELECT COUNT(*) FROM agg_weekly_tracks").fetchone()[0]
    results["tracks"] = count_t
    if progress_callback:
        progress_callback("预聚合: 单曲完成", 0.33)

    # 2. Albums
    sql_albums = f"""
        INSERT INTO agg_weekly_albums (billboard_week, album_id, play_count, total_ms)
        SELECT {bw_expr} AS billboard_week,
               t.album_id,
               COUNT(*) AS play_count,
               SUM(p.ms_played) AS total_ms
        FROM plays p
        JOIN tracks t ON p.track_id = t.track_id
        {where}
        AND t.album_id IS NOT NULL
        GROUP BY billboard_week, t.album_id
    """
    conn.execute(sql_albums, fp)
    conn.commit()
    count_a = conn.execute("SELECT COUNT(*) FROM agg_weekly_albums").fetchone()[0]
    results["albums"] = count_a
    if progress_callback:
        progress_callback("预聚合: 专辑完成", 0.66)

    # 3. Artists
    sql_artists = f"""
        INSERT INTO agg_weekly_artists (billboard_week, artist_id, play_count, total_ms)
        SELECT {bw_expr} AS billboard_week,
               t.artist_id,
               COUNT(*) AS play_count,
               SUM(p.ms_played) AS total_ms
        FROM plays p
        JOIN tracks t ON p.track_id = t.track_id
        {where}
        AND t.artist_id IS NOT NULL
        GROUP BY billboard_week, t.artist_id
    """
    conn.execute(sql_artists, fp)
    conn.commit()
    count_ar = conn.execute("SELECT COUNT(*) FROM agg_weekly_artists").fetchone()[0]
    results["artists"] = count_ar
    if progress_callback:
        progress_callback("预聚合: 艺人完成", 1.0)

    # Store param hash
    param_hash = _agg_param_hash(min_ms, exclude_skipped, music_only, week_start_dow, week_start_hour)
    conn.execute(
        "INSERT OR REPLACE INTO agg_config(key, value) VALUES ('param_hash', ?)",
        (param_hash,),
    )
    conn.commit()
    conn.close()

    return results


def load_agg_weekly_tracks(conn: sqlite3.Connection) -> "pd.DataFrame":
    """Load pre-aggregated track-week data joined with dimension names."""
    import pandas as pd
    df = pd.read_sql_query(
        """SELECT awt.billboard_week, awt.track_id, t.track_name, a.artist_name,
                  al.album_name, awt.play_count, awt.total_ms
           FROM agg_weekly_tracks awt
           JOIN tracks t ON awt.track_id = t.track_id
           JOIN artists a ON t.artist_id = a.artist_id
           LEFT JOIN albums al ON t.album_id = al.album_id
           ORDER BY awt.billboard_week""",
        conn,
    )
    df["billboard_week"] = pd.to_datetime(df["billboard_week"]).dt.date
    return df


def load_agg_weekly_albums(conn: sqlite3.Connection) -> "pd.DataFrame":
    """Load pre-aggregated album-week data joined with dimension names."""
    import pandas as pd
    df = pd.read_sql_query(
        """SELECT awa.billboard_week, awa.album_id, al.album_name, a.artist_name,
                  awa.play_count, awa.total_ms
           FROM agg_weekly_albums awa
           JOIN albums al ON awa.album_id = al.album_id
           JOIN artists a ON al.artist_id = a.artist_id
           ORDER BY awa.billboard_week""",
        conn,
    )
    df["billboard_week"] = pd.to_datetime(df["billboard_week"]).dt.date
    return df


def load_agg_weekly_artists(conn: sqlite3.Connection) -> "pd.DataFrame":
    """Load pre-aggregated artist-week data joined with dimension names."""
    import pandas as pd
    df = pd.read_sql_query(
        """SELECT awar.billboard_week, awar.artist_id, a.artist_name,
                  awar.play_count, awar.total_ms
           FROM agg_weekly_artists awar
           JOIN artists a ON awar.artist_id = a.artist_id
           ORDER BY awar.billboard_week""",
        conn,
    )
    df["billboard_week"] = pd.to_datetime(df["billboard_week"]).dt.date
    return df
