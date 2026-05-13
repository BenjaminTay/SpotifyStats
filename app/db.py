"""SQLite database layer: schema, connection, and common query helpers."""

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
CREATE INDEX IF NOT EXISTS idx_tracks_artist  ON tracks(artist_id);
CREATE INDEX IF NOT EXISTS idx_tracks_album   ON tracks(album_id);
CREATE INDEX IF NOT EXISTS idx_albums_artist  ON albums(artist_id);
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
