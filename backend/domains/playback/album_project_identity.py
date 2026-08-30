"""Stable album-project identity resolution for public detail consumers."""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import asdict, dataclass
from typing import Literal

AlbumProjectMatch = Literal["project_id", "canonical_name", "member_album_name"]


def normalize_album_project_lookup(value: str) -> str:
    """Normalize user-facing names without changing their stored presentation."""

    normalized = unicodedata.normalize("NFKC", str(value)).casefold().strip()
    return re.sub(r"\s+", " ", normalized)


@dataclass(frozen=True)
class AlbumProjectIdentity:
    project_id: int
    canonical_name: str
    artist_id: int | None
    artist_name: str | None
    primary_album_id: int | None
    scope: str
    matched_by: AlbumProjectMatch
    requested_album_name: str | None
    requested_project_id: int | None
    matched_album_id: int | None = None
    matched_album_name: str | None = None

    def payload(self) -> dict[str, object]:
        return asdict(self)


def _project_rows(conn: sqlite3.Connection, *, project_id: int | None = None) -> list[sqlite3.Row]:
    where = "WHERE ap.project_id=?" if project_id is not None else ""
    return conn.execute(
        """SELECT ap.project_id, ap.canonical_name, ap.artist_id,
                  ap.primary_album_id, ap.scope, ar.artist_name,
                  apa.album_id AS member_album_id,
                  member.album_name AS member_album_name
             FROM album_projects ap
             LEFT JOIN artists ar ON ar.artist_id=ap.artist_id
             LEFT JOIN album_project_albums apa ON apa.project_id=ap.project_id
             LEFT JOIN albums member ON member.album_id=apa.album_id
            """
        + where
        + " ORDER BY ap.project_id, apa.album_id",
        (int(project_id),) if project_id is not None else (),
    ).fetchall()


def resolve_album_project_identity(
    conn: sqlite3.Connection,
    *,
    album_name: str | None = None,
    artist_name: str | None = None,
    project_id: int | None = None,
    merge_level: int = 2,
) -> AlbumProjectIdentity | None:
    """Resolve one unambiguous project by stable ID, canonical name, or member name.

    Name lookup uses NFKC, case-folding and collapsed whitespace. When both the
    release and composition projects contain the same alias, L2 prefers the
    release project and L3 prefers the composition project. Ambiguous matches
    across artists fail closed unless ``artist_name`` disambiguates them.
    """

    rows = _project_rows(conn, project_id=project_id)
    if project_id is not None:
        matching = [row for row in rows if int(row["project_id"]) == int(project_id)]
        if not matching:
            return None
        row = matching[0]
        return AlbumProjectIdentity(
            project_id=int(row["project_id"]),
            canonical_name=str(row["canonical_name"]),
            artist_id=int(row["artist_id"]) if row["artist_id"] is not None else None,
            artist_name=str(row["artist_name"]) if row["artist_name"] else None,
            primary_album_id=(
                int(row["primary_album_id"]) if row["primary_album_id"] is not None else None
            ),
            scope=str(row["scope"]),
            matched_by="project_id",
            requested_album_name=album_name,
            requested_project_id=int(project_id),
        )

    if not album_name:
        return None
    normalized_album = normalize_album_project_lookup(album_name)
    normalized_artist = normalize_album_project_lookup(artist_name) if artist_name else None
    matches: dict[int, tuple[sqlite3.Row, AlbumProjectMatch, int | None, str | None]] = {}
    for row in rows:
        if (
            normalized_artist is not None
            and normalize_album_project_lookup(str(row["artist_name"] or "")) != normalized_artist
        ):
            continue
        matched_by: AlbumProjectMatch | None = None
        matched_album_id: int | None = None
        matched_album_name: str | None = None
        if normalize_album_project_lookup(str(row["canonical_name"])) == normalized_album:
            matched_by = "canonical_name"
        elif (
            row["member_album_name"]
            and normalize_album_project_lookup(str(row["member_album_name"])) == normalized_album
        ):
            matched_by = "member_album_name"
            matched_album_id = int(row["member_album_id"])
            matched_album_name = str(row["member_album_name"])
        if matched_by is not None:
            existing = matches.get(int(row["project_id"]))
            if existing is None or (
                existing[1] == "member_album_name" and matched_by == "canonical_name"
            ):
                matches[int(row["project_id"])] = (
                    row,
                    matched_by,
                    matched_album_id,
                    matched_album_name,
                )

    preferred_scope = "composition" if merge_level >= 3 else "release"
    preferred = {
        key: value for key, value in matches.items() if str(value[0]["scope"]) == preferred_scope
    }
    if preferred:
        matches = preferred
    if len(matches) != 1:
        return None
    row, matched_by, matched_album_id, matched_album_name = next(iter(matches.values()))
    return AlbumProjectIdentity(
        project_id=int(row["project_id"]),
        canonical_name=str(row["canonical_name"]),
        artist_id=int(row["artist_id"]) if row["artist_id"] is not None else None,
        artist_name=str(row["artist_name"]) if row["artist_name"] else None,
        primary_album_id=(
            int(row["primary_album_id"]) if row["primary_album_id"] is not None else None
        ),
        scope=str(row["scope"]),
        matched_by=matched_by,
        requested_album_name=album_name,
        requested_project_id=None,
        matched_album_id=matched_album_id,
        matched_album_name=matched_album_name,
    )
