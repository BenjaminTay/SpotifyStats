"""SQLite database layer: schema, connection, and common query helpers."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.core.cache import singleflight
from backend.domains.playback.logical_timeline import reconstruct_logical_plays

logger = logging.getLogger(__name__)

# Column downcast map: common int64 columns → int32 (safe within typical data sizes)
_INT32_COLUMNS = frozenset(
    {
        "track_id",
        "l1_id",
        "source_track_id",
        "representative_track_id",
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
    spotify_track_id   TEXT
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

-- Spotify ids are provider aliases owned by the existing application track.
-- This is intentionally directional: one track_id may own several Spotify
-- ids, while a Spotify id can never resolve to more than one track_id.
CREATE TABLE IF NOT EXISTS spotify_track_owners (
    spotify_track_id TEXT PRIMARY KEY,
    track_id         INTEGER NOT NULL REFERENCES tracks(track_id),
    evidence_type    TEXT NOT NULL DEFAULT 'import_match'
                     CHECK(evidence_type IN (
                         'import_match', 'play_majority',
                         'catalog_projection', 'manual_override'
                     )),
    first_seen_at    TEXT,
    last_seen_at     TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_spotify_track_owners_track
    ON spotify_track_owners(track_id);

-- Stable redirects for retired historical raw track ids. alias_track_id is
-- intentionally not a foreign key: its source row is removed after a
-- controlled cleanup, while canonical_track_id must always remain valid.
CREATE TABLE IF NOT EXISTS track_id_aliases (
    alias_track_id     INTEGER PRIMARY KEY,
    canonical_track_id INTEGER NOT NULL REFERENCES tracks(track_id),
    reason             TEXT NOT NULL,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK(alias_track_id != canonical_track_id)
);
CREATE INDEX IF NOT EXISTS idx_track_id_aliases_canonical
    ON track_id_aliases(canonical_track_id);

CREATE TABLE IF NOT EXISTS historical_fk_cleanup_runs (
    run_id          TEXT PRIMARY KEY,
    plan_token      TEXT NOT NULL,
    status          TEXT NOT NULL CHECK(status IN ('running', 'completed')),
    summary_json    TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at    TEXT
);

CREATE TABLE IF NOT EXISTS historical_fk_cleanup_archive (
    run_id          TEXT NOT NULL REFERENCES historical_fk_cleanup_runs(run_id),
    source_table    TEXT NOT NULL,
    source_row_key  TEXT NOT NULL,
    row_json        TEXT NOT NULL,
    archived_at     TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY(run_id, source_table, source_row_key)
);
CREATE INDEX IF NOT EXISTS idx_historical_fk_cleanup_archive_source
    ON historical_fk_cleanup_archive(source_table, source_row_key);

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
    l1_id INTEGER NOT NULL REFERENCES track_l1_identities(l1_id),
    track_id INTEGER NOT NULL REFERENCES tracks(track_id),
    play_count INTEGER NOT NULL,
    total_ms INTEGER NOT NULL,
    PRIMARY KEY (billboard_week, l1_id)
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
    l1_id INTEGER NOT NULL REFERENCES track_l1_identities(l1_id),
    track_id INTEGER NOT NULL REFERENCES tracks(track_id),
    source_album_id INTEGER NOT NULL DEFAULT 0,
    play_count INTEGER NOT NULL,
    total_ms INTEGER NOT NULL,
    PRIMARY KEY (billboard_week, play_date, l1_id, source_album_id)
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
    automatic_spotify_track_id TEXT,
    automatic_artist_id INTEGER,
    primary_l1_id     INTEGER REFERENCES track_l1_identities(l1_id),
    group_status      TEXT NOT NULL DEFAULT 'active'
                      CHECK(group_status IN ('active', 'archived', 'conflict')),
    created_at        TEXT DEFAULT (datetime('now')),
    CHECK(
        is_manual = 1
        OR (automatic_spotify_track_id IS NULL) = (automatic_artist_id IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS track_group_members (
    group_id   INTEGER REFERENCES track_groups(group_id),
    track_id   INTEGER REFERENCES tracks(track_id),
    UNIQUE(group_id, track_id)
);

CREATE INDEX IF NOT EXISTS idx_track_groups_scope ON track_groups(scope);
CREATE INDEX IF NOT EXISTS idx_track_groups_parent ON track_groups(parent_group_id);
CREATE INDEX IF NOT EXISTS idx_track_group_members_track ON track_group_members(track_id);

CREATE TABLE IF NOT EXISTS track_group_l1_members (
    group_id INTEGER NOT NULL REFERENCES track_groups(group_id),
    l1_id INTEGER NOT NULL REFERENCES track_l1_identities(l1_id),
    PRIMARY KEY(group_id, l1_id)
);
CREATE INDEX IF NOT EXISTS idx_track_group_l1_member ON track_group_l1_members(l1_id);

CREATE TRIGGER IF NOT EXISTS trg_track_group_l1_single_active_scope_insert
BEFORE INSERT ON track_group_l1_members
WHEN EXISTS (
    SELECT 1 FROM track_groups incoming
     WHERE incoming.group_id=NEW.group_id AND incoming.group_status='active'
) AND EXISTS (
    SELECT 1
      FROM track_group_l1_members existing
      JOIN track_groups existing_group ON existing_group.group_id=existing.group_id
      JOIN track_groups incoming ON incoming.group_id=NEW.group_id
     WHERE existing.l1_id=NEW.l1_id
       AND existing.group_id!=NEW.group_id
       AND existing_group.group_status='active'
       AND existing_group.scope=incoming.scope
)
BEGIN
    SELECT RAISE(ABORT, 'canonical track already belongs to an active group at this scope');
END;

CREATE TRIGGER IF NOT EXISTS trg_track_group_single_active_scope_update
BEFORE UPDATE OF group_status, scope ON track_groups
WHEN NEW.group_status='active' AND EXISTS (
    SELECT 1
      FROM track_group_l1_members incoming_member
      JOIN track_group_l1_members existing_member
        ON existing_member.l1_id=incoming_member.l1_id
       AND existing_member.group_id!=incoming_member.group_id
      JOIN track_groups existing_group ON existing_group.group_id=existing_member.group_id
     WHERE incoming_member.group_id=NEW.group_id
       AND existing_group.group_status='active'
       AND existing_group.scope=NEW.scope
)
BEGIN
    SELECT RAISE(ABORT, 'activating group would overlap another active group at this scope');
END;

CREATE TABLE IF NOT EXISTS track_group_migration_audit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    distinct_l1_count INTEGER NOT NULL,
    details TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS track_group_candidates (
    candidate_id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL CHECK(scope IN ('recording', 'composition')),
    original_l1_id INTEGER NOT NULL REFERENCES track_l1_identities(l1_id),
    candidate_l1_id INTEGER NOT NULL REFERENCES track_l1_identities(l1_id),
    confidence REAL,
    evidence_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending', 'accepted', 'rejected')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK(original_l1_id != candidate_l1_id),
    UNIQUE(scope, original_l1_id, candidate_l1_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_track_group_candidate_unordered_pair
    ON track_group_candidates(
        scope,
        MIN(original_l1_id, candidate_l1_id),
        MAX(original_l1_id, candidate_l1_id)
    );

-- Deprecated compatibility projection. l1_id is always the existing track_id;
-- authoritative Spotify ownership lives in spotify_track_owners. New product
-- code must not expose this as a separate public identity namespace.
CREATE TABLE IF NOT EXISTS track_l1_identities (
    l1_id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    -- Compatibility/display projection only. Authoritative ownership lives in
    -- track_l1_external_ids and may contain several rows per l1_id.
    provider                TEXT NOT NULL DEFAULT 'local',
    external_track_id       TEXT,
    fallback_track_id       INTEGER REFERENCES tracks(track_id),
    identity_status         TEXT NOT NULL DEFAULT 'active'
                            CHECK(identity_status IN ('active', 'unresolved', 'superseded')),
    representative_track_id INTEGER REFERENCES tracks(track_id),
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_track_l1_local_identity
    ON track_l1_identities(fallback_track_id)
    WHERE fallback_track_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_track_l1_representative
    ON track_l1_identities(representative_track_id);

CREATE TABLE IF NOT EXISTS track_l1_external_ids (
    provider          TEXT NOT NULL,
    external_track_id TEXT NOT NULL,
    l1_id             INTEGER NOT NULL REFERENCES track_l1_identities(l1_id),
    evidence_type     TEXT NOT NULL DEFAULT 'provider_observed'
                      CHECK(evidence_type IN (
                          'provider_observed', 'provider_relink',
                          'manual_confirmed', 'migration'
                      )),
    is_primary        INTEGER NOT NULL DEFAULT 0 CHECK(is_primary IN (0, 1)),
    first_seen_at     TEXT,
    last_seen_at      TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY(provider, external_track_id)
);
CREATE INDEX IF NOT EXISTS idx_track_l1_external_owner
    ON track_l1_external_ids(l1_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_track_l1_primary_external
    ON track_l1_external_ids(l1_id, provider)
    WHERE is_primary=1;

CREATE TABLE IF NOT EXISTS track_l1_source_links (
    l1_id          INTEGER NOT NULL REFERENCES track_l1_identities(l1_id),
    track_id       INTEGER NOT NULL REFERENCES tracks(track_id),
    evidence_type  TEXT NOT NULL
                   CHECK(evidence_type IN ('play_at_time', 'track_projection', 'manual')),
    observed_plays INTEGER NOT NULL DEFAULT 0 CHECK(observed_plays >= 0),
    first_seen_at  TEXT,
    last_seen_at   TEXT,
    PRIMARY KEY(l1_id, track_id, evidence_type)
);

CREATE INDEX IF NOT EXISTS idx_track_l1_source_track
    ON track_l1_source_links(track_id);

CREATE TABLE IF NOT EXISTS track_identity_events (
    event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    action          TEXT NOT NULL CHECK(action IN ('merge', 'split', 'attach_external_id')),
    survivor_l1_id  INTEGER REFERENCES track_l1_identities(l1_id),
    affected_l1_ids TEXT NOT NULL DEFAULT '[]',
    before_json     TEXT NOT NULL DEFAULT '{}',
    after_json      TEXT NOT NULL DEFAULT '{}',
    reason          TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_track_identity_events_survivor
    ON track_identity_events(survivor_l1_id, event_id);

CREATE TABLE IF NOT EXISTS track_identity_state (
    state_id        INTEGER PRIMARY KEY CHECK(state_id = 1),
    current_revision INTEGER NOT NULL DEFAULT 0,
    policy_version  TEXT NOT NULL DEFAULT 'spotify_owner_track_v1',
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO track_identity_state(state_id, current_revision, policy_version)
VALUES (1, 0, 'spotify_owner_track_v1');

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
    pre_review_recommendation TEXT,
    pre_review_confidence REAL,
    pre_review_note TEXT,
    pre_reviewed_by TEXT,
    pre_reviewed_at TEXT,
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

CREATE TABLE IF NOT EXISTS artist_identity_groups (
    identity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
    display_artist_id INTEGER REFERENCES artists(artist_id),
    display_name TEXT NOT NULL,
    display_source TEXT NOT NULL DEFAULT 'canonical_artist',
    provider_metadata_artist_id INTEGER REFERENCES artists(artist_id),
    status TEXT NOT NULL DEFAULT 'active',
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS artist_identity_members (
    membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_id INTEGER NOT NULL REFERENCES artist_identity_groups(identity_id),
    artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
    role TEXT NOT NULL DEFAULT 'alias',
    evidence_type TEXT NOT NULL DEFAULT 'legacy_alias',
    evidence_json TEXT NOT NULL DEFAULT '{}',
    confidence REAL NOT NULL DEFAULT 1.0,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    removed_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_artist_identity_member_active
ON artist_identity_members(artist_id) WHERE active = 1;

CREATE TABLE IF NOT EXISTS artist_identity_external_ids (
    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
    provider TEXT NOT NULL,
    external_id TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    evidence_source TEXT,
    confidence REAL NOT NULL DEFAULT 1.0,
    verified INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(artist_id, provider, external_id)
);

CREATE TABLE IF NOT EXISTS artist_identity_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    identity_id INTEGER REFERENCES artist_identity_groups(identity_id),
    action TEXT NOT NULL,
    before_json TEXT NOT NULL DEFAULT '{}',
    after_json TEXT NOT NULL DEFAULT '{}',
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    revision INTEGER NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    undo_of_event_id INTEGER REFERENCES artist_identity_events(event_id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS artist_identity_state (
    state_id INTEGER PRIMARY KEY CHECK (state_id = 1),
    current_revision INTEGER NOT NULL DEFAULT 0,
    active_aggregate_revision INTEGER NOT NULL DEFAULT 0,
    rebuild_status TEXT NOT NULL DEFAULT 'ready',
    last_error TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT OR IGNORE INTO artist_identity_state(
    state_id, current_revision, active_aggregate_revision, rebuild_status
) VALUES (1, 0, 0, 'ready');

CREATE TABLE IF NOT EXISTS track_credit_overrides (
    override_id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL REFERENCES tracks(track_id),
    artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
    action TEXT NOT NULL CHECK (action IN ('add', 'remove', 'set_role')),
    role TEXT CHECK (role IN ('primary', 'featured')),
    evidence_type TEXT NOT NULL DEFAULT 'user_confirmed',
    evidence_source TEXT,
    reason TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'local-user',
    revision INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    supersedes_override_id INTEGER REFERENCES track_credit_overrides(override_id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    deactivated_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_track_credit_override_active
ON track_credit_overrides(track_id, artist_id) WHERE active = 1;
CREATE INDEX IF NOT EXISTS idx_track_credit_overrides_track
ON track_credit_overrides(track_id, active);

CREATE TABLE IF NOT EXISTS track_credit_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL REFERENCES tracks(track_id),
    artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
    action TEXT NOT NULL,
    before_json TEXT NOT NULL DEFAULT '{}',
    after_json TEXT NOT NULL DEFAULT '{}',
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    revision INTEGER NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    undo_of_event_id INTEGER REFERENCES track_credit_events(event_id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_track_credit_events_track
ON track_credit_events(track_id, event_id DESC);

CREATE TABLE IF NOT EXISTS track_credit_state (
    state_id INTEGER PRIMARY KEY CHECK (state_id = 1),
    current_revision INTEGER NOT NULL DEFAULT 0,
    active_aggregate_revision INTEGER NOT NULL DEFAULT 0,
    rebuild_status TEXT NOT NULL DEFAULT 'ready'
        CHECK (rebuild_status IN ('ready', 'pending', 'running', 'failed')),
    last_error TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT OR IGNORE INTO track_credit_state(
    state_id, current_revision, active_aggregate_revision, rebuild_status
) VALUES (1, 0, 0, 'ready');

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
    spotify_track_id TEXT,
    added_date_source TEXT CHECK(added_date_source IN ('oauth', 'manual', 'legacy'))
);

CREATE INDEX IF NOT EXISTS idx_saved_tracks_spotify_track_id ON saved_tracks(spotify_track_id);

CREATE TABLE IF NOT EXISTS account_archive_state (
    state_id INTEGER PRIMARY KEY CHECK (state_id = 1),
    account_import_revision INTEGER NOT NULL DEFAULT 0,
    collection_date_revision INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT OR IGNORE INTO account_archive_state(
    state_id, account_import_revision, collection_date_revision
) VALUES (1, 0, 0);

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


def enforce_sqlite_foreign_keys(conn: sqlite3.Connection) -> sqlite3.Connection:
    """Enable and verify SQLite foreign-key enforcement for one connection.

    SQLite keeps this setting per connection and otherwise defaults to OFF.
    Silent fallback would recreate historical orphan rows, so every persistent
    application connection fails closed when enforcement cannot be enabled.
    """

    conn.execute("PRAGMA foreign_keys = ON")
    row = conn.execute("PRAGMA foreign_keys").fetchone()
    if row is None or int(row[0]) != 1:
        conn.close()
        raise RuntimeError("SQLite foreign-key enforcement could not be enabled")
    return conn


def get_db(readonly: bool = True) -> sqlite3.Connection:
    """Get a database connection."""
    # A public-readonly request must remain read-only even if a legacy service
    # explicitly asks for ``readonly=False``.  ContextVars are propagated by
    # Starlette/AnyIO into sync endpoint worker threads, so this is a genuine
    # request-level final defence rather than a convention at individual APIs.
    from backend.core.access_surface import public_readonly_db_guard_active

    public_request = public_readonly_db_guard_active()
    effective_readonly = readonly or public_request

    # Ensure parent directory exists — CI and fresh checkouts may not have data/
    db_dir = os.path.dirname(DB_PATH)
    if not public_request and db_dir and not os.path.exists(db_dir):
        try:
            os.makedirs(db_dir, exist_ok=True)
        except OSError:
            pass  # allow sqlite3.connect to raise the original error

    # check_same_thread=False 是必需的：
    # Starlette 的 generator 依赖在后台任务中执行 finally 清理代码，
    # 该任务可能运行在不同于创建连接的线程中（即使只是 close() 也会报错）。
    # 由于每个请求都创建独立的连接，不存在真正的跨线程并发使用同一连接，
    # 因此禁用线程检查是安全的。
    if public_request:
        # URI ``mode=ro`` prevents SQLite from creating the database, journal,
        # or WAL as a side effect of a public request. ``query_only`` remains a
        # second guard against accidental writes through the open connection.
        db_uri = f"{Path(DB_PATH).resolve().as_uri()}?mode=ro"
        conn = sqlite3.connect(db_uri, uri=True, timeout=30, check_same_thread=False)
        enforce_sqlite_foreign_keys(conn)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")
    elif effective_readonly:
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        enforce_sqlite_foreign_keys(conn)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")
    else:
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        enforce_sqlite_foreign_keys(conn)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


def connect_sqlite_path(
    path: str | os.PathLike[str],
    *,
    timeout: float = 30,
    check_same_thread: bool = False,
) -> sqlite3.Connection:
    """Open an auxiliary SQLite path with the public request guard applied.

    Some cached readers reopen a path derived from an injected connection.
    Centralising those opens prevents them from bypassing public ``mode=ro``.
    """

    from backend.core.access_surface import public_readonly_db_guard_active

    if public_readonly_db_guard_active():
        uri = f"{Path(path).resolve().as_uri()}?mode=ro"
        conn = sqlite3.connect(
            uri,
            uri=True,
            timeout=timeout,
            check_same_thread=check_same_thread,
        )
        enforce_sqlite_foreign_keys(conn)
        conn.execute("PRAGMA query_only = ON")
        return conn
    conn = sqlite3.connect(path, timeout=timeout, check_same_thread=check_same_thread)
    return enforce_sqlite_foreign_keys(conn)


def init_db() -> None:
    """Create tables and indexes if they don't exist."""
    conn = get_db(readonly=False)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def ensure_schema() -> None:
    """Ensure all tables/indexes exist (safe to call repeatedly).

    Delegates to the versioned migration system. Kept for backward
    compatibility with callers in import_data and scripts.
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
    max_gap_minutes: int | None = 5,
    boundary_column: str | list[str] | None = None,
    dynamic_threshold: bool = False,
) -> pd.DataFrame:
    """Compatibility facade for logical-play timeline reconstruction.

    ``max_gap_minutes`` now measures actual idle time between the previous
    stop and the next inferred start. Date/month/Billboard boundaries must not
    be supplied here; temporal attribution happens after reconstruction.
    """
    return reconstruct_logical_plays(
        df,
        min_ms,
        identity_column="l1_id" if "l1_id" in df.columns else "track_id",
        dynamic_threshold=dynamic_threshold,
        max_gap_minutes=max_gap_minutes,
        boundary_column=boundary_column,
    )


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


_AGG_SHADOW_TABLES = {
    "agg_weekly_tracks": "agg_weekly_tracks_shadow",
    "agg_weekly_albums": "agg_weekly_albums_shadow",
    "agg_weekly_track_sources": "agg_weekly_track_sources_shadow",
    "agg_weekly_artists": "agg_weekly_artists_shadow",
}

_BILLBOARD_AGGREGATION_BUILDER_VERSION = "billboard_aggregation_v3_l1"


def _prepare_aggregation_shadows(conn: sqlite3.Connection) -> None:
    """Create connection-local staging tables without touching live aggregates."""
    for live_table, shadow_table in _AGG_SHADOW_TABLES.items():
        conn.execute(f'DROP TABLE IF EXISTS temp."{shadow_table}"')
        conn.execute(
            f'CREATE TEMP TABLE "{shadow_table}" AS SELECT * FROM main."{live_table}" WHERE 0'
        )
    conn.commit()


def _copy_unaffected_aggregation_weeks(
    conn: sqlite3.Connection,
    affected_weeks: set[str],
) -> None:
    """Seed every shadow with live rows outside the exact replacement scope."""
    params = sorted(affected_weeks)
    for live_table, shadow_table in _AGG_SHADOW_TABLES.items():
        if params:
            placeholders = ",".join("?" for _ in params)
            conn.execute(
                f'INSERT INTO temp."{shadow_table}" '
                f'SELECT * FROM main."{live_table}" '
                f"WHERE billboard_week NOT IN ({placeholders})",
                params,
            )
        else:
            conn.execute(f'INSERT INTO temp."{shadow_table}" SELECT * FROM main."{live_table}"')
    conn.commit()


def _validate_aggregation_shadows(conn: sqlite3.Connection) -> None:
    """Reject corrupt staged partitions before the atomic four-table publish."""
    keys = {
        "agg_weekly_tracks": ("billboard_week", "l1_id"),
        "agg_weekly_albums": ("billboard_week", "album_id"),
        "agg_weekly_track_sources": (
            "billboard_week",
            "play_date",
            "l1_id",
            "source_album_id",
        ),
        "agg_weekly_artists": ("billboard_week", "artist_id"),
    }
    for live_table, shadow_table in _AGG_SHADOW_TABLES.items():
        key_sql = ", ".join(keys[live_table])
        duplicate = conn.execute(
            f'SELECT 1 FROM temp."{shadow_table}" GROUP BY {key_sql} HAVING COUNT(*) > 1 LIMIT 1'
        ).fetchone()
        invalid_weight = conn.execute(
            f'SELECT 1 FROM temp."{shadow_table}" WHERE play_count < 0 OR total_ms < 0 LIMIT 1'
        ).fetchone()
        if duplicate or invalid_weight:
            raise RuntimeError(f"invalid staged Billboard aggregate: {live_table}")


def _publish_aggregation_shadows(
    conn: sqlite3.Connection,
    *,
    param_hash: str,
    data_generation_id: str | None,
    data_digest: str | None = None,
    build_strategy: str = "full",
    base_generation_id: str | None = None,
    semantic_dependencies: dict[str, str] | None = None,
) -> None:
    """Atomically replace every live aggregate table with one staged snapshot."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        current_generation_id = _active_playback_generation(conn)
        if current_generation_id != data_generation_id:
            raise RuntimeError(
                "playback generation changed while Billboard aggregates were building"
            )
        if data_digest is not None and _active_playback_dataset_digest(conn) != data_digest:
            raise RuntimeError("playback dataset changed while Billboard aggregates were building")
        for live_table, shadow_table in _AGG_SHADOW_TABLES.items():
            conn.execute(f'DELETE FROM main."{live_table}"')
            conn.execute(f'INSERT INTO main."{live_table}" SELECT * FROM temp."{shadow_table}"')
        conn.execute("DELETE FROM agg_config")
        conn.execute(
            "INSERT INTO agg_config(key, value) VALUES ('param_hash', ?)",
            (param_hash,),
        )
        if data_generation_id is not None:
            conn.execute(
                """INSERT INTO agg_config(key, value)
                   VALUES ('data_generation_id', ?)""",
                (data_generation_id,),
            )
        if data_digest is not None:
            conn.execute(
                "INSERT INTO agg_config(key, value) VALUES ('source_dataset_digest', ?)",
                (data_digest,),
            )
        conn.execute(
            "INSERT INTO agg_config(key, value) VALUES ('build_strategy', ?)",
            (build_strategy,),
        )
        if base_generation_id is not None:
            conn.execute(
                "INSERT INTO agg_config(key, value) VALUES ('base_generation_id', ?)",
                (base_generation_id,),
            )
        for key, value in sorted((semantic_dependencies or {}).items()):
            conn.execute(
                "INSERT INTO agg_config(key, value) VALUES (?, ?)",
                (key, value),
            )
        if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='track_credit_state'"
        ).fetchone():
            conn.execute(
                """UPDATE track_credit_state
                   SET active_aggregate_revision=current_revision,
                       rebuild_status='ready', last_error=NULL, updated_at=datetime('now')
                   WHERE state_id=1"""
            )
        if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='artist_identity_state'"
        ).fetchone():
            conn.execute(
                """UPDATE artist_identity_state
                   SET active_aggregate_revision=current_revision,
                       rebuild_status='ready', last_error=NULL, updated_at=datetime('now')
                   WHERE state_id=1"""
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _active_playback_generation(conn: sqlite3.Connection) -> str | None:
    """Return the generation bound to the currently published playback facts."""
    if not conn.execute(
        """SELECT 1 FROM sqlite_master
           WHERE type='table' AND name='playback_import_state'"""
    ).fetchone():
        return None
    row = conn.execute(
        """SELECT active_generation_id FROM playback_import_state
           WHERE state_id=1"""
    ).fetchone()
    return str(row[0]) if row is not None and row[0] else None


def _active_playback_dataset_digest(conn: sqlite3.Connection) -> str | None:
    """Return the exact fingerprint-set digest bound to active playback facts."""
    if not conn.execute(
        """SELECT 1 FROM sqlite_master
           WHERE type='table' AND name='playback_import_state'"""
    ).fetchone():
        return None
    row = conn.execute(
        "SELECT dataset_digest FROM playback_import_state WHERE state_id=1"
    ).fetchone()
    return str(row[0]) if row is not None and row[0] else None


def _aggregation_config(conn: sqlite3.Connection) -> dict[str, str]:
    try:
        return {
            str(row[0]): str(row[1])
            for row in conn.execute("SELECT key, value FROM agg_config").fetchall()
        }
    except sqlite3.OperationalError:
        return {}


def _partition_base_generation(
    conn: sqlite3.Connection,
    *,
    param_hash: str,
    previous_dataset_digest: str | None,
    semantic_dependencies: dict[str, str],
) -> str | None:
    """Return a reusable aggregate generation only when its facts are proven."""
    if previous_dataset_digest is None:
        return None
    config = _aggregation_config(conn)
    if config.get("param_hash") != param_hash:
        return None
    if config.get("source_dataset_digest") != previous_dataset_digest:
        return None
    if any(config.get(key) != value for key, value in semantic_dependencies.items()):
        return None
    generation_id = config.get("data_generation_id")
    return generation_id or None


def _played_track_duration_revision(
    conn: sqlite3.Connection,
    *,
    excluded_generation_id: str | None = None,
) -> str:
    """Hash duration semantics for every track reachable from playback facts."""
    digest = hashlib.sha256(b"spotifystats-played-track-duration-v1\0")
    exclusion = "AND COALESCE(import_generation_id, '') != ?" if excluded_generation_id else ""
    params = (excluded_generation_id,) if excluded_generation_id else ()
    rows = conn.execute(
        f"""SELECT t.track_id, t.spotify_track_id, stm.duration_ms
           FROM tracks t
           JOIN (SELECT DISTINCT track_id FROM plays
                 WHERE track_id IS NOT NULL {exclusion}) p
             ON p.track_id=t.track_id
           LEFT JOIN spotify_track_meta stm
             ON stm.spotify_track_id=t.spotify_track_id
           ORDER BY t.track_id""",
        params,
    ).fetchall()
    for row in rows:
        digest.update(json.dumps(list(row), ensure_ascii=True, separators=(",", ":")).encode())
        digest.update(b"\n")
    return digest.hexdigest()[:20]


def _played_track_credit_membership_revision(
    conn: sqlite3.Connection,
    *,
    excluded_generation_id: str | None = None,
) -> str:
    """Hash canonical artist memberships for tracks reachable from playback facts.

    Excluding one append generation removes only tracks that have no older
    playback rows. Existing tracks remain in the base digest, so a newly added
    raw or manual credit cannot silently reuse historical artist aggregates.
    """
    exclusion = "AND COALESCE(import_generation_id, '') != ?" if excluded_generation_id else ""
    params = (excluded_generation_id,) if excluded_generation_id else ()
    played_track_ids = {
        int(row[0])
        for row in conn.execute(
            f"""SELECT DISTINCT track_id FROM plays
                WHERE track_id IS NOT NULL {exclusion}""",
            params,
        ).fetchall()
    }
    digest = hashlib.sha256(b"spotifystats-played-canonical-credit-membership-v1\0")
    if not played_track_ids:
        return digest.hexdigest()[:20]

    from backend.domains.metadata.track_credits import get_effective_track_credits

    memberships = sorted(
        (int(row["track_id"]), int(row["artist_id"]))
        for row in get_effective_track_credits(conn)
        if int(row["track_id"]) in played_track_ids
    )
    for track_id, artist_id in memberships:
        digest.update(f"{track_id}:{artist_id}\n".encode("ascii"))
    return digest.hexdigest()[:20]


def _aggregation_fact_dependencies(
    conn: sqlite3.Connection,
    *,
    excluded_generation_id: str | None = None,
) -> dict[str, str]:
    from backend.domains.playback.logical_timeline import PLAYBACK_EVENT_POLICY_VERSION

    return {
        "builder_version": _BILLBOARD_AGGREGATION_BUILDER_VERSION,
        "playback_policy_version": PLAYBACK_EVENT_POLICY_VERSION,
        "duration_revision": _played_track_duration_revision(
            conn,
            excluded_generation_id=excluded_generation_id,
        ),
        "credit_membership_revision": _played_track_credit_membership_revision(
            conn,
            excluded_generation_id=excluded_generation_id,
        ),
    }


def _aggregation_semantic_dependencies(
    conn: sqlite3.Connection,
    *,
    identity_revision: int,
    track_credit_revision: int,
    track_identity_revision: int,
    excluded_generation_id: str | None = None,
) -> dict[str, str]:
    from backend.domains.yearly_review.context import _album_project_semantic_revision

    return {
        **_aggregation_fact_dependencies(
            conn,
            excluded_generation_id=excluded_generation_id,
        ),
        "identity_revision": str(identity_revision),
        "track_credit_revision": str(track_credit_revision),
        "track_identity_revision": str(track_identity_revision),
        "album_project_revision": _album_project_semantic_revision(conn),
    }


def _clear_aggregations_for_generation(
    conn: sqlite3.Connection,
    *,
    data_generation_id: str | None,
) -> None:
    """Clear live aggregates only if the facts still match this build."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        if _active_playback_generation(conn) != data_generation_id:
            raise RuntimeError(
                "playback generation changed while Billboard aggregates were building"
            )
        for live_table in _AGG_SHADOW_TABLES:
            conn.execute(f'DELETE FROM main."{live_table}"')
        conn.execute("DELETE FROM agg_config")
        if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='track_credit_state'"
        ).fetchone():
            conn.execute(
                """UPDATE track_credit_state
                   SET active_aggregate_revision=current_revision,
                       rebuild_status='ready', last_error=NULL, updated_at=datetime('now')
                   WHERE state_id=1"""
            )
        if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='artist_identity_state'"
        ).fetchone():
            conn.execute(
                """UPDATE artist_identity_state
                   SET active_aggregate_revision=current_revision,
                       rebuild_status='ready', last_error=NULL, updated_at=datetime('now')
                   WHERE state_id=1"""
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


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
    max_merge_gap_minutes: int | None = 5,
    boundary_column: str | None = None,
    track_identity_revision: int = 0,
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

        identity_ready = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='track_l1_external_ids'"
        ).fetchone()
        if identity_ready:
            identity_columns = (
                "p.track_id AS source_track_id, "
                "COALESCE(li_spotify.l1_id, li_local.l1_id, p.track_id) AS l1_id, "
                "COALESCE(li_spotify.representative_track_id, "
                "li_local.representative_track_id, p.track_id) AS resolved_track_id"
            )
            identity_joins = (
                "LEFT JOIN tracks t_source ON p.track_id = t_source.track_id "
                "LEFT JOIN track_l1_external_ids external_spotify "
                "ON external_spotify.provider='spotify' "
                "AND external_spotify.external_track_id="
                "COALESCE(NULLIF(p.spotify_track_id_at_play, ''), "
                "NULLIF(t_source.spotify_track_id, '')) "
                "LEFT JOIN track_l1_identities li_spotify "
                "ON li_spotify.l1_id=external_spotify.l1_id "
                "AND li_spotify.identity_status!='superseded' "
                "LEFT JOIN track_l1_identities li_local "
                "ON li_local.fallback_track_id=p.track_id "
                "AND li_local.identity_status!='superseded' "
                "AND COALESCE(NULLIF(p.spotify_track_id_at_play, ''), "
                "NULLIF(t_source.spotify_track_id, '')) IS NULL "
                "LEFT JOIN tracks t ON t.track_id=COALESCE("
                "li_spotify.representative_track_id, "
                "li_local.representative_track_id, p.track_id) "
            )
        else:
            # Compatibility for isolated legacy/unit-test databases. Production
            # databases are migrated before serving and therefore use L1.
            identity_columns = (
                "p.track_id AS source_track_id, p.track_id AS l1_id, "
                "p.track_id AS resolved_track_id"
            )
            identity_joins = (
                "LEFT JOIN tracks t_source ON p.track_id = t_source.track_id "
                "LEFT JOIN tracks t ON p.track_id = t.track_id "
            )
        if columns == "*":
            if join_albums:
                cols = f"p.*, {identity_columns}, t.track_name, t.spotify_track_uri, t.album_id AS track_album_id, t.artist_id, a.artist_name, al.album_name, al_src.album_name AS source_album_name"
            else:
                cols = f"p.*, {identity_columns}, t.track_name, t.spotify_track_uri, t.artist_id, a.artist_name"
            if filtered:
                cols += ", stm.duration_ms"
        else:
            cols = f"{columns}, {identity_columns}"

        if join_albums:
            from_clause = (
                "FROM plays p "
                + identity_joins
                + "LEFT JOIN artists a ON t.artist_id = a.artist_id "
                "LEFT JOIN albums al ON t.album_id = al.album_id "
                "LEFT JOIN albums al_src ON p.source_album_id = al_src.album_id"
            )
        else:
            from_clause = (
                "FROM plays p "
                + identity_joins
                + "LEFT JOIN artists a ON t.artist_id = a.artist_id"
            )
        if filtered:
            from_clause += (
                " LEFT JOIN spotify_track_meta stm ON stm.spotify_track_id="
                "COALESCE(NULLIF(p.spotify_track_id_at_play, ''), "
                "NULLIF(t_source.spotify_track_id, ''))"
            )

        sql = f"SELECT {cols} {from_clause} {where} ORDER BY p.ts"
        df = pd.read_sql_query(sql, conn, params=params)
        if "resolved_track_id" in df.columns:
            df["representative_track_id"] = df["resolved_track_id"]
            if "l1_id" in df.columns:
                df["track_id"] = df["l1_id"].fillna(df["resolved_track_id"])
            else:
                df["track_id"] = df["resolved_track_id"]
            df = df.drop(columns=["resolved_track_id"])

        if filtered and merge_enabled:
            df = merge_consecutive_plays(
                df,
                min_ms,
                max_gap_minutes=max_merge_gap_minutes,
                boundary_column=boundary_column,
                dynamic_threshold=dynamic_threshold,
            )
            if min_ms > 0:
                from backend.domains.playback.counting import filter_effective_plays

                df = filter_effective_plays(df, min_ms=min_ms, dynamic_threshold=dynamic_threshold)

        # Primary-credit fields are still needed by track/album consumers,
        # but their identity and display must follow the same global resolver
        # as artist fan-out.  No rows are removed on this path.
        from backend.domains.metadata.artist_identity import canonicalize_artist_frame

        df = canonicalize_artist_frame(df, conn, dedupe=False)

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
    max_merge_gap_minutes: int | None = 5,
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
    from backend.domains.metadata.track_identity import get_track_identity_revision

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
        track_identity_revision=get_track_identity_revision(conn),
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
    max_merge_gap_minutes: int | None = 5,
    boundary_column: str | None = None,
    identity_revision: int = 0,
    track_credit_revision: int = 0,
    track_identity_revision: int = 0,
) -> pd.DataFrame:
    """Same as _load_plays_cached but fans out through effective credits after merge
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

        identity_ready = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='track_l1_external_ids'"
        ).fetchone()
        if identity_ready:
            identity_columns = (
                "p.track_id AS source_track_id, "
                "COALESCE(li_spotify.l1_id, li_local.l1_id, p.track_id) AS l1_id, "
                "COALESCE(li_spotify.representative_track_id, "
                "li_local.representative_track_id, p.track_id) AS resolved_track_id"
            )
            identity_joins = (
                "LEFT JOIN tracks t_source ON p.track_id = t_source.track_id "
                "LEFT JOIN track_l1_external_ids external_spotify "
                "ON external_spotify.provider='spotify' "
                "AND external_spotify.external_track_id="
                "COALESCE(NULLIF(p.spotify_track_id_at_play, ''), "
                "NULLIF(t_source.spotify_track_id, '')) "
                "LEFT JOIN track_l1_identities li_spotify "
                "ON li_spotify.l1_id=external_spotify.l1_id "
                "AND li_spotify.identity_status!='superseded' "
                "LEFT JOIN track_l1_identities li_local "
                "ON li_local.fallback_track_id=p.track_id "
                "AND li_local.identity_status!='superseded' "
                "AND COALESCE(NULLIF(p.spotify_track_id_at_play, ''), "
                "NULLIF(t_source.spotify_track_id, '')) IS NULL "
                "LEFT JOIN tracks t ON t.track_id=COALESCE("
                "li_spotify.representative_track_id, "
                "li_local.representative_track_id, p.track_id) "
            )
        else:
            identity_columns = (
                "p.track_id AS source_track_id, p.track_id AS l1_id, "
                "p.track_id AS resolved_track_id"
            )
            identity_joins = (
                "LEFT JOIN tracks t_source ON p.track_id = t_source.track_id "
                "LEFT JOIN tracks t ON p.track_id = t.track_id "
            )
        if columns == "*":
            if join_albums:
                cols = f"p.*, {identity_columns}, t.track_name, t.spotify_track_uri, a.artist_name, al.album_name"
            else:
                cols = f"p.*, {identity_columns}, t.track_name, t.spotify_track_uri, a.artist_name"
            if filtered:
                cols += ", stm.duration_ms"
        else:
            cols = f"{columns}, {identity_columns}"

        # Step 1: Load single-artist data (same as _load_plays_cached)
        if join_albums:
            from_clause = (
                "FROM plays p "
                + identity_joins
                + "LEFT JOIN artists a ON t.artist_id = a.artist_id "
                "LEFT JOIN albums al ON t.album_id = al.album_id"
            )
        else:
            from_clause = (
                "FROM plays p "
                + identity_joins
                + "LEFT JOIN artists a ON t.artist_id = a.artist_id"
            )
        if filtered:
            from_clause += (
                " LEFT JOIN spotify_track_meta stm ON stm.spotify_track_id="
                "COALESCE(NULLIF(p.spotify_track_id_at_play, ''), "
                "NULLIF(t_source.spotify_track_id, ''))"
            )

        sql = f"SELECT {cols} {from_clause} {where} ORDER BY p.ts"
        df = pd.read_sql_query(sql, conn, params=params)
        if "resolved_track_id" in df.columns:
            df["representative_track_id"] = df["resolved_track_id"]
            if "l1_id" in df.columns:
                df["track_id"] = df["l1_id"].fillna(df["resolved_track_id"])
            else:
                df["track_id"] = df["resolved_track_id"]
            df = df.drop(columns=["resolved_track_id"])

        if filtered and merge_enabled:
            df = merge_consecutive_plays(
                df,
                min_ms,
                max_gap_minutes=max_merge_gap_minutes,
                boundary_column=boundary_column,
                dynamic_threshold=dynamic_threshold,
            )
            if min_ms > 0:
                from backend.domains.playback.counting import filter_effective_plays

                df = filter_effective_plays(df, min_ms=min_ms, dynamic_threshold=dynamic_threshold)

        # Step 2: Fan out through the raw + manual effective credit resolver.
        # Assign the event identity before the many-to-many merge.  A merged
        # logical play can share its source play_id with another output, so
        # play_id alone is not a valid artist dedupe key.
        from backend.domains.playback.counting import assign_logical_event_id

        df = assign_logical_event_id(df, preserve_legacy_artist_event_id=True)
        from backend.domains.metadata.track_credits import get_effective_track_credit_frame

        track_artists_df = get_effective_track_credit_frame(conn).rename(
            columns={"track_id": "representative_track_id"}
        )
        # Drop the single-artist artist_name (will be replaced by fan-out join)
        df = df.drop(columns=["artist_name"], errors="ignore")
        df = df.merge(
            track_artists_df[
                ["representative_track_id", "artist_id", "raw_artist_id", "artist_name"]
            ],
            on="representative_track_id",
            how="inner",
        )
        df["artist_id"] = df["raw_artist_id"]
        df = df.drop(columns=["raw_artist_id"])

        from backend.domains.metadata.artist_identity import canonicalize_artist_frame

        df = canonicalize_artist_frame(df, conn)

        # Keep the stable logical-event ordinal after artist fan-out. A single
        # play can produce several credited-artist rows; consumers that reason
        # about sequence continuity must compare event ordinals rather than
        # treating the additional credit rows as intervening plays.

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
    max_merge_gap_minutes: int | None = 5,
    boundary_column: str | None = "source_album_id",
):
    """Load plays with multi-artist fan-out for artist-statistics queries.

    Identical to load_plays() but joins through track_artists so each play
    produces one row per credited artist. artist_name comes from the
    track_artists join, not from tracks.artist_id.

    DO NOT USE for total play counts, track statistics, or album statistics
    — it duplicates rows for multi-artist tracks.
    """
    from backend.domains.metadata.artist_identity import get_identity_revision
    from backend.domains.metadata.track_credits import get_track_credit_revision
    from backend.domains.metadata.track_identity import get_track_identity_revision

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
        identity_revision=get_identity_revision(conn),
        track_credit_revision=get_track_credit_revision(conn),
        track_identity_revision=get_track_identity_revision(conn),
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
    """Return the effective multi-artist display map keyed only by L1 ID.

    L1 IDs and raw ``tracks.track_id`` values are independent numeric
    namespaces and can collide.  Mixing both in one dictionary silently
    overwrites unrelated songs, so raw-source consumers must use
    :func:`get_raw_track_all_artists_map` explicitly.
    """
    conn = get_db()
    from backend.domains.metadata.track_credits import canonical_artist_names_for_effective_tracks

    raw_resolved = canonical_artist_names_for_effective_tracks(conn)
    resolved: dict[int, list[str]] = {}
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='track_l1_identities'"
    ).fetchone():
        for l1_id, representative_track_id in conn.execute(
            """SELECT l1_id, representative_track_id
                 FROM track_l1_identities
                WHERE representative_track_id IS NOT NULL"""
        ).fetchall():
            names = raw_resolved.get(int(representative_track_id))
            if names:
                resolved[int(l1_id)] = names
    else:
        resolved = raw_resolved
    conn.close()
    return {tid: ", ".join(names) for tid, names in resolved.items() if len(names) > 1}


@lru_cache(maxsize=1)
def get_track_artist_names_map() -> dict[int, list[str]]:
    """Return effective artist names keyed only by canonical L1 ID."""
    conn = get_db()
    from backend.domains.metadata.track_credits import canonical_artist_names_for_effective_tracks

    raw_result = canonical_artist_names_for_effective_tracks(conn)
    result: dict[int, list[str]] = {}
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='track_l1_identities'"
    ).fetchone():
        for l1_id, representative_track_id in conn.execute(
            """SELECT l1_id, representative_track_id
                 FROM track_l1_identities
                WHERE representative_track_id IS NOT NULL"""
        ).fetchall():
            names = raw_result.get(int(representative_track_id))
            if names:
                result[int(l1_id)] = names
    else:
        result = raw_result
    conn.close()
    return result


def get_raw_track_artist_names_map() -> dict[int, list[str]]:
    """Return effective artist names keyed by immutable source ``track_id``."""
    conn = get_db()
    try:
        from backend.domains.metadata.track_credits import (
            canonical_artist_names_for_effective_tracks,
        )

        return canonical_artist_names_for_effective_tracks(conn)
    finally:
        conn.close()


def get_raw_track_all_artists_map() -> dict[int, str]:
    """Return multi-artist display labels keyed by source ``track_id``."""
    return {
        track_id: ", ".join(names)
        for track_id, names in get_raw_track_artist_names_map().items()
        if len(names) > 1
    }


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
    if not names_map and "artist_names" not in weekly_df.columns:
        return weekly_df

    expanded = weekly_df.copy()
    existing_names = (
        expanded["artist_names"] if "artist_names" in expanded.columns else [None] * len(expanded)
    )
    expanded["_credited_artist_names"] = [
        existing
        if isinstance(existing, list) and existing
        else names_map.get(track_id, [artist_name])
        for track_id, artist_name, existing in zip(
            expanded["track_id"], expanded["artist_name"], existing_names
        )
    ]
    expanded = expanded.explode("_credited_artist_names", ignore_index=True)
    expanded["artist_name"] = expanded.pop("_credited_artist_names")
    return expanded


def primary_artist_names_for_tracks(df: pd.DataFrame) -> pd.DataFrame:
    """Use the primary canonical artist for album-owner and primary joins.

    Billboard record calculations may receive a frame after
    :func:`enrich_track_artist_names`, where ``artist_name`` is intentionally a
    comma-separated display label. Artist-level metrics should use
    :func:`fan_out_weekly_for_artists` instead.
    """
    if df.empty or "track_id" not in df.columns or "artist_name" not in df.columns:
        return df

    names_map = get_track_artist_names_map()
    if not names_map and "artist_names" not in df.columns:
        return df

    result = df.copy()

    existing_names = (
        result["artist_names"] if "artist_names" in result.columns else [None] * len(result)
    )
    result["artist_name"] = [
        existing[0]
        if isinstance(existing, list) and existing
        else (names_map.get(track_id) or [artist_name])[0]
        for track_id, artist_name, existing in zip(
            result["track_id"], result["artist_name"], existing_names
        )
    ]
    return result


# ═══════════════════════════════════════════════════════════════════════════
# Pre-aggregated Billboard weekly data
# ═══════════════════════════════════════════════════════════════════════════


def _agg_param_hash(
    min_ms: int,
    music_only: bool,
    week_start_dow: int,
    week_start_hour: int,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = 5,
    identity_revision: int = 0,
    track_credit_revision: int = 0,
    track_identity_revision: int = 0,
) -> str:
    """Compute a content-hash of the parameters that affect aggregation results."""
    from backend.domains.playback.logical_timeline import PLAYBACK_EVENT_POLICY_VERSION

    payload = json.dumps(
        [
            PLAYBACK_EVENT_POLICY_VERSION,
            min_ms,
            music_only,
            week_start_dow,
            week_start_hour,
            dynamic_threshold,
            max_merge_gap_minutes,
            identity_revision,
            track_credit_revision,
            track_identity_revision,
        ],
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def check_agg_valid(conn: sqlite3.Connection, param_hash: str) -> bool:
    """Check that the aggregate is bound to current facts and fact semantics."""
    try:
        config = _aggregation_config(conn)
        if config.get("param_hash") != param_hash:
            return False
        has_playback_state = conn.execute(
            """SELECT 1 FROM sqlite_master
               WHERE type='table' AND name='playback_import_state'"""
        ).fetchone()
        active_generation: str | None = None
        active_digest: str | None = None
        if has_playback_state:
            active_generation = _active_playback_generation(conn)
            if (
                active_generation is not None
                and config.get("data_generation_id") != active_generation
            ):
                return False
            active_digest = _active_playback_dataset_digest(conn)
            if config.get("source_dataset_digest") != active_digest:
                return False
        if active_generation is None and active_digest is None and "builder_version" not in config:
            # Transitional compatibility for pre-generation databases. Once
            # facts are bound or a v2 aggregate is published, every semantic
            # dependency below becomes mandatory.
            return True
        current_dependencies = _aggregation_fact_dependencies(conn)
        return all(config.get(key) == value for key, value in current_dependencies.items())
    except sqlite3.OperationalError:
        return False


def build_aggregations(
    min_ms: int = 30000,
    music_only: bool = True,
    week_start_dow: int = 4,
    week_start_hour: int = 0,
    progress_callback=None,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = 5,
    expected_generation_id: str | None = None,
) -> dict[str, int | str]:
    """Build all 3 pre-aggregated weekly Billboard tables from the plays table.

    Called after import_data() completes. Builds connection-local shadow tables
    and publishes all four live tables in one transaction, so readers observe
    either the old complete snapshot or the new complete snapshot.
    Returns row counts for each agg table.
    """
    import pandas as pd

    # Rebuilders are also used by maintenance scripts and portable fixtures
    # that may predate the versioned L1 identity tables.  Upgrade the writable
    # target before opening the build connection so the projection repair
    # below never silently falls back to raw ``track_id`` grain.
    ensure_schema()

    conn = get_db(readonly=False)
    build_generation_id = _active_playback_generation(conn)
    build_dataset_digest = _active_playback_dataset_digest(conn)
    if expected_generation_id is not None and build_generation_id != expected_generation_id:
        conn.close()
        raise RuntimeError(
            "active playback generation does not match the requested aggregate generation"
        )

    from backend.domains.metadata.artist_identity import get_identity_revision
    from backend.domains.metadata.track_credits import get_track_credit_revision
    from backend.domains.metadata.track_identity import (
        get_track_identity_revision,
        synchronize_track_identity_projection,
    )

    synchronize_track_identity_projection(conn)
    identity_revision = get_identity_revision(conn)
    track_credit_revision = get_track_credit_revision(conn)
    track_identity_revision = get_track_identity_revision(conn)
    semantic_dependencies = _aggregation_semantic_dependencies(
        conn,
        identity_revision=identity_revision,
        track_credit_revision=track_credit_revision,
        track_identity_revision=track_identity_revision,
    )
    param_hash = _agg_param_hash(
        min_ms,
        music_only,
        week_start_dow,
        week_start_hour,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        identity_revision=identity_revision,
        track_credit_revision=track_credit_revision,
        track_identity_revision=track_identity_revision,
    )

    f, fp = base_filters(min_ms=0, music_only=music_only)
    where = f"WHERE {f}" if f else ""

    # Load raw data with track dimensions needed for merge and aggregation
    # (ms_played filter is applied AFTER merge to preserve short fragments)
    df = pd.read_sql_query(
        f"""SELECT p.play_id, p.ts, p.ts_date, p.ts_dow, p.ts_hour, p.ms_played,
                   p.track_id AS source_track_id,
                   COALESCE(li_spotify.l1_id, li_local.l1_id) AS l1_id,
                   COALESCE(li_spotify.representative_track_id,
                            li_local.representative_track_id, p.track_id) AS track_id,
                   p.source_album_id, t.album_id, t.artist_id, stm.duration_ms
            FROM plays p
            JOIN tracks t_source ON p.track_id = t_source.track_id
            LEFT JOIN track_l1_external_ids external_spotify
              ON external_spotify.provider='spotify'
             AND external_spotify.external_track_id=COALESCE(
                    NULLIF(p.spotify_track_id_at_play, ''),
                    NULLIF(t_source.spotify_track_id, '')
                 )
            LEFT JOIN track_l1_identities li_spotify
              ON li_spotify.l1_id=external_spotify.l1_id
             AND li_spotify.identity_status!='superseded'
            LEFT JOIN track_l1_identities li_local
              ON li_local.fallback_track_id=p.track_id
             AND li_local.identity_status!='superseded'
             AND COALESCE(NULLIF(p.spotify_track_id_at_play, ''),
                          NULLIF(t_source.spotify_track_id, '')) IS NULL
            JOIN tracks t ON t.track_id=COALESCE(
                    li_spotify.representative_track_id,
                    li_local.representative_track_id,
                    p.track_id
                 )
            LEFT JOIN spotify_track_meta stm
              ON stm.spotify_track_id=COALESCE(
                    NULLIF(p.spotify_track_id_at_play, ''),
                    NULLIF(t_source.spotify_track_id, '')
                 )
            {where}
            ORDER BY p.ts, p.play_id""",
        conn,
        params=fp,
    )

    if df.empty:
        _clear_aggregations_for_generation(
            conn,
            data_generation_id=build_generation_id,
        )
        conn.close()
        from backend.core.cache_manager import invalidate_playback_caches

        invalidate_playback_caches()
        return {"tracks": 0, "albums": 0, "track_sources": 0, "artists": 0}

    if progress_callback:
        progress_callback("合并连续播放...", 0.0)

    # Store source_album_id for album-level aggregation before dropping
    df["_source_album_id"] = df["source_album_id"].fillna(0).astype(int)

    # Merge consecutive same-track plays, then apply ms_played threshold
    df = merge_consecutive_plays(
        df,
        min_ms,
        max_gap_minutes=max_merge_gap_minutes,
        boundary_column="source_album_id",
        dynamic_threshold=dynamic_threshold,
    )
    if min_ms > 0:
        from backend.domains.playback.counting import filter_effective_plays

        df = filter_effective_plays(df, min_ms=min_ms, dynamic_threshold=dynamic_threshold)

    if df.empty:
        _clear_aggregations_for_generation(
            conn,
            data_generation_id=build_generation_id,
        )
        conn.close()
        from backend.core.cache_manager import invalidate_playback_caches

        invalidate_playback_caches()
        return {"tracks": 0, "albums": 0, "track_sources": 0, "artists": 0}

    event_df = df.copy()
    from backend.domains.playback.logical_timeline import build_billboard_weighted_frame

    df = build_billboard_weighted_frame(
        event_df,
        week_start_dow=week_start_dow,
        week_start_hour=week_start_hour,
    )

    _prepare_aggregation_shadows(conn)

    results = {}

    # 1. Tracks
    if progress_callback:
        progress_callback("预聚合: 单曲...", 0.0)
    tracks_agg = (
        df.groupby(["billboard_week", "l1_id", "track_id"])
        .agg(play_count=("play_count", "sum"), total_ms=("total_ms", "sum"))
        .reset_index()
    )
    t_rows = [
        (
            str(r.billboard_week),
            int(r.l1_id),
            int(r.track_id),
            int(r.play_count),
            int(r.total_ms),
        )
        for r in tracks_agg.itertuples(index=False)
    ]
    _write_agg_batch(
        conn,
        _AGG_SHADOW_TABLES["agg_weekly_tracks"],
        t_rows,
        ["billboard_week", "l1_id", "track_id", "play_count", "total_ms"],
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
        df.groupby(["billboard_week", "ts_date", "l1_id", "track_id", "_source_album_id"])
        .agg(play_count=("play_count", "sum"), total_ms=("total_ms", "sum"))
        .reset_index()
        .rename(columns={"ts_date": "play_date", "_source_album_id": "source_album_id"})
    )
    ts_rows = [
        (
            str(r.billboard_week),
            str(r.play_date),
            int(r.l1_id),
            int(r.track_id),
            int(r.source_album_id),
            int(r.play_count),
            int(r.total_ms),
        )
        for r in track_sources_agg.itertuples(index=False)
    ]
    _write_agg_batch(
        conn,
        _AGG_SHADOW_TABLES["agg_weekly_track_sources"],
        ts_rows,
        [
            "billboard_week",
            "play_date",
            "l1_id",
            "track_id",
            "source_album_id",
            "play_count",
            "total_ms",
        ],
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
            .agg(play_count=("play_count", "sum"), total_ms=("total_ms", "sum"))
            .reset_index()
            .rename(columns={"_album_id_for_agg": "album_id"})
        )
        a_rows = [
            (str(r.billboard_week), int(r.album_id), int(r.play_count), int(r.total_ms))
            for r in albums_agg.itertuples(index=False)
        ]
        _write_agg_batch(
            conn,
            _AGG_SHADOW_TABLES["agg_weekly_albums"],
            a_rows,
            ["billboard_week", "album_id", "play_count", "total_ms"],
        )
        results["albums"] = len(a_rows)
    else:
        results["albums"] = 0
    if progress_callback:
        progress_callback("预聚合: 专辑完成", 0.66)

    # 4. Artists — fan out through effective raw + manual credits.
    if progress_callback:
        progress_callback("预聚合: 艺人...", 0.66)
    from backend.domains.metadata.track_credits import (
        get_effective_track_credit_frame,
    )
    from backend.domains.playback.counting import assign_logical_event_id

    # The track aggregation above operates on logical event rows.  Preserve
    # that same grain through artist fan-out so canonicalization can collapse
    # aliases without collapsing two expanded events from one source play.
    df_artists = assign_logical_event_id(event_df)
    track_artists_df = get_effective_track_credit_frame(conn)
    df_artists = df_artists.merge(
        track_artists_df, on="track_id", how="inner", suffixes=("_primary", "")
    )
    df_artists["artist_id"] = df_artists["raw_artist_id"]
    df_artists = df_artists.drop(columns=["raw_artist_id"])
    from backend.domains.metadata.artist_identity import (
        canonicalize_artist_frame,
    )

    df_artists = canonicalize_artist_frame(df_artists, conn)
    df_artists = build_billboard_weighted_frame(
        df_artists,
        week_start_dow=week_start_dow,
        week_start_hour=week_start_hour,
    )
    artists_agg = (
        df_artists.groupby(["billboard_week", "artist_id"])
        .agg(play_count=("play_count", "sum"), total_ms=("total_ms", "sum"))
        .reset_index()
    )
    ar_rows = [
        (str(r.billboard_week), int(r.artist_id), int(r.play_count), int(r.total_ms))
        for r in artists_agg.itertuples(index=False)
    ]
    _write_agg_batch(
        conn,
        _AGG_SHADOW_TABLES["agg_weekly_artists"],
        ar_rows,
        ["billboard_week", "artist_id", "play_count", "total_ms"],
    )
    results["artists"] = len(ar_rows)
    if progress_callback:
        progress_callback("预聚合: 艺人完成", 1.0)

    _validate_aggregation_shadows(conn)
    _publish_aggregation_shadows(
        conn,
        param_hash=param_hash,
        data_generation_id=build_generation_id,
        data_digest=build_dataset_digest,
        build_strategy="full",
        semantic_dependencies=semantic_dependencies,
    )
    for result_key, live_table in (
        ("tracks", "agg_weekly_tracks"),
        ("albums", "agg_weekly_albums"),
        ("track_sources", "agg_weekly_track_sources"),
        ("artists", "agg_weekly_artists"),
    ):
        results[result_key] = int(
            conn.execute(f'SELECT COUNT(*) FROM "{live_table}"').fetchone()[0]
        )
    results["build_strategy"] = "full"
    results["affected_weeks"] = 0
    conn.close()

    # A rebuild changes the source of truth for every Billboard cache.  Clear
    # registered runtime caches here so API-triggered rebuilds cannot continue
    # serving the previous aggregate snapshot from the same process.
    from backend.core.cache_manager import invalidate_playback_caches

    invalidate_playback_caches()

    return results


def _weekly_aggregate_map(
    frame: pd.DataFrame,
    group_columns: list[str],
) -> dict[tuple[Any, ...], tuple[int, int]]:
    if frame.empty:
        return {}
    grouped = (
        frame.groupby(group_columns, dropna=False)
        .agg(play_count=("play_count", "sum"), total_ms=("total_ms", "sum"))
        .reset_index()
    )
    result: dict[tuple[Any, ...], tuple[int, int]] = {}
    for row in grouped.to_dict("records"):
        key: list[Any] = []
        for column in group_columns:
            value = row[column]
            if column in {"billboard_week", "play_date", "ts_date"}:
                key.append(str(value))
            else:
                key.append(int(value))
        result[tuple(key)] = (int(row["play_count"]), int(row["total_ms"]))
    return result


def _billboard_aggregate_maps(
    conn: sqlite3.Connection,
    events: pd.DataFrame,
    *,
    week_start_dow: int,
    week_start_hour: int,
) -> dict[str, tuple[tuple[str, ...], dict[tuple[Any, ...], tuple[int, int]]]]:
    import pandas as pd

    key_columns = {
        "agg_weekly_tracks": ("billboard_week", "l1_id", "track_id"),
        "agg_weekly_albums": ("billboard_week", "album_id"),
        "agg_weekly_track_sources": (
            "billboard_week",
            "play_date",
            "l1_id",
            "track_id",
            "source_album_id",
        ),
        "agg_weekly_artists": ("billboard_week", "artist_id"),
    }
    if events.empty:
        return {table: (columns, {}) for table, columns in key_columns.items()}

    from backend.domains.playback.logical_timeline import build_billboard_weighted_frame

    weighted = build_billboard_weighted_frame(
        events,
        week_start_dow=week_start_dow,
        week_start_hour=week_start_hour,
    )
    weighted["source_album_id"] = weighted["_source_album_id"].fillna(0).astype(int)
    track_map = _weekly_aggregate_map(weighted, ["billboard_week", "l1_id", "track_id"])
    source_map = _weekly_aggregate_map(
        weighted,
        ["billboard_week", "ts_date", "l1_id", "track_id", "source_album_id"],
    )
    source_map = {
        (week, play_date, l1_id, track_id, source_album_id): values
        for (week, play_date, l1_id, track_id, source_album_id), values in source_map.items()
    }

    album_weighted = weighted.copy()
    fallback_album = pd.to_numeric(album_weighted["album_id"], errors="coerce").astype("Int64")
    source_album = pd.to_numeric(album_weighted["source_album_id"], errors="coerce").astype("Int64")
    album_weighted["album_id"] = source_album.where(source_album.fillna(0) != 0, fallback_album)
    album_weighted = album_weighted[album_weighted["album_id"].notna()].copy()
    album_map = _weekly_aggregate_map(album_weighted, ["billboard_week", "album_id"])

    from backend.domains.metadata.artist_identity import canonicalize_artist_frame
    from backend.domains.metadata.track_credits import get_effective_track_credit_frame
    from backend.domains.playback.counting import assign_logical_event_id

    artist_events = assign_logical_event_id(events)
    credits = get_effective_track_credit_frame(conn)
    artist_events = artist_events.merge(
        credits,
        on="track_id",
        how="inner",
        suffixes=("_primary", ""),
    )
    if artist_events.empty:
        artist_map: dict[tuple[Any, ...], tuple[int, int]] = {}
    else:
        artist_events["artist_id"] = artist_events["raw_artist_id"]
        artist_events = artist_events.drop(columns=["raw_artist_id"])
        artist_events = canonicalize_artist_frame(artist_events, conn)
        artist_weighted = build_billboard_weighted_frame(
            artist_events,
            week_start_dow=week_start_dow,
            week_start_hour=week_start_hour,
        )
        artist_map = _weekly_aggregate_map(
            artist_weighted,
            ["billboard_week", "artist_id"],
        )

    return {
        "agg_weekly_tracks": (key_columns["agg_weekly_tracks"], track_map),
        "agg_weekly_albums": (key_columns["agg_weekly_albums"], album_map),
        "agg_weekly_track_sources": (
            key_columns["agg_weekly_track_sources"],
            source_map,
        ),
        "agg_weekly_artists": (key_columns["agg_weekly_artists"], artist_map),
    }


def _apply_aggregate_map_delta(
    conn: sqlite3.Connection,
    *,
    shadow_table: str,
    key_columns: tuple[str, ...],
    old: dict[tuple[Any, ...], tuple[int, int]],
    new: dict[tuple[Any, ...], tuple[int, int]],
) -> None:
    where = " AND ".join(f"{column}=?" for column in key_columns)
    insert_columns = [*key_columns, "play_count", "total_ms"]
    placeholders = ",".join("?" for _ in insert_columns)
    for key in sorted(old.keys() | new.keys()):
        old_count, old_ms = old.get(key, (0, 0))
        new_count, new_ms = new.get(key, (0, 0))
        count_delta = new_count - old_count
        ms_delta = new_ms - old_ms
        if count_delta == 0 and ms_delta == 0:
            continue
        cursor = conn.execute(
            f'UPDATE temp."{shadow_table}" '
            f"SET play_count=play_count+?, total_ms=total_ms+? WHERE {where}",
            (count_delta, ms_delta, *key),
        )
        if cursor.rowcount == 0:
            if old_count or old_ms:
                raise RuntimeError(f"Billboard base partition missing row in {shadow_table}")
            conn.execute(
                f'INSERT INTO temp."{shadow_table}" '
                f"({','.join(insert_columns)}) VALUES ({placeholders})",
                (*key, new_count, new_ms),
            )
    conn.execute(f'DELETE FROM temp."{shadow_table}" WHERE play_count=0 AND total_ms=0')


_HISTORICAL_WEEK_REPLACEMENT_MAX_ROWS = 100_000


class _HistoricalWeekReplacementFallbackError(RuntimeError):
    """Internal signal that the bounded proof must use a full rebuild."""


def _billboard_week_windows(
    affected_weeks: set[str],
    *,
    week_start_dow: int,
    week_start_hour: int,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Return merged UTC windows for valid adjacent local Billboard weeks."""
    import pandas as pd

    from backend.domains.playback.logical_timeline import PLAYBACK_TIMEZONE

    starts: list[pd.Timestamp] = []
    for encoded in sorted(affected_weeks):
        try:
            local_start = pd.Timestamp(encoded, tz=PLAYBACK_TIMEZONE) + pd.Timedelta(
                hours=week_start_hour
            )
        except (TypeError, ValueError) as exc:
            raise _HistoricalWeekReplacementFallbackError("affected_week_invalid") from exc
        if local_start.weekday() != int(week_start_dow):
            raise _HistoricalWeekReplacementFallbackError("affected_week_boundary_invalid")
        starts.append(local_start.tz_convert("UTC"))
    windows: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for start in starts:
        end = start + pd.Timedelta(days=7)
        if windows and start == windows[-1][1]:
            windows[-1] = (windows[-1][0], end)
        else:
            windows.append((start, end))
    return windows


def _historical_replacement_row_query() -> str:
    return """SELECT p.play_id, p.ts, p.ts_date, p.ts_dow, p.ts_hour,
                     p.ms_played, p.track_id AS source_track_id,
                     COALESCE(li_spotify.l1_id, li_local.l1_id) AS l1_id,
                     COALESCE(li_spotify.representative_track_id,
                              li_local.representative_track_id, p.track_id) AS track_id,
                     p.source_album_id, t.album_id, t.artist_id, stm.duration_ms
              FROM plays p
              JOIN tracks t_source ON p.track_id=t_source.track_id
              LEFT JOIN track_l1_external_ids external_spotify
                ON external_spotify.provider='spotify'
               AND external_spotify.external_track_id=COALESCE(
                      NULLIF(p.spotify_track_id_at_play, ''),
                      NULLIF(t_source.spotify_track_id, '')
                   )
              LEFT JOIN track_l1_identities li_spotify
                ON li_spotify.l1_id=external_spotify.l1_id
               AND li_spotify.identity_status!='superseded'
              LEFT JOIN track_l1_identities li_local
                ON li_local.fallback_track_id=p.track_id
               AND li_local.identity_status!='superseded'
               AND COALESCE(NULLIF(p.spotify_track_id_at_play, ''),
                            NULLIF(t_source.spotify_track_id, '')) IS NULL
              JOIN tracks t ON t.track_id=COALESCE(
                      li_spotify.representative_track_id,
                      li_local.representative_track_id,
                      p.track_id
                   )
              LEFT JOIN spotify_track_meta stm
                ON stm.spotify_track_id=COALESCE(
                     NULLIF(p.spotify_track_id_at_play, ''),
                     NULLIF(t_source.spotify_track_id, '')
                   )"""


def _historical_rows_can_merge(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    max_gap_minutes: int,
) -> bool:
    import pandas as pd

    if left["l1_id"] != right["l1_id"]:
        return False
    if left["source_album_id"] != right["source_album_id"]:
        return False
    left_end = pd.to_datetime(left["ts"], errors="coerce", utc=True)
    right_end = pd.to_datetime(right["ts"], errors="coerce", utc=True)
    if pd.isna(left_end) or pd.isna(right_end):
        return False
    right_start = right_end - pd.to_timedelta(max(int(right["ms_played"] or 0), 0), unit="ms")
    gap = right_start - left_end
    return pd.Timedelta(seconds=-2) <= gap <= pd.Timedelta(minutes=max_gap_minutes)


def _adjacent_historical_row(
    conn: sqlite3.Connection,
    row: dict[str, Any],
    *,
    forward: bool,
) -> dict[str, Any] | None:
    comparator = ">" if forward else "<"
    order = "ASC" if forward else "DESC"
    candidate = conn.execute(
        _historical_replacement_row_query()
        + f""" WHERE (p.ts {comparator} ? OR (p.ts=? AND p.play_id {comparator} ?))
              ORDER BY p.ts {order}, p.play_id {order} LIMIT 1""",
        (row["ts"], row["ts"], row["play_id"]),
    ).fetchone()
    return dict(candidate) if candidate is not None else None


def _load_historical_week_replacement_frame(
    conn: sqlite3.Connection,
    windows: list[tuple[pd.Timestamp, pd.Timestamp]],
    *,
    max_gap_minutes: int,
) -> pd.DataFrame:
    """Load only current raw rows that can contribute to the target weeks.

    Seed rows overlap one target week by their inferred listened interval.
    Their complete adjacent same-track/source merge chains are then included
    so logical event qualification remains identical to a lifetime rebuild.
    """
    import pandas as pd

    maximum_ms = int(
        conn.execute("SELECT COALESCE(MAX(MAX(ms_played, 0)), 0) FROM plays").fetchone()[0] or 0
    )
    selected: dict[int, dict[str, Any]] = {}
    for start, end in windows:
        upper = end + pd.to_timedelta(maximum_ms, unit="ms")
        raw_rows = conn.execute(
            _historical_replacement_row_query()
            + """ WHERE julianday(p.ts) > julianday(?)
                    AND julianday(p.ts) < julianday(?)
                  ORDER BY p.ts, p.play_id
                  LIMIT ?""",
            (
                start.isoformat(),
                upper.isoformat(),
                _HISTORICAL_WEEK_REPLACEMENT_MAX_ROWS + 1,
            ),
        ).fetchall()
        if len(raw_rows) > _HISTORICAL_WEEK_REPLACEMENT_MAX_ROWS:
            raise _HistoricalWeekReplacementFallbackError("historical_scope_row_limit_exceeded")
        rows = [dict(raw) for raw in raw_rows]
        overlaps: list[bool] = []
        for row in rows:
            end_at = pd.to_datetime(row["ts"], errors="coerce", utc=True)
            if pd.isna(end_at):
                overlaps.append(False)
                continue
            start_at = end_at - pd.to_timedelta(max(int(row["ms_played"] or 0), 0), unit="ms")
            overlaps.append(bool(end_at > start and start_at < end))

        # Resolve every in-window run in one linear pass. The previous
        # implementation issued two ordered SQLite queries for every seed row,
        # which made a one-week replacement slower than a lifetime rebuild.
        # Rows that do not themselves overlap the target week are retained when
        # they belong to a selected run, preserving qualification semantics.
        run_start = 0
        selected_runs: list[tuple[int, int]] = []
        while run_start < len(rows):
            run_end = run_start + 1
            while run_end < len(rows) and _historical_rows_can_merge(
                rows[run_end - 1],
                rows[run_end],
                max_gap_minutes=max_gap_minutes,
            ):
                run_end += 1
            if any(overlaps[run_start:run_end]):
                selected_runs.append((run_start, run_end))
                for row in rows[run_start:run_end]:
                    selected[int(row["play_id"])] = row
            run_start = run_end

        # Only a selected run touching the SQL window boundary can continue
        # outside the bulk-loaded frame. At most one chain per side needs the
        # ordered neighbor walker, independent of the number of plays in-week.
        if selected_runs and selected_runs[0][0] == 0:
            cursor = rows[0]
            while True:
                previous = _adjacent_historical_row(conn, cursor, forward=False)
                if previous is None or not _historical_rows_can_merge(
                    previous,
                    cursor,
                    max_gap_minutes=max_gap_minutes,
                ):
                    break
                selected[int(previous["play_id"])] = previous
                if len(selected) > _HISTORICAL_WEEK_REPLACEMENT_MAX_ROWS:
                    raise _HistoricalWeekReplacementFallbackError(
                        "historical_scope_row_limit_exceeded"
                    )
                cursor = previous
        if selected_runs and selected_runs[-1][1] == len(rows):
            cursor = rows[-1]
            while True:
                following = _adjacent_historical_row(conn, cursor, forward=True)
                if following is None or not _historical_rows_can_merge(
                    cursor,
                    following,
                    max_gap_minutes=max_gap_minutes,
                ):
                    break
                selected[int(following["play_id"])] = following
                if len(selected) > _HISTORICAL_WEEK_REPLACEMENT_MAX_ROWS:
                    raise _HistoricalWeekReplacementFallbackError(
                        "historical_scope_row_limit_exceeded"
                    )
                cursor = following
        if len(selected) > _HISTORICAL_WEEK_REPLACEMENT_MAX_ROWS:
            raise _HistoricalWeekReplacementFallbackError("historical_scope_row_limit_exceeded")
    if not selected:
        return pd.DataFrame()
    return pd.DataFrame(selected.values()).sort_values(["ts", "play_id"]).reset_index(drop=True)


def _insert_historical_replacement_maps(
    conn: sqlite3.Connection,
    maps: dict[str, tuple[tuple[str, ...], dict[tuple[Any, ...], tuple[int, int]]]],
    *,
    affected_weeks: set[str],
) -> None:
    for table, shadow_table in _AGG_SHADOW_TABLES.items():
        key_columns, values = maps[table]
        columns = [*key_columns, "play_count", "total_ms"]
        placeholders = ",".join("?" for _ in columns)
        rows = [
            (*key, play_count, total_ms)
            for key, (play_count, total_ms) in sorted(values.items())
            if str(key[0]) in affected_weeks
        ]
        conn.executemany(
            f'INSERT INTO temp."{shadow_table}" ({",".join(columns)}) VALUES ({placeholders})',
            rows,
        )


def build_aggregations_for_replaced_weeks(
    affected_weeks: set[str] | frozenset[str],
    *,
    replacement_scope_exact: bool,
    expected_generation_id: str,
    expected_dataset_digest: str,
    previous_dataset_digest: str | None,
    min_ms: int = 30000,
    music_only: bool = True,
    week_start_dow: int = 4,
    week_start_hour: int = 0,
    progress_callback=None,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = 5,
) -> dict[str, int | str]:
    """Exactly replace proven historical week partitions from current facts."""
    import pandas as pd

    ensure_schema()

    def full_fallback(reason: str) -> dict[str, int | str]:
        result = build_aggregations(
            min_ms=min_ms,
            music_only=music_only,
            week_start_dow=week_start_dow,
            week_start_hour=week_start_hour,
            progress_callback=progress_callback,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
            expected_generation_id=expected_generation_id,
        )
        result["fallback_reason"] = reason
        return result

    weeks = {str(week) for week in affected_weeks}
    if (
        not replacement_scope_exact
        or not weeks
        or max_merge_gap_minutes is None
        or max_merge_gap_minutes < 0
    ):
        return full_fallback("historical_replacement_scope_not_proven")

    conn = get_db(readonly=False)
    try:
        build_generation_id = _active_playback_generation(conn)
        build_dataset_digest = _active_playback_dataset_digest(conn)
        if (
            build_generation_id != expected_generation_id
            or build_dataset_digest != expected_dataset_digest
        ):
            raise _HistoricalWeekReplacementFallbackError("historical_active_lineage_drift")

        from backend.domains.metadata.artist_identity import get_identity_revision
        from backend.domains.metadata.track_credits import get_track_credit_revision
        from backend.domains.metadata.track_identity import (
            get_track_identity_revision,
            synchronize_track_identity_projection,
        )

        synchronize_track_identity_projection(conn)
        identity_revision = get_identity_revision(conn)
        credit_revision = get_track_credit_revision(conn)
        track_identity_revision = get_track_identity_revision(conn)
        current_dependencies = _aggregation_semantic_dependencies(
            conn,
            identity_revision=identity_revision,
            track_credit_revision=credit_revision,
            track_identity_revision=track_identity_revision,
        )
        reusable_dependencies = dict(current_dependencies)
        reusable_dependencies.pop("album_project_revision", None)
        param_hash = _agg_param_hash(
            min_ms,
            music_only,
            week_start_dow,
            week_start_hour,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
            identity_revision=identity_revision,
            track_credit_revision=credit_revision,
            track_identity_revision=track_identity_revision,
        )
        config = _aggregation_config(conn)
        if config.get("param_hash") != param_hash or any(
            config.get(key) != value for key, value in reusable_dependencies.items()
        ):
            raise _HistoricalWeekReplacementFallbackError("historical_base_semantics_incompatible")
        base_generation_id = config.get("data_generation_id")
        if (
            previous_dataset_digest is None
            or not base_generation_id
            or base_generation_id == build_generation_id
            or config.get("source_dataset_digest") != previous_dataset_digest
        ):
            raise _HistoricalWeekReplacementFallbackError("historical_base_lineage_missing")

        live_weeks = {
            str(row[0])
            for row in conn.execute(
                "SELECT DISTINCT billboard_week FROM agg_weekly_tracks"
            ).fetchall()
        }
        total_weeks = live_weeks | weeks
        if total_weeks and len(weeks) / len(total_weeks) > 0.25:
            raise _HistoricalWeekReplacementFallbackError("affected_week_ratio_exceeded")
        windows = _billboard_week_windows(
            weeks,
            week_start_dow=week_start_dow,
            week_start_hour=week_start_hour,
        )
        latest_ts = conn.execute("SELECT MAX(ts) FROM plays").fetchone()[0]
        from backend.domains.playback.logical_timeline import (
            billboard_week_for_timestamps,
        )

        open_week = billboard_week_for_timestamps(
            pd.Series([latest_ts], dtype=object),
            week_start_dow=week_start_dow,
            week_start_hour=week_start_hour,
        ).iloc[0]
        if pd.isna(open_week) or any(week >= str(open_week) for week in weeks):
            raise _HistoricalWeekReplacementFallbackError("affected_week_not_complete")

        raw = _load_historical_week_replacement_frame(
            conn,
            windows,
            max_gap_minutes=int(max_merge_gap_minutes),
        )
        if raw.empty:
            events = raw
        else:
            raw["_source_album_id"] = raw["source_album_id"].fillna(0).astype(int)
            events = merge_consecutive_plays(
                raw,
                min_ms,
                max_gap_minutes=max_merge_gap_minutes,
                boundary_column="source_album_id",
                dynamic_threshold=dynamic_threshold,
            )
            if min_ms > 0:
                from backend.domains.playback.counting import filter_effective_plays

                events = filter_effective_plays(
                    events,
                    min_ms=min_ms,
                    dynamic_threshold=dynamic_threshold,
                )
        maps = _billboard_aggregate_maps(
            conn,
            events,
            week_start_dow=week_start_dow,
            week_start_hour=week_start_hour,
        )
        _prepare_aggregation_shadows(conn)
        _copy_unaffected_aggregation_weeks(conn, weeks)
        _insert_historical_replacement_maps(conn, maps, affected_weeks=weeks)
        _validate_aggregation_shadows(conn)
        conn.commit()
        _publish_aggregation_shadows(
            conn,
            param_hash=param_hash,
            data_generation_id=build_generation_id,
            data_digest=build_dataset_digest,
            build_strategy="historical_partition",
            base_generation_id=base_generation_id,
            semantic_dependencies=current_dependencies,
        )
        results: dict[str, int | str] = {
            "tracks": int(conn.execute("SELECT COUNT(*) FROM agg_weekly_tracks").fetchone()[0]),
            "albums": int(conn.execute("SELECT COUNT(*) FROM agg_weekly_albums").fetchone()[0]),
            "track_sources": int(
                conn.execute("SELECT COUNT(*) FROM agg_weekly_track_sources").fetchone()[0]
            ),
            "artists": int(conn.execute("SELECT COUNT(*) FROM agg_weekly_artists").fetchone()[0]),
            "build_strategy": "historical_partition",
            "affected_weeks": len(weeks),
        }
    except _HistoricalWeekReplacementFallbackError as exc:
        conn.close()
        return full_fallback(str(exc))
    except Exception as exc:
        logger.exception("Historical Billboard partition build failed; falling back to full.")
        conn.close()
        return full_fallback(f"historical_partition_failed:{type(exc).__name__}:{str(exc)[:120]}")
    conn.close()

    from backend.core.cache_manager import invalidate_playback_caches

    invalidate_playback_caches()
    return results


def build_aggregations_for_weeks(
    affected_weeks: set[str] | frozenset[str],
    *,
    change_generation_id: str,
    previous_dataset_digest: str | None,
    billboard_scope_exact: bool,
    min_ms: int = 30000,
    music_only: bool = True,
    week_start_dow: int = 4,
    week_start_hour: int = 0,
    progress_callback=None,
    dynamic_threshold: bool = False,
    max_merge_gap_minutes: int | None = 5,
    expected_generation_id: str | None = None,
) -> dict[str, int | str]:
    """Apply a proven tail contribution delta or safely fall back to full."""

    ensure_schema()

    def full_fallback(reason: str) -> dict[str, int | str]:
        result = build_aggregations(
            min_ms=min_ms,
            music_only=music_only,
            week_start_dow=week_start_dow,
            week_start_hour=week_start_hour,
            progress_callback=progress_callback,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
            expected_generation_id=expected_generation_id,
        )
        result["fallback_reason"] = reason
        return result

    if not billboard_scope_exact or max_merge_gap_minutes is None:
        return full_fallback("billboard_scope_not_proven")

    conn = get_db(readonly=False)
    build_generation_id = _active_playback_generation(conn)
    build_dataset_digest = _active_playback_dataset_digest(conn)
    if expected_generation_id is not None and build_generation_id != expected_generation_id:
        conn.close()
        raise RuntimeError(
            "active playback generation does not match the requested aggregate generation"
        )
    from backend.domains.metadata.artist_identity import get_identity_revision
    from backend.domains.metadata.track_credits import get_track_credit_revision
    from backend.domains.metadata.track_identity import (
        get_track_identity_revision,
        synchronize_track_identity_projection,
    )

    synchronize_track_identity_projection(conn)
    identity_revision = get_identity_revision(conn)
    credit_revision = get_track_credit_revision(conn)
    track_identity_revision = get_track_identity_revision(conn)
    current_dependencies = _aggregation_semantic_dependencies(
        conn,
        identity_revision=identity_revision,
        track_credit_revision=credit_revision,
        track_identity_revision=track_identity_revision,
    )
    base_dependencies = _aggregation_semantic_dependencies(
        conn,
        identity_revision=identity_revision,
        track_credit_revision=credit_revision,
        track_identity_revision=track_identity_revision,
        excluded_generation_id=change_generation_id,
    )
    # Album Project membership is applied from track-source rows at read time;
    # it is recorded for audit but is not baked into these four aggregate tables.
    base_dependencies.pop("album_project_revision", None)
    param_hash = _agg_param_hash(
        min_ms,
        music_only,
        week_start_dow,
        week_start_hour,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        identity_revision=identity_revision,
        track_credit_revision=credit_revision,
        track_identity_revision=track_identity_revision,
    )
    base_generation_id = _partition_base_generation(
        conn,
        param_hash=param_hash,
        previous_dataset_digest=previous_dataset_digest,
        semantic_dependencies=base_dependencies,
    )
    weeks = {str(week) for week in affected_weeks}
    live_weeks = {
        str(row[0])
        for row in conn.execute("SELECT DISTINCT billboard_week FROM agg_weekly_tracks").fetchall()
    }
    total_weeks = live_weeks | weeks
    if base_generation_id is None:
        conn.close()
        return full_fallback("billboard_base_incompatible")
    if total_weeks and len(weeks & total_weeks) / len(total_weeks) > 0.25:
        conn.close()
        return full_fallback("affected_week_ratio_exceeded")

    try:
        from backend.domains.imports.change_set import (
            build_billboard_tail_contribution_frames,
        )

        old_events, new_events = build_billboard_tail_contribution_frames(
            conn,
            generation_id=change_generation_id,
            min_ms=min_ms,
            music_only=music_only,
            dynamic_threshold=dynamic_threshold,
            max_gap_minutes=int(max_merge_gap_minutes),
        )
        old_maps = _billboard_aggregate_maps(
            conn,
            old_events,
            week_start_dow=week_start_dow,
            week_start_hour=week_start_hour,
        )
        new_maps = _billboard_aggregate_maps(
            conn,
            new_events,
            week_start_dow=week_start_dow,
            week_start_hour=week_start_hour,
        )
        delta_weeks: set[str] = set()
        for table in _AGG_SHADOW_TABLES:
            old_values = old_maps[table][1]
            new_values = new_maps[table][1]
            delta_weeks.update(
                str(key[0])
                for key in old_values.keys() | new_values.keys()
                if old_values.get(key) != new_values.get(key)
            )
        if not delta_weeks.issubset(weeks):
            raise RuntimeError("Billboard delta escaped the proven affected-week closure")

        _prepare_aggregation_shadows(conn)
        _copy_unaffected_aggregation_weeks(conn, set())
        for table, shadow_table in _AGG_SHADOW_TABLES.items():
            _apply_aggregate_map_delta(
                conn,
                shadow_table=shadow_table,
                key_columns=old_maps[table][0],
                old=old_maps[table][1],
                new=new_maps[table][1],
            )
        _validate_aggregation_shadows(conn)
        conn.commit()
        _publish_aggregation_shadows(
            conn,
            param_hash=param_hash,
            data_generation_id=build_generation_id,
            data_digest=build_dataset_digest,
            build_strategy="partition",
            base_generation_id=base_generation_id,
            semantic_dependencies=current_dependencies,
        )
        results: dict[str, int | str] = {
            "tracks": int(conn.execute("SELECT COUNT(*) FROM agg_weekly_tracks").fetchone()[0]),
            "albums": int(conn.execute("SELECT COUNT(*) FROM agg_weekly_albums").fetchone()[0]),
            "track_sources": int(
                conn.execute("SELECT COUNT(*) FROM agg_weekly_track_sources").fetchone()[0]
            ),
            "artists": int(conn.execute("SELECT COUNT(*) FROM agg_weekly_artists").fetchone()[0]),
            "build_strategy": "partition",
            "affected_weeks": len(weeks),
        }
        conn.close()
    except Exception as exc:
        logger.exception("Billboard partition build failed; falling back to full rebuild.")
        conn.close()
        return full_fallback(f"partition_proof_failed:{type(exc).__name__}:{str(exc)[:120]}")

    from backend.core.cache_manager import invalidate_playback_caches

    invalidate_playback_caches()
    return results


def load_agg_weekly_tracks(conn: sqlite3.Connection) -> pd.DataFrame:
    """Load pre-aggregated track-week data joined with dimension names."""
    import pandas as pd

    df = pd.read_sql_query(
        """SELECT awt.billboard_week,
                  awt.l1_id,
                  awt.l1_id AS track_id,
                  awt.track_id AS representative_track_id,
                  t.track_name,
                  t.artist_id, a.artist_name,
                  al.album_name, awt.play_count, awt.total_ms
           FROM agg_weekly_tracks awt
           JOIN tracks t ON awt.track_id = t.track_id
           JOIN artists a ON t.artist_id = a.artist_id
           LEFT JOIN albums al ON t.album_id = al.album_id
           ORDER BY awt.billboard_week""",
        conn,
    )
    df["billboard_week"] = pd.to_datetime(df["billboard_week"]).dt.date
    from backend.domains.metadata.artist_identity import canonicalize_artist_frame

    return canonicalize_artist_frame(df, conn, dedupe=False)


def load_agg_weekly_albums(conn: sqlite3.Connection) -> pd.DataFrame:
    """Load pre-aggregated album-week data joined with dimension names."""
    import pandas as pd

    df = pd.read_sql_query(
        """SELECT awa.billboard_week, awa.album_id, al.album_name,
                  al.artist_id, a.artist_name,
                  awa.play_count, awa.total_ms
           FROM agg_weekly_albums awa
           JOIN albums al ON awa.album_id = al.album_id
           JOIN artists a ON al.artist_id = a.artist_id
           ORDER BY awa.billboard_week""",
        conn,
    )
    df["billboard_week"] = pd.to_datetime(df["billboard_week"]).dt.date
    from backend.domains.metadata.artist_identity import canonicalize_artist_frame

    return canonicalize_artist_frame(df, conn, dedupe=False)


def load_agg_weekly_track_sources(conn: sqlite3.Connection) -> pd.DataFrame:
    """Load track-source pre-aggregates for album project weekly rankings."""
    import pandas as pd

    df = pd.read_sql_query(
        """SELECT awts.billboard_week,
                  awts.play_date,
                  awts.l1_id,
                  awts.l1_id AS track_id,
                  awts.track_id AS representative_track_id,
                  t.track_name,
                  t.artist_id,
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
    from backend.domains.metadata.artist_identity import canonicalize_artist_frame

    return canonicalize_artist_frame(df, conn, dedupe=False)


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
    from backend.domains.metadata.artist_identity import canonicalize_artist_frame

    return canonicalize_artist_frame(df, conn, dedupe=False)


# ── Cache registration ─────────────────────────────────────────────────
from backend.core.cache_manager import register_lru  # noqa: E402

register_lru("db", "plays", _load_plays_cached)
register_lru("db", "plays_for_artists", _load_plays_for_artists_cached)
register_lru("db", "track_all_artists_map", get_track_all_artists_map)
register_lru("db", "track_artist_names_map", get_track_artist_names_map)
