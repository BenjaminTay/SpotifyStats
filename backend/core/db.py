"""SQLite database layer: schema, connection, and common query helpers."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from functools import lru_cache
from typing import Any

from backend.core.cache import singleflight

# Column downcast map: common int64 columns → int32 (safe within typical data sizes)
_INT32_COLUMNS = frozenset(
    {
        "track_id",
        "artist_id",
        "album_id",
        "source_album_id",
        "ms_played",
        "play_count",
        "total_ms",
        "duration_ms",
        "skipped",
        "shuffle",
        "offline",
        "incognito_mode",
        "ts_year",
        "ts_month",
        "ts_week",
        "ts_dow",
        "ts_hour",
        "play_id",
        "disc_number",
        "track_number",
    }
)


def _downcast_ints(df):
    """Downcast int64 columns to int32 where safe, saving ~50% memory for those columns."""
    import numpy as np
    import pandas as pd  # noqa: F811 — needed at call time, module-level import cyclic

    for col in df.columns:
        if col not in _INT32_COLUMNS:
            continue
        if df[col].dtype != np.int64:
            continue
        mn, mx = df[col].min(), df[col].max()
        if (
            pd.notna(mn)
            and pd.notna(mx)
            and mn >= np.iinfo(np.int32).min
            and mx <= np.iinfo(np.int32).max
        ):
            df[col] = df[col].astype(np.int32)
    return df


# backend/core/ → os.path.dirname x3 = project root
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "spotify_stats.db"
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS artists (
    artist_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_name        TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS albums (
    album_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    album_name         TEXT NOT NULL,
    artist_id          INTEGER NOT NULL REFERENCES artists(artist_id),
    UNIQUE(album_name, artist_id)
);

CREATE TABLE IF NOT EXISTS tracks (
    track_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    track_name         TEXT NOT NULL,
    artist_id          INTEGER NOT NULL REFERENCES artists(artist_id),
    album_id           INTEGER REFERENCES albums(album_id),
    spotify_track_uri  TEXT,
    spotify_track_id   TEXT,
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
    incognito_mode   INTEGER NOT NULL DEFAULT 0,
    content_type     TEXT NOT NULL DEFAULT 'audio',
    source_album_id  INTEGER REFERENCES albums(album_id),
    spotify_track_id_at_play TEXT,
    spotify_album_id_at_play TEXT
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
CREATE INDEX IF NOT EXISTS idx_plays_source_album ON plays(source_album_id);
CREATE INDEX IF NOT EXISTS idx_plays_spotify_track_at_play ON plays(spotify_track_id_at_play);
CREATE INDEX IF NOT EXISTS idx_plays_spotify_album_at_play ON plays(spotify_album_id_at_play);
CREATE INDEX IF NOT EXISTS idx_tracks_name ON tracks(track_name);
CREATE INDEX IF NOT EXISTS idx_tracks_spotify_track_id ON tracks(spotify_track_id);
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

CREATE TABLE IF NOT EXISTS track_artists (
    track_id INTEGER NOT NULL REFERENCES tracks(track_id),
    artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
    role TEXT NOT NULL DEFAULT 'primary',
    UNIQUE(track_id, artist_id)
);
CREATE INDEX IF NOT EXISTS idx_track_artists_track ON track_artists(track_id);
CREATE INDEX IF NOT EXISTS idx_track_artists_artist ON track_artists(artist_id);

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

CREATE TABLE IF NOT EXISTS agg_weekly_track_sources (
    billboard_week TEXT NOT NULL,
    play_date TEXT NOT NULL,
    track_id INTEGER NOT NULL,
    source_album_id INTEGER NOT NULL DEFAULT 0,
    play_count INTEGER NOT NULL,
    total_ms INTEGER NOT NULL,
    PRIMARY KEY (billboard_week, play_date, track_id, source_album_id)
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

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agg_wt_week ON agg_weekly_tracks(billboard_week);
CREATE INDEX IF NOT EXISTS idx_agg_wa_week ON agg_weekly_albums(billboard_week);
CREATE INDEX IF NOT EXISTS idx_agg_wts_week ON agg_weekly_track_sources(billboard_week);
CREATE INDEX IF NOT EXISTS idx_agg_wts_track ON agg_weekly_track_sources(track_id);
CREATE INDEX IF NOT EXISTS idx_agg_war_week ON agg_weekly_artists(billboard_week);

-- Version merging: group different album/track releases into canonical entities
CREATE TABLE IF NOT EXISTS release_groups (
    group_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name    TEXT NOT NULL,
    artist_id         INTEGER NOT NULL REFERENCES artists(artist_id),
    primary_album_id  INTEGER REFERENCES albums(album_id),
    scope             TEXT NOT NULL DEFAULT 'release' CHECK(scope IN ('release', 'composition')),
    parent_group_id   INTEGER REFERENCES release_groups(group_id),
    is_manual         INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT DEFAULT (datetime('now')),
    UNIQUE(canonical_name, artist_id, scope)
);

CREATE TABLE IF NOT EXISTS release_group_members (
    group_id   INTEGER REFERENCES release_groups(group_id),
    album_id   INTEGER REFERENCES albums(album_id),
    UNIQUE(group_id, album_id)
);

CREATE INDEX IF NOT EXISTS idx_rgm_album ON release_group_members(album_id);
CREATE INDEX IF NOT EXISTS idx_rg_artist ON release_groups(artist_id);
CREATE INDEX IF NOT EXISTS idx_rg_scope ON release_groups(scope);
CREATE INDEX IF NOT EXISTS idx_rg_parent ON release_groups(parent_group_id);

-- Track version groups (L1/L2/L3 merge)
CREATE TABLE IF NOT EXISTS track_groups (
    group_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name    TEXT NOT NULL,
    primary_track_id  INTEGER REFERENCES tracks(track_id),
    scope             TEXT NOT NULL DEFAULT 'recording' CHECK(scope IN ('recording', 'composition')),
    parent_group_id   INTEGER REFERENCES track_groups(group_id),
    is_manual         INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT DEFAULT (datetime('now')),
    UNIQUE(canonical_name, scope)
);

CREATE TABLE IF NOT EXISTS track_group_members (
    group_id   INTEGER REFERENCES track_groups(group_id),
    track_id   INTEGER REFERENCES tracks(track_id),
    UNIQUE(group_id, track_id)
);

CREATE INDEX IF NOT EXISTS idx_track_groups_scope ON track_groups(scope);
CREATE INDEX IF NOT EXISTS idx_track_groups_parent ON track_groups(parent_group_id);
CREATE INDEX IF NOT EXISTS idx_track_group_members_track ON track_group_members(track_id);

-- Album projects (statistics-level album membership)
CREATE TABLE IF NOT EXISTS album_projects (
    project_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name    TEXT NOT NULL,
    artist_id         INTEGER REFERENCES artists(artist_id),
    primary_album_id  INTEGER REFERENCES albums(album_id),
    release_date      TEXT,
    scope             TEXT NOT NULL DEFAULT 'release',
    project_type      TEXT NOT NULL DEFAULT 'album',
    include_in_charts INTEGER NOT NULL DEFAULT 1,
    is_manual         INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(canonical_name, artist_id, scope)
);

CREATE TABLE IF NOT EXISTS album_project_albums (
    project_id    INTEGER NOT NULL REFERENCES album_projects(project_id),
    album_id      INTEGER NOT NULL REFERENCES albums(album_id),
    role          TEXT NOT NULL DEFAULT 'member',
    source_bucket TEXT NOT NULL DEFAULT 'other',
    inferred      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(project_id, album_id)
);

CREATE TABLE IF NOT EXISTS album_project_tracks (
    project_id       INTEGER NOT NULL REFERENCES album_projects(project_id),
    track_id         INTEGER NOT NULL REFERENCES tracks(track_id),
    membership_role  TEXT NOT NULL DEFAULT 'standard',
    min_merge_level  INTEGER NOT NULL DEFAULT 2,
    source_album_id  INTEGER REFERENCES albums(album_id),
    is_exclusive     INTEGER NOT NULL DEFAULT 0,
    inferred         INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(project_id, track_id, min_merge_level)
);

CREATE INDEX IF NOT EXISTS idx_album_projects_artist ON album_projects(artist_id);
CREATE INDEX IF NOT EXISTS idx_album_projects_primary_album ON album_projects(primary_album_id);
CREATE INDEX IF NOT EXISTS idx_album_project_albums_album ON album_project_albums(album_id);
CREATE INDEX IF NOT EXISTS idx_album_project_tracks_track ON album_project_tracks(track_id);

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

CREATE INDEX IF NOT EXISTS idx_spotify_track_meta_album ON spotify_track_meta(spotify_album_id);

CREATE TABLE IF NOT EXISTS spotify_album_meta (
    spotify_album_id   TEXT PRIMARY KEY,
    album_name         TEXT NOT NULL,
    album_type         TEXT,
    release_date       TEXT,
    popularity         INTEGER,
    label              TEXT,
    genres             TEXT,
    image_url          TEXT,
    album_artists      TEXT,
    total_tracks       INTEGER,
    track_list         TEXT    -- JSON array of Spotify track IDs in this album
);

CREATE INDEX IF NOT EXISTS idx_spotify_album_meta_name ON spotify_album_meta(album_name);

CREATE TABLE IF NOT EXISTS album_spotify_links (
    album_id INTEGER NOT NULL REFERENCES albums(album_id),
    spotify_album_id TEXT NOT NULL REFERENCES spotify_album_meta(spotify_album_id),
    evidence TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.0,
    play_count INTEGER NOT NULL DEFAULT 0,
    track_count INTEGER NOT NULL DEFAULT 0,
    first_seen TEXT,
    last_seen TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(album_id, spotify_album_id, evidence)
);

CREATE INDEX IF NOT EXISTS idx_album_spotify_links_album ON album_spotify_links(album_id);
CREATE INDEX IF NOT EXISTS idx_album_spotify_links_spotify_album ON album_spotify_links(spotify_album_id);

CREATE TABLE IF NOT EXISTS spotify_artist_meta (
    spotify_artist_id  TEXT PRIMARY KEY,
    artist_name        TEXT NOT NULL,
    popularity         INTEGER,
    followers          INTEGER,
    genres             TEXT,
    image_url          TEXT
);

CREATE INDEX IF NOT EXISTS idx_spotify_artist_meta_name ON spotify_artist_meta(artist_name);

CREATE TABLE IF NOT EXISTS artist_genre_sources (
    source_id INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_name TEXT NOT NULL,
    spotify_artist_id TEXT,
    source TEXT NOT NULL,
    source_key TEXT NOT NULL,
    raw_genres_json TEXT,
    normalized_genres_json TEXT NOT NULL,
    primary_genre TEXT,
    language TEXT,
    region TEXT,
    confidence REAL NOT NULL DEFAULT 0.0,
    evidence_url TEXT,
    evidence_summary TEXT,
    status TEXT NOT NULL DEFAULT 'approved',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(artist_name, source, source_key)
);

CREATE INDEX IF NOT EXISTS idx_artist_genre_sources_artist
ON artist_genre_sources(artist_name, status, confidence);

CREATE TABLE IF NOT EXISTS artist_genre_overrides (
    artist_name TEXT PRIMARY KEY,
    normalized_genres_json TEXT NOT NULL,
    primary_genre TEXT,
    language TEXT,
    region TEXT,
    confidence REAL NOT NULL DEFAULT 1.0,
    note TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS artist_genre_review_queue (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_name TEXT NOT NULL,
    play_hours REAL NOT NULL DEFAULT 0,
    reason TEXT NOT NULL,
    suggested_source_id INTEGER REFERENCES artist_genre_sources(source_id),
    status TEXT NOT NULL DEFAULT 'open',
    reviewed_by TEXT,
    reviewed_at TEXT,
    resolution_note TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS artist_identity_aliases (
    alias_artist_id INTEGER PRIMARY KEY REFERENCES artists(artist_id),
    canonical_artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (alias_artist_id != canonical_artist_id)
);

CREATE TABLE IF NOT EXISTS artist_metadata_attribution_overrides (
    track_id INTEGER PRIMARY KEY REFERENCES tracks(track_id),
    artist_id INTEGER REFERENCES artists(artist_id),
    reason TEXT NOT NULL,
    evidence_url TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── Genius Lyrics Cache ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS track_lyrics (
    track_id       INTEGER PRIMARY KEY,
    genius_song_id INTEGER,
    lyrics_text    TEXT,
    genius_url     TEXT,
    fetched_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (track_id) REFERENCES tracks(track_id)
);

-- ── Spotify Account Data ─────────────────────────────────────────────
-- Wrapped 2025
CREATE TABLE IF NOT EXISTS wrapped_top_artists (
    rank INTEGER,
    artist_uri TEXT,
    ms_played INTEGER,
    percentile REAL
);

CREATE TABLE IF NOT EXISTS wrapped_top_tracks (
    rank INTEGER,
    track_uri TEXT,
    play_count INTEGER,
    ms_played INTEGER
);

CREATE TABLE IF NOT EXISTS wrapped_top_albums (
    rank INTEGER,
    album_uri TEXT,
    play_count INTEGER,
    ms_played INTEGER
);

CREATE TABLE IF NOT EXISTS wrapped_artist_race (
    artist_uri TEXT,
    month TEXT,
    rank INTEGER,
    trail_size TEXT
);

CREATE TABLE IF NOT EXISTS wrapped_clubs (
    club_name TEXT,
    percent_in_club REAL,
    role TEXT,
    artist_uri TEXT
);

CREATE TABLE IF NOT EXISTS wrapped_party (
    metric TEXT PRIMARY KEY,
    value REAL
);

CREATE TABLE IF NOT EXISTS wrapped_listening_age (
    listening_age INTEGER,
    window_start_year INTEGER,
    decade_phase TEXT
);

CREATE TABLE IF NOT EXISTS wrapped_archive_reports (
    column_qualifier TEXT,
    title TEXT,
    description TEXT,
    reason TEXT,
    minutes_listened INTEGER,
    filed_under_tags TEXT
);

CREATE TABLE IF NOT EXISTS wrapped_top_genres (
    rank INTEGER,
    genre_uri TEXT
);

CREATE TABLE IF NOT EXISTS wrapped_top_podcasts (
    rank INTEGER,
    podcast_uri TEXT
);

-- Music Library
CREATE TABLE IF NOT EXISTS saved_tracks (
    track_uri TEXT PRIMARY KEY,
    track_name TEXT,
    artist_name TEXT,
    album_name TEXT,
    added_date TEXT,
    spotify_track_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_saved_tracks_spotify_track_id ON saved_tracks(spotify_track_id);

CREATE TABLE IF NOT EXISTS saved_albums (
    album_uri TEXT PRIMARY KEY,
    album_name TEXT,
    artist_name TEXT
);

CREATE TABLE IF NOT EXISTS saved_artists (
    artist_uri TEXT PRIMARY KEY,
    artist_name TEXT
);

CREATE TABLE IF NOT EXISTS saved_shows (
    show_uri TEXT PRIMARY KEY,
    show_name TEXT,
    publisher TEXT
);

CREATE TABLE IF NOT EXISTS banned_items (
    uri TEXT PRIMARY KEY,
    item_name TEXT,
    item_type TEXT
);

CREATE TABLE IF NOT EXISTS playlists (
    playlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
    playlist_name TEXT NOT NULL,
    last_modified_date TEXT,
    track_count INTEGER,
    follower_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS playlist_tracks (
    playlist_id INTEGER REFERENCES playlists(playlist_id),
    track_uri TEXT,
    track_name TEXT,
    artist_name TEXT,
    album_name TEXT,
    added_date TEXT
);
CREATE INDEX IF NOT EXISTS idx_playlist_tracks_uri ON playlist_tracks(track_uri);

-- Search
CREATE TABLE IF NOT EXISTS search_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_text TEXT NOT NULL,
    search_time_utc TEXT NOT NULL,
    search_date TEXT NOT NULL,
    search_hour INTEGER NOT NULL,
    search_dow INTEGER NOT NULL,
    platform TEXT,
    interaction_uri TEXT
);
CREATE INDEX IF NOT EXISTS idx_search_date ON search_queries(search_date);
CREATE INDEX IF NOT EXISTS idx_search_query ON search_queries(query_text);

-- Insights & Highlights
CREATE TABLE IF NOT EXISTS inferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inference_text TEXT NOT NULL,
    category TEXT
);

CREATE TABLE IF NOT EXISTS sound_capsule_highlights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    highlight_date TEXT NOT NULL,
    highlight_type TEXT NOT NULL,
    entity_name TEXT,
    detail_json TEXT
);

CREATE TABLE IF NOT EXISTS sound_capsule_daily (
    date TEXT PRIMARY KEY,
    stream_count INTEGER,
    seconds_played INTEGER,
    top_data_json TEXT
);

CREATE TABLE IF NOT EXISTS marquee_impressions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_name TEXT,
    segment TEXT
);
CREATE INDEX IF NOT EXISTS idx_marquee_artist ON marquee_impressions(artist_name);

-- Podcast
CREATE TABLE IF NOT EXISTS podcast_plays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    end_time TEXT NOT NULL,
    podcast_name TEXT NOT NULL,
    episode_name TEXT NOT NULL,
    ms_played INTEGER NOT NULL,
    play_date TEXT NOT NULL,
    play_hour INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS podcast_interactions (
    interaction_type TEXT NOT NULL,
    entity_uri TEXT,
    content_json TEXT,
    created_at TEXT
);

-- User Profile
CREATE TABLE IF NOT EXISTS user_profile (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS llm_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_name TEXT NOT NULL UNIQUE,
    llm_provider TEXT NOT NULL DEFAULT 'deepseek',
    llm_model TEXT NOT NULL DEFAULT '',
    llm_api_key TEXT NOT NULL DEFAULT '',
    llm_base_url TEXT NOT NULL DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_follows (
    relationship_type TEXT NOT NULL,
    display_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message TEXT,
    created_timestamp TEXT
);

-- Background job queue (for async enrichment & cover downloads)
CREATE TABLE IF NOT EXISTS background_jobs (
    job_id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    payload_json TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT,
    updated_at TEXT,
    attempts INTEGER DEFAULT 0,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_bg_jobs_status ON background_jobs(status);
CREATE INDEX IF NOT EXISTS idx_bg_jobs_entity ON background_jobs(job_type, entity_id);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT '新对话',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'error')),
    content TEXT NOT NULL,
    meta_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated ON chat_sessions(updated_at DESC);

CREATE TABLE IF NOT EXISTS wikipedia_cache (
    cache_key TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    fetched_at REAL NOT NULL
);
"""


def get_db(readonly: bool = True) -> sqlite3.Connection:
    """Get a database connection."""
    # Ensure parent directory exists — CI and fresh checkouts may not have data/
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        try:
            os.makedirs(db_dir, exist_ok=True)
        except OSError:
            pass  # allow sqlite3.connect to raise the original error

    # check_same_thread=False 是必需的：
    # Starlette 的 generator 依赖在后台任务中执行 finally 清理代码，
    # 该任务可能运行在不同于创建连接的线程中（即使只是 close() 也会报错）。
    # 由于每个请求都创建独立的连接，不存在真正的跨线程并发使用同一连接，
    # 因此禁用线程检查是安全的。
    if readonly:
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")
    else:
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db() -> None:
    """Create tables and indexes if they don't exist."""
    conn = get_db(readonly=False)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def ensure_schema() -> None:
    """Ensure all tables/indexes exist (safe to call repeatedly).

    Delegates to the versioned migration system. Kept for backward
    compatibility with callers in import_data, scripts, and frozen
    Streamlit app code.
    """
    from backend.core.migrations import run_migrations

    run_migrations()


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


def merge_consecutive_plays(
    df: pd.DataFrame,
    min_ms: int,
    max_gap_minutes: int | None = None,
    boundary_column: str | list[str] | None = None,
) -> pd.DataFrame:
    """Merge consecutive plays of the same track into logical play counts.

    Consecutive rows with the same track_id are treated as one listening session.
    Logical play count = total_ms // duration_ms + (1 if remainder >= min_ms else 0).

    Group boundaries are introduced by:
    - track_id change (always)
    - timestamp gap > max_gap_minutes (when provided)
    - boundary_column value change (when provided, e.g. source_album_id).
      Accepts a single column name or a list of column names; when a list is
      given, a change in ANY column starts a new merge group (OR semantics).

    Rows with NULL/0 duration_ms are passed through unchanged (can't merge).
    Requires DataFrame sorted by ts, with columns: track_id, ms_played, duration_ms.
    """
    import numpy as np
    import pandas as pd

    if df.empty:
        return df

    df = df.copy()

    track_changed = df["track_id"] != df["track_id"].shift(1)

    gap_changed = pd.Series(False, index=df.index)
    if max_gap_minutes is not None and "ts" in df.columns:
        ts = pd.to_datetime(df["ts"])
        gap_changed = ts.diff().dt.total_seconds().gt(max_gap_minutes * 60).fillna(False)

    boundary_changed = pd.Series(False, index=df.index)
    if boundary_column:
        columns = [boundary_column] if isinstance(boundary_column, str) else boundary_column
        for col in columns:
            if col in df.columns:
                col_vals = df[col].fillna(-1)
                boundary_changed = boundary_changed | (col_vals != col_vals.shift(1))

    df["_merge_group"] = (track_changed | gap_changed | boundary_changed).cumsum()

    grouped = df.groupby("_merge_group", sort=False)
    first_rows = grouped.head(1).set_index("_merge_group", drop=False)
    group_totals = grouped["ms_played"].sum()
    group_durations = first_rows["duration_ms"]

    valid_duration = group_durations.notna() & group_durations.ne(0)
    result_frames = []

    valid_group_ids = group_durations.index[valid_duration]
    if len(valid_group_ids) > 0:
        totals = group_totals.loc[valid_group_ids].astype("int64")
        durations = group_durations.loc[valid_group_ids].astype("int64")
        full_plays = totals // durations
        remainders = totals % durations
        output_counts = full_plays + remainders.ge(min_ms).astype("int64")
        output_counts = output_counts[output_counts > 0]

        if not output_counts.empty:
            repeated_group_ids = np.repeat(output_counts.index.to_numpy(), output_counts.to_numpy())
            output_seq = np.concatenate(
                [np.arange(count, dtype="int64") for count in output_counts.to_numpy()]
            )
            repeated_rows = first_rows.loc[repeated_group_ids].copy()
            repeated_rows["_merge_seq"] = output_seq

            repeated_full_plays = np.repeat(
                full_plays.loc[output_counts.index].to_numpy(), output_counts.to_numpy()
            )
            repeated_durations = np.repeat(
                durations.loc[output_counts.index].to_numpy(), output_counts.to_numpy()
            )
            repeated_remainders = np.repeat(
                remainders.loc[output_counts.index].to_numpy(), output_counts.to_numpy()
            )
            repeated_rows["ms_played"] = np.where(
                output_seq < repeated_full_plays,
                repeated_durations,
                repeated_remainders,
            )
            result_frames.append(repeated_rows)

    invalid_group_ids = group_durations.index[~valid_duration]
    if len(invalid_group_ids) > 0:
        invalid_rows = df[df["_merge_group"].isin(invalid_group_ids)].copy()
        invalid_rows["_merge_seq"] = invalid_rows.groupby("_merge_group", sort=False).cumcount()
        result_frames.append(invalid_rows)

    if not result_frames:
        return df.iloc[0:0].drop(columns=["_merge_group"], errors="ignore")

    result = pd.concat(result_frames, axis=0, ignore_index=True, sort=False)
    result = result.sort_values(["_merge_group", "_merge_seq"], kind="stable")
    result = result.drop(columns=["_merge_group", "_merge_seq"], errors="ignore")
    return result.reset_index(drop=True)


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
    extra_params: list[Any] | None = None,
    min_ms: int = 30000,
    music_only: bool = True,
    filtered: bool = True,
) -> list[sqlite3.Row]:
    """Execute a query against plays.

    When `filtered=True` (default), base_filters() are applied to count only valid
    plays. Set `filtered=False` to query raw data.
    `base_sql` should contain the SELECT and FROM clauses.
    """
    parts = [base_sql, "WHERE 1=1"]
    params: list[Any] = []

    if filtered:
        filters, filter_params = base_filters(min_ms=min_ms, music_only=music_only)
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


@singleflight
@lru_cache(maxsize=16)
def _load_plays_cached(
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    filtered: bool,
    join_albums: bool,
    columns: str,
    extra_where: str,
    extra_params: tuple,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = None,
    boundary_column: str | None = None,
) -> pd.DataFrame:
    """Cacheable inner loader — connection is created internally so it
    doesn't appear in the LRU cache key."""
    import pandas as pd

    conn = get_db()
    try:
        params: list[Any] = []

        if filtered:
            if merge_enabled:
                f, fp = base_filters(min_ms=0, music_only=music_only)
            else:
                f, fp = base_filters(min_ms=min_ms, music_only=music_only)
            where = f"WHERE {f}" if f else ""
        else:
            where = "WHERE p.track_id IS NOT NULL" if music_only else ""
            fp = []

        if extra_where:
            where += f" AND {extra_where}" if where else f"WHERE {extra_where}"
        params = fp + list(extra_params)

        if columns == "*":
            if join_albums:
                cols = "p.*, t.track_name, t.spotify_track_uri, t.album_id AS track_album_id, a.artist_name, al.album_name, al_src.album_name AS source_album_name"
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
                "LEFT JOIN albums al ON t.album_id = al.album_id "
                "LEFT JOIN albums al_src ON p.source_album_id = al_src.album_id"
            )
        else:
            from_clause = (
                "FROM plays p "
                "LEFT JOIN tracks t ON p.track_id = t.track_id "
                "LEFT JOIN artists a ON t.artist_id = a.artist_id"
            )
        if filtered:
            from_clause += (
                " LEFT JOIN spotify_track_meta stm ON t.spotify_track_id = stm.spotify_track_id"
            )

        sql = f"SELECT {cols} {from_clause} {where} ORDER BY p.ts"
        df = pd.read_sql_query(sql, conn, params=params)

        if filtered and merge_enabled:
            df = merge_consecutive_plays(
                df,
                min_ms,
                max_gap_minutes=max_merge_gap_minutes,
                boundary_column=boundary_column,
            )
            if min_ms > 0:
                from backend.domains.playback.counting import filter_effective_plays

                df = filter_effective_plays(df, min_ms=min_ms, dynamic_threshold=dynamic_threshold)

        return _downcast_ints(df)
    finally:
        conn.close()


def load_plays(
    conn: sqlite3.Connection,
    columns: str = "*",
    extra_where: str = "",
    extra_params: list[Any] | None = None,
    min_ms: int = 30000,
    music_only: bool = True,
    join_albums: bool = True,
    filtered: bool = True,
    merge_enabled: bool = True,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = None,
    boundary_column: str | None = "source_album_id",
):
    """统一的播放数据加载函数，所有统计页面复用。

    内部封装 base_filters() + 标准 JOIN，返回 pd.DataFrame。
    结果按参数缓存于内存中，避免重复 SQL 查询和 merge 计算。
    filtered=False 可跳过 base_filters 获取原始数据（行为分析等）。
    columns="*" 时自动选择完整列集合，也可传入自定义列字符串。
    join_albums=False 可跳过 albums JOIN 减少查询开销。

    当 merge_enabled=True 时，先合并连续同曲目播放再过滤 ms_played，
    避免碎片化播放片段被误丢弃。

    dynamic_threshold=True 启用动态有效播放阈值（长曲目需更高播放比例）。
    max_merge_gap_minutes 设置连续播放合并的最大间隔，超时则视为不同 session。
    boundary_column 默认 "source_album_id"，跨 source album 的连续同曲不合并；
    列不存在时自动忽略。
    """
    return _load_plays_cached(
        min_ms=min_ms,
        music_only=music_only,
        merge_enabled=merge_enabled,
        filtered=filtered,
        join_albums=join_albums,
        columns=columns,
        extra_where=extra_where,
        extra_params=tuple(extra_params or ()),
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        boundary_column=boundary_column,
    ).copy()


@singleflight
@lru_cache(maxsize=16)
def _load_plays_for_artists_cached(
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    filtered: bool,
    join_albums: bool,
    columns: str,
    extra_where: str,
    extra_params: tuple,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = None,
    boundary_column: str | None = None,
) -> pd.DataFrame:
    """Same as _load_plays_cached but fans out through track_artists after merge
    so featured artists get their own rows. One play on a multi-artist track
    produces one row per credited artist.

    Merge happens BEFORE fan-out to keep merge_consecutive_plays correct.
    Only use for artist-grouped statistics.
    """
    import pandas as pd

    conn = get_db()
    try:
        params: list[Any] = []

        if filtered:
            if merge_enabled:
                f, fp = base_filters(min_ms=0, music_only=music_only)
            else:
                f, fp = base_filters(min_ms=min_ms, music_only=music_only)
            where = f"WHERE {f}" if f else ""
        else:
            where = "WHERE p.track_id IS NOT NULL" if music_only else ""
            fp = []

        if extra_where:
            where += f" AND {extra_where}" if where else f"WHERE {extra_where}"
        params = fp + list(extra_params)

        if columns == "*":
            if join_albums:
                cols = "p.*, t.track_name, t.spotify_track_uri, a.artist_name, al.album_name"
            else:
                cols = "p.*, t.track_name, t.spotify_track_uri, a.artist_name"
            if filtered:
                cols += ", stm.duration_ms"
        else:
            cols = columns

        # Step 1: Load single-artist data (same as _load_plays_cached)
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
                " LEFT JOIN spotify_track_meta stm ON t.spotify_track_id = stm.spotify_track_id"
            )

        sql = f"SELECT {cols} {from_clause} {where} ORDER BY p.ts"
        df = pd.read_sql_query(sql, conn, params=params)

        if filtered and merge_enabled:
            df = merge_consecutive_plays(
                df,
                min_ms,
                max_gap_minutes=max_merge_gap_minutes,
                boundary_column=boundary_column,
            )
            if min_ms > 0:
                from backend.domains.playback.counting import filter_effective_plays

                df = filter_effective_plays(df, min_ms=min_ms, dynamic_threshold=dynamic_threshold)

        # Step 2: Fan out through track_artists for multi-artist attribution
        track_artists_df = pd.read_sql_query("SELECT track_id, artist_id FROM track_artists", conn)
        # Drop the single-artist artist_name (will be replaced by fan-out join)
        df = df.drop(columns=["artist_name"], errors="ignore")
        df = df.merge(track_artists_df, on="track_id", how="inner")
        # Re-join artist names from the fanned-out artist_ids
        artists_df = pd.read_sql_query("SELECT artist_id, artist_name FROM artists", conn)
        df = df.merge(artists_df, on="artist_id", how="left")

        return _downcast_ints(df)
    finally:
        conn.close()


def load_plays_for_artists(
    conn: sqlite3.Connection,
    columns: str = "*",
    extra_where: str = "",
    extra_params: list[Any] | None = None,
    min_ms: int = 30000,
    music_only: bool = True,
    join_albums: bool = True,
    filtered: bool = True,
    merge_enabled: bool = True,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = None,
    boundary_column: str | None = "source_album_id",
):
    """Load plays with multi-artist fan-out for artist-statistics queries.

    Identical to load_plays() but joins through track_artists so each play
    produces one row per credited artist. artist_name comes from the
    track_artists join, not from tracks.artist_id.

    DO NOT USE for total play counts, track statistics, or album statistics
    — it duplicates rows for multi-artist tracks.
    """
    return _load_plays_for_artists_cached(
        min_ms=min_ms,
        music_only=music_only,
        merge_enabled=merge_enabled,
        filtered=filtered,
        join_albums=join_albums,
        columns=columns,
        extra_where=extra_where,
        extra_params=tuple(extra_params or ()),
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        boundary_column=boundary_column,
    ).copy()


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
# Track artist display helpers
# ═══════════════════════════════════════════════════════════════════════════


@lru_cache(maxsize=1)
def get_track_all_artists_map() -> dict[int, str]:
    """Return {track_id: 'Primary, Featured1, Featured2, ...'} for tracks with
    multiple credited artists. Tracks with only a primary artist are excluded
    from the dict so callers can use .get() with the existing artist_name as
    fallback."""
    conn = get_db()
    rows = conn.execute(
        """SELECT ta.track_id, a.artist_name
           FROM track_artists ta
           JOIN artists a ON ta.artist_id = a.artist_id
           ORDER BY ta.track_id, CASE ta.role WHEN 'primary' THEN 0 ELSE 1 END"""
    ).fetchall()
    conn.close()

    from collections import defaultdict

    track_artists = defaultdict(list)
    for track_id, artist_name in rows:
        track_artists[track_id].append(artist_name)

    return {tid: ", ".join(names) for tid, names in track_artists.items() if len(names) > 1}


@lru_cache(maxsize=1)
def get_track_artist_names_map() -> dict[int, list[str]]:
    """Return {track_id: [artist_name, ...]} for ALL tracks that have
    track_artists entries (at minimum the primary artist)."""
    conn = get_db()
    rows = conn.execute(
        """SELECT ta.track_id, a.artist_name
           FROM track_artists ta
           JOIN artists a ON ta.artist_id = a.artist_id
           ORDER BY ta.track_id, CASE ta.role WHEN 'primary' THEN 0 ELSE 1 END"""
    ).fetchall()
    conn.close()

    from collections import defaultdict

    track_artists = defaultdict(list)
    for track_id, artist_name in rows:
        track_artists[track_id].append(artist_name)

    return dict(track_artists)


def enrich_track_artist_names(df: pd.DataFrame) -> pd.DataFrame:
    """Enrich the artist_name column with featured artists for display, and
    add an artist_names list column for individual linking.

    - artist_name → 'Primary, Featured1, Featured2, ...'  (for display)
    - artist_names → ['Primary', 'Featured1', 'Featured2', ...]  (for linking)

    Returns a new DataFrame — does not mutate the input.
    """
    if df.empty or "track_id" not in df.columns:
        return df
    artist_map = get_track_all_artists_map()
    names_map = get_track_artist_names_map()
    if not artist_map and not names_map:
        return df
    df = df.copy()
    if artist_map:
        df["artist_name"] = df["track_id"].map(artist_map).fillna(df["artist_name"])
    if names_map:
        df["artist_names"] = df["track_id"].map(names_map)
        df["artist_names"] = df["artist_names"].apply(lambda x: x if isinstance(x, list) else [])
    return df


def fan_out_weekly_for_artists(weekly_df: pd.DataFrame) -> pd.DataFrame:
    """Duplicate rows in weekly_df so every credited artist gets their own entry.

    Each row is duplicated for each artist in track_artists (primary + featured).
    The artist_name column is set to the individual artist's name.
    Used for artist_summary and artist-level filtering.
    """
    if weekly_df.empty or "track_id" not in weekly_df.columns:
        return weekly_df

    names_map = get_track_artist_names_map()
    if not names_map:
        return weekly_df

    import pandas as pd

    rows = []
    for _, row in weekly_df.iterrows():
        tid = row["track_id"]
        artists = names_map.get(tid, [row["artist_name"]])
        for artist in artists:
            new_row = row.to_dict()
            new_row["artist_name"] = artist
            rows.append(new_row)

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════
# Pre-aggregated Billboard weekly data
# ═══════════════════════════════════════════════════════════════════════════


def _agg_param_hash(
    min_ms: int,
    music_only: bool,
    week_start_dow: int,
    week_start_hour: int,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = None,
) -> str:
    """Compute a content-hash of the parameters that affect aggregation results."""
    payload = json.dumps(
        [
            min_ms,
            music_only,
            week_start_dow,
            week_start_hour,
            dynamic_threshold,
            max_merge_gap_minutes,
        ],
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def check_agg_valid(conn: sqlite3.Connection, param_hash: str) -> bool:
    """Check if the stored aggregation matches the current parameter hash."""
    try:
        row = conn.execute("SELECT value FROM agg_config WHERE key = 'param_hash'").fetchone()
        return row is not None and row[0] == param_hash
    except sqlite3.OperationalError:
        return False


def build_aggregations(
    min_ms: int = 30000,
    music_only: bool = True,
    week_start_dow: int = 4,
    week_start_hour: int = 0,
    progress_callback=None,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = None,
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
                   p.source_album_id, t.album_id, t.artist_id, stm.duration_ms
            FROM plays p
            JOIN tracks t ON p.track_id = t.track_id
            LEFT JOIN spotify_track_meta stm
              ON t.spotify_track_id = stm.spotify_track_id
            {where}
            ORDER BY p.ts""",
        conn,
        params=fp,
    )

    if df.empty:
        conn.execute("DELETE FROM agg_weekly_tracks")
        conn.execute("DELETE FROM agg_weekly_albums")
        conn.execute("DELETE FROM agg_weekly_track_sources")
        conn.execute("DELETE FROM agg_weekly_artists")
        conn.execute("DELETE FROM agg_config")
        conn.commit()
        conn.close()
        return {"tracks": 0, "albums": 0, "track_sources": 0, "artists": 0}

    if progress_callback:
        progress_callback("合并连续播放...", 0.0)

    # Compute billboard_week in pandas
    df["days_back"] = (df["ts_dow"] - week_start_dow) % 7
    mask_before = (df["ts_dow"] == week_start_dow) & (df["ts_hour"] < week_start_hour)
    df.loc[mask_before, "days_back"] = 7
    df["ts_date_dt"] = pd.to_datetime(df["ts_date"])
    df["billboard_week"] = (df["ts_date_dt"] - pd.to_timedelta(df["days_back"], unit="D")).dt.date

    # Store source_album_id for album-level aggregation before dropping
    df["_source_album_id"] = df["source_album_id"].fillna(0).astype(int)

    # Merge consecutive same-track plays, then apply ms_played threshold
    df = merge_consecutive_plays(
        df,
        min_ms,
        max_gap_minutes=max_merge_gap_minutes,
        boundary_column=["source_album_id", "billboard_week"],
    )
    if min_ms > 0:
        from backend.domains.playback.counting import filter_effective_plays

        df = filter_effective_plays(df, min_ms=min_ms, dynamic_threshold=dynamic_threshold)

    if df.empty:
        conn.execute("DELETE FROM agg_weekly_tracks")
        conn.execute("DELETE FROM agg_weekly_albums")
        conn.execute("DELETE FROM agg_weekly_track_sources")
        conn.execute("DELETE FROM agg_weekly_artists")
        conn.execute("DELETE FROM agg_config")
        conn.commit()
        conn.close()
        return {"tracks": 0, "albums": 0, "track_sources": 0, "artists": 0}

    # Clear old aggregations
    conn.execute("DELETE FROM agg_weekly_tracks")
    conn.execute("DELETE FROM agg_weekly_albums")
    conn.execute("DELETE FROM agg_weekly_track_sources")
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
    _write_agg_batch(
        conn, "agg_weekly_tracks", t_rows, ["billboard_week", "track_id", "play_count", "total_ms"]
    )
    results["tracks"] = len(t_rows)
    if progress_callback:
        progress_callback("预聚合: 单曲完成", 0.33)

    # 2. Track-source rows — preserves album project attribution inputs.
    if progress_callback:
        progress_callback("预聚合: 单曲来源...", 0.33)
    if "_source_album_id" not in df.columns:
        df["_source_album_id"] = df.get("source_album_id", 0)
    df["_source_album_id"] = df["_source_album_id"].fillna(0).astype(int)
    track_sources_agg = (
        df.groupby(["billboard_week", "ts_date", "track_id", "_source_album_id"])
        .agg(play_count=("ms_played", "count"), total_ms=("ms_played", "sum"))
        .reset_index()
        .rename(columns={"ts_date": "play_date", "_source_album_id": "source_album_id"})
    )
    ts_rows = [
        (
            str(r.billboard_week),
            str(r.play_date),
            int(r.track_id),
            int(r.source_album_id),
            int(r.play_count),
            int(r.total_ms),
        )
        for r in track_sources_agg.itertuples(index=False)
    ]
    _write_agg_batch(
        conn,
        "agg_weekly_track_sources",
        ts_rows,
        ["billboard_week", "play_date", "track_id", "source_album_id", "play_count", "total_ms"],
    )
    results["track_sources"] = len(ts_rows)

    # 3. Albums — legacy container pre-agg kept for compatibility.
    if progress_callback:
        progress_callback("预聚合: 专辑...", 0.45)
    has_source = df["_source_album_id"].notna() & (df["_source_album_id"] != 0)
    df["_album_id_for_agg"] = df["_source_album_id"].where(has_source, df["album_id"]).astype(int)
    df_album = df[df["_album_id_for_agg"].notna()]
    if not df_album.empty:
        albums_agg = (
            df_album.groupby(["billboard_week", "_album_id_for_agg"])
            .agg(play_count=("ms_played", "count"), total_ms=("ms_played", "sum"))
            .reset_index()
            .rename(columns={"_album_id_for_agg": "album_id"})
        )
        a_rows = [
            (str(r.billboard_week), int(r.album_id), int(r.play_count), int(r.total_ms))
            for r in albums_agg.itertuples(index=False)
        ]
        _write_agg_batch(
            conn,
            "agg_weekly_albums",
            a_rows,
            ["billboard_week", "album_id", "play_count", "total_ms"],
        )
        results["albums"] = len(a_rows)
    else:
        results["albums"] = 0
    if progress_callback:
        progress_callback("预聚合: 专辑完成", 0.66)

    # 4. Artists — fan out through track_artists for multi-artist attribution
    if progress_callback:
        progress_callback("预聚合: 艺人...", 0.66)
    track_artists_df = pd.read_sql_query("SELECT track_id, artist_id FROM track_artists", conn)
    df_artists = df.merge(track_artists_df, on="track_id", how="inner", suffixes=("_primary", ""))
    artists_agg = (
        df_artists.groupby(["billboard_week", "artist_id"])
        .agg(play_count=("ms_played", "count"), total_ms=("ms_played", "sum"))
        .reset_index()
    )
    ar_rows = [
        (str(r.billboard_week), int(r.artist_id), int(r.play_count), int(r.total_ms))
        for r in artists_agg.itertuples(index=False)
    ]
    _write_agg_batch(
        conn,
        "agg_weekly_artists",
        ar_rows,
        ["billboard_week", "artist_id", "play_count", "total_ms"],
    )
    results["artists"] = len(ar_rows)
    if progress_callback:
        progress_callback("预聚合: 艺人完成", 1.0)

    # Store param hash
    param_hash = _agg_param_hash(
        min_ms,
        music_only,
        week_start_dow,
        week_start_hour,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
    )
    conn.execute(
        "INSERT OR REPLACE INTO agg_config(key, value) VALUES ('param_hash', ?)",
        (param_hash,),
    )
    conn.commit()
    conn.close()

    return results


def load_agg_weekly_tracks(conn: sqlite3.Connection) -> pd.DataFrame:
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


def load_agg_weekly_albums(conn: sqlite3.Connection) -> pd.DataFrame:
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


def load_agg_weekly_track_sources(conn: sqlite3.Connection) -> pd.DataFrame:
    """Load track-source pre-aggregates for album project weekly rankings."""
    import pandas as pd

    df = pd.read_sql_query(
        """SELECT awts.billboard_week,
                  awts.play_date,
                  awts.track_id,
                  t.track_name,
                  a.artist_name,
                  t.album_id AS track_album_id,
                  COALESCE(al_src.album_name, al.album_name) AS album_name,
                  NULLIF(awts.source_album_id, 0) AS source_album_id,
                  awts.play_count,
                  awts.total_ms,
                  awts.play_date AS ts,
                  awts.play_date AS ts_date
           FROM agg_weekly_track_sources awts
           JOIN tracks t ON awts.track_id = t.track_id
           JOIN artists a ON t.artist_id = a.artist_id
           LEFT JOIN albums al ON t.album_id = al.album_id
           LEFT JOIN albums al_src ON awts.source_album_id = al_src.album_id
           ORDER BY awts.billboard_week, awts.play_date""",
        conn,
    )
    df["billboard_week"] = pd.to_datetime(df["billboard_week"]).dt.date
    return df


def load_agg_weekly_artists(conn: sqlite3.Connection) -> pd.DataFrame:
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


# ── Cache registration ─────────────────────────────────────────────────
from backend.core.cache_manager import register_lru  # noqa: E402

register_lru("db", "plays", _load_plays_cached)
register_lru("db", "track_all_artists_map", get_track_all_artists_map)
register_lru("db", "track_artist_names_map", get_track_artist_names_map)
