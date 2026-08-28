"""Persistent, generation-based music-search document index."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, cast
from urllib.parse import quote

from backend.domains.metadata.artist_identity import (
    get_artist_identity_map,
    get_identity_revision,
)
from backend.domains.metadata.track_credits import (
    get_effective_track_credits,
    get_track_credit_revision,
)
from backend.domains.metadata.track_identity import (
    TRACK_IDENTITY_POLICY_VERSION,
    get_track_identity_revision,
)
from backend.domains.music_search.contracts import make_music_search_entity_key
from backend.domains.music_search.normalization import (
    SEARCH_NORMALIZATION_VERSION,
    cjk_search_ngrams,
    normalize_search_text,
)
from backend.domains.music_search.revisions import get_music_search_revision_state

INDEX_SCHEMA_VERSION = "music_search_candidate_index_v4_l1"


@dataclass(frozen=True)
class SearchIndexRuntime:
    fts5: bool
    trigram: bool
    status: str
    tokenizer: str


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name=?",
            (table_name,),
        ).fetchone()
        is not None
    )


def inspect_search_index_runtime(conn: sqlite3.Connection) -> SearchIndexRuntime:
    fts5 = False
    trigram = False
    probe = sqlite3.connect(":memory:")
    try:
        try:
            probe.execute("CREATE VIRTUAL TABLE fts_probe USING fts5(body)")
            fts5 = True
            probe.execute("CREATE VIRTUAL TABLE trigram_probe USING fts5(body, tokenize='trigram')")
            trigram = True
        except sqlite3.Error:
            pass
    finally:
        probe.close()
    table_ready = _table_exists(conn, "music_search_documents_fts")
    ready = fts5 and trigram and table_ready
    return SearchIndexRuntime(
        fts5=fts5,
        trigram=trigram,
        status="ready" if ready else "degraded",
        tokenizer="fts5_trigram" if ready else "bounded_like_fallback",
    )


def music_search_source_revision(conn: sqlite3.Connection) -> str:
    """Return the O(1) candidate source revision, independent of plays."""
    revisions = get_music_search_revision_state(conn)
    payload = {
        "candidate_revision": revisions.candidate_revision,
        "identity_revision": get_identity_revision(conn),
        "track_credit_revision": get_track_credit_revision(conn),
        "track_identity_revision": get_track_identity_revision(conn),
        "track_identity_policy": TRACK_IDENTITY_POLICY_VERSION,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def legacy_v2_music_search_source_revision(
    conn: sqlite3.Connection,
    *,
    normalization_version: str,
) -> str:
    """Audit the pre-split candidate source during one-time v2 adoption."""
    digest = hashlib.sha256()
    digest.update(b"music_search_index_v2")
    digest.update(normalization_version.encode())
    for table, id_column in (
        ("plays", "play_id"),
        ("tracks", "track_id"),
        ("albums", "album_id"),
        ("artists", "artist_id"),
        ("album_projects", "project_id"),
        ("album_project_albums", "project_id"),
        ("album_project_tracks", "project_id"),
    ):
        if not _table_exists(conn, table):
            digest.update(f"{table}:missing\n".encode())
            continue
        row = conn.execute(
            f'SELECT COUNT(*), COALESCE(MAX("{id_column}"), 0) FROM "{table}"'
        ).fetchone()
        digest.update(f"{table}:{int(row[0])}:{int(row[1])}\n".encode())
    digest.update(f"identity:{get_identity_revision(conn)}\n".encode())
    digest.update(f"credits:{get_track_credit_revision(conn)}\n".encode())
    for table in ("track_groups", "track_group_members"):
        if not _table_exists(conn, table):
            digest.update(f"{table}:missing\n".encode())
            continue
        columns = [str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')]
        quoted = ", ".join(f'"{column}"' for column in columns)
        digest.update(f"{table}:".encode())
        for row in conn.execute(f'SELECT {quoted} FROM "{table}" ORDER BY {quoted}'):
            digest.update(
                json.dumps(
                    list(row),
                    ensure_ascii=True,
                    separators=(",", ":"),
                    default=str,
                ).encode()
            )
            digest.update(b"\n")
    return digest.hexdigest()


def candidate_index_version(*, source_revision: str, tokenizer: str) -> str:
    payload = {
        "builder": INDEX_SCHEMA_VERSION,
        "normalization": SEARCH_NORMALIZATION_VERSION,
        "tokenizer": tokenizer,
        "source_revision": source_revision,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def expected_candidate_index_version(conn: sqlite3.Connection) -> str:
    runtime = inspect_search_index_runtime(conn)
    return candidate_index_version(
        source_revision=music_search_source_revision(conn),
        tokenizer=runtime.tokenizer,
    )


def get_music_search_candidate_maintenance_state(
    conn: sqlite3.Connection,
) -> dict[str, Any]:
    """Return shadow-build state without weakening pre-migration readers."""

    if not _table_exists(conn, "music_search_candidate_maintenance_state"):
        serving = get_music_search_index_state(conn)
        legacy_status = str(serving.get("status") or "missing")
        if legacy_status in {"building", "failed"}:
            maintenance_status = legacy_status
        elif serving.get("active_generation_id"):
            maintenance_status = "ready"
        else:
            maintenance_status = "missing"
        return {
            "maintenance_status": maintenance_status,
            "target_source_revision": serving.get("source_revision"),
            "target_candidate_index_version": serving.get("candidate_index_version"),
            "building_generation_id": None,
            "job_id": None,
            "last_error": serving.get("last_error"),
        }
    row = conn.execute(
        """SELECT * FROM music_search_candidate_maintenance_state
           WHERE state_id=1"""
    ).fetchone()
    return dict(row) if row else {"maintenance_status": "missing"}


def mark_music_search_candidate_maintenance_pending(
    conn: sqlite3.Connection,
    *,
    target_source_revision: str | None = None,
    target_candidate_index_version: str | None = None,
) -> None:
    """Record a new build target while leaving the serving proof untouched."""

    if not _table_exists(conn, "music_search_candidate_maintenance_state"):
        return
    target_source_revision = target_source_revision or music_search_source_revision(conn)
    target_candidate_index_version = (
        target_candidate_index_version or expected_candidate_index_version(conn)
    )
    conn.execute(
        """UPDATE music_search_candidate_maintenance_state
              SET target_source_revision=?, target_candidate_index_version=?,
                  maintenance_status='pending', building_generation_id=NULL,
                  job_id=NULL, started_at=NULL, finished_at=NULL, last_error=NULL,
                  updated_at=datetime('now')
            WHERE state_id=1""",
        (target_source_revision, target_candidate_index_version),
    )


def _document_content_digest(documents: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for document in sorted(
        documents,
        key=lambda item: (str(item["entity_key"]), int(item["merge_level"])),
    ):
        digest.update(
            json.dumps(document, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
        )
        digest.update(b"\n")
    return digest.hexdigest()


def _cover_url(kind: str, entity_id: int | None) -> str | None:
    return f"/covers/{kind}/{entity_id}.jpg" if entity_id else None


def _album_href(album_name: str, artist_name: str | None) -> str:
    href = f"/music/albums/{quote(album_name, safe='')}"
    return f"{href}?artist={quote(artist_name, safe='')}" if artist_name else href


def _document(
    *,
    entity_key: str,
    kind: str,
    label: str,
    secondary: str | None,
    aliases: list[str] | None,
    popularity: int,
    href: str,
    cover_url: str | None,
    track_id: int | None = None,
    album_id: int | None = None,
    album_project_id: int | None = None,
    artist_id: int | None = None,
    album_name: str | None = None,
    artist_name: str | None = None,
    merge_level: int = 0,
) -> dict[str, Any]:
    alias_text = " · ".join(dict.fromkeys(aliases or []))
    normalized_label = normalize_search_text(label)
    normalized_secondary = normalize_search_text(secondary or "")
    normalized_alias = normalize_search_text(alias_text)
    return {
        "entity_key": entity_key,
        "kind": kind,
        "merge_level": merge_level,
        "label": label,
        "normalized_label": normalized_label,
        "secondary": secondary,
        "normalized_secondary": normalized_secondary,
        "alias_text": alias_text,
        "normalized_alias": normalized_alias,
        "search_text": " ".join(
            value for value in (normalized_label, normalized_secondary, normalized_alias) if value
        ),
        "popularity_tiebreaker": max(0, int(popularity)),
        "href": href,
        "cover_url": cover_url,
        "track_id": track_id,
        "album_id": album_id,
        "album_project_id": album_project_id,
        "artist_id": artist_id,
        "album_name": album_name,
        "artist_name": artist_name,
    }


def _track_group_map(
    conn: sqlite3.Connection,
    merge_level: int,
) -> dict[int, tuple[int, str]]:
    if merge_level <= 1 or not all(
        _table_exists(conn, table) for table in ("track_groups", "track_group_members")
    ):
        return {}
    from backend.domains.playback.track_groups import load_track_group_keys

    frame = load_track_group_keys(conn, merge_level)
    if "l1_id" in frame.columns and "track_agg_l1_id" in frame.columns:
        return {
            int(cast(Any, row.l1_id)): (
                int(cast(Any, row.track_agg_l1_id)),
                str(row.track_agg_name),
            )
            for row in frame.itertuples(index=False)
        }
    return {
        int(cast(Any, row.track_id)): (
            int(cast(Any, row.track_agg_id)),
            str(row.track_agg_name),
        )
        for row in frame.itertuples(index=False)
    }


def _active_music_entity_ids(
    conn: sqlite3.Connection,
) -> tuple[set[int], set[int], set[int]]:
    """Return the local entity closure reachable from the active play facts.

    Import reconciliation intentionally preserves durable metadata and manual
    governance rows.  Candidate search, however, represents the active
    playback dataset and must not resurrect dimensions that are only retained
    for audit/history after their final play was removed.
    """
    if _table_exists(conn, "track_l1_external_ids"):
        track_ids = {
            int(row[0])
            for row in conn.execute(
                """SELECT DISTINCT COALESCE(spotify_li.l1_id, local_li.l1_id)
                     FROM plays p
                     LEFT JOIN tracks t ON t.track_id=p.track_id
                     LEFT JOIN track_l1_external_ids spotify_external
                       ON spotify_external.provider='spotify'
                      AND spotify_external.external_track_id=COALESCE(
                            NULLIF(p.spotify_track_id_at_play, ''),
                            NULLIF(t.spotify_track_id, '')
                          )
                     LEFT JOIN track_l1_identities spotify_li
                       ON spotify_li.l1_id=spotify_external.l1_id
                      AND spotify_li.identity_status!='superseded'
                     LEFT JOIN track_l1_identities local_li
                       ON local_li.fallback_track_id=p.track_id
                      AND local_li.identity_status!='superseded'
                    WHERE COALESCE(spotify_li.l1_id, local_li.l1_id) IS NOT NULL"""
            ).fetchall()
        }
    else:
        track_ids = {
            int(row[0])
            for row in conn.execute(
                "SELECT DISTINCT track_id FROM plays WHERE track_id IS NOT NULL"
            ).fetchall()
        }
    album_ids = {
        int(row[0])
        for row in conn.execute(
            """SELECT source_album_id AS album_id
               FROM plays WHERE source_album_id IS NOT NULL
               UNION
               SELECT t.album_id
               FROM plays p JOIN tracks t ON t.track_id=p.track_id
               WHERE t.album_id IS NOT NULL
                 AND (
                   NOT EXISTS (
                     SELECT 1 FROM plays current
                     WHERE current.track_id=t.track_id
                       AND current.source_album_id IS NOT NULL
                   )
                   OR EXISTS (
                     SELECT 1 FROM plays current
                     WHERE current.track_id=t.track_id
                       AND current.source_album_id=t.album_id
                   )
                 )"""
        ).fetchall()
    }
    if _table_exists(conn, "track_albums"):
        album_ids.update(
            int(row[0])
            for row in conn.execute(
                """SELECT DISTINCT ta.album_id
                   FROM track_albums ta
                   WHERE EXISTS (SELECT 1 FROM plays p WHERE p.track_id=ta.track_id)
                     AND (
                       NOT EXISTS (
                         SELECT 1 FROM plays p
                         WHERE p.track_id=ta.track_id AND p.source_album_id IS NOT NULL
                       )
                       OR EXISTS (
                         SELECT 1 FROM plays p
                         WHERE p.track_id=ta.track_id AND p.source_album_id=ta.album_id
                       )
                     )"""
            ).fetchall()
        )

    artist_ids = {
        int(row[0])
        for row in conn.execute(
            """SELECT t.artist_id
               FROM plays p JOIN tracks t ON t.track_id=p.track_id
               UNION
               SELECT al.artist_id
               FROM albums al
               WHERE al.album_id IN (
                   SELECT source_album_id FROM plays WHERE source_album_id IS NOT NULL
                   UNION
                   SELECT t.album_id
                   FROM plays p JOIN tracks t ON t.track_id=p.track_id
                   WHERE t.album_id IS NOT NULL
                     AND (
                       NOT EXISTS (
                         SELECT 1 FROM plays current
                         WHERE current.track_id=t.track_id
                           AND current.source_album_id IS NOT NULL
                       )
                       OR EXISTS (
                         SELECT 1 FROM plays current
                         WHERE current.track_id=t.track_id
                           AND current.source_album_id=t.album_id
                       )
                     )
               )"""
        ).fetchall()
    }
    if _table_exists(conn, "track_artists"):
        artist_ids.update(
            int(row[0])
            for row in conn.execute(
                """SELECT DISTINCT ta.artist_id
                   FROM track_artists ta
                   JOIN plays p ON p.track_id=ta.track_id"""
            ).fetchall()
        )
    return track_ids, album_ids, artist_ids


def _active_album_project_ids(
    conn: sqlite3.Connection,
    *,
    track_ids: set[int],
    album_ids: set[int],
) -> set[int]:
    project_ids: set[int] = set()
    if track_ids and _table_exists(conn, "album_project_tracks"):
        if _table_exists(conn, "track_l1_source_links"):
            placeholders = ",".join("?" for _ in track_ids)
            project_ids.update(
                int(row[0])
                for row in conn.execute(
                    f"""SELECT DISTINCT apt.project_id
                           FROM album_project_tracks apt
                           JOIN track_l1_source_links links ON links.track_id=apt.track_id
                          WHERE links.l1_id IN ({placeholders})""",
                    tuple(sorted(track_ids)),
                ).fetchall()
            )
        else:
            project_ids.update(
                int(row[0])
                for row in conn.execute(
                    """SELECT DISTINCT apt.project_id
                       FROM album_project_tracks apt
                       JOIN plays p ON p.track_id=apt.track_id"""
                ).fetchall()
            )
    if album_ids and _table_exists(conn, "album_project_albums"):
        project_ids.update(
            int(row[0])
            for row in conn.execute(
                """SELECT DISTINCT apa.project_id
                   FROM album_project_albums apa
                   WHERE apa.album_id IN (
                       SELECT source_album_id FROM plays WHERE source_album_id IS NOT NULL
                       UNION
                       SELECT t.album_id
                       FROM plays p JOIN tracks t ON t.track_id=p.track_id
                       WHERE t.album_id IS NOT NULL
                         AND (
                           NOT EXISTS (
                             SELECT 1 FROM plays current
                             WHERE current.track_id=t.track_id
                               AND current.source_album_id IS NOT NULL
                           )
                           OR EXISTS (
                             SELECT 1 FROM plays current
                             WHERE current.track_id=t.track_id
                               AND current.source_album_id=t.album_id
                           )
                         )
                       UNION
                       SELECT ta.album_id
                       FROM track_albums ta
                       WHERE EXISTS (SELECT 1 FROM plays p WHERE p.track_id=ta.track_id)
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
                   )"""
            ).fetchall()
        )
    return project_ids


def build_music_search_documents(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    identity_map = get_artist_identity_map(conn)
    active_track_ids, active_album_ids, active_artist_ids = _active_music_entity_ids(conn)
    active_project_ids = _active_album_project_ids(
        conn,
        track_ids=active_track_ids,
        album_ids=active_album_ids,
    )
    if active_project_ids:
        active_artist_ids.update(
            int(row["artist_id"])
            for row in conn.execute(
                "SELECT project_id, artist_id FROM album_projects WHERE artist_id IS NOT NULL"
            ).fetchall()
            if int(row["project_id"]) in active_project_ids
        )
    artist_rows = {
        int(row["artist_id"]): dict(row)
        for row in conn.execute(
            "SELECT artist_id, artist_name FROM artists ORDER BY artist_id"
        ).fetchall()
    }
    raw_names_by_canonical: dict[int, list[str]] = defaultdict(list)
    for raw_id, row in artist_rows.items():
        resolution = identity_map.get(raw_id)
        canonical_id = resolution.canonical_artist_id if resolution else raw_id
        if raw_id in active_artist_ids or canonical_id in active_artist_ids:
            raw_names_by_canonical[canonical_id].append(str(row["artist_name"]))

    credits_by_track: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for credit in get_effective_track_credits(conn):
        track_id = int(credit["track_id"])
        raw_artist_id = int(credit["artist_id"])
        resolution = identity_map.get(raw_artist_id)
        canonical_id = resolution.canonical_artist_id if resolution else raw_artist_id
        display_name = (
            resolution.display_name
            if resolution
            else str(artist_rows.get(raw_artist_id, {}).get("artist_name") or raw_artist_id)
        )
        if all(existing_id != canonical_id for existing_id, _ in credits_by_track[track_id]):
            item = (canonical_id, display_name)
            if credit.get("role") == "primary":
                credits_by_track[track_id].insert(0, item)
            else:
                credits_by_track[track_id].append(item)

    documents: list[dict[str, Any]] = []
    if _table_exists(conn, "track_l1_external_ids"):
        track_rows = conn.execute(
            """SELECT li.l1_id AS track_id,
                      li.representative_track_id,
                      t.track_name, t.album_id, t.artist_id, al.album_name
                 FROM track_l1_identities li
                 JOIN tracks t ON t.track_id=li.representative_track_id
                 LEFT JOIN albums al ON al.album_id=t.album_id
                WHERE li.identity_status!='superseded' AND (
                    EXISTS (
                        SELECT 1 FROM track_l1_source_links links
                        WHERE links.l1_id=li.l1_id
                          AND links.evidence_type='play_at_time'
                    )
                ) OR (
                    li.identity_status!='superseded' AND li.fallback_track_id IS NOT NULL
                    AND EXISTS (
                        SELECT 1 FROM plays p
                        WHERE p.track_id=li.fallback_track_id
                    )
                )
                ORDER BY li.l1_id"""
        ).fetchall()
    else:
        track_rows = conn.execute(
            """WITH active_tracks AS (
               SELECT t.track_id, t.track_name, t.artist_id,
                      CASE
                        WHEN EXISTS (
                          SELECT 1 FROM plays p
                          WHERE p.track_id=t.track_id AND p.source_album_id=t.album_id
                        ) THEN t.album_id
                        ELSE COALESCE(
                          (
                            SELECT p.source_album_id
                            FROM plays p
                            WHERE p.track_id=t.track_id AND p.source_album_id IS NOT NULL
                            GROUP BY p.source_album_id
                            ORDER BY COUNT(*) DESC, p.source_album_id
                            LIMIT 1
                          ),
                          t.album_id
                        )
                      END AS album_id
               FROM tracks t
               WHERE EXISTS (SELECT 1 FROM plays p WHERE p.track_id=t.track_id)
           )
           SELECT t.track_id, t.track_name, t.album_id, t.artist_id, al.album_name
           FROM active_tracks t
           LEFT JOIN albums al ON al.album_id=t.album_id
           ORDER BY t.track_id"""
        ).fetchall()
    track_rows_by_id = {int(row["track_id"]): row for row in track_rows}
    for merge_level in (2, 3):
        group_map = _track_group_map(conn, merge_level)
        members_by_entity: dict[int, list[sqlite3.Row]] = defaultdict(list)
        group_names: dict[int, str] = {}
        for row in track_rows:
            track_id = int(row["track_id"])
            entity_id, group_name = group_map.get(
                track_id,
                (track_id, str(row["track_name"])),
            )
            members_by_entity[entity_id].append(row)
            group_names[entity_id] = group_name
        for entity_id, member_rows in sorted(members_by_entity.items()):
            row = track_rows_by_id.get(entity_id, member_rows[0])
            track_id = int(row["track_id"])
            credit_track_id = (
                int(row["representative_track_id"] or track_id)
                if "representative_track_id" in row.keys()
                else track_id
            )
            credits = credits_by_track.get(credit_track_id)
            if credits:
                credit_names = [name for _, name in credits]
                primary_artist_id = credits[0][0]
            else:
                raw_artist_id = int(row["artist_id"])
                resolution = identity_map.get(raw_artist_id)
                primary_artist_id = resolution.canonical_artist_id if resolution else raw_artist_id
                fallback_artist = artist_rows.get(raw_artist_id, {}).get("artist_name")
                display_artist = resolution.display_name if resolution else fallback_artist
                credit_names = [str(display_artist)] if display_artist else []
            album_name = str(row["album_name"]) if row["album_name"] else None
            secondary = " · ".join([*credit_names, *([album_name] if album_name else [])])
            label = group_names[entity_id]
            aliases = [
                str(member["track_name"])
                for member in member_rows
                if str(member["track_name"]) != label
            ]
            documents.append(
                _document(
                    entity_key=make_music_search_entity_key("track", entity_id),
                    kind="track",
                    label=label,
                    secondary=secondary,
                    aliases=aliases,
                    popularity=0,
                    href=f"/music/tracks/{entity_id}",
                    cover_url=_cover_url(
                        "albums", int(row["album_id"]) if row["album_id"] else None
                    ),
                    track_id=entity_id,
                    album_id=int(row["album_id"]) if row["album_id"] else None,
                    artist_id=primary_artist_id,
                    album_name=album_name,
                    artist_name=credit_names[0] if credit_names else None,
                    merge_level=merge_level,
                )
            )

    album_rows = [
        row
        for row in conn.execute(
            "SELECT album_id, album_name, artist_id FROM albums ORDER BY album_id"
        ).fetchall()
        if int(row["album_id"]) in active_album_ids
    ]
    for row in album_rows:
        album_id = int(row["album_id"])
        raw_artist_id = int(row["artist_id"])
        resolution = identity_map.get(raw_artist_id)
        artist_id = resolution.canonical_artist_id if resolution else raw_artist_id
        fallback_artist = artist_rows.get(raw_artist_id, {}).get("artist_name")
        artist_name = (
            resolution.display_name
            if resolution
            else str(fallback_artist)
            if fallback_artist
            else None
        )
        album_name = str(row["album_name"])
        documents.append(
            _document(
                entity_key=make_music_search_entity_key("album", album_id),
                kind="album",
                label=album_name,
                secondary=artist_name,
                aliases=None,
                popularity=0,
                href=_album_href(album_name, artist_name),
                cover_url=_cover_url("albums", album_id),
                album_id=album_id,
                artist_id=artist_id,
                album_name=album_name,
                artist_name=artist_name,
            )
        )

    if _table_exists(conn, "album_projects") and active_project_ids:
        project_rows = conn.execute(
            """SELECT ap.project_id, ap.canonical_name, ap.artist_id,
                      ap.primary_album_id, ar.artist_name
               FROM album_projects ap
               LEFT JOIN artists ar ON ar.artist_id=ap.artist_id
               WHERE ap.include_in_charts=1
               ORDER BY ap.project_id"""
        ).fetchall()
        for row in project_rows:
            if int(row["project_id"]) not in active_project_ids:
                continue
            project_id = int(row["project_id"])
            raw_artist_id = int(row["artist_id"]) if row["artist_id"] else None
            resolution = identity_map.get(raw_artist_id) if raw_artist_id else None
            artist_id = resolution.canonical_artist_id if resolution else raw_artist_id
            artist_name = (
                resolution.display_name
                if resolution
                else (str(row["artist_name"]) if row["artist_name"] else None)
            )
            album_name = str(row["canonical_name"])
            documents.append(
                _document(
                    entity_key=make_music_search_entity_key("album_project", project_id),
                    kind="album_project",
                    label=album_name,
                    secondary=artist_name,
                    aliases=None,
                    popularity=0,
                    href=_album_href(album_name, artist_name),
                    cover_url=_cover_url(
                        "albums",
                        int(row["primary_album_id"]) if row["primary_album_id"] else None,
                    ),
                    album_id=(int(row["primary_album_id"]) if row["primary_album_id"] else None),
                    album_project_id=project_id,
                    artist_id=artist_id,
                    album_name=album_name,
                    artist_name=artist_name,
                )
            )

    for canonical_id, aliases in sorted(raw_names_by_canonical.items()):
        resolution = identity_map.get(canonical_id)
        display_name = (
            resolution.display_name
            if resolution
            else str(artist_rows.get(canonical_id, {}).get("artist_name") or aliases[0])
        )
        documents.append(
            _document(
                entity_key=make_music_search_entity_key("artist", canonical_id),
                kind="artist",
                label=display_name,
                secondary=None,
                aliases=[alias for alias in aliases if alias != display_name],
                popularity=0,
                href=f"/music/artists/{quote(display_name, safe='')}",
                cover_url=_cover_url("artists", canonical_id),
                artist_id=canonical_id,
                artist_name=display_name,
            )
        )
    return documents


def rebuild_music_search_index(conn: sqlite3.Connection) -> dict[str, Any]:
    runtime = inspect_search_index_runtime(conn)
    generation_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:12]
    )
    source_revision = music_search_source_revision(conn)
    index_version = candidate_index_version(
        source_revision=source_revision,
        tokenizer=runtime.tokenizer,
    )
    maintenance_table_ready = _table_exists(conn, "music_search_candidate_maintenance_state")
    if maintenance_table_ready:
        conn.execute(
            """UPDATE music_search_candidate_maintenance_state
                  SET target_source_revision=?, target_candidate_index_version=?,
                      maintenance_status='building', building_generation_id=?,
                      started_at=datetime('now'), finished_at=NULL, last_error=NULL,
                      updated_at=datetime('now')
                WHERE state_id=1""",
            (source_revision, index_version, generation_id),
        )
    else:
        conn.execute(
            """UPDATE music_search_index_state
                  SET status='building', last_error=NULL, updated_at=datetime('now')
                WHERE state_id=1"""
        )
    conn.commit()
    try:
        documents = build_music_search_documents(conn)
        content_digest = _document_content_digest(documents)
        entity_keys = [(str(item["entity_key"]), int(item["merge_level"])) for item in documents]
        if len(entity_keys) != len(set(entity_keys)):
            raise ValueError("duplicate music-search entity keys")
        if any(not item["normalized_label"] or not item["href"] for item in documents):
            raise ValueError("music-search documents contain empty labels or links")

        columns = (
            "generation_id",
            "entity_key",
            "kind",
            "merge_level",
            "label",
            "normalized_label",
            "secondary",
            "normalized_secondary",
            "alias_text",
            "normalized_alias",
            "search_text",
            "popularity_tiebreaker",
            "href",
            "cover_url",
            "track_id",
            "album_id",
            "album_project_id",
            "artist_id",
            "album_name",
            "artist_name",
        )
        rows = [(generation_id, *(item[column] for column in columns[1:])) for item in documents]
        ngram_rows = sorted(
            {
                (
                    generation_id,
                    str(item["entity_key"]),
                    int(item["merge_level"]),
                    field,
                    ngram,
                )
                for item in documents
                for field, value in (
                    ("label", item["normalized_label"]),
                    ("secondary", item["normalized_secondary"]),
                    ("alias", item["normalized_alias"]),
                )
                for ngram in cjk_search_ngrams(str(value))
            }
        )
        with conn:
            # Acquire the publication lock before the revision fence.  The
            # expensive document build above remains outside the write lock.
            conn.execute("BEGIN IMMEDIATE")
            if music_search_source_revision(conn) != source_revision:
                raise RuntimeError("music-search candidate target changed during shadow build")
            previous = conn.execute(
                "SELECT active_generation_id FROM music_search_index_state WHERE state_id=1"
            ).fetchone()
            previous_id = str(previous[0]) if previous and previous[0] else None
            placeholders = ",".join("?" for _ in columns)
            conn.executemany(
                f"INSERT INTO music_search_documents({','.join(columns)}) VALUES ({placeholders})",
                rows,
            )
            conn.executemany(
                """INSERT INTO music_search_document_ngrams(
                       generation_id, entity_key, merge_level, field, ngram
                   ) VALUES (?, ?, ?, ?, ?)""",
                ngram_rows,
            )
            if runtime.status == "ready":
                conn.executemany(
                    """INSERT INTO music_search_documents_fts(
                           generation_id, entity_key, merge_level, search_text
                       ) VALUES (?, ?, ?, ?)""",
                    [
                        (
                            generation_id,
                            item["entity_key"],
                            item["merge_level"],
                            item["search_text"],
                        )
                        for item in documents
                    ],
                )
            conn.execute(
                """UPDATE music_search_index_state
                   SET active_generation_id=?, previous_generation_id=?, status=?,
                       tokenizer=?, normalization_version=?, source_revision=?,
                       candidate_index_version=?, content_digest=?,
                       document_count=?, built_at=datetime('now'), last_error=NULL,
                       updated_at=datetime('now') WHERE state_id=1""",
                (
                    generation_id,
                    previous_id,
                    runtime.status,
                    runtime.tokenizer,
                    SEARCH_NORMALIZATION_VERSION,
                    source_revision,
                    index_version,
                    content_digest,
                    len(documents),
                ),
            )
            if maintenance_table_ready:
                conn.execute(
                    """UPDATE music_search_candidate_maintenance_state
                          SET target_source_revision=?, target_candidate_index_version=?,
                              maintenance_status='ready', building_generation_id=NULL,
                              finished_at=datetime('now'), last_error=NULL,
                              updated_at=datetime('now')
                        WHERE state_id=1""",
                    (source_revision, index_version),
                )
            from backend.domains.music_search.deny_overlay import (
                clear_confirmed_music_search_denials,
            )

            clear_confirmed_music_search_denials(
                conn,
                generation_id=generation_id,
                source_revision=source_revision,
            )
            keep = [generation_id, *([previous_id] if previous_id else [])]
            placeholders = ",".join("?" for _ in keep)
            conn.execute(
                f"DELETE FROM music_search_documents WHERE generation_id NOT IN ({placeholders})",
                keep,
            )
            conn.execute(
                f"""DELETE FROM music_search_document_ngrams
                    WHERE generation_id NOT IN ({placeholders})""",
                keep,
            )
            if runtime.status == "ready":
                conn.execute(
                    f"DELETE FROM music_search_documents_fts WHERE generation_id NOT IN ({placeholders})",
                    keep,
                )
        return {
            "status": runtime.status,
            "generation_id": generation_id,
            "previous_generation_id": previous_id,
            "document_count": len(documents),
            "source_revision": source_revision,
            "candidate_index_version": index_version,
            "content_digest": content_digest,
            "ngram_count": len(ngram_rows),
            "tokenizer": runtime.tokenizer,
        }
    except Exception as exc:
        if maintenance_table_ready:
            conn.execute(
                """UPDATE music_search_candidate_maintenance_state
                      SET maintenance_status='failed', building_generation_id=NULL,
                          finished_at=datetime('now'), last_error=?,
                          updated_at=datetime('now')
                    WHERE state_id=1 AND building_generation_id=?""",
                (type(exc).__name__, generation_id),
            )
        else:
            conn.execute(
                """UPDATE music_search_index_state
                      SET status='failed', last_error=?, updated_at=datetime('now')
                    WHERE state_id=1""",
                (type(exc).__name__,),
            )
        conn.commit()
        raise


def get_music_search_index_state(conn: sqlite3.Connection) -> dict[str, Any]:
    if not _table_exists(conn, "music_search_index_state"):
        return {"status": "missing", "active_generation_id": None}
    row = conn.execute("SELECT * FROM music_search_index_state WHERE state_id=1").fetchone()
    return dict(row) if row else {"status": "missing", "active_generation_id": None}
