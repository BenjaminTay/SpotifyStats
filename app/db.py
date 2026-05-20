"""SQLite database layer: schema, connection, and common query helpers."""

import hashlib
import json
import sqlite3
import os
from typing import Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "spotify_stats.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS artists (
    artist_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_name        TEXT NOT NULL UNIQUE,
    spotify_artist_id  TEXT,
    popularity         INTEGER,
    followers          INTEGER,
    genres             TEXT,
    image_url          TEXT
);

CREATE TABLE IF NOT EXISTS albums (
    album_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    album_name         TEXT NOT NULL,
    artist_id          INTEGER NOT NULL REFERENCES artists(artist_id),
    spotify_album_id   TEXT,
    album_type         TEXT,
    release_date       TEXT,
    popularity         INTEGER,
    label              TEXT,
    genres             TEXT,
    image_url          TEXT,
    UNIQUE(album_name, artist_id)
);

CREATE TABLE IF NOT EXISTS tracks (
    track_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    track_name         TEXT NOT NULL,
    artist_id          INTEGER NOT NULL REFERENCES artists(artist_id),
    album_id           INTEGER REFERENCES albums(album_id),
    spotify_track_uri  TEXT,
    duration_ms        INTEGER,
    popularity         INTEGER,
    explicit           INTEGER,
    track_number       INTEGER,
    disc_number        INTEGER,
    isrc               TEXT,
    spotify_album_id   TEXT,
    UNIQUE(artist_id, track_name)
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
CREATE INDEX IF NOT EXISTS idx_plays_ts ON plays(ts);
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

-- Spotify metadata tables (independent from import cycle, survive data re-imports)
CREATE TABLE IF NOT EXISTS spotify_track_meta (
    spotify_track_id   TEXT PRIMARY KEY,
    track_name         TEXT NOT NULL,
    duration_ms        INTEGER,
    popularity         INTEGER,
    explicit           INTEGER,
    track_number       INTEGER,
    disc_number        INTEGER,
    isrc               TEXT,
    spotify_album_id   TEXT
);

CREATE TABLE IF NOT EXISTS spotify_album_meta (
    spotify_album_id   TEXT PRIMARY KEY,
    album_name         TEXT NOT NULL,
    album_type         TEXT,
    release_date       TEXT,
    popularity         INTEGER,
    label              TEXT,
    genres             TEXT,
    image_url          TEXT
);

CREATE TABLE IF NOT EXISTS spotify_artist_meta (
    spotify_artist_id  TEXT PRIMARY KEY,
    artist_name        TEXT NOT NULL,
    popularity         INTEGER,
    followers          INTEGER,
    genres             TEXT,
    image_url          TEXT
);
"""


def get_db(readonly: bool = True) -> sqlite3.Connection:
    """Get a database connection. Thread-safe for Streamlit's execution model."""
    uri = f"file:{DB_PATH}?mode=ro" if readonly else DB_PATH
    conn = sqlite3.connect(uri, uri=True if readonly else False)
    conn.row_factory = sqlite3.Row
    if readonly:
        conn.execute("PRAGMA query_only = ON")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.OperationalError:
        pass  # read-only connection may not be able to set journal mode
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
    # 增量添加新列（SQLite 不支持 ADD COLUMN IF NOT EXISTS）
    _add_columns = [
        # tracks
        ("tracks", "duration_ms", "INTEGER"),
        ("tracks", "popularity", "INTEGER"),
        ("tracks", "explicit", "INTEGER"),
        ("tracks", "track_number", "INTEGER"),
        ("tracks", "disc_number", "INTEGER"),
        ("tracks", "isrc", "TEXT"),
        ("tracks", "spotify_album_id", "TEXT"),
        # albums
        ("albums", "spotify_album_id", "TEXT"),
        ("albums", "album_type", "TEXT"),
        ("albums", "release_date", "TEXT"),
        ("albums", "popularity", "INTEGER"),
        ("albums", "label", "TEXT"),
        ("albums", "genres", "TEXT"),
        ("albums", "image_url", "TEXT"),
        # artists
        ("artists", "spotify_artist_id", "TEXT"),
        ("artists", "popularity", "INTEGER"),
        ("artists", "followers", "INTEGER"),
        ("artists", "genres", "TEXT"),
        ("artists", "image_url", "TEXT"),
    ]
    for table, col, col_type in _add_columns:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass
    # Create UNIQUE indexes (safe after deduplication in import_data)
    try:
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tracks_artist_name ON tracks(artist_id, track_name)")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_albums_name_artist ON albums(album_name, artist_id)")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def base_filters(
    min_ms: int = 30000,
    music_only: bool = True,
    table_alias: str = "p",
) -> tuple[str, list[Any]]:
    """Return a WHERE clause fragment and parameters for the standard data filters.

    These filters define what counts as a "valid play":
      - Minimum ms_played threshold (the only reliable filter — skipped and
        reason_end fields reflect button presses, not listening behavior)
      - Exclude podcasts/audiobooks if `music_only` (track_id IS NOT NULL)

    Returns (sql_clause, params) that can be appended to a WHERE 1=1 query.
    """
    clauses = []
    params: list[Any] = []

    if min_ms > 0:
        clauses.append(f"{table_alias}.ms_played >= ?")
        params.append(min_ms)

    if music_only:
        clauses.append(f"{table_alias}.track_id IS NOT NULL")

    return " AND ".join(clauses), params


def merge_consecutive_plays(df: "pd.DataFrame", min_ms: int) -> "pd.DataFrame":
    """Merge consecutive plays of the same track into logical play counts.

    Consecutive rows with the same track_id are treated as one listening session.
    Logical play count = total_ms // duration_ms + (1 if remainder >= min_ms else 0).

    Rows with NULL/0 duration_ms are passed through unchanged (can't merge).
    Requires DataFrame sorted by ts, with columns: track_id, ms_played, duration_ms.
    """
    import pandas as pd

    if df.empty:
        return df

    df = df.copy()
    df["_merge_group"] = (df["track_id"] != df["track_id"].shift(1)).cumsum()

    result_rows = []
    for _gid, group in df.groupby("_merge_group", sort=False):
        duration = group["duration_ms"].iloc[0]
        total_ms_val = int(group["ms_played"].sum())

        if pd.isna(duration) or duration == 0:
            for _, row in group.iterrows():
                result_rows.append(row.to_dict())
            continue

        duration = int(duration)
        full_plays = total_ms_val // duration
        remainder = total_ms_val % duration

        count = full_plays
        if remainder >= min_ms:
            count += 1

        if count == 0:
            continue

        base_row = group.iloc[0].to_dict()
        for i in range(count):
            new_row = base_row.copy()
            new_row["ms_played"] = duration if i < full_plays else remainder
            result_rows.append(new_row)

    result = pd.DataFrame(result_rows)
    result = result.drop(columns=["_merge_group"], errors="ignore")
    return result


def _write_agg_batch(
    conn: sqlite3.Connection,
    table: str,
    rows: list[tuple],
    cols: list[str],
) -> None:
    """Batch insert pre-aggregated rows into a table."""
    placeholders = ",".join("?" * len(cols))
    sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
    for i in range(0, len(rows), 5000):
        conn.executemany(sql, rows[i : i + 5000])
    conn.commit()


def query_plays(
    conn: sqlite3.Connection,
    base_sql: str,
    extra_where: str = "",
    extra_params: Optional[list[Any]] = None,
    min_ms: int = 30000,
    music_only: bool = True,
    filtered: bool = True,
) -> list[sqlite3.Row]:
    """Execute a query against plays.

    When `filtered=True` (default), base_filters() are applied to count only valid
    plays. Set `filtered=False` to query raw data (e.g. for skip-rate analysis).
    `base_sql` should contain the SELECT and FROM clauses.
    """
    parts = [base_sql, "WHERE 1=1"]
    params: list[Any] = []

    if filtered:
        filters, filter_params = base_filters(
            min_ms=min_ms, music_only=music_only
        )
        if filters:
            parts.append(f"AND {filters}")
            params.extend(filter_params)
    else:
        if music_only:
            parts.append("AND p.track_id IS NOT NULL")

    if extra_where:
        parts.append(f"AND {extra_where}")
        if extra_params:
            params.extend(extra_params)

    sql = " ".join(parts)
    return conn.execute(sql, params).fetchall()


def load_plays(
    conn: sqlite3.Connection,
    columns: str = "*",
    extra_where: str = "",
    extra_params: Optional[list[Any]] = None,
    min_ms: int = 30000,
    music_only: bool = True,
    join_albums: bool = True,
    filtered: bool = True,
    merge_enabled: bool = True,
):
    """统一的播放数据加载函数，所有统计页面复用。

    内部封装 base_filters() + 标准 JOIN，返回 pd.DataFrame。
    filtered=False 可跳过 base_filters 获取原始数据（行为分析等）。
    columns="*" 时自动选择完整列集合，也可传入自定义列字符串。
    join_albums=False 可跳过 albums JOIN 减少查询开销。

    当 merge_enabled=True 时，先合并连续同曲目播放再过滤 ms_played，
    避免碎片化播放片段被误丢弃。
    """
    import pandas as pd

    params: list[Any] = []

    if filtered:
        if merge_enabled:
            # 先不过滤 ms_played：查全量数据 → 合并 → 再过滤
            f, fp = base_filters(min_ms=0, music_only=music_only)
        else:
            f, fp = base_filters(min_ms=min_ms, music_only=music_only)
        where = f"WHERE {f}" if f else ""
    else:
        where = "WHERE p.track_id IS NOT NULL" if music_only else ""
        fp = []

    if extra_where:
        where += f" AND {extra_where}" if where else f"WHERE {extra_where}"
    params = fp + (extra_params or [])

    if columns == "*":
        if join_albums:
            cols = "p.*, t.track_name, t.spotify_track_uri, a.artist_name, al.album_name"
        else:
            cols = "p.*, t.track_name, t.spotify_track_uri, a.artist_name"
        if filtered:
            cols += ", stm.duration_ms"
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
    if filtered:
        from_clause += (
            " LEFT JOIN spotify_track_meta stm "
            "ON REPLACE(t.spotify_track_uri, 'spotify:track:', '') = stm.spotify_track_id"
        )

    sql = f"SELECT {cols} {from_clause} {where} ORDER BY p.ts"
    df = pd.read_sql_query(sql, conn, params=params)

    if filtered and merge_enabled:
        df = merge_consecutive_plays(df, min_ms)
        if min_ms > 0:
            df = df[df["ms_played"] >= min_ms]

    return df

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
    music_only: bool,
    week_start_dow: int,
    week_start_hour: int,
) -> str:
    """Compute a content-hash of the parameters that affect aggregation results."""
    payload = json.dumps([min_ms, music_only, week_start_dow, week_start_hour], sort_keys=True)
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
    music_only: bool = True,
    week_start_dow: int = 4,
    week_start_hour: int = 0,
    progress_callback=None,
) -> dict[str, int]:
    """Build all 3 pre-aggregated weekly Billboard tables from the plays table.

    Called after import_data() completes. Drops existing agg data and rebuilds.
    Uses pandas pipeline to apply merge_consecutive_plays() before aggregation.
    Returns row counts for each agg table.
    """
    import pandas as pd

    conn = get_db(readonly=False)

    f, fp = base_filters(min_ms=0, music_only=music_only)
    where = f"WHERE {f}" if f else ""

    # Load raw data with track dimensions needed for merge and aggregation
    # (ms_played filter is applied AFTER merge to preserve short fragments)
    df = pd.read_sql_query(
        f"""SELECT p.ts, p.ts_date, p.ts_dow, p.ts_hour, p.ms_played, p.track_id,
                   t.album_id, t.artist_id, stm.duration_ms
            FROM plays p
            JOIN tracks t ON p.track_id = t.track_id
            LEFT JOIN spotify_track_meta stm
              ON REPLACE(t.spotify_track_uri, 'spotify:track:', '') = stm.spotify_track_id
            {where}
            ORDER BY p.ts""",
        conn,
        params=fp,
    )

    if df.empty:
        conn.execute("DELETE FROM agg_weekly_tracks")
        conn.execute("DELETE FROM agg_weekly_albums")
        conn.execute("DELETE FROM agg_weekly_artists")
        conn.execute("DELETE FROM agg_config")
        conn.commit()
        conn.close()
        return {"tracks": 0, "albums": 0, "artists": 0}

    if progress_callback:
        progress_callback("合并连续播放...", 0.0)

    # Compute billboard_week in pandas
    df["days_back"] = (df["ts_dow"] - week_start_dow) % 7
    mask_before = (df["ts_dow"] == week_start_dow) & (df["ts_hour"] < week_start_hour)
    df.loc[mask_before, "days_back"] = 7
    df["ts_date_dt"] = pd.to_datetime(df["ts_date"])
    df["billboard_week"] = (
        df["ts_date_dt"] - pd.to_timedelta(df["days_back"], unit="D")
    ).dt.date

    # Merge consecutive same-track plays, then apply ms_played threshold
    df = merge_consecutive_plays(df, min_ms)
    if min_ms > 0:
        df = df[df["ms_played"] >= min_ms]

    if df.empty:
        conn.execute("DELETE FROM agg_weekly_tracks")
        conn.execute("DELETE FROM agg_weekly_albums")
        conn.execute("DELETE FROM agg_weekly_artists")
        conn.execute("DELETE FROM agg_config")
        conn.commit()
        conn.close()
        return {"tracks": 0, "albums": 0, "artists": 0}

    # Clear old aggregations
    conn.execute("DELETE FROM agg_weekly_tracks")
    conn.execute("DELETE FROM agg_weekly_albums")
    conn.execute("DELETE FROM agg_weekly_artists")
    conn.execute("DELETE FROM agg_config")
    conn.commit()

    results = {}

    # 1. Tracks
    if progress_callback:
        progress_callback("预聚合: 单曲...", 0.0)
    tracks_agg = (
        df.groupby(["billboard_week", "track_id"])
        .agg(play_count=("ms_played", "count"), total_ms=("ms_played", "sum"))
        .reset_index()
    )
    t_rows = [
        (str(r.billboard_week), int(r.track_id), int(r.play_count), int(r.total_ms))
        for r in tracks_agg.itertuples(index=False)
    ]
    _write_agg_batch(conn, "agg_weekly_tracks", t_rows,
                     ["billboard_week", "track_id", "play_count", "total_ms"])
    results["tracks"] = len(t_rows)
    if progress_callback:
        progress_callback("预聚合: 单曲完成", 0.33)

    # 2. Albums
    if progress_callback:
        progress_callback("预聚合: 专辑...", 0.33)
    df_album = df[df["album_id"].notna()]
    if not df_album.empty:
        albums_agg = (
            df_album.groupby(["billboard_week", "album_id"])
            .agg(play_count=("ms_played", "count"), total_ms=("ms_played", "sum"))
            .reset_index()
        )
        a_rows = [
            (str(r.billboard_week), int(r.album_id), int(r.play_count), int(r.total_ms))
            for r in albums_agg.itertuples(index=False)
        ]
        _write_agg_batch(conn, "agg_weekly_albums", a_rows,
                         ["billboard_week", "album_id", "play_count", "total_ms"])
        results["albums"] = len(a_rows)
    else:
        results["albums"] = 0
    if progress_callback:
        progress_callback("预聚合: 专辑完成", 0.66)

    # 3. Artists
    if progress_callback:
        progress_callback("预聚合: 艺人...", 0.66)
    artists_agg = (
        df.groupby(["billboard_week", "artist_id"])
        .agg(play_count=("ms_played", "count"), total_ms=("ms_played", "sum"))
        .reset_index()
    )
    ar_rows = [
        (str(r.billboard_week), int(r.artist_id), int(r.play_count), int(r.total_ms))
        for r in artists_agg.itertuples(index=False)
    ]
    _write_agg_batch(conn, "agg_weekly_artists", ar_rows,
                     ["billboard_week", "artist_id", "play_count", "total_ms"])
    results["artists"] = len(ar_rows)
    if progress_callback:
        progress_callback("预聚合: 艺人完成", 1.0)

    # Store param hash
    param_hash = _agg_param_hash(min_ms, music_only, week_start_dow, week_start_hour)
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
