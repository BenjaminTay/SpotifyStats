"""Identity-aware Spotify artist metadata resolution.

Spotify display names are mutable, while an artist identity can intentionally
use a historical or user-selected display name.  Provider metadata therefore
must be resolved through stable external ids (when available) or, as a final
fallback, through every active member of the identity group.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ArtistSpotifyMetaResolution:
    metadata: dict[str, Any] | None
    source: str | None
    conflict_external_ids: tuple[str, ...] = ()

    @property
    def has_conflict(self) -> bool:
        return bool(self.conflict_external_ids)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(conn, table):
        return set()
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _identity_members(conn: sqlite3.Connection, artist_name: str) -> list[sqlite3.Row]:
    """Return all active raw members for a raw, canonical, or display name."""
    if not _table_exists(conn, "artists"):
        return []
    spotify_id_column = (
        "a.spotify_artist_id" if "spotify_artist_id" in _columns(conn, "artists") else "NULL"
    )
    provider_artist_column = (
        "g.provider_metadata_artist_id"
        if "provider_metadata_artist_id" in _columns(conn, "artist_identity_groups")
        else "NULL"
    )
    group_id: int | None = None
    raw = conn.execute(
        "SELECT artist_id FROM artists WHERE lower(artist_name)=lower(?) ORDER BY artist_id LIMIT 1",
        (artist_name,),
    ).fetchone()
    if raw and _table_exists(conn, "artist_identity_members"):
        group = conn.execute(
            """SELECT m.identity_id
               FROM artist_identity_members m
               JOIN artist_identity_groups g ON g.identity_id=m.identity_id
               WHERE m.artist_id=? AND m.active=1 AND g.status='active'
               LIMIT 1""",
            (raw[0],),
        ).fetchone()
        group_id = int(group[0]) if group else None
    if group_id is None and _table_exists(conn, "artist_identity_groups"):
        group = conn.execute(
            """SELECT identity_id FROM artist_identity_groups
               WHERE status='active' AND lower(display_name)=lower(?)
               ORDER BY identity_id LIMIT 1""",
            (artist_name,),
        ).fetchone()
        group_id = int(group[0]) if group else None
    if group_id is not None:
        return conn.execute(
            f"""SELECT a.artist_id, a.artist_name, {spotify_id_column} AS spotify_artist_id,
                       {provider_artist_column} AS provider_metadata_artist_id
               FROM artist_identity_members m
               JOIN artist_identity_groups g ON g.identity_id=m.identity_id
               JOIN artists a ON a.artist_id=m.artist_id
               WHERE m.identity_id=? AND m.active=1
               ORDER BY a.artist_id""",
            (group_id,),
        ).fetchall()
    if raw:
        return conn.execute(
            f"""SELECT a.artist_id, a.artist_name,
                       {spotify_id_column} AS spotify_artist_id,
                       NULL AS provider_metadata_artist_id
                FROM artists a WHERE a.artist_id=?""",
            (raw[0],),
        ).fetchall()
    return []


def _metadata_by_ids(
    conn: sqlite3.Connection, external_ids: set[str], source: str
) -> ArtistSpotifyMetaResolution:
    ids = sorted(value for value in external_ids if value)
    if len(ids) > 1:
        return ArtistSpotifyMetaResolution(None, source, tuple(ids))
    if not ids:
        return ArtistSpotifyMetaResolution(None, None)
    row = conn.execute(
        """SELECT spotify_artist_id, artist_name, popularity, followers, genres, image_url
           FROM spotify_artist_meta WHERE spotify_artist_id=?""",
        (ids[0],),
    ).fetchone()
    return (
        ArtistSpotifyMetaResolution(_row_to_metadata(row), source)
        if row
        else ArtistSpotifyMetaResolution(None, source)
    )


def _row_to_metadata(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    genres: list[str] = []
    if row["genres"]:
        try:
            value = json.loads(row["genres"])
            genres = [str(item) for item in value] if isinstance(value, list) else []
        except (TypeError, ValueError):
            genres = []
    return {
        "spotify_artist_id": str(row["spotify_artist_id"]),
        "artist_name": str(row["artist_name"]),
        "popularity": row["popularity"],
        "followers": row["followers"],
        "genres": genres,
        "image_url": row["image_url"],
    }


def resolve_artist_spotify_meta(
    conn: sqlite3.Connection, artist_name: str
) -> ArtistSpotifyMetaResolution:
    """Resolve one unambiguous Spotify metadata row for an artist identity.

    Priority is verified identity external ids, then ``artists.spotify_artist_id``,
    then exact metadata rows for every active identity member.  A priority tier
    with multiple distinct Spotify ids is a conflict and never falls through to
    an arbitrary row.
    """
    if not artist_name or not _table_exists(conn, "spotify_artist_meta"):
        return ArtistSpotifyMetaResolution(None, None)
    members = _identity_members(conn, artist_name)
    member_ids = [int(row["artist_id"]) for row in members]
    preferred_artist_id = (
        int(members[0]["provider_metadata_artist_id"])
        if members and members[0]["provider_metadata_artist_id"] is not None
        else None
    )

    if member_ids and _table_exists(conn, "artist_identity_external_ids"):
        placeholders = ",".join("?" for _ in member_ids)
        verified_rows = conn.execute(
            f"""SELECT artist_id, external_id FROM artist_identity_external_ids
                    WHERE provider='spotify' AND verified=1
                      AND artist_id IN ({placeholders})""",
            member_ids,
        ).fetchall()
        verified = {str(row["external_id"]) for row in verified_rows if row["external_id"]}
        if verified:
            if len(verified) > 1 and preferred_artist_id is not None:
                preferred = {
                    str(row["external_id"])
                    for row in verified_rows
                    if int(row["artist_id"]) == preferred_artist_id and row["external_id"]
                }
                if len(preferred) == 1:
                    selected = _metadata_by_ids(conn, preferred, "user_selected_provider_metadata")
                    return ArtistSpotifyMetaResolution(
                        selected.metadata, selected.source, tuple(sorted(verified))
                    )
            return _metadata_by_ids(conn, verified, "verified_external_id")

    if members and "spotify_artist_id" in _columns(conn, "artists"):
        artist_ids = {str(row["spotify_artist_id"]) for row in members if row["spotify_artist_id"]}
        if artist_ids:
            if len(artist_ids) > 1 and preferred_artist_id is not None:
                preferred = {
                    str(row["spotify_artist_id"])
                    for row in members
                    if int(row["artist_id"]) == preferred_artist_id and row["spotify_artist_id"]
                }
                if len(preferred) == 1:
                    selected = _metadata_by_ids(conn, preferred, "user_selected_provider_metadata")
                    return ArtistSpotifyMetaResolution(
                        selected.metadata, selected.source, tuple(sorted(artist_ids))
                    )
            return _metadata_by_ids(conn, artist_ids, "artists.spotify_artist_id")

    names = {str(row["artist_name"]) for row in members}
    if not names:
        names = {artist_name}
    placeholders = ",".join("?" for _ in names)
    rows = conn.execute(
        f"""SELECT spotify_artist_id, artist_name, popularity, followers, genres, image_url
            FROM spotify_artist_meta WHERE artist_name IN ({placeholders})""",
        sorted(names),
    ).fetchall()
    candidates = {str(row["spotify_artist_id"]): row for row in rows}
    if len(candidates) > 1:
        preferred_name = next(
            (
                str(row["artist_name"])
                for row in members
                if preferred_artist_id is not None and int(row["artist_id"]) == preferred_artist_id
            ),
            None,
        )
        preferred_rows = [
            row for row in rows if preferred_name and str(row["artist_name"]) == preferred_name
        ]
        if len(preferred_rows) == 1:
            return ArtistSpotifyMetaResolution(
                _row_to_metadata(preferred_rows[0]),
                "user_selected_provider_metadata",
                tuple(sorted(candidates)),
            )
        return ArtistSpotifyMetaResolution(None, "identity_member_name", tuple(sorted(candidates)))
    if candidates:
        return ArtistSpotifyMetaResolution(
            _row_to_metadata(next(iter(candidates.values()))), "identity_member_name"
        )
    return ArtistSpotifyMetaResolution(None, None)


def resolve_artist_image_url(conn: sqlite3.Connection, artist_name: str) -> str:
    resolved = resolve_artist_spotify_meta(conn, artist_name)
    if resolved.metadata and resolved.metadata.get("image_url"):
        return str(resolved.metadata["image_url"])
    return ""
