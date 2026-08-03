"""Read-only local entity resolver for AI Agent tools."""

from __future__ import annotations

import sqlite3
from typing import Any, Literal

EntityType = Literal["track", "album", "artist"]

_ENTITY_NAME_COLUMNS: dict[EntityType, str] = {
    "track": "track_name",
    "album": "album_name",
    "artist": "artist_name",
}


def _row_value(row: Any, key: str, index: int) -> Any:
    if isinstance(row, sqlite3.Row):
        return row[key]
    if isinstance(row, dict):
        return row[key]
    return row[index]


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(_row_value(row, "name", 1)) for row in rows}


def _has_columns(conn: sqlite3.Connection, table_name: str, columns: set[str]) -> bool:
    return columns.issubset(_table_columns(conn, table_name))


def _bounded_limit(limit: int) -> int:
    return max(1, min(int(limit), 10))


def _empty_result(query: str, entity_type: EntityType) -> dict[str, Any]:
    return {
        "found": False,
        "query": query,
        "entity_type": entity_type,
        "candidates": [],
    }


def _search_terms(query: str) -> tuple[str, str, str]:
    normalized = query.strip().lower()
    return f"%{normalized}%", normalized, f"{normalized}%"


def _normalized_query(conn: sqlite3.Connection, entity_type: EntityType, query: str, limit: int):
    if entity_type == "track":
        return _normalized_track_query(conn, query, limit)
    if entity_type == "album":
        return _normalized_album_query(conn, query, limit)
    return _normalized_artist_query(conn, query, limit)


def _normalized_track_query(conn: sqlite3.Connection, query: str, limit: int) -> list[sqlite3.Row]:
    if not (
        _has_columns(conn, "tracks", {"track_id", "track_name"})
        and _has_columns(conn, "plays", {"track_id", "ms_played"})
    ):
        return []

    track_columns = _table_columns(conn, "tracks")
    artist_join = ""
    artist_select = "NULL AS artist_name"
    artist_group: list[str] = []
    if "artist_id" in track_columns and _has_columns(conn, "artists", {"artist_id", "artist_name"}):
        artist_join = "LEFT JOIN artists ar ON ar.artist_id = t.artist_id"
        artist_select = "ar.artist_name AS artist_name"
        artist_group = ["ar.artist_name"]

    album_join = ""
    album_id_select = "NULL AS album_id"
    album_select = "NULL AS album_name"
    album_id_group: list[str] = []
    album_group: list[str] = []
    if "album_id" in track_columns:
        album_id_select = "t.album_id AS album_id"
        album_id_group = ["t.album_id"]
    if "album_id" in track_columns and _has_columns(conn, "albums", {"album_id", "album_name"}):
        album_join = "LEFT JOIN albums al ON al.album_id = t.album_id"
        album_select = "al.album_name AS album_name"
        album_group = ["al.album_name"]

    like_term, exact_term, prefix_term = _search_terms(query)
    group_by = ", ".join(
        ["t.track_id", "t.track_name", *artist_group, *album_id_group, *album_group]
    )
    return conn.execute(
        f"""
        SELECT
            t.track_name AS name,
            t.track_id AS track_id,
            {album_id_select},
            {artist_select},
            {album_select},
            COUNT(*) AS play_events,
            COALESCE(SUM(p.ms_played), 0) AS total_ms
        FROM tracks t
        JOIN plays p ON p.track_id = t.track_id
        {artist_join}
        {album_join}
        WHERE lower(t.track_name) LIKE ?
          AND t.track_name IS NOT NULL
          AND TRIM(t.track_name) != ''
        GROUP BY {group_by}
        ORDER BY
            CASE
                WHEN lower(t.track_name) = ? THEN 0
                WHEN lower(t.track_name) LIKE ? THEN 1
                ELSE 2
            END ASC,
            play_events DESC,
            total_ms DESC,
            name COLLATE NOCASE ASC
        LIMIT ?
        """,
        (like_term, exact_term, prefix_term, _bounded_limit(limit)),
    ).fetchall()


def _normalized_album_query(conn: sqlite3.Connection, query: str, limit: int) -> list[sqlite3.Row]:
    if not (
        _has_columns(conn, "albums", {"album_id", "album_name"})
        and _has_columns(conn, "tracks", {"track_id"})
        and _has_columns(conn, "plays", {"track_id", "ms_played"})
    ):
        return []

    track_columns = _table_columns(conn, "tracks")
    play_columns = _table_columns(conn, "plays")
    play_key = "p.play_id" if "play_id" in play_columns else "p.rowid"
    album_play_sources: list[str] = []
    if "album_id" in track_columns:
        album_play_sources.append(
            f"""
            SELECT {play_key} AS play_key, t.album_id AS album_id, p.ms_played AS ms_played
            FROM plays p
            JOIN tracks t ON t.track_id = p.track_id
            WHERE t.album_id IS NOT NULL
            """
        )
    if _has_columns(conn, "track_albums", {"track_id", "album_id"}):
        album_play_sources.append(
            f"""
            SELECT {play_key} AS play_key, ta.album_id AS album_id, p.ms_played AS ms_played
            FROM plays p
            JOIN track_albums ta ON ta.track_id = p.track_id
            WHERE ta.album_id IS NOT NULL
            """
        )
    if "source_album_id" in play_columns:
        album_play_sources.append(
            f"""
            SELECT {play_key} AS play_key, p.source_album_id AS album_id, p.ms_played AS ms_played
            FROM plays p
            WHERE p.source_album_id IS NOT NULL
              AND p.source_album_id != 0
            """
        )
    if not album_play_sources:
        return []

    album_columns = _table_columns(conn, "albums")
    artist_join = ""
    artist_select = "NULL AS artist_name"
    artist_id_select = "NULL AS artist_id"
    artist_group: list[str] = []
    if "artist_id" in album_columns:
        artist_id_select = "al.artist_id AS artist_id"
        artist_group.append("al.artist_id")
        if _has_columns(conn, "artists", {"artist_id", "artist_name"}):
            artist_join = "LEFT JOIN artists ar ON ar.artist_id = al.artist_id"
            artist_select = "ar.artist_name AS artist_name"
            artist_group.append("ar.artist_name")

    like_term, exact_term, prefix_term = _search_terms(query)
    group_by = ", ".join(["al.album_id", "al.album_name", *artist_group])
    album_play_cte = "\nUNION\n".join(album_play_sources)
    return conn.execute(
        f"""
        WITH album_play_events AS (
            {album_play_cte}
        )
        SELECT
            al.album_name AS name,
            al.album_id AS album_id,
            al.album_name AS album_name,
            {artist_id_select},
            {artist_select},
            COUNT(*) AS play_events,
            COALESCE(SUM(ape.ms_played), 0) AS total_ms
        FROM albums al
        JOIN album_play_events ape ON ape.album_id = al.album_id
        {artist_join}
        WHERE lower(al.album_name) LIKE ?
          AND al.album_name IS NOT NULL
          AND TRIM(al.album_name) != ''
        GROUP BY {group_by}
        ORDER BY
            CASE
                WHEN lower(al.album_name) = ? THEN 0
                WHEN lower(al.album_name) LIKE ? THEN 1
                ELSE 2
            END ASC,
            play_events DESC,
            total_ms DESC,
            name COLLATE NOCASE ASC
        LIMIT ?
        """,
        (like_term, exact_term, prefix_term, _bounded_limit(limit)),
    ).fetchall()


def _normalized_artist_query(conn: sqlite3.Connection, query: str, limit: int) -> list[sqlite3.Row]:
    if not (
        _has_columns(conn, "artists", {"artist_id", "artist_name"})
        and _has_columns(conn, "tracks", {"track_id"})
        and _has_columns(conn, "plays", {"track_id", "ms_played"})
    ):
        return []

    like_term, exact_term, prefix_term = _search_terms(query)
    return conn.execute(
        """
        SELECT
            ar.artist_name AS name,
            ar.artist_id AS artist_id,
            ar.artist_name AS artist_name,
            0 AS play_events,
            0 AS total_ms
        FROM artists ar
        WHERE lower(ar.artist_name) LIKE ?
          AND ar.artist_name IS NOT NULL
          AND TRIM(ar.artist_name) != ''
        ORDER BY
            CASE
                WHEN lower(ar.artist_name) = ? THEN 0
                WHEN lower(ar.artist_name) LIKE ? THEN 1
                ELSE 2
            END ASC,
            name COLLATE NOCASE ASC
        LIMIT ?
        """,
        (like_term, exact_term, prefix_term, _bounded_limit(limit)),
    ).fetchall()


def _simple_query(conn: sqlite3.Connection, entity_type: EntityType, query: str, limit: int):
    tracks_columns = _table_columns(conn, "tracks")
    name_column = _ENTITY_NAME_COLUMNS[entity_type]
    if name_column not in tracks_columns or "ms_played" not in tracks_columns:
        return []

    select_columns = [f"{name_column} AS name"]
    group_columns = [name_column]
    if entity_type == "track":
        track_id_column = "track_id" if "track_id" in tracks_columns else "id"
        if track_id_column in tracks_columns:
            select_columns.append(f"{track_id_column} AS track_id")
            group_columns.append(track_id_column)
        if "album_id" in tracks_columns:
            select_columns.append("album_id AS album_id")
            group_columns.append("album_id")
        for column in ("artist_name", "album_name"):
            if column in tracks_columns:
                select_columns.append(f"{column} AS {column}")
                group_columns.append(column)
    elif entity_type == "album":
        if "album_id" in tracks_columns:
            select_columns.append("album_id AS album_id")
            group_columns.append("album_id")
        select_columns.append("album_name AS album_name")
        if "artist_name" in tracks_columns:
            select_columns.append("artist_name AS artist_name")
            group_columns.append("artist_name")
    else:
        if "artist_id" in tracks_columns:
            select_columns.append("artist_id AS artist_id")
            group_columns.append("artist_id")
        select_columns.append("artist_name AS artist_name")

    like_term, exact_term, prefix_term = _search_terms(query)
    return conn.execute(
        f"""
        SELECT
            {", ".join(select_columns)},
            COUNT(*) AS play_events,
            COALESCE(SUM(ms_played), 0) AS total_ms
        FROM tracks
        WHERE lower({name_column}) LIKE ?
          AND {name_column} IS NOT NULL
          AND TRIM({name_column}) != ''
        GROUP BY {", ".join(group_columns)}
        ORDER BY
            CASE
                WHEN lower({name_column}) = ? THEN 0
                WHEN lower({name_column}) LIKE ? THEN 1
                ELSE 2
            END ASC,
            play_events DESC,
            total_ms DESC,
            name COLLATE NOCASE ASC
        LIMIT ?
        """,
        (like_term, exact_term, prefix_term, _bounded_limit(limit)),
    ).fetchall()


def _candidate_from_row(row: sqlite3.Row, entity_type: EntityType) -> dict[str, Any]:
    values = _row_dict(row)
    candidate: dict[str, Any] = {
        "name": values["name"],
        "entity_type": entity_type,
        "play_events": int(values.get("play_events") or 0),
        "total_ms": int(values.get("total_ms") or 0),
    }
    for key in (
        "track_id",
        "album_id",
        "artist_id",
        "track_name",
        "album_name",
        "artist_name",
    ):
        value = values.get(key)
        if value is not None:
            candidate[key] = value
    return candidate


def resolve_entities(
    conn: sqlite3.Connection,
    *,
    query: str,
    entity_type: EntityType,
    limit: int = 5,
) -> dict[str, Any]:
    """Resolve a user-provided name against local listening-history entities."""
    if entity_type not in _ENTITY_NAME_COLUMNS:
        raise ValueError(f"Unsupported entity_type: {entity_type}")

    if not query.strip():
        return _empty_result(query, entity_type)

    rows = _normalized_query(conn, entity_type, query, limit)
    if not rows:
        rows = _simple_query(conn, entity_type, query, limit)

    candidates = [_candidate_from_row(row, entity_type) for row in rows]
    if entity_type == "artist" and candidates:
        from backend.domains.metadata.artist_identity import get_artist_identity_map

        mapping = get_artist_identity_map(conn)
        if not mapping:
            return {
                "found": bool(candidates),
                "query": query,
                "entity_type": entity_type,
                "candidates": candidates,
            }
        canonical_candidates: dict[int, dict[str, Any]] = {}
        exact_canonical_ids: set[int] = set()
        for candidate in candidates:
            raw_id = int(candidate["artist_id"])
            resolved = mapping.get(raw_id)
            canonical_id = resolved.canonical_artist_id if resolved else raw_id
            display_name = resolved.display_name if resolved else str(candidate["artist_name"])
            if str(candidate["artist_name"]).casefold() == query.strip().casefold():
                exact_canonical_ids.add(canonical_id)
            item = canonical_candidates.setdefault(
                canonical_id,
                {
                    **candidate,
                    "name": display_name,
                    "artist_name": display_name,
                    "artist_id": canonical_id,
                    "raw_artist_ids": [],
                },
            )
            item["raw_artist_ids"].append(raw_id)
        from backend.domains.metadata.track_credits import get_effective_track_credits

        credit_tracks: dict[int, set[int]] = {}
        for credit in get_effective_track_credits(conn):
            credit_tracks.setdefault(int(credit["artist_id"]), set()).add(int(credit["track_id"]))
        play_metrics = {
            int(row["track_id"]): (int(row["play_events"]), int(row["total_ms"]))
            for row in conn.execute(
                """SELECT track_id, COUNT(*) AS play_events,
                          COALESCE(SUM(ms_played), 0) AS total_ms
                   FROM plays WHERE track_id IS NOT NULL GROUP BY track_id"""
            ).fetchall()
        }
        for canonical_id, item in canonical_candidates.items():
            metrics = [
                play_metrics.get(track_id, (0, 0))
                for track_id in credit_tracks.get(canonical_id, set())
            ]
            item["play_events"] = sum(value[0] for value in metrics)
            item["total_ms"] = sum(value[1] for value in metrics)
            item.pop("raw_artist_ids", None)
        if exact_canonical_ids:
            canonical_candidates = {
                canonical_id: candidate
                for canonical_id, candidate in canonical_candidates.items()
                if canonical_id in exact_canonical_ids
            }
        candidates = list(canonical_candidates.values())[: _bounded_limit(limit)]
    return {
        "found": bool(candidates),
        "query": query,
        "entity_type": entity_type,
        "candidates": candidates,
    }
