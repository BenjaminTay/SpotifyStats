"""Resolve representative Spotify metadata for album detail pages.

``album_spotify_links`` records evidence that plays came from a Spotify album
container.  It is intentionally many-to-many and therefore cannot, by itself,
identify the canonical release represented by an album project.  Detail pages
must resolve the project first and only then choose a representative provider
row.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from backend.core.version_merge import normalize_album_name
from backend.domains.music_search.normalization import normalize_search_text

_META_FIELDS = ("album_type", "release_date", "popularity", "label", "total_tracks")


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


def _resolve_project(
    conn: sqlite3.Connection,
    album_name: str,
    artist_name: str,
    album_project_id: int | None,
) -> sqlite3.Row | None:
    if not _table_exists(conn, "album_projects"):
        return None
    if album_project_id is not None:
        return conn.execute(
            """SELECT project_id, canonical_name, primary_album_id,
                      release_date, project_type
               FROM album_projects WHERE project_id=?""",
            (album_project_id,),
        ).fetchone()
    return conn.execute(
        """SELECT ap.project_id, ap.canonical_name, ap.primary_album_id,
                  ap.release_date, ap.project_type
           FROM album_projects ap
           JOIN artists ar ON ar.artist_id=ap.artist_id
           WHERE lower(ap.canonical_name)=lower(?)
             AND lower(ar.artist_name)=lower(?)
             AND ap.scope='release'
           ORDER BY ap.is_manual DESC, ap.project_id
           LIMIT 1""",
        (album_name, artist_name),
    ).fetchone()


def _album_ids(
    conn: sqlite3.Connection,
    album_name: str,
    artist_name: str,
    *,
    project: sqlite3.Row | None,
    album_id: int | None,
) -> list[int]:
    if project is not None and _table_exists(conn, "album_project_albums"):
        rows = conn.execute(
            "SELECT album_id FROM album_project_albums WHERE project_id=? ORDER BY album_id",
            (project["project_id"],),
        ).fetchall()
        values = [int(row[0]) for row in rows]
        primary = project["primary_album_id"]
        if primary is not None and int(primary) not in values:
            values.insert(0, int(primary))
        return values
    if album_id is not None:
        return [int(album_id)]
    rows = conn.execute(
        """SELECT al.album_id
           FROM albums al
           JOIN artists ar ON ar.artist_id=al.artist_id
           WHERE lower(al.album_name)=lower(?) AND lower(ar.artist_name)=lower(?)
           ORDER BY al.album_id""",
        (album_name, artist_name),
    ).fetchall()
    return [int(row[0]) for row in rows]


def _load_candidates(
    conn: sqlite3.Connection,
    album_ids: list[int],
    primary_album_id: int | None,
) -> list[dict[str, Any]]:
    if not album_ids:
        return []
    placeholders = ",".join("?" for _ in album_ids)
    candidates: list[dict[str, Any]] = []
    if _table_exists(conn, "album_spotify_links"):
        rows = conn.execute(
            f"""SELECT sam.spotify_album_id, sam.album_name, sam.album_type,
                       sam.release_date, sam.popularity, sam.label,
                       sam.total_tracks,
                       MAX(asl.confidence) AS confidence,
                       SUM(asl.play_count) AS play_count,
                       MIN(CASE WHEN asl.album_id=? THEN 0 ELSE 1 END) AS source_rank
                FROM album_spotify_links asl
                JOIN spotify_album_meta sam
                  ON sam.spotify_album_id=asl.spotify_album_id
                WHERE asl.album_id IN ({placeholders})
                GROUP BY sam.spotify_album_id
                ORDER BY sam.spotify_album_id""",
            (primary_album_id, *album_ids),
        ).fetchall()
        candidates = [dict(row) for row in rows]
    if candidates or not _table_exists(conn, "spotify_track_meta"):
        return candidates

    rows = conn.execute(
        f"""WITH album_tracks AS (
                 SELECT track_id, album_id FROM tracks
                 WHERE album_id IN ({placeholders})
                 UNION
                 SELECT track_id, album_id FROM track_albums
                 WHERE album_id IN ({placeholders})
               )
               SELECT sam.spotify_album_id, sam.album_name, sam.album_type,
                      sam.release_date, sam.popularity, sam.label,
                      sam.total_tracks, 0.0 AS confidence, 0 AS play_count,
                      MIN(CASE WHEN at.album_id=? THEN 0 ELSE 1 END) AS source_rank
               FROM album_tracks at
               JOIN tracks t ON t.track_id=at.track_id
               JOIN spotify_track_meta stm ON stm.spotify_track_id=t.spotify_track_id
               JOIN spotify_album_meta sam ON sam.spotify_album_id=stm.spotify_album_id
               GROUP BY sam.spotify_album_id
               ORDER BY sam.spotify_album_id""",
        (*album_ids, *album_ids, primary_album_id),
    ).fetchall()
    return [dict(row) for row in rows]


def _date_matches(project_date: str | None, candidate_date: str | None) -> bool:
    if not project_date or not candidate_date:
        return False
    precision = len(project_date)
    if precision not in {4, 7, 10}:
        return candidate_date == project_date
    return candidate_date[:precision] == project_date


def _type_rank(project_type: str | None, album_type: str | None) -> int:
    value = (album_type or "").casefold()
    if project_type == "compilation_exclusive":
        return 0 if value == "compilation" else 1
    return 0 if value == "album" else 1


def _select_candidate(
    candidates: list[dict[str, Any]],
    *,
    album_name: str,
    project_date: str | None,
    project_type: str | None,
) -> dict[str, Any] | None:
    if not candidates:
        return None
    normalized_name = normalize_search_text(album_name)
    normalized_base = normalize_search_text(normalize_album_name(album_name))

    def key(row: dict[str, Any]) -> tuple[Any, ...]:
        candidate_name = str(row.get("album_name") or "")
        candidate_normalized = normalize_search_text(candidate_name)
        candidate_base = normalize_search_text(normalize_album_name(candidate_name))
        common = (
            0 if candidate_normalized == normalized_name else 1,
            0 if candidate_base == normalized_base else 1,
            _type_rank(project_type, row.get("album_type")),
            -float(row.get("confidence") or 0),
            -int(row.get("play_count") or 0),
        )
        if project_date:
            return (
                0 if _date_matches(project_date, row.get("release_date")) else 1,
                int(row.get("source_rank") or 0),
                *common,
                str(row.get("release_date") or "9999"),
                str(row.get("spotify_album_id") or ""),
            )
        return (
            *common,
            str(row.get("release_date") or "9999"),
            str(row.get("spotify_album_id") or ""),
        )

    return min(candidates, key=key)


def _local_track_count(conn: sqlite3.Connection, album_ids: list[int]) -> int | None:
    if not album_ids:
        return None
    placeholders = ",".join("?" for _ in album_ids)
    row = conn.execute(
        f"""SELECT COUNT(DISTINCT track_id) FROM (
              SELECT track_id FROM tracks WHERE album_id IN ({placeholders})
              UNION
              SELECT track_id FROM track_albums WHERE album_id IN ({placeholders})
            )""",
        (*album_ids, *album_ids),
    ).fetchone()
    count = int(row[0] or 0) if row is not None else 0
    return count or None


def resolve_album_detail_meta(
    conn: sqlite3.Connection,
    album_name: str,
    artist_name: str,
    *,
    merge_level: int = 2,
    album_project_id: int | None = None,
    album_id: int | None = None,
) -> dict[str, Any] | None:
    """Return representative provider metadata for one detail identity.

    L2/L3 details represent an album project, so its governed release date is
    authoritative.  L1 details represent a physical/source album and retain the
    selected Spotify release date.
    """

    project = (
        _resolve_project(conn, album_name, artist_name, album_project_id)
        if merge_level > 1
        else None
    )
    primary_album_id = (
        int(project["primary_album_id"])
        if project is not None and project["primary_album_id"] is not None
        else album_id
    )
    ids = _album_ids(
        conn,
        album_name,
        artist_name,
        project=project,
        album_id=album_id,
    )
    candidates = _load_candidates(conn, ids, primary_album_id)
    project_date = (
        str(project["release_date"]) if project is not None and project["release_date"] else None
    )
    project_type = (
        str(project["project_type"]) if project is not None and project["project_type"] else None
    )
    selected = _select_candidate(
        candidates,
        album_name=str(project["canonical_name"]) if project is not None else album_name,
        project_date=project_date,
        project_type=project_type,
    )

    meta = {
        field: selected.get(field)
        for field in _META_FIELDS
        if selected is not None and selected.get(field) is not None
    }
    if project_date:
        meta["release_date"] = project_date
    if "album_type" not in meta and project_type:
        meta["album_type"] = "compilation" if project_type == "compilation_exclusive" else "album"
    if "total_tracks" not in meta:
        track_count = _local_track_count(conn, [primary_album_id] if primary_album_id else ids)
        if track_count is not None:
            meta["total_tracks"] = track_count
    return meta or None
