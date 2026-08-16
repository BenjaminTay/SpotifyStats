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
from backend.domains.music_search.contracts import make_music_search_entity_key
from backend.domains.music_search.normalization import (
    SEARCH_NORMALIZATION_VERSION,
    normalize_search_text,
)

INDEX_SCHEMA_VERSION = "music_search_index_v2"


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
    digest = hashlib.sha256()
    digest.update(INDEX_SCHEMA_VERSION.encode())
    digest.update(SEARCH_NORMALIZATION_VERSION.encode())
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
    return {
        int(cast(Any, row.track_id)): (
            int(cast(Any, row.track_agg_id)),
            str(row.track_agg_name),
        )
        for row in frame.itertuples(index=False)
    }


def build_music_search_documents(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    identity_map = get_artist_identity_map(conn)
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
        raw_names_by_canonical[canonical_id].append(str(row["artist_name"]))

    credits_by_track: dict[int, list[tuple[int, str]]] = defaultdict(list)
    tracks_by_canonical_artist: dict[int, set[int]] = defaultdict(set)
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
        tracks_by_canonical_artist[canonical_id].add(track_id)

    play_count_by_track = {
        int(row["track_id"]): int(row["play_count"])
        for row in conn.execute(
            """SELECT track_id, COUNT(*) AS play_count FROM plays
               WHERE track_id IS NOT NULL GROUP BY track_id"""
        ).fetchall()
    }
    documents: list[dict[str, Any]] = []
    track_rows = conn.execute(
        """SELECT t.track_id, t.track_name, t.album_id, t.artist_id,
                  al.album_name
           FROM tracks t
           LEFT JOIN albums al ON al.album_id=t.album_id
           ORDER BY t.track_id"""
    ).fetchall()
    track_rows_by_id = {int(row["track_id"]): row for row in track_rows}
    for merge_level in (1, 2, 3):
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
            credits = credits_by_track.get(track_id)
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
            popularity = sum(
                play_count_by_track.get(int(member["track_id"]), 0) for member in member_rows
            )
            documents.append(
                _document(
                    entity_key=make_music_search_entity_key("track", entity_id),
                    kind="track",
                    label=label,
                    secondary=secondary,
                    aliases=aliases,
                    popularity=popularity,
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

    album_popularity = {
        int(row["album_id"]): int(row["play_count"])
        for row in conn.execute(
            """WITH sources AS (
                   SELECT play_id, source_album_id AS album_id FROM plays
                   WHERE source_album_id IS NOT NULL AND source_album_id != 0
                   UNION
                   SELECT p.play_id, t.album_id FROM plays p
                   JOIN tracks t ON t.track_id=p.track_id
                   WHERE t.album_id IS NOT NULL
               )
               SELECT album_id, COUNT(*) AS play_count FROM sources GROUP BY album_id"""
        ).fetchall()
    }
    for row in conn.execute(
        "SELECT album_id, album_name, artist_id FROM albums ORDER BY album_id"
    ).fetchall():
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
                popularity=album_popularity.get(album_id, 0),
                href=_album_href(album_name, artist_name),
                cover_url=_cover_url("albums", album_id),
                album_id=album_id,
                artist_id=artist_id,
                album_name=album_name,
                artist_name=artist_name,
            )
        )

    if _table_exists(conn, "album_projects"):
        project_popularity = {
            int(row["project_id"]): int(row["play_count"])
            for row in conn.execute(
                """SELECT apt.project_id, COUNT(DISTINCT p.play_id) AS play_count
                   FROM album_project_tracks apt
                   JOIN plays p ON p.track_id=apt.track_id
                   GROUP BY apt.project_id"""
            ).fetchall()
        }
        for row in conn.execute(
            """SELECT ap.project_id, ap.canonical_name, ap.artist_id,
                      ap.primary_album_id, ar.artist_name
               FROM album_projects ap
               LEFT JOIN artists ar ON ar.artist_id=ap.artist_id
               WHERE ap.include_in_charts=1
               ORDER BY ap.project_id"""
        ).fetchall():
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
                    popularity=project_popularity.get(project_id, 0),
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
        popularity = sum(
            play_count_by_track.get(track_id, 0)
            for track_id in tracks_by_canonical_artist.get(canonical_id, set())
        )
        documents.append(
            _document(
                entity_key=make_music_search_entity_key("artist", canonical_id),
                kind="artist",
                label=display_name,
                secondary=None,
                aliases=[alias for alias in aliases if alias != display_name],
                popularity=popularity,
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
    conn.execute(
        """UPDATE music_search_index_state
           SET status='building', last_error=NULL, updated_at=datetime('now')
           WHERE state_id=1"""
    )
    conn.commit()
    try:
        documents = build_music_search_documents(conn)
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
        previous = conn.execute(
            "SELECT active_generation_id FROM music_search_index_state WHERE state_id=1"
        ).fetchone()
        previous_id = str(previous[0]) if previous and previous[0] else None
        with conn:
            placeholders = ",".join("?" for _ in columns)
            conn.executemany(
                f"INSERT INTO music_search_documents({','.join(columns)}) VALUES ({placeholders})",
                rows,
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
                       document_count=?, built_at=datetime('now'), last_error=NULL,
                       updated_at=datetime('now') WHERE state_id=1""",
                (
                    generation_id,
                    previous_id,
                    runtime.status,
                    runtime.tokenizer,
                    SEARCH_NORMALIZATION_VERSION,
                    source_revision,
                    len(documents),
                ),
            )
            keep = [generation_id, *([previous_id] if previous_id else [])]
            placeholders = ",".join("?" for _ in keep)
            conn.execute(
                f"DELETE FROM music_search_documents WHERE generation_id NOT IN ({placeholders})",
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
            "tokenizer": runtime.tokenizer,
        }
    except Exception as exc:
        conn.execute(
            """UPDATE music_search_index_state
               SET status='failed', last_error=?, updated_at=datetime('now') WHERE state_id=1""",
            (type(exc).__name__,),
        )
        conn.commit()
        raise


def get_music_search_index_state(conn: sqlite3.Connection) -> dict[str, Any]:
    if not _table_exists(conn, "music_search_index_state"):
        return {"status": "missing", "active_generation_id": None}
    row = conn.execute("SELECT * FROM music_search_index_state WHERE state_id=1").fetchone()
    return dict(row) if row else {"status": "missing", "active_generation_id": None}
