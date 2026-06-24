"""Album project attribution and aggregation helpers.

Album projects are statistics-level albums: an album project owns a deduped
set of canonical songs, while source albums remain explanation metadata.
"""

from __future__ import annotations

import sqlite3

import pandas as pd

SOURCE_BUCKET_ORDER = {
    "original_album": 0,
    "deluxe": 1,
    "single": 2,
    "compilation": 3,
    "live_acoustic_remix": 4,
    "rerecord": 5,
    "other": 6,
    "inferred": 7,
}

_ALBUM_PROJECT_SCHEMA = """
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
"""


def ensure_album_project_schema(conn: sqlite3.Connection) -> None:
    """Create album project tables if the current DB predates this feature."""
    conn.executescript(_ALBUM_PROJECT_SCHEMA)


def ensure_album_projects(conn: sqlite3.Connection) -> None:
    """Create deterministic album projects from existing release groups and metadata."""
    ensure_album_project_schema(conn)
    existing = conn.execute("SELECT COUNT(*) FROM album_projects").fetchone()[0]
    if existing:
        return
    bootstrap_album_projects(conn)


def bootstrap_album_projects(conn: sqlite3.Connection) -> None:
    """Populate album project tables without deleting user-maintained rows."""
    _bootstrap_from_release_groups(conn)
    _bootstrap_standalone_album_projects(conn)
    _bootstrap_compilation_exclusive_projects(conn)
    conn.commit()


def rebuild_album_projects(conn: sqlite3.Connection) -> None:
    """Rebuild inferred album project rows while preserving manual projects."""
    ensure_album_project_schema(conn)
    conn.execute(
        """DELETE FROM album_project_tracks
           WHERE project_id IN (
               SELECT project_id FROM album_projects WHERE is_manual = 0
           )"""
    )
    conn.execute(
        """DELETE FROM album_project_albums
           WHERE project_id IN (
               SELECT project_id FROM album_projects WHERE is_manual = 0
           )"""
    )
    conn.execute("DELETE FROM album_projects WHERE is_manual = 0")
    bootstrap_album_projects(conn)


def apply_canonical_song_keys(
    df: pd.DataFrame,
    conn: sqlite3.Connection,
    merge_level: int,
) -> pd.DataFrame:
    """Return df with canonical_song_key and canonical_song_name columns."""
    out = df.copy()
    if out.empty:
        out["canonical_song_key"] = pd.Series(dtype="object")
        out["canonical_song_name"] = pd.Series(dtype="object")
        return out

    out["canonical_song_key"] = out["track_id"].astype("Int64").astype(str)
    if "track_name" in out.columns:
        out["canonical_song_name"] = out["track_name"]
    else:
        names = _track_name_map(conn)
        out["canonical_song_name"] = out["track_id"].map(names).fillna("")
    if merge_level <= 1:
        return out

    from backend.domains.playback.track_groups import load_track_group_keys

    keys = load_track_group_keys(conn, merge_level=merge_level)
    if keys.empty:
        return out

    keys = keys.copy()
    keys["_scope_rank"] = keys["track_group_scope"].map(
        {"composition": 0, "recording": 1} if merge_level >= 3 else {"recording": 0}
    )
    keys = keys.sort_values(["track_id", "_scope_rank", "track_agg_id"]).drop_duplicates("track_id")
    key_map = keys.set_index("track_id")
    mapped_id = out["track_id"].map(key_map["track_agg_id"])
    mapped_name = out["track_id"].map(key_map["track_agg_name"])
    mask = mapped_id.notna()
    out.loc[mask, "canonical_song_key"] = "group:" + mapped_id[mask].astype(int).astype(str)
    out.loc[mask, "canonical_song_name"] = mapped_name[mask]
    return out


def load_album_project_membership(
    conn: sqlite3.Connection,
    merge_level: int = 2,
    include_compilations: bool = False,
) -> pd.DataFrame:
    """Return one default album project owner per canonical song."""
    ensure_album_projects(conn)
    raw = pd.read_sql_query(
        """SELECT ap.project_id,
                  ap.canonical_name AS album_project_name,
                  ap.artist_id,
                  ar.artist_name,
                  ap.primary_album_id,
                  ap.release_date,
                  ap.scope,
                  ap.project_type,
                  ap.include_in_charts,
                  apt.track_id,
                  t.track_name,
                  apt.membership_role,
                  apt.min_merge_level,
                  apt.source_album_id,
                  apa.source_bucket,
                  apt.is_exclusive,
                  apt.inferred
           FROM album_project_tracks apt
           JOIN album_projects ap ON ap.project_id = apt.project_id
           LEFT JOIN artists ar ON ar.artist_id = ap.artist_id
           JOIN tracks t ON t.track_id = apt.track_id
           LEFT JOIN album_project_albums apa
             ON apa.project_id = apt.project_id
            AND apa.album_id = COALESCE(apt.source_album_id, ap.primary_album_id)
           WHERE apt.min_merge_level <= ?
             AND ap.include_in_charts = 1""",
        conn,
        params=(merge_level,),
    )
    if raw.empty:
        return raw
    if not include_compilations:
        raw = raw[raw["project_type"] != "compilation_exclusive"]
    if raw.empty:
        return raw

    keyed = apply_canonical_song_keys(raw, conn, merge_level)
    keyed["_owner_rank"] = keyed["source_bucket"].map(SOURCE_BUCKET_ORDER).fillna(99)
    keyed["_scope_rank"] = keyed["scope"].map(
        {"composition": 0, "release": 1} if merge_level >= 3 else {"release": 0, "composition": 1}
    )
    keyed = keyed.sort_values(
        ["canonical_song_key", "_scope_rank", "_owner_rank", "release_date", "project_id"],
        ascending=[True, True, True, True, True],
    )
    return keyed.drop_duplicates("canonical_song_key").drop(columns=["_owner_rank", "_scope_rank"])


def compute_album_project_plays(
    df: pd.DataFrame,
    conn: sqlite3.Connection,
    merge_level: int = 2,
    include_compilations: bool = False,
    billboard_mode: bool = False,
) -> pd.DataFrame:
    """Aggregate valid play events to album projects."""
    if df.empty:
        return _empty_album_project_frame()
    if merge_level <= 1:
        return _compute_l1_album_container_plays(df, conn, include_compilations)

    events = apply_canonical_song_keys(df, conn, merge_level)
    membership = load_album_project_membership(conn, merge_level, include_compilations)
    if membership.empty:
        return _empty_album_project_frame()

    merged = events.merge(
        membership,
        on="canonical_song_key",
        how="inner",
        suffixes=("", "_project"),
    )
    if billboard_mode:
        merged = _filter_to_project_release_date(merged)
    if merged.empty:
        return _empty_album_project_frame()

    result = (
        merged.groupby(
            ["project_id", "album_project_name", "artist_name_project", "release_date"],
            dropna=False,
        )
        .agg(
            **_play_weight_aggs(merged),
            unique_canonical_songs=("canonical_song_key", "nunique"),
        )
        .reset_index()
        .rename(
            columns={
                "project_id": "album_project_id",
                "artist_name_project": "artist_name",
            }
        )
    )
    return result.sort_values(["play_count", "total_ms"], ascending=[False, False])


def compute_album_project_weekly_plays(
    df: pd.DataFrame,
    conn: sqlite3.Connection,
    merge_level: int = 2,
    include_compilations: bool = False,
    billboard_mode: bool = False,
) -> pd.DataFrame:
    """Aggregate valid play events to album projects by Billboard week."""
    if df.empty:
        return _empty_album_project_weekly_frame()

    events_input = df.copy()
    if "billboard_week" not in events_input.columns:
        if "ts_date" in events_input.columns:
            events_input["billboard_week"] = events_input["ts_date"]
        elif "ts" in events_input.columns:
            events_input["billboard_week"] = events_input["ts"]
        else:
            return _empty_album_project_weekly_frame()

    if merge_level <= 1:
        return _compute_l1_album_container_weekly_plays(
            events_input,
            conn,
            include_compilations,
            billboard_mode=billboard_mode,
        )

    events = apply_canonical_song_keys(events_input, conn, merge_level)
    membership = load_album_project_membership(conn, merge_level, include_compilations)
    if membership.empty:
        return _empty_album_project_weekly_frame()

    merged = events.merge(
        membership,
        on="canonical_song_key",
        how="inner",
        suffixes=("", "_project"),
    )
    if billboard_mode:
        merged = _filter_to_project_release_date(merged)
    if merged.empty:
        return _empty_album_project_weekly_frame()

    result = (
        merged.groupby(
            [
                "billboard_week",
                "project_id",
                "album_project_name",
                "artist_name_project",
                "release_date",
            ],
            dropna=False,
        )
        .agg(
            **_play_weight_aggs(merged),
            unique_canonical_songs=("canonical_song_key", "nunique"),
        )
        .reset_index()
        .rename(
            columns={
                "project_id": "album_project_id",
                "artist_name_project": "artist_name",
            }
        )
    )
    return result.sort_values(
        ["billboard_week", "play_count", "total_ms"],
        ascending=[True, False, False],
    )


def compute_album_source_breakdown(
    df: pd.DataFrame,
    conn: sqlite3.Connection,
    merge_level: int = 2,
) -> pd.DataFrame:
    """Explain album project plays by source album bucket."""
    if df.empty:
        return _empty_source_breakdown_frame()
    events = apply_canonical_song_keys(df, conn, merge_level)
    membership = load_album_project_membership(conn, merge_level, include_compilations=True)
    if membership.empty:
        return _empty_source_breakdown_frame()

    merged = events.merge(
        membership,
        on="canonical_song_key",
        how="inner",
        suffixes=("", "_project"),
    )
    merged = _attach_source_album_bucket(merged, conn)
    if merged.empty:
        return _empty_source_breakdown_frame()

    return (
        merged.groupby(
            [
                "project_id",
                "album_project_name",
                "source_album_id",
                "source_album_name",
                "source_bucket",
            ],
            dropna=False,
        )
        .agg(**_play_weight_aggs(merged))
        .reset_index()
        .rename(columns={"project_id": "album_project_id"})
    )


def _bootstrap_from_release_groups(conn: sqlite3.Connection) -> None:
    groups = conn.execute(
        """SELECT rg.group_id, rg.canonical_name, rg.artist_id, rg.primary_album_id, rg.scope,
                  sam.release_date
           FROM release_groups rg
           LEFT JOIN albums al ON al.album_id = rg.primary_album_id
           LEFT JOIN artists ar ON ar.artist_id = al.artist_id
           LEFT JOIN spotify_album_meta sam
             ON lower(sam.album_name) = lower(al.album_name)
            AND (sam.album_artists IS NULL OR ar.artist_name IS NULL OR instr(lower(sam.album_artists), lower(ar.artist_name)) > 0)
           ORDER BY rg.group_id"""
    ).fetchall()
    for group in groups:
        artist_id = int(group["artist_id"])
        # 🌟 防御：artist_id 为 0 时从 albums 表纠正（防止手动创建的 release group 缺艺人 ID）
        if artist_id <= 0 and group["primary_album_id"]:
            fallback = conn.execute(
                "SELECT artist_id FROM albums WHERE album_id = ?",
                (group["primary_album_id"],),
            ).fetchone()
            if fallback:
                artist_id = int(fallback["artist_id"])
        if artist_id <= 0:
            continue
        project_id = _upsert_project(
            conn,
            canonical_name=group["canonical_name"],
            artist_id=artist_id,
            primary_album_id=group["primary_album_id"],
            release_date=group["release_date"],
            scope=group["scope"],
            project_type="album",
            include_in_charts=1,
            is_manual=0,
        )
        members = conn.execute(
            "SELECT album_id FROM release_group_members WHERE group_id = ?",
            (group["group_id"],),
        ).fetchall()
        member_ids = [int(row["album_id"]) for row in members]
        for album_id in member_ids:
            _insert_project_album(
                conn,
                project_id=project_id,
                album_id=album_id,
                primary_album_id=group["primary_album_id"],
            )
        min_merge_level = 3 if group["scope"] == "composition" else 2
        for track_id, album_id in _tracks_for_albums(conn, member_ids):
            _insert_project_track(
                conn,
                project_id=project_id,
                track_id=track_id,
                source_album_id=album_id,
                min_merge_level=min_merge_level,
                membership_role=_membership_role_for_album(
                    conn, album_id, group["primary_album_id"]
                ),
            )


def _bootstrap_standalone_album_projects(conn: sqlite3.Connection) -> None:
    albums = conn.execute(
        """SELECT al.album_id, al.album_name, al.artist_id, ar.artist_name,
                  sam.album_type, sam.total_tracks, sam.release_date,
                  COUNT(DISTINCT t.track_id) AS local_tracks
           FROM albums al
           JOIN artists ar ON ar.artist_id = al.artist_id
           LEFT JOIN spotify_album_meta sam
             ON lower(sam.album_name) = lower(al.album_name)
            AND (sam.album_artists IS NULL OR instr(lower(sam.album_artists), lower(ar.artist_name)) > 0)
           LEFT JOIN tracks t ON t.album_id = al.album_id
           WHERE NOT EXISTS (
               SELECT 1
               FROM release_group_members rgm
               JOIN release_groups rg ON rg.group_id = rgm.group_id
               WHERE rgm.album_id = al.album_id
                 AND rg.scope = 'release'
           )
           GROUP BY al.album_id
           ORDER BY al.album_id"""
    ).fetchall()
    from backend.domains.playback.album_type import classify_album

    for album in albums:
        spotify_type = album["album_type"]
        spotify_tracks = album["total_tracks"]
        release_date = album["release_date"]
        local_tracks = int(album["local_tracks"] or 0)
        linked = _best_spotify_album_for_local_album(conn, int(album["album_id"]))
        if linked:
            # Use linked metadata for classification (album_type, total_tracks).
            # Only override release_date when the name-matched spotify row has
            # the wrong type (e.g. a single shadowing a real album), keeping
            # the original release_date for albums that have deluxe variants.
            linked_type = linked["album_type"]
            if linked_type == "album" and (spotify_type or "").lower() in ("single", "", None):
                release_date = linked["release_date"] or release_date
            elif not release_date:
                release_date = linked["release_date"]
            spotify_type = linked_type or spotify_type
            spotify_tracks = (
                linked["total_tracks"] if linked["total_tracks"] is not None else spotify_tracks
            )

        if (spotify_type or "").lower() == "single" and local_tracks >= 7:
            spotify_type = "album"
            spotify_tracks = max(int(spotify_tracks or 0), local_tracks)
        elif (spotify_type or "").lower() == "single" and 3 <= local_tracks <= 6:
            spotify_tracks = max(int(spotify_tracks or 0), local_tracks)

        # Skip compilations (handled by _bootstrap_compilation_exclusive_projects)
        if (spotify_type or "").lower() == "compilation":
            continue

        # Use local track count as fallback when Spotify metadata is missing
        effective_tracks = (
            int(spotify_tracks)
            if spotify_tracks is not None and int(spotify_tracks) > 0
            else local_tracks
        )

        category = classify_album(
            spotify_type,
            total_tracks=effective_tracks if effective_tracks > 0 else None,
        )

        # 容错：无 Spotify 元数据但有足够本地曲目的专辑，按本地曲目数分级
        if category == "unknown" and local_tracks >= 7:
            category = "lp"
        elif category == "unknown" and 3 <= local_tracks <= 6:
            category = "ep"

        if category not in {"lp", "ep"}:
            continue
        project_id = _upsert_project(
            conn,
            canonical_name=album["album_name"],
            artist_id=album["artist_id"],
            primary_album_id=album["album_id"],
            release_date=release_date,
            scope="release",
            project_type="album",
            include_in_charts=1,
            is_manual=0,
        )
        _insert_project_album(
            conn,
            project_id=project_id,
            album_id=album["album_id"],
            primary_album_id=album["album_id"],
        )
        for track_id, source_album_id in _tracks_for_albums(conn, [int(album["album_id"])]):
            _insert_project_track(
                conn,
                project_id=project_id,
                track_id=track_id,
                source_album_id=source_album_id,
                min_merge_level=2,
                membership_role="standard",
            )


def _best_spotify_album_for_local_album(conn: sqlite3.Connection, album_id: int):
    try:
        return conn.execute(
            """SELECT sam.spotify_album_id, sam.album_type, sam.total_tracks,
                      sam.release_date, sam.album_artists, sam.image_url,
                      MAX(asl.confidence) AS confidence,
                      SUM(asl.play_count) AS play_count,
                      MAX(asl.track_count) AS link_track_count
               FROM album_spotify_links asl
               JOIN spotify_album_meta sam ON sam.spotify_album_id = asl.spotify_album_id
               WHERE asl.album_id = ?
               GROUP BY sam.spotify_album_id
               ORDER BY
                 CASE sam.album_type WHEN 'album' THEN 0 WHEN 'single' THEN 1 ELSE 2 END,
                 COALESCE(sam.total_tracks, 0) DESC,
                 COALESCE(play_count, 0) DESC,
                 confidence DESC
               LIMIT 1""",
            (album_id,),
        ).fetchone()
    except sqlite3.OperationalError as exc:
        if "album_spotify_links" not in str(exc):
            raise
        return None


def _bootstrap_compilation_exclusive_projects(conn: sqlite3.Connection) -> None:
    compilations = conn.execute(
        """SELECT al.album_id, al.album_name, al.artist_id, sam.release_date
           FROM albums al
           JOIN artists ar ON ar.artist_id = al.artist_id
           JOIN spotify_album_meta sam
             ON lower(sam.album_name) = lower(al.album_name)
            AND sam.album_type = 'compilation'
           ORDER BY al.album_id"""
    ).fetchall()
    for album in compilations:
        exclusive_tracks = [
            track_id
            for track_id, _source_album_id in _tracks_for_albums(conn, [int(album["album_id"])])
            if not _track_has_non_compilation_project(conn, track_id)
        ]
        if not exclusive_tracks:
            continue
        project_id = _upsert_project(
            conn,
            canonical_name=album["album_name"],
            artist_id=album["artist_id"],
            primary_album_id=album["album_id"],
            release_date=album["release_date"],
            scope="release",
            project_type="compilation_exclusive",
            include_in_charts=1,
            is_manual=0,
        )
        _insert_project_album(
            conn,
            project_id=project_id,
            album_id=album["album_id"],
            primary_album_id=album["album_id"],
        )
        for track_id in exclusive_tracks:
            _insert_project_track(
                conn,
                project_id=project_id,
                track_id=track_id,
                source_album_id=album["album_id"],
                min_merge_level=2,
                membership_role="compilation_exclusive",
                is_exclusive=1,
            )


def _upsert_project(
    conn: sqlite3.Connection,
    canonical_name: str,
    artist_id: int,
    primary_album_id: int,
    release_date: str | None,
    scope: str,
    project_type: str,
    include_in_charts: int,
    is_manual: int,
) -> int:
    conn.execute(
        """INSERT OR IGNORE INTO album_projects
           (canonical_name, artist_id, primary_album_id, release_date, scope,
            project_type, include_in_charts, is_manual)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            canonical_name,
            artist_id,
            primary_album_id,
            release_date,
            scope,
            project_type,
            include_in_charts,
            is_manual,
        ),
    )
    row = conn.execute(
        """SELECT project_id FROM album_projects
           WHERE canonical_name = ? AND artist_id = ? AND scope = ?""",
        (canonical_name, artist_id, scope),
    ).fetchone()
    return int(row["project_id"])


def _insert_project_album(
    conn: sqlite3.Connection,
    project_id: int,
    album_id: int,
    primary_album_id: int,
) -> None:
    role = "primary" if album_id == primary_album_id else "member"
    bucket = _source_bucket_for_album(conn, album_id, primary_album_id=primary_album_id)
    conn.execute(
        """INSERT OR REPLACE INTO album_project_albums
           (project_id, album_id, role, source_bucket, inferred)
           VALUES (?, ?, ?, ?, 0)""",
        (project_id, album_id, role, bucket),
    )


def _insert_project_track(
    conn: sqlite3.Connection,
    project_id: int,
    track_id: int,
    source_album_id: int,
    min_merge_level: int,
    membership_role: str,
    is_exclusive: int = 0,
) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO album_project_tracks
           (project_id, track_id, membership_role, min_merge_level, source_album_id,
            is_exclusive, inferred)
           VALUES (?, ?, ?, ?, ?, ?, 0)""",
        (project_id, track_id, membership_role, min_merge_level, source_album_id, is_exclusive),
    )


def _tracks_for_albums(conn: sqlite3.Connection, album_ids: list[int]) -> list[tuple[int, int]]:
    if not album_ids:
        return []
    placeholders = ",".join("?" for _ in album_ids)
    rows = conn.execute(
        f"""SELECT DISTINCT track_id, album_id
            FROM (
                SELECT track_id, album_id FROM tracks WHERE album_id IN ({placeholders})
                UNION
                SELECT track_id, album_id FROM track_albums WHERE album_id IN ({placeholders})
            )
            ORDER BY album_id, track_id""",
        tuple(album_ids) + tuple(album_ids),
    ).fetchall()
    return [(int(row["track_id"]), int(row["album_id"])) for row in rows]


def _track_has_non_compilation_project(conn: sqlite3.Connection, track_id: int) -> bool:
    row = conn.execute(
        """SELECT 1
           FROM album_project_tracks apt
           JOIN album_projects ap ON ap.project_id = apt.project_id
           WHERE apt.track_id = ?
             AND ap.project_type != 'compilation_exclusive'
           LIMIT 1""",
        (track_id,),
    ).fetchone()
    return row is not None


def _membership_role_for_album(
    conn: sqlite3.Connection, album_id: int, primary_album_id: int
) -> str:
    if album_id == primary_album_id:
        return "standard"
    bucket = _source_bucket_for_album(conn, album_id, primary_album_id=primary_album_id)
    if bucket == "deluxe":
        return "deluxe"
    if bucket == "rerecord":
        return "rerecord"
    return "member"


def _source_bucket_for_album(
    conn: sqlite3.Connection,
    album_id: int | None,
    primary_album_id: int | None = None,
) -> str:
    if album_id is None:
        return "inferred"
    row = conn.execute(
        """SELECT al.album_name, sam.album_type
           FROM albums al
           LEFT JOIN spotify_album_meta sam ON lower(sam.album_name) = lower(al.album_name)
           WHERE al.album_id = ?
           LIMIT 1""",
        (album_id,),
    ).fetchone()
    if row is None:
        return "other"
    return _bucket_from_album_meta(
        album_id=album_id,
        album_name=row["album_name"],
        album_type=row["album_type"],
        primary_album_id=primary_album_id,
    )


def _bucket_from_album_meta(
    album_id: int | None,
    album_name: str | None,
    album_type: str | None,
    primary_album_id: int | None = None,
) -> str:
    if album_id is None:
        return "inferred"
    name = (album_name or "").lower()
    album_type = (album_type or "").lower()
    if any(token in name for token in ("remix", "acoustic", " live")):
        return "live_acoustic_remix"
    if any(token in name for token in ("taylor's version", "rerecorded", "re-recorded")):
        return "rerecord"
    if album_type == "compilation":
        return "compilation"
    if album_type == "single":
        return "single"
    if any(token in name for token in ("deluxe", "expanded", "anniversary", "spilled", "edition")):
        return "deluxe"
    if primary_album_id is not None and album_id == primary_album_id:
        return "original_album"
    if album_type == "album":
        return "original_album"
    return "other"


def _attach_source_album_bucket(df: pd.DataFrame, conn: sqlite3.Connection) -> pd.DataFrame:
    out = df.copy()
    out["_source_album_id_int"] = pd.to_numeric(out["source_album_id"], errors="coerce").astype(
        "Int64"
    )
    source_ids = [
        int(v)
        for v in out["_source_album_id_int"].dropna().unique().tolist()
        if str(v) not in {"nan", "<NA>"}
    ]
    if source_ids:
        placeholders = ",".join("?" for _ in source_ids)
        rows = conn.execute(
            f"""SELECT al.album_id, al.album_name, sam.album_type
                FROM albums al
                LEFT JOIN spotify_album_meta sam ON lower(sam.album_name) = lower(al.album_name)
                WHERE al.album_id IN ({placeholders})""",
            tuple(source_ids),
        ).fetchall()
        name_map = {int(row["album_id"]): row["album_name"] for row in rows}
        bucket_map = {
            int(row["album_id"]): _bucket_from_album_meta(
                album_id=int(row["album_id"]),
                album_name=row["album_name"],
                album_type=row["album_type"],
            )
            for row in rows
        }
    else:
        name_map = {}
        bucket_map = {}
    out["source_album_name"] = out["_source_album_id_int"].map(name_map)
    out["source_bucket"] = out["_source_album_id_int"].map(bucket_map).fillna("other")
    out.loc[out["_source_album_id_int"].isna(), "source_bucket"] = "inferred"
    return out.drop(columns=["_source_album_id_int"])


def _filter_to_project_release_date(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    event_source = out["ts_date"] if "ts_date" in out.columns else out["ts"]
    out["_event_date"] = pd.to_datetime(event_source, errors="coerce")
    out["_release_date"] = pd.to_datetime(out["release_date"], errors="coerce")
    return out[
        out["_release_date"].isna() | (out["_event_date"].dt.date >= out["_release_date"].dt.date)
    ].drop(columns=["_event_date", "_release_date"])


def _compute_l1_album_container_plays(
    df: pd.DataFrame, conn: sqlite3.Connection, include_compilations: bool
) -> pd.DataFrame:
    events = df.copy()
    if "source_album_id" in events.columns:
        if "track_album_id" in events.columns:
            fallback_album = events["track_album_id"]
        elif "album_id" in events.columns:
            fallback_album = events["album_id"]
        else:
            fallback_album = pd.Series([pd.NA] * len(events), index=events.index)
        events["_album_id"] = events["source_album_id"].fillna(fallback_album)
    elif "track_album_id" in events.columns:
        events["_album_id"] = events["track_album_id"]
    else:
        events["_album_id"] = None
    events = events[events["_album_id"].notna()]
    if events.empty:
        return _empty_album_project_frame()
    album_ids = [int(v) for v in events["_album_id"].dropna().unique().tolist()]
    placeholders = ",".join("?" for _ in album_ids)
    meta = pd.read_sql_query(
        f"""SELECT al.album_id,
                  al.album_name AS meta_album_name,
                  ar.artist_name AS meta_artist_name,
                  sam.release_date,
                  sam.album_type
            FROM albums al
            JOIN artists ar ON ar.artist_id = al.artist_id
            LEFT JOIN spotify_album_meta sam ON lower(sam.album_name) = lower(al.album_name)
            WHERE al.album_id IN ({placeholders})""",
        conn,
        params=tuple(album_ids),
    )
    events = events.merge(meta, left_on="_album_id", right_on="album_id", how="left")
    if not include_compilations:
        events = events[events["album_type"].fillna("").str.lower() != "compilation"]
    events = events[events["album_type"].fillna("").str.lower() != "single"]
    if events.empty:
        return _empty_album_project_frame()
    result = (
        events.groupby(
            ["album_id", "meta_album_name", "meta_artist_name", "release_date"],
            dropna=False,
        )
        .agg(
            **_play_weight_aggs(events),
            unique_canonical_songs=("track_id", "nunique"),
        )
        .reset_index()
        .rename(
            columns={
                "album_id": "album_project_id",
                "meta_album_name": "album_project_name",
                "meta_artist_name": "artist_name",
            }
        )
    )
    return result.sort_values(["play_count", "total_ms"], ascending=[False, False])


def _compute_l1_album_container_weekly_plays(
    df: pd.DataFrame,
    conn: sqlite3.Connection,
    include_compilations: bool,
    billboard_mode: bool = False,
) -> pd.DataFrame:
    events = _attach_l1_album_id(df)
    events = events[events["_album_id"].notna()]
    if events.empty:
        return _empty_album_project_weekly_frame()
    album_ids = [int(v) for v in events["_album_id"].dropna().unique().tolist()]
    placeholders = ",".join("?" for _ in album_ids)
    meta = pd.read_sql_query(
        f"""SELECT al.album_id,
                  al.album_name AS meta_album_name,
                  ar.artist_name AS meta_artist_name,
                  sam.release_date,
                  sam.album_type
            FROM albums al
            JOIN artists ar ON ar.artist_id = al.artist_id
            LEFT JOIN spotify_album_meta sam ON lower(sam.album_name) = lower(al.album_name)
            WHERE al.album_id IN ({placeholders})""",
        conn,
        params=tuple(album_ids),
    )
    events = events.merge(meta, left_on="_album_id", right_on="album_id", how="left")
    if not include_compilations:
        events = events[events["album_type"].fillna("").str.lower() != "compilation"]
    events = events[events["album_type"].fillna("").str.lower() != "single"]
    if billboard_mode:
        events = _filter_to_project_release_date(events)
    if events.empty:
        return _empty_album_project_weekly_frame()
    result = (
        events.groupby(
            ["billboard_week", "album_id", "meta_album_name", "meta_artist_name", "release_date"],
            dropna=False,
        )
        .agg(
            **_play_weight_aggs(events),
            unique_canonical_songs=("track_id", "nunique"),
        )
        .reset_index()
        .rename(
            columns={
                "album_id": "album_project_id",
                "meta_album_name": "album_project_name",
                "meta_artist_name": "artist_name",
            }
        )
    )
    return result.sort_values(
        ["billboard_week", "play_count", "total_ms"],
        ascending=[True, False, False],
    )


def _attach_l1_album_id(df: pd.DataFrame) -> pd.DataFrame:
    events = df.copy()
    if "source_album_id" in events.columns:
        if "track_album_id" in events.columns:
            fallback_album = events["track_album_id"]
        elif "album_id" in events.columns:
            fallback_album = events["album_id"]
        else:
            fallback_album = pd.Series([pd.NA] * len(events), index=events.index)
        events["_album_id"] = events["source_album_id"].fillna(fallback_album)
    elif "track_album_id" in events.columns:
        events["_album_id"] = events["track_album_id"]
    else:
        events["_album_id"] = None
    return events


def _play_weight_aggs(df: pd.DataFrame) -> dict[str, tuple[str, str]]:
    if {"play_count", "total_ms"} <= set(df.columns):
        return {
            "play_count": ("play_count", "sum"),
            "total_ms": ("total_ms", "sum"),
        }
    return {
        "play_count": ("ms_played", "count"),
        "total_ms": ("ms_played", "sum"),
    }


def _track_name_map(conn: sqlite3.Connection) -> dict[int, str]:
    rows = conn.execute("SELECT track_id, track_name FROM tracks").fetchall()
    return {int(row["track_id"]): row["track_name"] for row in rows}


def _empty_album_project_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "album_project_id",
            "album_project_name",
            "artist_name",
            "play_count",
            "total_ms",
            "unique_canonical_songs",
            "release_date",
        ]
    )


def _empty_album_project_weekly_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "billboard_week",
            "album_project_id",
            "album_project_name",
            "artist_name",
            "play_count",
            "total_ms",
            "unique_canonical_songs",
            "release_date",
        ]
    )


def _empty_source_breakdown_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "album_project_id",
            "album_project_name",
            "source_album_id",
            "source_album_name",
            "source_bucket",
            "play_count",
            "total_ms",
        ]
    )
