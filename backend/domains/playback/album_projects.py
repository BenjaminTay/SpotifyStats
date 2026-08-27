"""Album project attribution and aggregation helpers.

Album projects are statistics-level albums: an album project owns a deduped
set of canonical songs, while source albums remain explanation metadata.
"""

from __future__ import annotations

import math
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass

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


@dataclass(frozen=True)
class AlbumProjectRebuildReport:
    """Execution evidence for a targeted or conservative full rebuild."""

    strategy: str
    fallback_reason: str | None
    affected_album_count: int
    affected_release_group_count: int
    affected_project_count: int
    affected_track_count: int


@dataclass(frozen=True)
class _AlbumProjectImpactPlan:
    album_ids: frozenset[int]
    release_group_ids: frozenset[int]
    project_ids: frozenset[int]
    track_ids: frozenset[int]
    compilation_album_ids: frozenset[int]


class _AlbumProjectClosureError(RuntimeError):
    pass


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
    _populate_album_projects(conn)
    conn.commit()


def rebuild_album_projects(conn: sqlite3.Connection) -> None:
    """Rebuild inferred projects without changing stable semantic identities."""
    ensure_album_project_schema(conn)
    conn.execute("SAVEPOINT rebuild_album_projects")
    try:
        # Membership is derived state. Clear it first so reused project IDs do not
        # retain albums or tracks that disappeared from the latest source graph.
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

        seen_project_ids: set[int] = set()
        _populate_album_projects(conn, seen_project_ids=seen_project_ids)

        # Delete only inferred identities that no longer exist. Child rows were
        # already cleared, which also keeps this correct when foreign keys are off.
        existing_inferred_ids = {
            int(row["project_id"])
            for row in conn.execute(
                "SELECT project_id FROM album_projects WHERE is_manual = 0"
            ).fetchall()
        }
        stale_project_ids = sorted(existing_inferred_ids - seen_project_ids)
        conn.executemany(
            "DELETE FROM album_projects WHERE project_id = ? AND is_manual = 0",
            ((project_id,) for project_id in stale_project_ids),
        )
        conn.execute("RELEASE SAVEPOINT rebuild_album_projects")
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT rebuild_album_projects")
        conn.execute("RELEASE SAVEPOINT rebuild_album_projects")
        raise
    conn.commit()


def rebuild_album_projects_for_impact(
    conn: sqlite3.Connection,
    *,
    local_album_ids: Iterable[int] = (),
    spotify_album_ids: Iterable[str] = (),
    spotify_track_ids: Iterable[str] = (),
    impact_scope_exact: bool,
    has_deletions: bool = False,
    max_affected_albums: int = 500,
    max_affected_ratio: float = 0.25,
) -> AlbumProjectRebuildReport:
    """Rebuild the proven Album Project closure or conservatively rebuild all.

    The Spotify ID inputs must describe rows that were actually refreshed, not
    merely requested. ``local_album_ids`` must include every local album whose
    Spotify link evidence was rewritten. Deletions are deliberately unsupported
    because an absent row cannot prove its former reverse mappings.
    """

    ensure_album_project_schema(conn)
    if not impact_scope_exact:
        return _fallback_album_project_rebuild(conn, "impact_scope_inexact")
    if has_deletions:
        return _fallback_album_project_rebuild(conn, "deletion_semantics")
    if max_affected_albums < 0 or not 0 < max_affected_ratio <= 1:
        raise ValueError("invalid Album Project impact threshold")

    try:
        plan = _plan_album_project_impact(
            conn,
            local_album_ids=local_album_ids,
            spotify_album_ids=spotify_album_ids,
            spotify_track_ids=spotify_track_ids,
        )
    except (sqlite3.DatabaseError, _AlbumProjectClosureError):
        return _fallback_album_project_rebuild(conn, "closure_unproven")

    total_albums = int(conn.execute("SELECT COUNT(*) FROM albums").fetchone()[0])
    ratio_limit = max(1, math.ceil(total_albums * max_affected_ratio))
    album_limit = min(max_affected_albums, ratio_limit)
    if len(plan.album_ids | plan.compilation_album_ids) > album_limit:
        return _fallback_album_project_rebuild(conn, "closure_too_large")

    conn.execute("SAVEPOINT rebuild_album_projects_for_impact")
    try:
        affected_project_ids = set(plan.project_ids)
        if affected_project_ids:
            placeholders = ",".join("?" for _ in affected_project_ids)
            params = tuple(sorted(affected_project_ids))
            conn.execute(
                f"DELETE FROM album_project_tracks WHERE project_id IN ({placeholders})",
                params,
            )
            conn.execute(
                f"DELETE FROM album_project_albums WHERE project_id IN ({placeholders})",
                params,
            )

        seen_project_ids: set[int] = set()
        _bootstrap_from_release_groups(
            conn,
            seen_project_ids=seen_project_ids,
            group_ids=set(plan.release_group_ids),
        )
        _bootstrap_standalone_album_projects(
            conn,
            seen_project_ids=seen_project_ids,
            album_ids=set(plan.album_ids),
        )
        _bootstrap_compilation_exclusive_projects(
            conn,
            seen_project_ids=seen_project_ids,
            album_ids=set(plan.compilation_album_ids),
        )

        stale_project_ids = sorted(affected_project_ids - seen_project_ids)
        conn.executemany(
            "DELETE FROM album_projects WHERE project_id = ? AND is_manual = 0",
            ((project_id,) for project_id in stale_project_ids),
        )
        conn.execute("RELEASE SAVEPOINT rebuild_album_projects_for_impact")
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT rebuild_album_projects_for_impact")
        conn.execute("RELEASE SAVEPOINT rebuild_album_projects_for_impact")
        raise
    conn.commit()

    return AlbumProjectRebuildReport(
        strategy="targeted",
        fallback_reason=None,
        affected_album_count=len(plan.album_ids | plan.compilation_album_ids),
        affected_release_group_count=len(plan.release_group_ids),
        affected_project_count=len(affected_project_ids | seen_project_ids),
        affected_track_count=len(plan.track_ids),
    )


def _fallback_album_project_rebuild(
    conn: sqlite3.Connection,
    reason: str,
) -> AlbumProjectRebuildReport:
    rebuild_album_projects(conn)
    return AlbumProjectRebuildReport(
        strategy="full",
        fallback_reason=reason,
        affected_album_count=int(conn.execute("SELECT COUNT(*) FROM albums").fetchone()[0]),
        affected_release_group_count=int(
            conn.execute("SELECT COUNT(*) FROM release_groups").fetchone()[0]
        ),
        affected_project_count=int(
            conn.execute("SELECT COUNT(*) FROM album_projects WHERE is_manual = 0").fetchone()[0]
        ),
        affected_track_count=int(
            conn.execute(
                """SELECT COUNT(DISTINCT apt.track_id)
                   FROM album_project_tracks apt
                   JOIN album_projects ap ON ap.project_id = apt.project_id
                   WHERE ap.is_manual = 0"""
            ).fetchone()[0]
        ),
    )


def _plan_album_project_impact(
    conn: sqlite3.Connection,
    *,
    local_album_ids: Iterable[int],
    spotify_album_ids: Iterable[str],
    spotify_track_ids: Iterable[str],
) -> _AlbumProjectImpactPlan:
    local_ids = _normalise_integer_ids(local_album_ids)
    spotify_album_id_set = _normalise_spotify_ids(spotify_album_ids)
    spotify_track_id_set = _normalise_spotify_ids(spotify_track_ids)

    if local_ids:
        existing_local_ids = _select_integer_ids(
            conn,
            "albums",
            "album_id",
            local_ids,
        )
        if existing_local_ids != local_ids:
            raise _AlbumProjectClosureError("unknown local album impact")
    if spotify_track_id_set:
        existing_track_meta_ids = _select_text_ids(
            conn,
            "spotify_track_meta",
            "spotify_track_id",
            spotify_track_id_set,
        )
        if existing_track_meta_ids != spotify_track_id_set:
            raise _AlbumProjectClosureError("missing refreshed Spotify track metadata")
    if spotify_album_id_set:
        existing_album_meta_ids = _select_text_ids(
            conn,
            "spotify_album_meta",
            "spotify_album_id",
            spotify_album_id_set,
        )
        if existing_album_meta_ids != spotify_album_id_set:
            raise _AlbumProjectClosureError("missing refreshed Spotify album metadata")

    seed_album_ids = set(local_ids)
    impacted_track_ids: set[int] = set()
    if spotify_track_id_set:
        placeholders = ",".join("?" for _ in spotify_track_id_set)
        spotify_track_params = tuple(sorted(spotify_track_id_set))
        impacted_track_ids.update(
            int(row[0])
            for row in conn.execute(
                f"""SELECT track_id FROM tracks
                    WHERE spotify_track_id IN ({placeholders})""",
                spotify_track_params,
            ).fetchall()
        )
        impacted_track_ids.update(
            int(row[0])
            for row in conn.execute(
                f"""SELECT DISTINCT track_id FROM plays
                    WHERE spotify_track_id_at_play IN ({placeholders})
                      AND track_id IS NOT NULL""",
                spotify_track_params,
            ).fetchall()
        )
        seed_album_ids.update(
            int(row[0])
            for row in conn.execute(
                f"""SELECT DISTINCT source_album_id FROM plays
                    WHERE spotify_track_id_at_play IN ({placeholders})
                      AND source_album_id IS NOT NULL""",
                spotify_track_params,
            ).fetchall()
        )
        spotify_album_id_set.update(
            str(row[0])
            for row in conn.execute(
                f"""SELECT DISTINCT spotify_album_id FROM spotify_track_meta
                    WHERE spotify_track_id IN ({placeholders})
                      AND spotify_album_id IS NOT NULL
                      AND spotify_album_id != ''""",
                spotify_track_params,
            ).fetchall()
        )

    if impacted_track_ids:
        placeholders = ",".join("?" for _ in impacted_track_ids)
        track_params = tuple(sorted(impacted_track_ids))
        seed_album_ids.update(
            int(row[0])
            for row in conn.execute(
                f"""SELECT album_id FROM tracks
                    WHERE track_id IN ({placeholders}) AND album_id IS NOT NULL
                    UNION
                    SELECT album_id FROM track_albums
                    WHERE track_id IN ({placeholders})""",
                track_params + track_params,
            ).fetchall()
        )

    if spotify_album_id_set:
        placeholders = ",".join("?" for _ in spotify_album_id_set)
        spotify_album_params = tuple(sorted(spotify_album_id_set))
        seed_album_ids.update(
            int(row[0])
            for row in conn.execute(
                f"""SELECT album_id FROM album_spotify_links
                    WHERE spotify_album_id IN ({placeholders})""",
                spotify_album_params,
            ).fetchall()
        )
        seed_album_ids.update(
            int(row[0])
            for row in conn.execute(
                f"""SELECT DISTINCT al.album_id
                    FROM albums al
                    JOIN artists ar ON ar.artist_id = al.artist_id
                    JOIN spotify_album_meta sam
                      ON lower(sam.album_name) = lower(al.album_name)
                     AND (sam.album_artists IS NULL
                          OR ar.artist_name IS NULL
                          OR instr(lower(sam.album_artists), lower(ar.artist_name)) > 0)
                    WHERE sam.spotify_album_id IN ({placeholders})""",
                spotify_album_params,
            ).fetchall()
        )

    album_ids, group_ids, project_ids = _expand_non_compilation_closure(
        conn,
        seed_album_ids,
    )
    non_compilation_track_ids = {
        track_id for track_id, _album_id in _tracks_for_albums(conn, sorted(album_ids))
    }
    non_compilation_track_ids.update(impacted_track_ids)

    compilation_album_ids, compilation_project_ids, compilation_track_ids = _compilation_closure(
        conn,
        album_ids=album_ids,
        track_ids=non_compilation_track_ids,
    )
    return _AlbumProjectImpactPlan(
        album_ids=frozenset(album_ids),
        release_group_ids=frozenset(group_ids),
        project_ids=frozenset(project_ids | compilation_project_ids),
        track_ids=frozenset(non_compilation_track_ids | compilation_track_ids),
        compilation_album_ids=frozenset(compilation_album_ids),
    )


def _expand_non_compilation_closure(
    conn: sqlite3.Connection,
    seed_album_ids: set[int],
) -> tuple[set[int], set[int], set[int]]:
    albums = {
        int(row["album_id"]): (str(row["album_name"]), int(row["artist_id"]))
        for row in conn.execute(
            "SELECT album_id, album_name, artist_id FROM albums ORDER BY album_id"
        ).fetchall()
    }
    group_members: dict[int, set[int]] = {}
    for row in conn.execute(
        "SELECT group_id, album_id FROM release_group_members ORDER BY group_id, album_id"
    ).fetchall():
        group_members.setdefault(int(row["group_id"]), set()).add(int(row["album_id"]))
    groups: dict[int, tuple[tuple[str, int, str], set[int]]] = {}
    for row in conn.execute(
        """SELECT rg.group_id, rg.canonical_name, rg.artist_id,
                  rg.primary_album_id, rg.scope, al.artist_id AS primary_artist_id
           FROM release_groups rg
           LEFT JOIN albums al ON al.album_id = rg.primary_album_id
           ORDER BY rg.group_id"""
    ).fetchall():
        artist_id = int(row["artist_id"] or 0)
        if artist_id <= 0 and row["primary_artist_id"] is not None:
            artist_id = int(row["primary_artist_id"])
        if artist_id <= 0:
            continue
        members = set(group_members.get(int(row["group_id"]), set()))
        if row["primary_album_id"] is not None:
            members.add(int(row["primary_album_id"]))
        groups[int(row["group_id"])] = (
            (str(row["canonical_name"]), artist_id, str(row["scope"])),
            members,
        )

    project_albums: dict[int, set[int]] = {}
    for row in conn.execute(
        "SELECT project_id, album_id FROM album_project_albums ORDER BY project_id, album_id"
    ).fetchall():
        project_albums.setdefault(int(row["project_id"]), set()).add(int(row["album_id"]))
    projects: dict[int, tuple[tuple[str, int, str], set[int]]] = {}
    for row in conn.execute(
        """SELECT project_id, canonical_name, artist_id, primary_album_id, scope
           FROM album_projects WHERE is_manual = 0 ORDER BY project_id"""
    ).fetchall():
        member_ids = set(project_albums.get(int(row["project_id"]), set()))
        if row["primary_album_id"] is not None:
            member_ids.add(int(row["primary_album_id"]))
        projects[int(row["project_id"])] = (
            (str(row["canonical_name"]), int(row["artist_id"]), str(row["scope"])),
            member_ids,
        )

    album_ids = set(seed_album_ids)
    group_ids: set[int] = set()
    project_ids: set[int] = set()
    while True:
        before = (len(album_ids), len(group_ids), len(project_ids))
        semantic_keys = {
            (album_name, artist_id, "release")
            for album_id, (album_name, artist_id) in albums.items()
            if album_id in album_ids
        }
        semantic_keys.update(groups[group_id][0] for group_id in group_ids)

        for group_id, (semantic_key, member_ids) in groups.items():
            if member_ids & album_ids or semantic_key in semantic_keys:
                group_ids.add(group_id)
                album_ids.update(member_ids)
                semantic_keys.add(semantic_key)
        for album_id, (album_name, artist_id) in albums.items():
            if (album_name, artist_id, "release") in semantic_keys:
                album_ids.add(album_id)
        for project_id, (semantic_key, member_ids) in projects.items():
            if member_ids & album_ids or semantic_key in semantic_keys:
                project_ids.add(project_id)
                album_ids.update(member_ids)
                semantic_keys.add(semantic_key)

        after = (len(album_ids), len(group_ids), len(project_ids))
        if after == before:
            break

    if not album_ids.issubset(albums):
        raise _AlbumProjectClosureError("Album Project closure referenced a missing album")
    return album_ids, group_ids, project_ids


def _compilation_closure(
    conn: sqlite3.Connection,
    *,
    album_ids: set[int],
    track_ids: set[int],
) -> tuple[set[int], set[int], set[int]]:
    current_compilation_ids = {
        int(row[0])
        for row in conn.execute(
            """SELECT DISTINCT al.album_id
               FROM albums al
               JOIN artists ar ON ar.artist_id = al.artist_id
               JOIN spotify_album_meta sam
                 ON lower(sam.album_name) = lower(al.album_name)
                AND sam.album_type = 'compilation'"""
        ).fetchall()
    }
    compilation_tracks = {
        album_id: {track_id for track_id, _source_album_id in _tracks_for_albums(conn, [album_id])}
        for album_id in current_compilation_ids
    }

    project_albums: dict[int, set[int]] = {}
    for row in conn.execute(
        """SELECT apa.project_id, apa.album_id
           FROM album_project_albums apa
           JOIN album_projects ap ON ap.project_id = apa.project_id
           WHERE ap.is_manual = 0 AND ap.project_type = 'compilation_exclusive'"""
    ).fetchall():
        project_albums.setdefault(int(row["project_id"]), set()).add(int(row["album_id"]))
    project_tracks: dict[int, set[int]] = {}
    for row in conn.execute(
        """SELECT apt.project_id, apt.track_id
           FROM album_project_tracks apt
           JOIN album_projects ap ON ap.project_id = apt.project_id
           WHERE ap.is_manual = 0 AND ap.project_type = 'compilation_exclusive'"""
    ).fetchall():
        project_tracks.setdefault(int(row["project_id"]), set()).add(int(row["track_id"]))
    compilation_projects = {
        int(row["project_id"]): (
            (str(row["canonical_name"]), int(row["artist_id"]), str(row["scope"])),
            int(row["primary_album_id"]) if row["primary_album_id"] is not None else None,
        )
        for row in conn.execute(
            """SELECT project_id, canonical_name, artist_id, primary_album_id, scope
               FROM album_projects
               WHERE is_manual = 0 AND project_type = 'compilation_exclusive'"""
        ).fetchall()
    }

    selected_album_ids = set(album_ids & current_compilation_ids)
    selected_album_ids.update(
        album_id
        for album_id, member_track_ids in compilation_tracks.items()
        if member_track_ids & track_ids
    )
    selected_project_ids: set[int] = set()
    for project_id, (_semantic_key, primary_album_id) in compilation_projects.items():
        member_album_ids = set(project_albums.get(project_id, set()))
        if primary_album_id is not None:
            member_album_ids.add(primary_album_id)
        if member_album_ids & album_ids or project_tracks.get(project_id, set()) & track_ids:
            selected_project_ids.add(project_id)
            selected_album_ids.update(member_album_ids)

    albums = {
        int(row["album_id"]): (str(row["album_name"]), int(row["artist_id"]))
        for row in conn.execute(
            "SELECT album_id, album_name, artist_id FROM albums ORDER BY album_id"
        ).fetchall()
    }
    semantic_keys = {
        (albums[album_id][0], albums[album_id][1], "release")
        for album_id in selected_album_ids
        if album_id in albums
    }
    for project_id, (semantic_key, _primary_album_id) in compilation_projects.items():
        if semantic_key in semantic_keys:
            selected_project_ids.add(project_id)
            selected_album_ids.update(project_albums.get(project_id, set()))
    selected_album_ids.update(
        album_id
        for album_id in current_compilation_ids
        if album_id in albums
        and (albums[album_id][0], albums[album_id][1], "release") in semantic_keys
    )

    # A former compilation can only disappear safely when it was already part
    # of the non-compilation source closure (normally via its refreshed album
    # ID). Otherwise its prior name/type reverse mapping is no longer provable.
    stale_only_album_ids = selected_album_ids - current_compilation_ids - album_ids
    if stale_only_album_ids:
        raise _AlbumProjectClosureError("former compilation mapping is outside impact scope")

    selected_album_ids &= current_compilation_ids
    selected_track_ids = {
        track_id
        for album_id in selected_album_ids
        for track_id in compilation_tracks.get(album_id, set())
    }
    return selected_album_ids, selected_project_ids, selected_track_ids


def _normalise_integer_ids(values: Iterable[int]) -> set[int]:
    try:
        normalised = {int(value) for value in values}
    except (TypeError, ValueError) as exc:
        raise _AlbumProjectClosureError("invalid local album impact") from exc
    if any(value <= 0 for value in normalised):
        raise _AlbumProjectClosureError("invalid local album impact")
    return normalised


def _normalise_spotify_ids(values: Iterable[str]) -> set[str]:
    try:
        normalised = {str(value).strip() for value in values}
    except TypeError as exc:
        raise _AlbumProjectClosureError("invalid Spotify impact") from exc
    if "" in normalised:
        raise _AlbumProjectClosureError("invalid Spotify impact")
    return normalised


def _select_integer_ids(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    values: set[int],
) -> set[int]:
    if not values:
        return set()
    placeholders = ",".join("?" for _ in values)
    return {
        int(row[0])
        for row in conn.execute(
            f"SELECT {column} FROM {table} WHERE {column} IN ({placeholders})",
            tuple(sorted(values)),
        ).fetchall()
    }


def _select_text_ids(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    values: set[str],
) -> set[str]:
    if not values:
        return set()
    placeholders = ",".join("?" for _ in values)
    return {
        str(row[0])
        for row in conn.execute(
            f"SELECT {column} FROM {table} WHERE {column} IN ({placeholders})",
            tuple(sorted(values)),
        ).fetchall()
    }


def _populate_album_projects(
    conn: sqlite3.Connection,
    *,
    seen_project_ids: set[int] | None = None,
) -> None:
    """Populate inferred projects and optionally record identities used this pass."""
    _bootstrap_from_release_groups(conn, seen_project_ids=seen_project_ids)
    _bootstrap_standalone_album_projects(conn, seen_project_ids=seen_project_ids)
    _bootstrap_compilation_exclusive_projects(conn, seen_project_ids=seen_project_ids)


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
    has_l1 = (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='track_l1_source_links'"
        ).fetchone()
        is not None
        and conn.execute("SELECT 1 FROM track_l1_source_links LIMIT 1").fetchone() is not None
    )
    track_id_expr = "links.l1_id" if has_l1 else "apt.track_id"
    source_link_join = (
        "JOIN (SELECT DISTINCT track_id, l1_id FROM track_l1_source_links) links "
        "ON links.track_id=apt.track_id"
        if has_l1
        else ""
    )
    identity_track_join = (
        "JOIN track_l1_identities li ON li.l1_id=links.l1_id "
        "JOIN tracks t ON t.track_id=li.representative_track_id"
        if has_l1
        else "JOIN tracks t ON t.track_id = apt.track_id"
    )
    raw = pd.read_sql_query(
        f"""SELECT DISTINCT ap.project_id,
                  ap.canonical_name AS album_project_name,
                  ap.artist_id,
                  ar.artist_name,
                  ap.primary_album_id,
                  ap.release_date,
                  ap.scope,
                  ap.project_type,
                  ap.include_in_charts,
                  {track_id_expr} AS track_id,
                  t.track_name,
                  apt.membership_role,
                  apt.min_merge_level,
                  apt.source_album_id,
                  apa.source_bucket,
                  apt.is_exclusive,
                  apt.inferred
           FROM album_project_tracks apt
           {source_link_join}
           JOIN album_projects ap ON ap.project_id = apt.project_id
           LEFT JOIN artists ar ON ar.artist_id = ap.artist_id
           {identity_track_join}
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
    from backend.domains.metadata.artist_identity import canonicalize_artist_frame

    raw = canonicalize_artist_frame(raw, conn, dedupe=False)
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
    merged = _normalise_project_artist_column(merged)
    if billboard_mode:
        merged = _filter_to_project_release_date(merged)
    if merged.empty:
        return _empty_album_project_frame()

    aggregations = {
        **_play_weight_aggs(merged),
        "unique_canonical_songs": ("canonical_song_key", "nunique"),
    }
    # Keep the observation window attached to each album project.  Some
    # callers use pre-aggregated frames without an event timestamp, so only
    # add these fields when the source frame can support them.
    if "ts" in merged.columns:
        aggregations.update(
            {
                "first_played": ("ts", "min"),
                "last_played": ("ts", "max"),
            }
        )

    result = (
        merged.groupby(
            ["project_id", "album_project_name", "artist_name_project", "release_date"],
            dropna=False,
        )
        .agg(**aggregations)
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
    merged = _normalise_project_artist_column(merged)
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


def _normalise_project_artist_column(merged: pd.DataFrame) -> pd.DataFrame:
    """Expose the project owner under one schema for sparse event frames."""
    if "artist_name_project" in merged.columns:
        return merged
    if "artist_name" not in merged.columns:
        raise ValueError("album project membership is missing its artist name")
    return merged.rename(columns={"artist_name": "artist_name_project"})


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


def _bootstrap_from_release_groups(
    conn: sqlite3.Connection,
    *,
    seen_project_ids: set[int] | None = None,
    group_ids: set[int] | None = None,
) -> None:
    group_filter = ""
    group_params: tuple[int, ...] = ()
    if group_ids is not None:
        group_params = tuple(sorted(group_ids))
        if not group_params:
            return
        placeholders = ",".join("?" for _ in group_params)
        group_filter = f"WHERE rg.group_id IN ({placeholders})"
    groups = conn.execute(
        f"""SELECT rg.group_id, rg.canonical_name, rg.artist_id, rg.primary_album_id, rg.scope,
                  sam.release_date, sam.album_type, sam.total_tracks
           FROM release_groups rg
           LEFT JOIN albums al ON al.album_id = rg.primary_album_id
           LEFT JOIN artists ar ON ar.artist_id = al.artist_id
           LEFT JOIN spotify_album_meta sam
             ON lower(sam.album_name) = lower(al.album_name)
            AND (sam.album_artists IS NULL OR ar.artist_name IS NULL OR instr(lower(sam.album_artists), lower(ar.artist_name)) > 0)
           {group_filter}
           ORDER BY rg.group_id""",
        group_params,
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

        # Singles: skip release groups whose primary album is classified
        # as a single by Spotify metadata.  The name-match SQL already
        # prefers album > ep > single via the correlated subquery.
        spotify_type = group["album_type"]
        resolved = _resolve_standalone_album_type(
            conn, int(group["primary_album_id"]), spotify_type
        )
        if resolved in ("single", "unknown"):
            continue

        member_rows = conn.execute(
            "SELECT album_id FROM release_group_members WHERE group_id = ?",
            (group["group_id"],),
        ).fetchall()
        member_ids = [int(row["album_id"]) for row in member_rows]
        active_memberships = _tracks_for_albums(conn, member_ids)
        if not active_memberships:
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
        if project_id is None:
            continue
        if seen_project_ids is not None:
            seen_project_ids.add(project_id)
        for album_id in member_ids:
            _insert_project_album(
                conn,
                project_id=project_id,
                album_id=album_id,
                primary_album_id=group["primary_album_id"],
            )
        min_merge_level = 3 if group["scope"] == "composition" else 2
        for track_id, album_id in active_memberships:
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


def _resolve_standalone_album_type(
    conn: sqlite3.Connection, album_id: int, name_match_type: str | None
) -> str:
    """Determine album type using Spotify metadata as primary signal.

    1. Direct name-match in spotify_album_meta → trust Spotify's type
    2. No name-match → aggregate album_spotify_links by play_count majority
    3. No links → 'unknown'

    Returns 'album', 'ep', 'single', 'compilation', or 'unknown'.
    """
    # ① Direct name-match — Spotify's classification is the best signal
    if name_match_type:
        t = name_match_type.lower()
        if t in ("album", "ep", "single", "compilation"):
            return t

    # ② No name-match — vote by album_spotify_links (weighted by play_count)
    try:
        links = conn.execute(
            """SELECT sam.album_type, asl.play_count
               FROM album_spotify_links asl
               JOIN spotify_album_meta sam
                 ON sam.spotify_album_id = asl.spotify_album_id
               WHERE asl.album_id = ?""",
            (album_id,),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        if "album_spotify_links" not in str(exc):
            raise
        links = []

    if links:
        scores: dict[str, int] = {"album": 0, "ep": 0, "single": 0, "compilation": 0}
        for link in links:
            t = (link["album_type"] or "").lower()
            if t in scores:
                scores[t] += link["play_count"] or 1
        best = max(scores, key=scores.get)
        if scores[best] > 0:
            return best

    return "unknown"


def _bootstrap_standalone_album_projects(
    conn: sqlite3.Connection,
    *,
    seen_project_ids: set[int] | None = None,
    album_ids: set[int] | None = None,
) -> None:
    album_filter = ""
    album_params: tuple[int, ...] = ()
    if album_ids is not None:
        album_params = tuple(sorted(album_ids))
        if not album_params:
            return
        placeholders = ",".join("?" for _ in album_params)
        album_filter = f"AND al.album_id IN ({placeholders})"
    albums = conn.execute(
        f"""SELECT al.album_id, al.album_name, al.artist_id, ar.artist_name,
                  sam.album_type, sam.total_tracks, sam.release_date,
                  (SELECT COUNT(DISTINCT track_id) FROM (
                      SELECT track_id FROM tracks WHERE album_id = al.album_id
                      UNION
                      SELECT track_id FROM track_albums WHERE album_id = al.album_id
                  )) AS local_tracks
           FROM albums al
           JOIN artists ar ON ar.artist_id = al.artist_id
           LEFT JOIN spotify_album_meta sam ON sam.spotify_album_id = (
               SELECT s.spotify_album_id FROM spotify_album_meta s
               WHERE lower(s.album_name) = lower(al.album_name)
                 AND (s.album_artists IS NULL
                      OR instr(lower(s.album_artists), lower(ar.artist_name)) > 0)
               ORDER BY CASE s.album_type
                          WHEN 'album' THEN 0
                          WHEN 'ep' THEN 1
                          WHEN 'single' THEN 2
                          ELSE 3
                        END
               LIMIT 1
           )
           WHERE NOT EXISTS (
               SELECT 1
               FROM release_group_members rgm
               JOIN release_groups rg ON rg.group_id = rgm.group_id
               WHERE rgm.album_id = al.album_id
                 AND rg.scope = 'release'
           )
           {album_filter}
           GROUP BY al.album_id
           ORDER BY al.album_id""",
        album_params,
    ).fetchall()

    active_memberships_by_album: dict[int, list[tuple[int, int]]] = {}
    for track_id, album_id in _tracks_for_albums(
        conn, [int(album["album_id"]) for album in albums]
    ):
        active_memberships_by_album.setdefault(album_id, []).append((track_id, album_id))

    for album in albums:
        active_memberships = active_memberships_by_album.get(int(album["album_id"]), [])
        if not active_memberships:
            continue
        name_match_type = album["album_type"]  # Spotify type from name-match (or None)
        release_date = album["release_date"]
        local_tracks = len({track_id for track_id, _album_id in active_memberships})

        # ── Resolve album type: Spotify metadata first, links second ──
        resolved = _resolve_standalone_album_type(conn, int(album["album_id"]), name_match_type)

        # Singles do not chart (R13)
        if resolved == "single":
            continue

        # Compilations handled by _bootstrap_compilation_exclusive_projects
        if resolved == "compilation":
            continue

        # Unknown type: only create project when there's strong evidence (≥7 tracks)
        if resolved == "unknown":
            if local_tracks >= 7:
                resolved = "album"
            else:
                continue

        if resolved not in ("album", "ep"):
            continue

        # Release date: prefer name-match; fall back to best linked album
        if not release_date:
            linked = _best_spotify_album_for_local_album(conn, int(album["album_id"]))
            if linked:
                release_date = linked["release_date"] or release_date
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
        if project_id is None:
            continue
        if seen_project_ids is not None:
            seen_project_ids.add(project_id)
        _insert_project_album(
            conn,
            project_id=project_id,
            album_id=album["album_id"],
            primary_album_id=album["album_id"],
        )
        for track_id, source_album_id in active_memberships:
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


def _bootstrap_compilation_exclusive_projects(
    conn: sqlite3.Connection,
    *,
    seen_project_ids: set[int] | None = None,
    album_ids: set[int] | None = None,
) -> None:
    album_filter = ""
    album_params: tuple[int, ...] = ()
    if album_ids is not None:
        album_params = tuple(sorted(album_ids))
        if not album_params:
            return
        placeholders = ",".join("?" for _ in album_params)
        album_filter = f"AND al.album_id IN ({placeholders})"
    compilations = conn.execute(
        f"""SELECT al.album_id, al.album_name, al.artist_id, sam.release_date
           FROM albums al
           JOIN artists ar ON ar.artist_id = al.artist_id
           JOIN spotify_album_meta sam
             ON lower(sam.album_name) = lower(al.album_name)
            AND sam.album_type = 'compilation'
           WHERE 1=1 {album_filter}
           ORDER BY al.album_id""",
        album_params,
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
        if project_id is None:
            continue
        if seen_project_ids is not None:
            seen_project_ids.add(project_id)
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
) -> int | None:
    row = conn.execute(
        """SELECT project_id, is_manual FROM album_projects
           WHERE canonical_name = ? AND artist_id = ? AND scope = ?""",
        (canonical_name, artist_id, scope),
    ).fetchone()
    if row is None:
        conn.execute(
            """INSERT INTO album_projects
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
            """SELECT project_id, is_manual FROM album_projects
               WHERE canonical_name = ? AND artist_id = ? AND scope = ?""",
            (canonical_name, artist_id, scope),
        ).fetchone()
    if row is None:
        raise RuntimeError("album project insert did not produce an identity")
    if int(row["is_manual"] or 0) != 0 and is_manual == 0:
        # A manual project owns this semantic key. Do not let inferred rebuilds
        # mutate either its metadata or its hand-maintained memberships.
        return None
    conn.execute(
        """UPDATE album_projects
           SET primary_album_id = ?, release_date = ?, project_type = ?,
               include_in_charts = ?, is_manual = ?
           WHERE project_id = ?""",
        (
            primary_album_id,
            release_date,
            project_type,
            include_in_charts,
            is_manual,
            row["project_id"],
        ),
    )
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
    """Return catalog membership that is still reachable from active playback facts.

    ``track_albums`` is the import-maintained observation projection, while
    manual project membership lives in separate governance tables.  Keep this
    consumer defensive as well: automatic Album Projects only use relationships
    supported by current playback-time evidence, and exclude catalog orphans.
    """
    if not album_ids:
        return []
    placeholders = ",".join("?" for _ in album_ids)
    rows = conn.execute(
        f"""SELECT DISTINCT track_id, album_id
            FROM (
                SELECT t.track_id, t.album_id
                FROM tracks t
                WHERE t.album_id IN ({placeholders})
                  AND EXISTS (SELECT 1 FROM plays p WHERE p.track_id=t.track_id)
                  AND (
                    NOT EXISTS (
                        SELECT 1 FROM plays p
                        WHERE p.track_id=t.track_id AND p.source_album_id IS NOT NULL
                    )
                    OR EXISTS (
                        SELECT 1 FROM plays p
                        WHERE p.track_id=t.track_id AND p.source_album_id=t.album_id
                    )
                  )
                UNION
                SELECT ta.track_id, ta.album_id
                FROM track_albums ta
                WHERE ta.album_id IN ({placeholders})
                  AND EXISTS (SELECT 1 FROM plays p WHERE p.track_id=ta.track_id)
                  AND (
                    NOT EXISTS (
                        SELECT 1 FROM plays p
                        WHERE p.track_id=ta.track_id AND p.source_album_id IS NOT NULL
                    )
                    OR EXISTS (
                        SELECT 1 FROM plays p
                        WHERE p.track_id=ta.track_id AND p.source_album_id=ta.album_id
                    )
                  )
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
    meta = _load_l1_album_metadata(conn, album_ids)
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
    meta = _load_l1_album_metadata(conn, album_ids)
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


def _load_l1_album_metadata(
    conn: sqlite3.Connection,
    album_ids: list[int],
) -> pd.DataFrame:
    """Load one unambiguous metadata row per physical album container.

    Album names are not identities: different artists and editions can share
    the same title. Production databases therefore resolve Spotify metadata
    through the scored ``album_spotify_links`` relation. Minimal legacy/test
    schemas without that relation may use a normalized-name fallback only when
    the title is unique in both local albums and Spotify metadata; ambiguous
    titles keep local/unknown metadata instead of guessing.
    """
    if not album_ids:
        return pd.DataFrame(
            columns=[
                "album_id",
                "meta_album_name",
                "meta_artist_name",
                "release_date",
                "album_type",
            ]
        )
    album_columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(albums)").fetchall()}
    has_spotify_identity = "spotify_album_id" in album_columns
    has_local_release = "release_date" in album_columns
    has_local_type = "album_type" in album_columns
    has_album_links = (
        conn.execute(
            """SELECT 1 FROM sqlite_master
               WHERE type='table' AND name='album_spotify_links'"""
        ).fetchone()
        is not None
    )
    if has_spotify_identity:
        release_expression = (
            "COALESCE(sam.release_date, al.release_date)"
            if has_local_release
            else "sam.release_date"
        )
        type_expression = (
            "COALESCE(sam.album_type, al.album_type)" if has_local_type else "sam.album_type"
        )
        spotify_join = (
            "LEFT JOIN spotify_album_meta sam ON sam.spotify_album_id = al.spotify_album_id"
        )
    elif has_album_links:
        release_expression = (
            "COALESCE(sam.release_date, legacy_sam.release_date, al.release_date)"
            if has_local_release
            else "COALESCE(sam.release_date, legacy_sam.release_date)"
        )
        type_expression = (
            "COALESCE(sam.album_type, legacy_sam.album_type, al.album_type)"
            if has_local_type
            else "COALESCE(sam.album_type, legacy_sam.album_type)"
        )
        spotify_join = """LEFT JOIN (
                SELECT album_id, spotify_album_id
                FROM (
                    SELECT scored.*,
                           ROW_NUMBER() OVER (
                               PARTITION BY scored.album_id
                               ORDER BY scored.play_count DESC,
                                        scored.track_count DESC,
                                        scored.confidence DESC,
                                        scored.spotify_album_id ASC
                           ) AS link_rank
                    FROM (
                        SELECT album_id, spotify_album_id,
                               SUM(COALESCE(play_count, 0)) AS play_count,
                               MAX(COALESCE(track_count, 0)) AS track_count,
                               MAX(COALESCE(confidence, 0.0)) AS confidence
                        FROM album_spotify_links
                        GROUP BY album_id, spotify_album_id
                    ) scored
                ) ranked
                WHERE link_rank = 1
            ) best_link ON best_link.album_id = al.album_id
            LEFT JOIN spotify_album_meta sam
              ON sam.spotify_album_id = best_link.spotify_album_id
            LEFT JOIN spotify_album_meta legacy_sam
              ON best_link.spotify_album_id IS NULL
             AND lower(trim(legacy_sam.album_name)) = lower(trim(al.album_name))
             AND 1 = (
                 SELECT COUNT(*) FROM spotify_album_meta same_meta
                 WHERE lower(trim(same_meta.album_name)) = lower(trim(al.album_name))
             )
             AND 1 = (
                 SELECT COUNT(*) FROM albums same_album
                 WHERE lower(trim(same_album.album_name)) = lower(trim(al.album_name))
             )"""
    else:
        release_expression = (
            "COALESCE(sam.release_date, al.release_date)"
            if has_local_release
            else "sam.release_date"
        )
        type_expression = (
            "COALESCE(sam.album_type, al.album_type)" if has_local_type else "sam.album_type"
        )
        spotify_join = """LEFT JOIN spotify_album_meta sam
            ON lower(trim(sam.album_name)) = lower(trim(al.album_name))
           AND 1 = (
               SELECT COUNT(*) FROM spotify_album_meta same_meta
               WHERE lower(trim(same_meta.album_name)) = lower(trim(al.album_name))
           )
           AND 1 = (
               SELECT COUNT(*) FROM albums same_album
               WHERE lower(trim(same_album.album_name)) = lower(trim(al.album_name))
           )"""
    placeholders = ",".join("?" for _ in album_ids)
    metadata = pd.read_sql_query(
        f"""SELECT al.album_id,
                   al.album_name AS meta_album_name,
                   ar.artist_name AS meta_artist_name,
                   {release_expression} AS release_date,
                   {type_expression} AS album_type
            FROM albums al
            JOIN artists ar ON ar.artist_id = al.artist_id
            {spotify_join}
            WHERE al.album_id IN ({placeholders})""",
        conn,
        params=tuple(album_ids),
    )
    if metadata["album_id"].duplicated().any():
        raise RuntimeError("physical album metadata identity is not unique")
    return metadata


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
            "first_played",
            "last_played",
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
